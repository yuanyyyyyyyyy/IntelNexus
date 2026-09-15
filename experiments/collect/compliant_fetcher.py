"""合规抓取器（R1 前置改造的具体实现）。

三条硬性约束，缺一条就不满足论文 3.2 节的采集合规声明：

1. 遵守目标站点 robots.txt（User-agent 精确匹配优先，回退 ``*``）；
2. 请求间隔不低于配置的全局最小间隔（默认 2 秒），并对 429/5xx 做指数退避；
3. 明确 User-Agent 标识，不采集个人信息（本层只取公告正文，不做任何主体画像）。

设计上只用标准库 + requests，不改动 intelnexus 的既有采集器。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from experiments.logging_utils import get_logger

logger = get_logger("exp.fetcher")

DEFAULT_UA = "IntelNexusResearchBot/1.0 (academic; +https://github.com/zero-one-his2607/IntelNexus)"


@dataclass
class FetchResult:
    ok: bool
    url: str
    status: Optional[int] = None
    text: str = ""
    elapsed_ms: Optional[int] = None
    error: Optional[str] = None
    robots_allowed: Optional[bool] = None
    robots_source: Optional[str] = None
    retries: int = 0


@dataclass
class CompliantFetcher:
    """带 robots 解析与全局限速的抓取器。

    Attributes:
        min_interval_s: 全局最小请求间隔（秒）。所有请求串行发出，
            因此全局间隔与单主机间隔天然一致；单主机可用
            ``per_host_interval`` 覆盖为更大值（如 NVD 的 6 秒）。
    """

    user_agent: str = DEFAULT_UA
    min_interval_s: float = 2.0
    timeout_s: float = 20.0
    max_retries: int = 2
    per_host_interval: Dict[str, float] = field(default_factory=dict)
    _last_request_ts: float = field(default=0.0, repr=False)
    _robots: Dict[str, Optional[RobotFileParser]] = field(default_factory=dict, repr=False)
    _session: Optional[requests.Session] = field(default=None, repr=False)

    # ---------------------------------------------------------------- 会话
    def session(self) -> requests.Session:
        if self._session is None:
            s = requests.Session()
            s.headers.update({"User-Agent": self.user_agent, "Accept": "*/*"})
            self._session = s
        return self._session

    # ---------------------------------------------------------------- robots
    def _robots_for(self, url: str) -> tuple[Optional[RobotFileParser], str]:
        """返回 (parser, source)；解析失败时返回 (None, 原因)。"""
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin], "cached"
        parser: Optional[RobotFileParser] = None
        source = "fetch-failed"
        try:
            r = self.session().get(
                f"{origin}/robots.txt", timeout=self.timeout_s, allow_redirects=True
            )
            if r.status_code == 200 and r.text:
                parser = RobotFileParser()
                parser.parse(r.text.splitlines())
                source = "robots.txt"
            elif r.status_code == 404:
                source = "no-robots(404)"
            else:
                source = f"http-{r.status_code}"
        except Exception as e:  # noqa: BLE001
            source = f"error:{type(e).__name__}"
            logger.debug("robots.txt 获取失败 %s: %s", origin, e)
        self._robots[origin] = parser
        return parser, source

    def robots_allows(self, url: str) -> tuple[bool, str]:
        """robots.txt 不可得时按 RFC 9309 视为允许，但记录来源以便审计。"""
        parser, source = self._robots_for(url)
        if parser is None:
            return True, source
        try:
            return bool(parser.can_fetch(self.user_agent, url)), source
        except Exception as e:  # noqa: BLE001
            logger.warning("robots 解析异常 %s: %s", url, e)
            return True, f"parse-error:{type(e).__name__}"

    # ---------------------------------------------------------------- 限速
    def _throttle(self, host: str) -> None:
        interval = max(self.min_interval_s, float(self.per_host_interval.get(host, 0.0)))
        wait = interval - (time.perf_counter() - self._last_request_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.perf_counter()

    # ---------------------------------------------------------------- 抓取
    def get(self, url: str, params: Optional[Dict[str, object]] = None) -> FetchResult:
        host = urlparse(url).netloc
        allowed, robots_source = self.robots_allows(url)
        if not allowed:
            logger.warning("robots.txt 禁止抓取: %s", url)
            return FetchResult(ok=False, url=url, error="robots-disallow",
                               robots_allowed=False, robots_source=robots_source)

        retries = 0
        last_status: Optional[int] = None
        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            try:
                r = self.session().get(url, params=params, timeout=self.timeout_s, allow_redirects=True)
                last_status = r.status_code
                if r.status_code == 200:
                    return FetchResult(
                        ok=True, url=r.url, status=200, text=r.text,
                        elapsed_ms=int(r.elapsed.total_seconds() * 1000),
                        robots_allowed=True, robots_source=robots_source, retries=retries,
                    )
                if r.status_code in (429, 500, 502, 503, 504):
                    last_error = f"http-{r.status_code}"
                    retries = attempt + 1
                    backoff = self.min_interval_s * (2 ** attempt)
                    logger.warning("HTTP %s，退避 %.1fs 后重试: %s", r.status_code, backoff, url)
                    time.sleep(backoff)
                    continue
                return FetchResult(ok=False, url=url, status=r.status_code,
                                   error=f"http-{r.status_code}", robots_allowed=True,
                                   robots_source=robots_source, retries=retries)
            except Exception as e:  # noqa: BLE001
                last_error = f"{type(e).__name__}: {str(e)[:120]}"
                retries = attempt + 1
                time.sleep(self.min_interval_s * (2 ** attempt))
        return FetchResult(ok=False, url=url, status=last_status, error=last_error or "unknown",
                           robots_allowed=True, robots_source=robots_source, retries=retries)


def build_fetcher(sources_cfg: Dict[str, object]) -> CompliantFetcher:
    """从 sources.yaml 的 global 段构造抓取器。"""
    g = (sources_cfg or {}).get("global", {}) or {}
    per_host: Dict[str, float] = {}
    for s in ((sources_cfg or {}).get("sources", []) or []):
        try:
            host = urlparse(str(s.get("url", ""))).netloc
        except Exception:  # noqa: BLE001
            continue
        if host and s.get("min_interval_s"):
            per_host[host] = max(per_host.get(host, 0.0), float(s["min_interval_s"]))
    return CompliantFetcher(
        user_agent=str(g.get("user_agent") or DEFAULT_UA),
        min_interval_s=float(g.get("min_interval_s", 2.0)),
        timeout_s=float(g.get("timeout_s", 20.0)),
        max_retries=int(g.get("max_retries", 2)),
        per_host_interval=per_host,
    )
