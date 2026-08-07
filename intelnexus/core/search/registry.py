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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.search.modes import get_mode_categories
from intelnexus.core.search.source import BaseSearchSource
from intelnexus.core.search.sources.web_source import WebSearchSource
from intelnexus.core.search.sources.news_source import NewsSearchSource
from intelnexus.core.search.sources.darkweb_source import DarkWebSource
from intelnexus.core.search.sources.user_source import UserSource

logger = get_logger(__name__)


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
        ]
        # 用户源（运行时从 sources.py 加载）
        self._user_sources: List[UserSource] = []
        self._load_user_sources()

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
        """返回该模式下、已启用的源列表（按类别过滤）。"""
        categories = set(get_mode_categories(mode))
        out = []
        for src in self.all_sources():
            if not src.enabled:
                continue
            if src.category in categories:
                out.append(src)
        return out

    # ------------------------------------------------------------------
    # 执行 + 出口收口
    # ------------------------------------------------------------------
    def collect(self, mode: str, query, max_results: int = 20,
                threads: int = 5) -> List[Dict]:
        """按 mode 并发检索并做跨源去重，返回归一化结果列表。"""
        sources = self.get_sources_by_mode(mode)
        raw: List[Dict] = []
        with ThreadPoolExecutor(max_workers=max(1, min(threads, len(sources) or 1))) as executor:
            futures = [executor.submit(src.search, query, max_results) for src in sources]
            for f in as_completed(futures):
                try:
                    raw.extend(f.result() or [])
                except Exception as e:
                    logger.warning(f"源检索异常: {e}")

        # 出口统一收口：跨源去重（按 link 归一化）
        seen = set()
        unique: List[Dict] = []
        for r in raw:
            link = (r.get("link") or "").rstrip("/")
            if not link or link in seen:
                continue
            seen.add(link)
            # 兜底归一化
            norm = r if isinstance(r, dict) else {}
            norm.setdefault("title", "")
            norm.setdefault("description", "")
            norm.setdefault("source", "Unknown")
            norm.setdefault("category", sources[0].category if sources else "")
            unique.append(norm)
        return unique

