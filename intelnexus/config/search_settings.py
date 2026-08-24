"""
搜索服务配置持久化模块
======================
统一「UI 搜索设置」与「CLI / 调度器」链路的第三方搜索 API 密钥配置来源。

与 email_settings.py 同一约定——合并优先级：默认值 ← 环境变量 ← 配置文件。
即：UI 显式保存的值最权威；环境变量（含 .env 自动加载）仅作引导兜底，
只在文件对应字段为空时生效。密钥轮换后只需在 UI 重新保存即可生效。
"""

import os
from typing import Dict

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json
from intelnexus.config.paths import get_data_dir

logger = get_logger(__name__)

# 统一路径锚点：仓库内 <repo>/data/
SEARCH_SETTINGS_FILE = os.path.join(
    get_data_dir(), "search_settings.json"
)

_DEFAULTS: Dict = {
    "news_api_key": "",
}

# 环境变量 → 字段映射（兼容原 config.py 的 NEWS_API_KEY 命名）
_ENV_MAP = {
    "news_api_key": "NEWS_API_KEY",
}


def get_search_settings() -> Dict:
    """读取合并后的搜索配置（默认值 ← 环境变量 ← 文件；文件中已保存的字段最优先）。"""
    cfg = dict(_DEFAULTS)

    # 1) 环境变量作为引导兜底
    for key, env_name in _ENV_MAP.items():
        val = os.getenv(env_name)
        if val:
            cfg[key] = val.strip()

    # 2) UI/调用方显式保存到文件的字段最权威，覆盖环境变量
    stored = safe_read_json(SEARCH_SETTINGS_FILE)
    if isinstance(stored, dict):
        for key in _DEFAULTS:
            if key in stored and stored[key] not in (None, ""):
                cfg[key] = str(stored[key]).strip()

    # 占位符值（模板残留 your_xxx 等）一律视为未配置
    for key in _DEFAULTS:
        if cfg[key].lower().startswith("your_"):
            cfg[key] = ""

    return cfg


def save_search_settings(cfg: Dict) -> bool:
    """持久化搜索配置到 data/search_settings.json（字段级合并写入）。"""
    if not isinstance(cfg, dict):
        return False

    clean = {}
    for key in _DEFAULTS:
        if key in cfg:
            clean[key] = str(cfg[key] or "").strip()

    if not clean:
        return False

    existing = safe_read_json(SEARCH_SETTINGS_FILE)
    if isinstance(existing, dict):
        existing.update(clean)
        clean = existing

    ok = safe_write_json(SEARCH_SETTINGS_FILE, clean)
    if ok:
        saved_keys = ", ".join(clean.keys())
        logger.info("Search settings saved (%s) to %s", saved_keys, SEARCH_SETTINGS_FILE)
    return ok


def get_news_api_key() -> str:
    """当前生效的 NewsAPI key：文件(UI 显式保存) > 环境变量(.env 兜底) > 空。

    返回空串表示未配置；NewsSearchSource 收到空 key 时自动跳过 NewsAPI，
    行为与历史「config.NEWS_API_KEY 为空」完全一致。
    """
    return get_search_settings()["news_api_key"]
