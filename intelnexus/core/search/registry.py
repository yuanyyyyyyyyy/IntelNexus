"""
搜索源注册表
============
统一调度入口。内置源（web/news/darkweb）与用户源（custom_sources）在此注册，
调度层（main.py / search_pipeline.py）只通过 get_sources_by_mode / collect 与注册表交互，
不再硬编码 mode 分支。

collect() 出口统一收口：
  - 跨源去重（按归一化 link）
  - 字段归一化保证（每个源已归一化，此处兜底）
黑名单 / 相关性过滤保留在各源内部（web/news/user 已做，darkweb 走用户源 onion 时也做），
避免在 registry 重复过滤改变结果集语义。
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.search.modes import get_mode_categories
from intelnexus.core.search.source import BaseSearchSource
from intelnexus.core.search.sources.web_source import WebSearchSource
from intelnexus.core.search.sources.news_source import NewsSearchSource
from intelnexus.core.search.sources.darkweb_source import DarkWebSource
from intelnexus.core.search.sources.user_source import UserSource
from intelnexus.core.search.sources.nvd_source import NVDSearchSource
from intelnexus.core.search.sources.cisa_kev_source import CISAKEVSource
from intelnexus.core.search.sources.otx_source import AlienVaultOTXSource
from intelnexus.core.search.sources.hackernews_source import HackerNewsSource
from intelnexus.core.search.sources.exploitdb_source import ExploitDBSource
from intelnexus.core.search.sources.cnvd_source import CNVDSource
from intelnexus.core.search.sources.security_news_source import SecurityNewsSource
from intelnexus.core.search.sources.arxiv_source import ArxivSource
from intelnexus.core.search.sources.tech_community_source import TechCommunitySource
from intelnexus.core.search.sources.huggingface_source import HuggingFaceSource
from intelnexus.core.search.sources.qianxin_source import QianxinSource
from config import (
    ENABLE_OTX, ENABLE_HN, ENABLE_EXPLOITDB, ENABLE_NVD, ENABLE_CISA_KEV,
    ENABLE_CNVD, ENABLE_ARXIV, ENABLE_HUGGINGFACE,
)

logger = get_logger(__name__)

# 模块级注册表实例缓存（按构造参数维度），避免每次 collect 都重建并读盘
_registry_cache: Dict[tuple, "SearchSourceRegistry"] = {}
_registry_cache_lock = None


def get_registry(news_api_key: Optional[str] = None,
                 darkweb_advanced: bool = False, tor_port: int = 9150,
                 ui_sites: Optional[List[Dict]] = None, web_threads: int = 5):
    """
    获取进程内复用的 SearchSourceRegistry 实例（双检锁）。

    注册表构造涉及磁盘读取 sources.json，频繁重建代价高；
    同一组构造参数下复用单例可显著降低 CLI 重复检索开销。
    """
    import threading
    global _registry_cache_lock
    if _registry_cache_lock is None:
        _registry_cache_lock = threading.Lock()
    key = (news_api_key, darkweb_advanced, tor_port,
           tuple(sorted((s.get("name"), s.get("url")) for s in (ui_sites or []))),
           web_threads)
    cached = _registry_cache.get(key)
    if cached is not None:
        return cached
    with _registry_cache_lock:
        cached = _registry_cache.get(key)
        if cached is None:
            cached = SearchSourceRegistry(
                news_api_key=news_api_key, darkweb_advanced=darkweb_advanced,
                tor_port=tor_port, ui_sites=ui_sites, web_threads=web_threads)
            _registry_cache[key] = cached
    return cached


class SearchSourceRegistry:
    def __init__(self, news_api_key: Optional[str] = None,
                 darkweb_advanced: bool = False, tor_port: int = 9150,
                 ui_sites: Optional[List[Dict]] = None, web_threads: int = 5):
        self.news_api_key = news_api_key
        self.darkweb_advanced = darkweb_advanced
        self.tor_port = tor_port
        self.ui_sites = ui_sites or []
        self.web_threads = web_threads

        # 内置源
        self._builtin: List[BaseSearchSource] = [
            WebSearchSource(max_workers=web_threads),
            NewsSearchSource(api_key=news_api_key),
            DarkWebSource(max_workers=web_threads, advanced_mode=darkweb_advanced,
                          tor_port=tor_port, ui_sites=self.ui_sites),
            SecurityNewsSource(),
            TechCommunitySource(),
            QianxinSource(),
        ]
        # 条件启用的源（根据网络环境和可用性）
        if ENABLE_NVD:
            self._builtin.append(NVDSearchSource())
        if ENABLE_CISA_KEV:
            self._builtin.append(CISAKEVSource())
        if ENABLE_CNVD:
            self._builtin.append(CNVDSource())
        if ENABLE_ARXIV:
            self._builtin.append(ArxivSource())
        if ENABLE_HUGGINGFACE:
            self._builtin.append(HuggingFaceSource())
        if ENABLE_OTX:
            self._builtin.append(AlienVaultOTXSource())
        if ENABLE_HN:
            self._builtin.append(HackerNewsSource())
        if ENABLE_EXPLOITDB:
            self._builtin.append(ExploitDBSource())
        # 用户源（运行时从 sources.py 加载）
        self._user_sources: List[UserSource] = []
        self._load_user_sources()

        # 源权重配置（权威源权重更高）
        self._source_weights = {
            # 权威漏洞库
            "NVDSearchSource": 2.0,
            "CISAKEVSource": 2.0,
            "CNVDSource": 2.0,
            # 安全厂商
            "QianxinSource": 1.5,
            # 安全媒体
            "SecurityNewsSource": 1.2,
            "HackerNewsSource": 1.2,
            # 社区/论文
            "ArxivSource": 1.0,
            "TechCommunitySource": 1.0,
            "HuggingFaceSource": 1.0,
            # 其他
            "WebSearchSource": 1.0,
            "NewsSearchSource": 1.0,
            "DarkWebSource": 1.0,
            "AlienVaultOTXSource": 1.0,
            "ExploitDBSource": 1.0,
        }

    # ------------------------------------------------------------------
    # 用户源持久化（延迟导入 intel-briefing 的 sources.py，容错）
    # ------------------------------------------------------------------
    def _load_user_sources(self):
        self._user_sources = []
        try:
            from intelnexus.config.sources import get_all_sources  # intel-briefing 路径
        except ImportError:
            logger.debug("未找到 src.config.sources，跳过用户源加载")
            return
        try:
            data = get_all_sources()
        except Exception as e:
            logger.warning(f"读取用户源失败: {e}")
            return
        for cfg in data.get("custom_sources", []):
            try:
                self._user_sources.append(UserSource(cfg))
            except Exception as e:
                logger.warning(f"构造 UserSource 失败 {cfg.get('name')}: {e}")

    def add_user_source(self, source_type: str, name: str, url: str,
                        category: str, fetch_type: str = "rss",
                        requires_proxy: bool = False, auth=None) -> bool:
        """新增用户源并刷新内存副本。返回是否成功。"""
        try:
            from intelnexus.config.sources import add_source  # noqa: F401  (兼容旧签名)
        except ImportError:
            logger.warning("未找到 src.config.sources.add_source，无法持久化用户源")
            return False
        # 扩展字段：直接写 custom_sources，使用内部持久化函数
        try:
            from intelnexus.config.sources import (get_all_sources, safe_write_json,
                                            _ensure_sources_file, SOURCES_FILE)
        except ImportError:
            logger.warning("未找到 sources.py 持久化工具，无法新增用户源")
            return False
        _ensure_sources_file()
        data = get_all_sources()
        if not data:
            data = {"subscription_sources": [], "custom_sources": []}
        from datetime import datetime
        new_cfg = {
            "id": f"src_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "name": name, "url": url, "type": source_type,
            "category": category, "enabled": True,
            "fetch_type": fetch_type,
            "requires_proxy": requires_proxy,
            "auth": auth,
            "added_at": datetime.now().isoformat(),
        }
        data.setdefault("custom_sources", []).append(new_cfg)
        if safe_write_json(SOURCES_FILE, data):
            self._load_user_sources()
            return True
        return False

    def remove_user_source(self, source_id: str) -> bool:
        """删除用户源并刷新内存副本。"""
        try:
            from intelnexus.config.sources import remove_source
        except ImportError:
            logger.warning("未找到 src.config.sources.remove_source，无法删除用户源")
            return False
        ok = remove_source(source_id)
        if ok:
            self._load_user_sources()
        return ok

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def all_sources(self) -> List[BaseSearchSource]:
        return list(self._builtin) + list(self._user_sources)

    def get_sources_by_mode(self, mode: str) -> List[BaseSearchSource]:
        """返回该模式下、已启用的源列表（按类别过滤，健康降级排序）。"""
        from intelnexus.core.search.health import get_health
        categories = set(get_mode_categories(mode))
        healthy, degraded = [], []
        for src in self.all_sources():
            if not src.enabled:
                continue
            if src.category in categories:
                h = get_health(src.name)
                if h.status == "down":
                    logger.info(f"源 {src.name} 状态为 down，跳过")
                    continue
                elif h.status == "degraded":
                    degraded.append(src)
                else:
                    healthy.append(src)
        return healthy + degraded

    # ------------------------------------------------------------------
    # 执行 + 出口收口
    # ------------------------------------------------------------------
    def collect(self, mode: str, query, max_results: int = 20,
                threads: int = 5, global_timeout: int = 60) -> List[Dict]:
        """
        按 mode 并发检索并做跨源去重，返回归一化结果列表。

        Args:
            mode: 搜索模式
            query: 查询内容
            max_results: 每个源的最大结果数
            threads: 并发线程数
            global_timeout: 全局搜索超时（秒）
        """
        from intelnexus.core.search.health import update_health
        sources = self.get_sources_by_mode(mode)
        raw: List[Dict] = []
        t0 = time.time()

        def _timed_search(src, q, mr):
            # 检查全局超时
            if time.time() - t0 > global_timeout:
                logger.info(f"全局超时，跳过源 {src.name}")
                return []

            # 检查代理要求
            from intelnexus.core.search import get_http_proxies
            if src.requires_proxy and not get_http_proxies():
                logger.info(f"跳过需代理源 {src.name}（未配置代理）")
                return []

            t_start = time.time()
            try:
                # 单源超时 = 全局剩余时间的一半
                remaining = max(5, int((global_timeout - (time.time() - t0)) / 2))
                results = src.search(q, min(mr, 30))  # 限制单源结果数
                elapsed = (time.time() - t_start) * 1000
                update_health(src.name, len(results or []), elapsed)
                # 为每个结果添加源名称和权重
                source_weight = self._source_weights.get(src.name, 1.0)
                for r in (results or []):
                    if isinstance(r, dict):
                        r["_source_name"] = src.name
                        r["_source_weight"] = source_weight
                return results or []
            except Exception as e:
                update_health(src.name, 0, 0, error=str(e))
                logger.warning(f"源 {src.name} 检索异常: {e}")
                return []

        executor = ThreadPoolExecutor(max_workers=max(1, min(threads, len(sources) or 1)))
        future_map = {
            executor.submit(_timed_search, src, query, max_results): src
            for src in sources
        }
        try:
            for f in as_completed(future_map, timeout=global_timeout):
                try:
                    raw.extend(f.result() or [])
                except Exception as e:
                    logger.warning(f"源检索异常: {e}")

                # 检查全局超时
                if time.time() - t0 > global_timeout:
                    logger.info(f"全局超时，停止收集剩余结果")
                    break
        except FuturesTimeoutError:
            logger.info(f"全局超时 ({global_timeout}s)，收集已完成的结果")
            # 收集已完成的 futures
            for f in future_map:
                if f.done():
                    try:
                        raw.extend(f.result() or [])
                    except Exception:
                        pass
        finally:
            # 不等待仍在跑的慢线程：with-block 的隐式 shutdown(wait=True) 会把
            # 全局超时形同虚设（调用方墙钟时间被最慢单源拖满）。
            # cancel_futures 撤销尚未启动的任务；运行中的任务由各自请求超时兜底。
            executor.shutdown(wait=False, cancel_futures=True)

        # 出口统一收口：跨源去重（URL 精确去重 + 归一化标题键 + 受控模糊比对）
        seen_urls = set()
        seen_title_keys = set()
        seen_titles: List[str] = []
        unique: List[Dict] = []

        def _title_key(t: str) -> str:
            """标题归一化键：小写、去空白与常见标点，供精确重复判定。"""
            return re.sub(r"[\s\W_]+", "", t.lower())

        for r in raw:
            url = (r.get("url") or r.get("link") or "").rstrip("/")
            title = (r.get("title") or "").strip()

            # URL去重
            if not url or url in seen_urls:
                continue

            tkey = _title_key(title)
            # 1) 归一化标题精确重复（O(1)）
            if title and len(tkey) >= 8 and tkey in seen_title_keys:
                continue
            # 2) 长度相近的标题才做字符集相似度比对（控制 O(n²) 规模；
            #    阈值 0.92 收紧——旧值 0.8 对中文短标题误杀率过高）
            is_duplicate = False
            if title and len(tkey) >= 8:
                for seen_title in seen_titles:
                    if abs(len(seen_title) - len(title)) <= max(6, len(title) // 5) \
                            and _title_similarity(_title_key(seen_title), tkey) > 0.92:
                        is_duplicate = True
                        break
                if is_duplicate:
                    continue

            seen_urls.add(url)
            if title and len(tkey) >= 8:
                seen_title_keys.add(tkey)
                seen_titles.append(title)

            # 兜底归一化
            norm = r if isinstance(r, dict) else {}
            norm.setdefault("title", "")
            norm.setdefault("url", "")
            norm.setdefault("description", "")
            norm.setdefault("source", "Unknown")
            norm.setdefault("category", sources[0].category if sources else "")
            norm.setdefault("published_at", "")
            norm.setdefault("metadata", {})
            norm.setdefault("_source_name", "")
            norm.setdefault("_source_weight", 1.0)
            unique.append(norm)

        # 按 权重 × 时效性 排序（兑现注释承诺）：主键源权重降序，次键发布时间新者在前。
        # 次键专用映射（区别于相关性过滤用的 get_freshness_score）：
        # 无日期/解析失败给中间值 0.5——多数网页结果不带日期，不应被压到已知旧文之下。
        def _recency_rank(item: Dict) -> float:
            pub = str(item.get("published_at") or "").strip()
            if not pub or pub.lower().startswith("unknown"):
                return 0.5
            try:
                from datetime import datetime, timedelta
                if "T" in pub:
                    dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(pub[:10], "%Y-%m-%d")
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                delta = datetime.now() - dt
                if delta <= timedelta(days=1):
                    return 1.0
                if delta <= timedelta(days=7):
                    return 0.8
                if delta <= timedelta(days=30):
                    return 0.6
                return 0.0
            except Exception:
                return 0.5

        unique.sort(
            key=lambda x: (x.get("_source_weight", 1.0), _recency_rank(x)),
            reverse=True,
        )

        return unique


def _title_similarity(title1: str, title2: str) -> float:
    """
    计算两个标题的相似度（字符集合重叠率，Jaccard 系数）。

    Args:
        title1: 标题1
        title2: 标题2

    Returns:
        相似度（0.0 ~ 1.0）
    """
    if not title1 or not title2:
        return 0.0

    # 简化版：基于字符重叠率
    set1 = set(title1)
    set2 = set(title2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union if union > 0 else 0.0

