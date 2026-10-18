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
from intelnexus.core.search.sources.xiaohongshu_source import XiaohongshuSource
from config import (
    ENABLE_OTX, ENABLE_HN, ENABLE_EXPLOITDB, ENABLE_NVD, ENABLE_CISA_KEV,
    ENABLE_CNVD, ENABLE_ARXIV, ENABLE_HUGGINGFACE, ENABLE_XIAOHONGSHU,
)

logger = get_logger(__name__)

# 全局超时后的宽限期（秒）：给已在跑的慢源最后机会收割晚到的成功结果，
# 避免 shutdown(cancel_futures=True) 直接丢弃即将完成的检索。
_GRACE_PERIOD = 8

# stale（待复核）源的试探预算（秒）。
#
# stale 源只是「旧结论可能已过期，再试一次」——它的结果是**加分项**，不是
# 本次检索的必要组成。若与正常源同池无限等待，一个挂死 15s 的死源就会把整次
# 检索从 5s 拖到 20s（15 个源 / threads=5 时实测如此）。
#
# 因此：当未完成的 future **只剩** stale 源时，最多再等这么久就收工。
# 放弃的源线程仍在后台跑完并照常写健康表（成功即自愈，失败即重新冷却），
# 只是不再拖住本次返回。取 3s：足够覆盖「刚恢复的源首个请求」的常见耗时，
# 又不会让用户明显感到卡顿。
_STALE_PROBE_BUDGET = 3

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


def reset_registry_cache() -> None:
    """清空注册表单例缓存（源开关变更后调用，使下次 get_registry 重建）。"""
    import threading
    global _registry_cache_lock
    if _registry_cache_lock is None:
        _registry_cache_lock = threading.Lock()
    with _registry_cache_lock:
        _registry_cache.clear()


class SearchSourceRegistry:
    def __init__(self, news_api_key: Optional[str] = None,
                 darkweb_advanced: bool = False, tor_port: int = 9150,
                 ui_sites: Optional[List[Dict]] = None, web_threads: int = 5):
        self.news_api_key = news_api_key
        self.darkweb_advanced = darkweb_advanced
        self.tor_port = tor_port
        self.ui_sites = ui_sites or []
        self.web_threads = web_threads
        #: 上一次 get_sources_by_mode 因健康状态 down 被剔除的源名，
        #: 供 collect() 写入 source_stats，让结果页能解释「这个源为什么没结果」
        self.last_skipped_down: List[str] = []
        #: 上一次 get_sources_by_mode 判定为 stale（待复核）的源名。
        #: 它们只是试探，collect() 据此限制等待时长，不让慢的试探源拖住正常结果。
        self.last_stale_sources: List[str] = []

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
        if ENABLE_XIAOHONGSHU:
            self._builtin.append(XiaohongshuSource())
        # 用户源（运行时从 sources.py 加载）
        self._user_sources: List[UserSource] = []
        self._load_user_sources()

        # 源权重配置（权威源权重更高）。
        # 键必须与各源实例的 src.name（短名）一致——collect 内以
        # self._source_weights.get(src.name, 1.0) 取值，用类名作键会恒取默认 1.0。
        self._source_weights = {
            # 权威漏洞库
            "NVD": 2.0,
            "CISA_KEV": 2.0,
            "CNVD": 2.0,
            # 安全厂商
            "Qianxin": 1.5,
            # 安全媒体
            "SecRSS": 1.2,
            "HackerNews": 1.2,
            # 社区/论文
            "arXiv": 1.0,
            "TechCommunity": 1.0,
            "HuggingFace": 1.0,
            # UGC 社区（略低于一手情报源，避免刷屏）
            "Xiaohongshu": 0.9,
            # 其他
            "Web": 1.0,
            "News": 1.0,
            "DarkWeb": 1.0,
            "AlienVault_OTX": 1.0,
            "ExploitDB": 1.0,
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

    def site_scoped_source_names(self) -> List[str]:
        """返回依赖「站内检索后端」的源名（当前为小红书，未来可含微博/知乎等）。

        用 ``isinstance`` 判定而非按 category：``custom`` 类别也会被用户源占用，
        只有 ``SiteScopedSource`` 子类才真正依赖该后端。供「保存凭证后重置健康」
        与「自检结果写入健康表」使用。
        """
        from intelnexus.core.search.sources.site_scoped_source import SiteScopedSource
        return [s.name for s in self.all_sources()
                if isinstance(s, SiteScopedSource)]

    def get_sources_by_mode(self, mode: str) -> List[BaseSearchSource]:
        """返回该模式下、已启用的源列表（按类别过滤，健康状态排序）。

        排序：``healthy → degraded → stale``，被剔除的 ``down`` 不入列表。

        时间维度（见 ``health.view_status``）：
        - ``down`` 只在其冷却期（``DOWN_COOLDOWN_MINUTES``）内被剔除。冷却到期后
          该源转为 ``stale`` 并被放行——否则 down 就是**终态**：被剔除 → 永不执行
          → 永不成功 → 永远 down，唯一的出口是用户手动点「清除标记」。
        - ``stale`` 排在最后：旧判定已过期，值得再试一次，但不该抢占正常源的位置。

        健康状态为 ``down`` 的源名记录在 ``self.last_skipped_down``：``collect()``
        据此把它们写进 ``source_stats``（status="down"），否则结果页的「源完整性」
        会漏报，出现「健康面板说 4 个源不可用、结果页却说全部源正常」的自相矛盾。

        ``stale`` 源名另记在 ``self.last_stale_sources``：它们只是**试探**，
        ``collect()`` 据此给它们单独的等待预算，不让慢的试探源拖住正常结果
        （见 ``_STALE_PROBE_BUDGET``）。

        性能：整表**一次**读取（``get_health_map``），不再对每个源各调一次
        ``get_health``（22 个源时 33.5ms → 1.5ms）。
        """
        from intelnexus.core.search.health import get_health_map, view_status

        categories = set(get_mode_categories(mode))
        candidates = [
            src for src in self.all_sources()
            if src.enabled and src.category in categories
        ]
        health_map = get_health_map(src.name for src in candidates)

        healthy: List[BaseSearchSource] = []
        degraded: List[BaseSearchSource] = []
        stale: List[BaseSearchSource] = []
        skipped_down: List[str] = []
        for src in candidates:
            state = view_status(health_map[src.name])
            if state == "down":
                logger.info(f"源 {src.name} 状态为 down（冷却期内），跳过")
                skipped_down.append(src.name)
            elif state == "degraded":
                degraded.append(src)
            elif state == "stale":
                logger.info(f"源 {src.name} 健康判定已过期，按低优先级放行重试")
                stale.append(src)
            else:
                healthy.append(src)
        self.last_skipped_down = skipped_down
        self.last_stale_sources = [s.name for s in stale]
        return healthy + degraded + stale

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
        from intelnexus.core.search.health import HealthBatch, update_health

        # F6 源级统计：本次检索各源的成败/跳过情况，供 UI 透明度条展示
        source_stats: Dict[str, Dict] = {}

        def _mark(name, status, count=0):
            source_stats[name] = {"status": status, "count": count}

        sources = self.get_sources_by_mode(mode)
        # 因健康状态 down 被剔除的源不会进入 sources，但必须出现在本次统计里：
        # 结果页「源完整性」与报告 4.1 段据此解释「为什么这个源一条都没返回」。
        # 紧接调用后立刻取用，缩短与并发检索共享该属性的窗口。
        for _down_name in self.last_skipped_down:
            _mark(_down_name, "down")

        #: 本次检索的 stale 源名（试探源）：等待预算与正常源不同
        probation = set(self.last_stale_sources)
        #: 健康观测缓冲：15 个源各写一次 ≈ 150ms 串行 IO，合并成一次写盘
        health_batch = HealthBatch()

        def _record_health(name, result_count, latency_ms,
                           error=None, empty_is_healthy=False):
            """记录一条观测：优先并入批量写；缓冲已关闭则退回单条写（不丢信号）。"""
            if not health_batch.record(name, result_count, latency_ms,
                                       error=error, empty_is_healthy=empty_is_healthy):
                update_health(name, result_count, latency_ms,
                              error=error, empty_is_healthy=empty_is_healthy)

        raw: List[Dict] = []
        t0 = time.time()

        def _timed_search(src, q, mr):
            # 检查全局超时
            if time.time() - t0 > global_timeout:
                logger.info(f"全局超时，跳过源 {src.name}")
                _mark(src.name, "timeout")
                return []

            # 检查代理要求
            from intelnexus.core.search import get_http_proxies
            if src.requires_proxy and not get_http_proxies():
                logger.info(f"跳过需代理源 {src.name}（未配置代理）")
                _mark(src.name, "no_proxy")
                return []

            t_start = time.time()
            try:
                # 注意：此处**没有**单源超时——Python 无法中断正在跑的线程，
                # 真正的时限由各源自己的 requests timeout 决定（10～30s），
                # 全局兜底是 global_timeout + _GRACE_PERIOD。
                # 旧代码在这里算了 remaining 却从未使用，注释与行为不符，已删。
                # 先清残留失败信号：保证随后读到的 last_error 只属于本次调用，
                # 防上一轮超时后台线程晚归写入的信号被本轮误消费（桩可能无此属性）。
                setattr(src, "last_error", None)
                results = src.search(q, min(mr, 30))  # 限制单源结果数
                elapsed = (time.time() - t_start) * 1000
                if results:
                    # 非空结果路径：成功，同时清掉残留的失败信号（桩可能无此属性，setattr 防御）
                    setattr(src, "last_error", None)
                    _record_health(src.name, len(results), elapsed)
                    _mark(src.name, "ok", len(results))
                else:
                    # 空结果 + last_error 非空 → 判定为失败：适配器吞异常返回 []
                    # 时既有错误边界永不触发，靠失败信号通道补记健康统计。
                    err = getattr(src, "last_error", None)
                    if err:
                        _record_health(src.name, 0, elapsed, error=err)
                        _mark(src.name, "error")
                        setattr(src, "last_error", None)
                        logger.warning(f"源 {src.name} 检索失败: {err}")
                        return []
                    # 透传源自述标志：确知「空结果＝未命中」的源（站内检索源）
                    # 零结果按成功计，避免被永久钉在 degraded/down 且无法自愈
                    _record_health(src.name, 0, elapsed,
                                   empty_is_healthy=getattr(
                                       src, "empty_is_healthy", False))
                    # 观测：正式检索路径上也要能区分「后端没返回」与「被过滤干净」，
                    # 否则源长期返回 0 条时无法判断是源故障还是过滤太狠（试搜面板
                    # 已区分，这里补日志留痕）
                    _stats = getattr(src, "last_filter_stats", None) or {}
                    if int(_stats.get("raw") or 0) > 0:
                        logger.info(f"源 {src.name} 后端返回 "
                                    f"{_stats.get('raw')} 条，过滤后 0 条"
                                    f"（过滤生效，非源故障）")
                    _mark(src.name, "ok", 0)
                # 为每个结果添加源名称和权重
                source_weight = self._source_weights.get(src.name, 1.0)
                for r in (results or []):
                    if isinstance(r, dict):
                        r["_source_name"] = src.name
                        r["_source_weight"] = source_weight
                return results or []
            except Exception as e:
                _record_health(src.name, 0, 0, error=str(e))
                logger.warning(f"源 {src.name} 检索异常: {e}")
                _mark(src.name, "error")
                # 异常边界同样清残留信号，保持失败信号通道的单轮生命周期语义
                setattr(src, "last_error", None)
                return []

        executor = ThreadPoolExecutor(max_workers=max(1, min(threads, len(sources) or 1)))
        future_map = {
            executor.submit(_timed_search, src, query, max_results): src
            for src in sources
        }
        # 主循环已收割的 future 集合：超时统一收割时据此去重，避免重复条目。
        collected = set()

        def _harvest():
            """统一收割：先收已完成 future，再给未完成 future 宽限期。

            覆盖两条超时退出路径：as_completed 抛 FuturesTimeoutError（路径 A）
            与循环体内超时检查 break（路径 B）；collected 集合排除主循环已收割的。
            """
            for f in future_map:
                if f in collected:
                    continue
                if f.done():
                    collected.add(f)
                    try:
                        raw.extend(f.result() or [])
                    except Exception:
                        pass
            # 宽限期收割：给仍在跑的源最后 _GRACE_PERIOD 秒，避免
            # shutdown(cancel_futures=True) 丢弃晚到的成功结果；宽限期超时则放弃。
            pending = [f for f in future_map if f not in collected and not f.done()]
            if pending:
                try:
                    for f in as_completed(pending, timeout=_GRACE_PERIOD):
                        collected.add(f)
                        try:
                            raw.extend(f.result() or [])
                        except Exception as e:
                            logger.warning(f"宽限期收割源异常: {e}")
                except FuturesTimeoutError:
                    logger.info(f"宽限期 ({_GRACE_PERIOD}s) 超时，放弃收割未完成的源")

        def _only_probation_pending() -> bool:
            """未完成的 future 是否**只剩** stale 试探源。"""
            for f in future_map:
                if f in collected or f.done():
                    continue
                if future_map[f].name not in probation:
                    return False
            return True

        try:
            for f in as_completed(future_map, timeout=global_timeout):
                collected.add(f)
                try:
                    raw.extend(f.result() or [])
                except Exception as e:
                    logger.warning(f"源检索异常: {e}")

                # 检查全局超时（路径 B）：同样走统一宽限收割，避免晚到成功结果被丢弃
                if time.time() - t0 > global_timeout:
                    logger.info(f"全局超时，停止收集剩余结果")
                    _harvest()
                    break

                # 试探预算：正常源都已完成、只剩 stale 源时，改为**有界等待**后收工。
                # 不能只在循环体里记 deadline——as_completed 只在 future 完成时才
                # yield，若剩下的唯一 future 就是那个挂死的试探源，循环体根本不会
                # 再被执行，deadline 永远不会被检查。必须换成带 timeout 的 as_completed。
                if probation and _only_probation_pending():
                    pending = [pf for pf in future_map if pf not in collected]
                    if pending:
                        logger.info(f"正常源已全部返回，{len(probation)} 个试探源"
                                    f"最多再等 {_STALE_PROBE_BUDGET}s")
                        try:
                            for pf in as_completed(pending,
                                                   timeout=_STALE_PROBE_BUDGET):
                                collected.add(pf)
                                try:
                                    raw.extend(pf.result() or [])
                                except Exception as e:
                                    logger.warning(f"试探源收割异常: {e}")
                        except FuturesTimeoutError:
                            logger.info(f"试探源超出 {_STALE_PROBE_BUDGET}s 预算，"
                                        f"先返回已有结果（其健康观测仍会在后台写入）")
                    break
        except FuturesTimeoutError:
            logger.info(f"全局超时 ({global_timeout}s)，收集已完成的结果")
            # 路径 A：与路径 B 共用同一收割逻辑，口径一致且不重复收集。
            _harvest()
        finally:
            # 不等待仍在跑的慢线程：with-block 的隐式 shutdown(wait=True) 会把
            # 全局超时形同虚设（调用方墙钟时间被最慢单源拖满）。
            # cancel_futures 撤销尚未启动的任务；运行中的任务由各自请求超时兜底。
            executor.shutdown(wait=False, cancel_futures=True)
            # 健康观测合并写盘：15 个源各写一次约 150ms，合并后约 10ms。
            # 必须放在 shutdown 之后：仍在跑的线程若在 flush 后才记录，
            # HealthBatch.record 会返回 False 并退回单条写，信号不丢。
            try:
                health_batch.flush()
            except Exception as e:
                logger.warning(f"健康观测批量写盘失败: {e}")

        # F6：未被收集到的源（撤销/超时未完成）标记 timeout，避免统计缺口；
        # 与 _timed_search 内全局超时跳过分支的语义对齐，供 UI 透明度条展示。
        for src in sources:
            if src.name not in source_stats:
                source_stats[src.name] = {"status": "timeout", "count": 0}
        self.last_search_stats = source_stats

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

        # F9：中文查询时对英文专属源降权（延后位次而非砍源——保留长尾价值，
        # 但不让 HN/arxiv/exploitdb 等结构性噪声顶在中文地缘/民生查询前排）。
        # 判定：查询含 CJK 字符即视为中文语境；语义相关性排序（若可用）会
        # 进一步精排，这里只做廉价的先验调整。
        def _is_cjk_query(q) -> bool:
            return any("\u4e00" <= ch <= "\u9fff" for ch in str(q or ""))

        if _is_cjk_query(query):
            # 键同样须用 src.name 短名（与 _source_weights 对齐），否则降权永不生效
            en_only = {"HackerNews", "arXiv", "ExploitDB",
                       "HuggingFace", "TechCommunity"}
            for item in unique:
                if item.get("_source_name") in en_only:
                    item["_source_weight"] = min(
                        float(item.get("_source_weight", 1.0)), 0.7)

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

