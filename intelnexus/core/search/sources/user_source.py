"""
用户自定义搜索源
================
由 data/sources.json（custom_sources 段，由 intel-briefing/src/config/sources.py 管理）
驱动的统一搜索源。支持三种抓取方式：
  - rss        : RSS/Atom feed（支持 {query} 模板）
  - web_engine : 通用网页搜索 URL 模板（含 {query}）
  - onion      : .onion 站点搜索（走 Tor 代理，支持 basic/cookie 认证）

设计：UserSource 不负责持久化读写，registry 从 sources.py 读配置后构造实例，
便于测试与解耦。代理收口沿用 get_http_proxies_for(requires_proxy)。
"""
import base64
import random
import re
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from intelnexus.core.logger import get_logger
from intelnexus.core.search import USER_AGENTS, get_http_proxies_for, get_tor_proxy_port, \
    is_blocked_domain, relevance_passes
from intelnexus.core.search.source import BaseSearchSource, CATEGORY_CUSTOM

logger = get_logger(__name__)

RSS_TIMEOUT = 10


class UserSource(BaseSearchSource):
    """用户自定义源：从 sources.json 的 custom_sources 条目构造。"""

    def __init__(self, config: Dict, enabled: bool = True):
        """
        Args:
            config: sources.json 中 custom_sources 的一条，字段：
                id, name, url, type(rss/web), category, enabled,
                fetch_type(rss/web_engine/onion), requires_proxy, auth
            enabled: 默认取 config.enabled，可被 registry 覆盖。
        """
        fetch_type = config.get("fetch_type", "rss")
        category = config.get("category", CATEGORY_CUSTOM)
        # 类别映射：用户源可归属于 web/news/darkweb/custom
        if category not in ("web", "news", "darkweb", "custom"):
            category = CATEGORY_CUSTOM
        requires_proxy = bool(config.get("requires_proxy", fetch_type == "onion"))
        super().__init__(name=config.get("name", "UserSource"),
                         category=category,
                         enabled=config.get("enabled", enabled),
                         requires_proxy=requires_proxy)
        self.config = config
        self.source_id = config.get("id", "")
        self.url = config.get("url", "")
        self.fetch_type = fetch_type
        self.auth = config.get("auth")

    # ------------------------------------------------------------------
    def search(self, query, max_results: int = 20) -> List[Dict]:
        if not self.url:
            return []
        try:
            if self.fetch_type == "rss":
                raw = self._fetch_rss(query, max_results)
            elif self.fetch_type == "web_engine":
                raw = self._fetch_web_engine(query, max_results)
            elif self.fetch_type == "onion":
                raw = self._fetch_onion(query, max_results)
            else:
                logger.warning(f"UserSource 未知 fetch_type={self.fetch_type}")
                return []
        except Exception as e:
            logger.warning(f"UserSource[{self.name}] 检索失败: {e}")
            return []

        results = []
        for item in raw:
            item.setdefault("source", self.name)
            # 用户源统一做黑名单 + 相关性收口（与源内行为一致）
            link = item.get("link") or item.get("url", "")
            if is_blocked_domain(link):
                continue
            if not relevance_passes(item, query):
                continue
            norm = self.normalize_result(item)
            if norm.get("link"):
                results.append(norm)
        return results[:max_results]

    # ------------------------------------------------------------------
    # RSS 抓取（复用 news.py 解析思路）
    # ------------------------------------------------------------------
    def _fetch_rss(self, query, max_results: int) -> List[Dict]:
        url = self.url
        if "{query}" in url:
            url = url.format(query=quote(query))
        proxies = self.get_proxies()
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=RSS_TIMEOUT, proxies=proxies)
        if resp.status_code != 200:
            return []
        try:
            soup = BeautifulSoup(resp.content, "xml")
        except Exception:
            soup = BeautifulSoup(resp.content, "html.parser")

        items = soup.find_all("item")[:max_results] or \
            soup.find_all("entry")[:max_results]

        results = []
        for it in items:
            title = it.find("title")
            link = it.find("link")
            desc = it.find("description") or it.find("summary") or it.find("content")
            link_text = ""
            if link:
                link_text = link.get_text(strip=True) if hasattr(link, "get_text") \
                    else str(link)
            if not (title and link_text):
                continue
            title_text = title.get_text(strip=True) if hasattr(title, "get_text") \
                else str(title)
            results.append({
                "title": title_text,
                "link": link_text,
                "description": desc.get_text(strip=True)[:300] if desc and hasattr(desc, "get_text") else "",
            })
        return results

    # ------------------------------------------------------------------
    # 通用网页引擎（用户提供的搜索 URL 模板）
    # ------------------------------------------------------------------
    def _fetch_web_engine(self, query, max_results: int) -> List[Dict]:
        url = self.url
        if "{query}" not in url:
            return []
        url = url.format(query=quote(query))
        proxies = self.get_proxies()
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=12, proxies=proxies)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.find_all("a", href=True):
            href = str(a.get("href", ""))
            title = a.get_text(strip=True)
            if href.startswith("http") and len(title) > 2:
                results.append({"title": title[:150], "link": href})
            if len(results) >= max_results:
                break
        return results

    # ------------------------------------------------------------------
    # .onion 站点（走 Tor 代理 + 可选 basic/cookie 认证）
    # ------------------------------------------------------------------
    def _fetch_onion(self, query, max_results: int) -> List[Dict]:
        base_url = self.url
        if not base_url:
            return []

        auth = self.auth
        if auth and isinstance(auth.get("password"), str):
            try:
                auth = dict(auth)
                auth["password"] = base64.b64decode(
                    auth["password"].encode("utf-8")).decode("utf-8")
            except Exception:
                pass

        session = requests.Session()
        session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
        # 代理收口：优先用统一 get_proxies()（沿用 get_http_proxies_for），
        # 未配置全局代理时回退到本地 Tor SOCKS5（onion 必须走 Tor）。
        proxy = self.get_proxies()
        if not proxy:
            port = get_tor_proxy_port()
            proxy = {
                "http": f"socks5h://127.0.0.1:{port}",
                "https": f"socks5h://127.0.0.1:{port}",
            }
        session.proxies = proxy
        if auth:
            if auth.get("type") == "basic":
                session.auth = (auth.get("username"), auth.get("password"))
            elif auth.get("type") == "cookie":
                for k, v in auth.get("cookies", {}).items():
                    session.cookies.set(k, v)

        search_url = f"{base_url}?search={quote(query)}"
        try:
            resp = session.get(search_url, timeout=30)
        except Exception as e:
            logger.warning(f"UserSource onion 访问失败: {e}")
            return []

        results = []
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = str(a.get("href", ""))
                title = a.get_text(strip=True)
                if href and len(title) > 2:
                    if ".onion" in href.lower() or \
                            base_url.split("//")[1].split(".")[0] in href:
                        full = href if href.startswith("http") else f"{base_url}{href}"
                        results.append({"title": title[:100], "link": full})
                if len(results) >= max_results:
                    break
        return results
