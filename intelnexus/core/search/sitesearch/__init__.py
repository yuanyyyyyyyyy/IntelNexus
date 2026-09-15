"""
站内定向检索后端
================
按 ``search_settings`` 的配置解析出可用的 Provider（博查 / Brave / Google CSE），
并以模块级缓存复用实例；凭证变更后由 ``reset_site_search_backend()`` 失效。

Provider 选择：
- ``site_search_provider`` 为 ``auto``（默认）时，按 ``PROVIDER_PRIORITY``
  择第一个「已配置」的 Provider；
- 显式指定某 Provider 但该 Provider 凭证不全时，视为不可用（不静默回退到另一家，
  避免用户以为在用 A 实际在用 B）；
- 传入**未知**的 Provider 串（如拼写错误）时记 warning 并按 ``auto`` 处理，
  避免静默行为，也避免一个拼写错误让功能整体不可用。

**扩展点**：新增 Provider 只需实现 ``SiteSearchBackend`` 并登记到
``_BUILDERS``，核心系统与 ``SiteScopedSource`` 均无需改动 —— 用户自备的
采集实现（包括需登录态的实现）可借此挂载。
"""
import threading
import time
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.search.sitesearch.base import (
    SiteSearchBackend, SiteSearchError, redact_secrets,
)
from intelnexus.core.search.sitesearch.bocha import BochaBackend
from intelnexus.core.search.sitesearch.brave import BraveBackend
from intelnexus.core.search.sitesearch.google_cse import GoogleCSEBackend

logger = get_logger(__name__)

__all__ = [
    "SiteSearchBackend", "SiteSearchError",
    "BochaBackend", "GoogleCSEBackend", "BraveBackend",
    "PROVIDER_PRIORITY", "resolve_provider", "available_providers",
    "get_site_search_backend", "reset_site_search_backend", "probe_site_search",
]

#: auto 模式下的选择优先级。
#: 博查优先（国内直连免代理，当前推荐路径）；Google CSE 排末位——其官方文档
#: 已声明「不再向新客户开放」（存量客户须在 2027-01-01 前迁移），仅保留给已有 Key。
PROVIDER_PRIORITY = ("bocha", "brave", "google_cse")

#: Provider 名 → 构造函数（外部扩展点：登记新实现即可）
_BUILDERS = {
    "bocha": lambda cfg: BochaBackend(api_key=cfg.get("bocha_api_key", "")),
    "brave": lambda cfg: BraveBackend(api_key=cfg.get("brave_api_key", "")),
    "google_cse": lambda cfg: GoogleCSEBackend(
        api_key=cfg.get("google_cse_api_key", ""),
        cse_id=cfg.get("google_cse_id", "")),
}

_backend_cache: Optional[SiteSearchBackend] = None
_backend_cache_key = None
_backend_cache_lock = threading.Lock()


def _load_config() -> Dict:
    """读取站内检索配置；模块不可用时记 warning 并返回空配置（不抛出）。"""
    try:
        from intelnexus.config.search_settings import get_site_search_config
        return get_site_search_config() or {}
    except Exception as e:
        logger.warning(f"站内检索配置读取失败，按未配置处理: {e}")
        return {}


def _build(provider: str, cfg: Dict) -> SiteSearchBackend:
    return _BUILDERS[provider](cfg)


def resolve_provider(cfg: Optional[Dict] = None) -> str:
    """返回当前应使用的 Provider 名；无可用时返回空串。"""
    cfg = _load_config() if cfg is None else cfg
    wanted = str(cfg.get("site_search_provider", "auto") or "auto").strip().lower()
    if wanted not in _BUILDERS and wanted != "auto":
        logger.warning(f"未知的站内检索 Provider {wanted!r}，按 auto 处理")
        wanted = "auto"
    candidates = [wanted] if wanted in _BUILDERS else list(PROVIDER_PRIORITY)
    for name in candidates:
        if _build(name, cfg).is_configured():
            return name
    return ""


def available_providers(cfg: Optional[Dict] = None) -> List[str]:
    """返回已配置（凭证齐备）的 Provider 名列表。"""
    cfg = _load_config() if cfg is None else cfg
    return [n for n in PROVIDER_PRIORITY if _build(n, cfg).is_configured()]


def get_site_search_backend(cfg: Optional[Dict] = None) -> Optional[SiteSearchBackend]:
    """获取可用的站内检索后端实例（双检锁缓存）；未配置时返回 None。"""
    global _backend_cache, _backend_cache_key
    cfg = _load_config() if cfg is None else cfg
    provider = resolve_provider(cfg)
    if not provider:
        return None
    key = (provider, cfg.get("bocha_api_key", ""),
           cfg.get("google_cse_api_key", ""), cfg.get("google_cse_id", ""),
           cfg.get("brave_api_key", ""))
    with _backend_cache_lock:
        if _backend_cache is not None and _backend_cache_key == key:
            return _backend_cache
        _backend_cache = _build(provider, cfg)
        _backend_cache_key = key
        return _backend_cache


def probe_site_search(cfg: Optional[Dict] = None, domain: str = "") -> Dict:
    """最小成本自检：只回答「后端能不能通、Key 有没有效」。

    Args:
        domain: 自检目标域名。**强烈建议传站内源自己的域名**（如
            ``xiaohongshu.com``）：若留空会回落到占位域 ``example.com``，
            那么「该站点被后端限制 / include 限定失效」这类只在召回层可见的
            故障会被漏掉——自检照样 ok，源却始终取不到站内内容。

    不做端到端召回验证（那是「试搜」的职责、成本更高）——自检只发一次最小请求
    （1 条结果、不取摘要），且绕过缓存以保证结论来自当次真实请求。

    Returns:
        ``{"provider", "configured", "ok", "kind", "latency_ms", "message"}``。
        ``kind`` 取 ``ok`` / ``unconfigured`` / ``auth`` / ``quota`` / ``config`` /
        ``network`` / ``error``；``message`` 已 ``redact_secrets`` 脱敏
        （Google CSE 的 Key 走 query，异常消息会带出完整 URL）。

    成本提示：凭证有效时，博查等充值制后端会**消耗 1 次查询额度**；凭证无效
    （HTTP 401）不产生有效检索。UI 须在触发前向用户明示。
    """
    cfg = _load_config() if cfg is None else cfg
    provider = resolve_provider(cfg)
    if not provider:
        return {"provider": "", "configured": False, "ok": False,
                "kind": "unconfigured", "latency_ms": 0.0,
                "message": "未配置任何站内检索后端（博查 / Brave / Google CSE）"}

    def _result(ok: bool, kind: str, message: str, started: float) -> Dict:
        return {"provider": provider, "configured": True, "ok": ok, "kind": kind,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "message": redact_secrets(message)[:200]}

    backend = _build(provider, cfg)
    t0 = time.monotonic()
    try:
        backend.probe(domain)
    except SiteSearchError as e:
        logger.info(f"站内检索自检失败({e.kind}): {e}")
        return _result(False, e.kind, str(e), t0)
    except Exception as e:
        logger.warning(f"站内检索自检异常: {e}")
        return _result(False, "error", f"{type(e).__name__}: {e}", t0)
    return _result(True, "ok", "", t0)


def reset_site_search_backend() -> None:
    """清空后端实例缓存（凭证或 Provider 变更后调用，使下次重建）。"""
    global _backend_cache, _backend_cache_key
    with _backend_cache_lock:
        _backend_cache = None
        _backend_cache_key = None
