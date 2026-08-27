"""
SMTP 邮件配置持久化模块
======================
统一「UI 邮件设置」与「定时调度器 / CLI 推送」两条链路的配置来源。

修复的问题：
- 原 UI 将 SMTP 配置仅存于 st.session_state，刷新即丢；
- 调度器只读环境变量（SMTP_SERVER 等），UI 保存的配置对定时推送完全无效。

合并优先级：
- 非敏感字段：默认值 ← 环境变量 ← 配置文件（文件最优先）
- 敏感字段（password）：默认值 ← 配置文件 ← 环境变量（.env 最优先）

安全建议：
- SMTP 密码等敏感凭据应配置在 .env 文件中（已在 .gitignore），
  而非 data/email_settings.json。后者虽也在 .gitignore 中，
  但存在意外提交或打包泄露的风险。
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

# 敏感字段列表：这些字段的值应优先从 .env 读取，而非 JSON 文件
# 原因：.env 已在 .gitignore 中，而 data/ 目录存在意外打包/提交风险
_SENSITIVE_FIELDS = {"password"}


def get_email_settings() -> Dict:
    """读取合并后的邮件配置。

    优先级策略：
    - 非敏感字段：默认值 ← 环境变量 ← 文件（文件最优先）
    - 敏感字段（password）：默认值 ← 文件 ← 环境变量（.env 最优先）

    这样设计是为了让敏感凭据可以通过 .env 安全管理，
    同时保留 UI 配置非敏感字段的灵活性。
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

    # 2) UI/调用方显式保存到文件的字段
    stored = safe_read_json(EMAIL_SETTINGS_FILE)
    if isinstance(stored, dict):
        for key in _DEFAULTS:
            if key not in stored or stored[key] in (None, ""):
                continue
            # 敏感字段：仅当环境变量未设置时才使用文件中的值
            if key in _SENSITIVE_FIELDS:
                env_name = _ENV_MAP.get(key, "")
                if os.getenv(env_name):
                    logger.warning(
                        f"敏感字段 '{key}' 同时存在于 {env_name} 和 "
                        f"{EMAIL_SETTINGS_FILE}，优先使用环境变量（更安全）。"
                        f"建议从 JSON 文件中移除该字段。"
                    )
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
