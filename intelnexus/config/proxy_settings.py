"""
网络代理配置持久化模块
======================
统一「UI 代理设置」「系统代理自动检测」「.env 环境变量」三层代理来源。

解决的问题：
- 用户频繁切换梯子工具，代理端口每次不同，手动改 .env 对非技术用户不友好。
- 绝大多数梯子（Clash / v2rayN / Shadowsocks 等）开启后会自动写入 Windows 系统代理，
  通过注册表读取即可自动获取，无需用户手动配置。

合并优先级（高 → 低）：
  UI 手动设置 > 系统代理自动检测 > .env 环境变量 > 无代理（直连）

存储：
- UI 手动设置持久化到 data/proxy_settings.json
- 系统代理通过 Windows 注册表实时读取（不持久化）
"""

import os
import sys
from typing import Dict, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json
from intelnexus.config.paths import get_data_dir

logger = get_logger(__name__)

PROXY_SETTINGS_FILE = os.path.join(get_data_dir(), "proxy_settings.json")

_DEFAULTS: Dict = {
    # 手动代理地址，格式为 "http://127.0.0.1:7890" 或 "127.0.0.1:7890"
    # 为空表示不使用手动设置，回退到系统代理检测
    "proxy_url": "",
    # 是否启用系统代理自动检测（默认开启）
    "auto_detect": True,
}


# ============================================================================
# 系统代理自动检测（Windows）
# ============================================================================

def detect_system_proxy() -> str:
    """从 Windows 注册表读取当前系统 HTTP 代理地址。

    绝大多数梯子工具（Clash / v2rayN / Shadowsocks 等）开启后会自动
    写入 Windows 系统代理设置。读取注册表即可零配置获取当前代理。

    Returns:
        代理地址字符串（如 "127.0.0.1:7890"），未检测到返回空串。
    """
    if sys.platform != "win32":
        return ""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        try:
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not proxy_enable:
                winreg.CloseKey(key)
                return ""
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            winreg.CloseKey(key)
            if proxy_server:
                # 注册表值可能是 "127.0.0.1:7890" 或 "http=host:port;https=host:port"
                # 后者取第一个协议的值
                server_str = str(proxy_server).strip()
                if "=" in server_str:
                    # 多协议格式，取第一个
                    first = server_str.split(";")[0]
                    if "=" in first:
                        server_str = first.split("=", 1)[1]
                logger.debug("检测到系统代理: %s", server_str)
                return server_str
        except FileNotFoundError:
            # ProxyEnable 或 ProxyServer 键不存在
            pass
        finally:
            try:
                winreg.CloseKey(key)
            except Exception:
                pass
    except ImportError:
        pass
    except Exception as e:
        logger.debug("读取系统代理设置失败: %s", e)
    return ""


# ============================================================================
# 环境变量代理读取（兼容原 .env 方案）
# ============================================================================

def _read_env_proxy() -> str:
    """从 HTTP_PROXY / HTTPS_PROXY 环境变量读取代理地址。

    兼容原 .env 配置方式，作为兜底来源。
    """
    http = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    return http or https or ""


# ============================================================================
# 统一读取 / 保存
# ============================================================================

def get_proxy_settings() -> Dict:
    """读取合并后的代理配置。

    优先级（高 → 低）：
    1. UI 手动设置（data/proxy_settings.json 中的 proxy_url）
    2. 系统代理自动检测（Windows 注册表，auto_detect=True 时）
    3. .env 环境变量（HTTP_PROXY / HTTPS_PROXY）
    4. 无代理（直连）

    返回 dict 包含：
    - proxy_url: 当前生效的代理地址（已归一化为完整 URL）
    - source: 代理来源 ("manual" / "system" / "env" / "none")
    - auto_detect: 是否启用系统代理检测
    """
    cfg = dict(_DEFAULTS)

    # 1) 读取 UI 手动保存到文件的配置
    stored = safe_read_json(PROXY_SETTINGS_FILE)
    if isinstance(stored, dict):
        for key in _DEFAULTS:
            if key in stored and stored[key] not in (None, ""):
                cfg[key] = stored[key]

    # 2) 确定最终生效的代理地址
    proxy_url = ""
    source = "none"

    # 优先级 3: .env 环境变量（兜底）
    env_proxy = _read_env_proxy()
    if env_proxy:
        proxy_url = env_proxy
        source = "env"

    # 优先级 2: 系统代理自动检测
    if cfg.get("auto_detect", True):
        system_proxy = detect_system_proxy()
        if system_proxy:
            proxy_url = system_proxy
            source = "system"

    # 优先级 1: UI 手动设置（最权威）
    manual_url = str(cfg.get("proxy_url", "")).strip()
    if manual_url:
        proxy_url = manual_url
        source = "manual"

    # 归一化：确保 proxy_url 带协议前缀
    proxy_url = _normalize_proxy_url(proxy_url)

    return {
        "proxy_url": proxy_url,
        "source": source,
        "auto_detect": bool(cfg.get("auto_detect", True)),
    }


def save_proxy_settings(cfg: Dict) -> bool:
    """持久化代理设置到 data/proxy_settings.json（字段级合并写入）。"""
    if not isinstance(cfg, dict):
        return False

    clean = {}
    if "proxy_url" in cfg:
        clean["proxy_url"] = str(cfg["proxy_url"] or "").strip()
    if "auto_detect" in cfg:
        clean["auto_detect"] = bool(cfg["auto_detect"])

    if not clean:
        return False

    existing = safe_read_json(PROXY_SETTINGS_FILE)
    if isinstance(existing, dict):
        existing.update(clean)
        clean = existing

    ok = safe_write_json(PROXY_SETTINGS_FILE, clean)
    if ok:
        logger.info("Proxy settings saved to %s", PROXY_SETTINGS_FILE)
    return ok


def get_effective_proxy() -> Optional[Dict[str, str]]:
    """返回当前生效的代理配置 dict，可直接传给 requests.Session.proxies。

    格式: {"http": "http://...", "https": "http://..."} 或 None（无代理时）。

    这是搜索管线（get_http_proxies）和 LLM 管线的统一入口。
    """
    settings = get_proxy_settings()
    url = settings.get("proxy_url", "")
    if not url:
        return None
    return {"http": url, "https": url}


# ============================================================================
# 工具函数
# ============================================================================

def _normalize_proxy_url(url: str) -> str:
    """归一化代理地址：确保带 http:// 前缀。

    用户可能输入 "127.0.0.1:7890" 或 "http://127.0.0.1:7890"，
    统一为带协议的完整 URL。
    """
    url = url.strip()
    if not url:
        return ""
    # 已有协议前缀（http/https/socks5/socks5h 等）
    if "://" in url:
        return url
    # 默认补 http://
    return f"http://{url}"


def test_proxy_connection(proxy_url: str, timeout: int = 10) -> tuple:
    """测试代理是否可用。

    Args:
        proxy_url: 代理地址（如 "http://127.0.0.1:7890"）
        timeout: 超时秒数

    Returns:
        (success: bool, message: str)
    """
    if not proxy_url:
        return False, "代理地址为空"

    proxy_url = _normalize_proxy_url(proxy_url)
    proxies = {"http": proxy_url, "https": proxy_url}

    try:
        import requests
        resp = requests.get(
            "https://www.google.com",
            proxies=proxies,
            timeout=timeout,
        )
        if resp.status_code < 500:
            return True, f"代理可用 (HTTP {resp.status_code})"
        return False, f"代理返回异常状态码: {resp.status_code}"
    except requests.exceptions.ProxyError as e:
        return False, f"代理连接被拒绝，请确认梯子已启动: {type(e).__name__}"
    except requests.exceptions.ConnectTimeout:
        return False, "代理连接超时，请确认代理地址正确且梯子已启动"
    except Exception as e:
        return False, f"代理测试失败: {type(e).__name__}: {e}"
