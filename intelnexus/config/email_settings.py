"""
SMTP 邮件配置持久化模块
======================
统一「UI 邮件设置」与「定时调度器 / CLI 推送」两条链路的配置来源。

修复的问题：
- 原 UI 将 SMTP 配置仅存于 st.session_state，刷新即丢；
- 调度器只读环境变量（SMTP_SERVER 等），UI 保存的配置对定时推送完全无效。

合并优先级：
- 所有字段：默认值 ← 环境变量 ← 配置文件（文件最优先）

说明：
- data/email_settings.json 已在 .gitignore 中，仅保存在用户本地，不会泄露到仓库
- 普通用户通过 UI 配置即可，无需手动编辑 .env
- .env 仍可作为高级用户的兜底配置方式
"""

import os
from typing import Dict, Optional

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json
from intelnexus.config.paths import get_data_dir

logger = get_logger(__name__)

# 统一路径锚点：仓库内 <repo>/data/
EMAIL_SETTINGS_FILE = os.path.join(
    get_data_dir(), "email_settings.json"
)

_DEFAULTS: Dict = {
    "smtp_server": "",
    "smtp_port": 587,
    "username": "",
    "password": "",
    "use_tls": True,
    "from_name": "AI简报系统",
}

# 环境变量 → 字段映射（与 main.py 原有命名保持兼容）
_ENV_MAP = {
    "smtp_server": "SMTP_SERVER",
    "smtp_port": "SMTP_PORT",
    "username": "SMTP_USERNAME",
    "password": "SMTP_PASSWORD",
    "use_tls": "SMTP_USE_TLS",
    "from_name": "SMTP_FROM_NAME",
}


def get_email_settings() -> Dict:
    """读取合并后的邮件配置。

    优先级策略（所有字段统一）：
    默认值 ← 环境变量 ← 配置文件（文件最优先）

    这样设计是为了让普通用户通过 UI 配置即可，
    无需手动编辑 .env 文件。
    """
    cfg = dict(_DEFAULTS)

    # 1) 环境变量作为引导/兜底（含 .env 自动加载的值）
    for key, env_name in _ENV_MAP.items():
        val = os.getenv(env_name)
        if val is None or val == "":
            continue
        if key == "smtp_port":
            try:
                cfg[key] = int(val)
            except ValueError:
                logger.warning(f"Invalid {env_name}={val!r}, keeping {cfg[key]}")
        elif key == "use_tls":
            cfg[key] = val.strip().lower() == "true"
        else:
            cfg[key] = val

    # 2) UI/调用方显式保存到文件的字段（文件优先级最高）
    stored = safe_read_json(EMAIL_SETTINGS_FILE)
    if isinstance(stored, dict):
        for key in _DEFAULTS:
            if key not in stored or stored[key] in (None, ""):
                continue
            cfg[key] = stored[key]

    return cfg


def save_email_settings(cfg: Dict) -> bool:
    """持久化邮件配置到 data/email_settings.json（字段级合并写入）。"""
    if not isinstance(cfg, dict):
        return False

    clean = {}
    for key in _DEFAULTS:
        if key not in cfg:
            continue
        if key == "smtp_port":
            try:
                clean[key] = int(cfg[key])
            except (TypeError, ValueError):
                clean[key] = _DEFAULTS[key]
        elif key == "use_tls":
            clean[key] = bool(cfg[key])
        else:
            clean[key] = str(cfg[key] or "")

    existing = safe_read_json(EMAIL_SETTINGS_FILE)
    if isinstance(existing, dict):
        existing.update(clean)
        clean = existing

    ok = safe_write_json(EMAIL_SETTINGS_FILE, clean)
    if ok:
        logger.info("Email settings saved to %s", EMAIL_SETTINGS_FILE)
    return ok


def get_active_email_config() -> Optional[Dict]:
    """返回可直接用于 AIBriefingNotifier 的完整配置；不完整时返回 None。

    完整性标准与 notifier._send_email_once 一致：
    smtp_server / username / password 三项均非空才可发信。
    """
    cfg = get_email_settings()
    if not cfg.get("smtp_server") or not cfg.get("username") or not cfg.get("password"):
        return None
    return cfg


def test_email_settings(recipient: str) -> bool:
    """用当前生效配置向指定邮箱发送一封测试邮件。

    复用 AIBriefingNotifier.send_email（含 TLS 校验与重试），避免第二套 SMTP 实现。
    """
    if not recipient:
        return False
    cfg = get_active_email_config()
    if cfg is None:
        logger.warning("Email settings incomplete; cannot send test email")
        return False

    from intelnexus.briefing.notifier import AIBriefingNotifier

    notifier = AIBriefingNotifier(email_config=cfg)
    subject = "IntelNexus 邮件推送测试 / Test Email"
    content = (
        "这是一封来自 IntelNexus 简报系统的测试邮件。\n"
        "收到此邮件说明 SMTP 配置有效，定时简报可以正常推送到该邮箱。\n"
    )
    return notifier.send_email(email=recipient, subject=subject, content=content)
