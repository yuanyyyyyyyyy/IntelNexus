"""
关注点（WATCH_CATEGORIES）配置读写
=================================
默认关注点由 ai_briefing.config 提供（代码常量），用户可在
data/watch_categories.json 中覆盖或追加。本模块做 thin-wrapper：
优先读用户覆盖文件，回退到代码默认。

迁移说明：原 WATCH_CATEGORIES 写死在 ai_briefing/config.py，
现改为「代码默认 + 用户文件覆盖」的混合模式，满足"关注点可配置化"。
"""

import os
from typing import Dict, List

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json

logger = get_logger(__name__)


# 用户覆盖文件位于主项目 data 目录（主项目与子项目共享同一 data 卷）
from intelnexus.config.paths import get_data_dir

WATCH_CATEGORIES_FILE = os.path.join(get_data_dir(), "watch_categories.json")


def _default_categories() -> Dict:
    """从代码常量读取默认关注点（避免循环导入：延迟导入）。"""
    from intelnexus.briefing.config import WATCH_CATEGORIES
    return WATCH_CATEGORIES


def _ensure_file():
    """确保覆盖文件存在（初始为空 {}，表示完全回退默认）。"""
    if not os.path.exists(WATCH_CATEGORIES_FILE):
        try:
            safe_write_json(WATCH_CATEGORIES_FILE, {})
        except Exception as e:
            logger.warning(f"创建 watch_categories.json 失败: {e}")


def get_all_categories() -> Dict:
    """合并用户覆盖文件与代码默认，返回完整关注点字典。

    规则：
      - 用户在文件中删除某个默认类目（显式置 null/enabled=false）则不出现
      - 用户新增类目追加
      - 用户修改已有类目字段则覆盖
    """
    defaults = _default_categories()
    _ensure_file()
    overrides = safe_read_json(WATCH_CATEGORIES_FILE) or {}

    merged = {}
    for cid, cfg in defaults.items():
        if cid in overrides:
            ov = overrides[cid]
            # 用户显式禁用（enabled=false 或整个值为 null）则跳过
            if ov is None or (isinstance(ov, dict) and ov.get("enabled", True) is False):
                continue
            # 深合并：默认字段 + 用户覆盖字段
            merged[cid] = {**cfg, **ov}
        else:
            merged[cid] = cfg

    # 用户新增的、不在默认里的类目
    for cid, cfg in overrides.items():
        if cid not in defaults and isinstance(cfg, dict) and cfg.get("enabled", True) is not False:
            merged[cid] = cfg

    return merged


def get_category_ids() -> List[str]:
    """返回所有（合并后）关注点 ID 列表。"""
    return list(get_all_categories().keys())


def get_category(cid: str) -> Dict:
    """根据 ID 获取单个关注点配置（不存在返回 None）。"""
    return get_all_categories().get(cid)


def add_category(cid: str, cfg: Dict) -> bool:
    """新增或覆盖一个关注点。cfg 至少需要 name / search_queries 字段。"""
    if not cid or not isinstance(cfg, dict):
        return False
    _ensure_file()
    overrides = safe_read_json(WATCH_CATEGORIES_FILE) or {}
    cfg = dict(cfg)
    cfg["enabled"] = cfg.get("enabled", True)
    overrides[cid] = cfg
    return safe_write_json(WATCH_CATEGORIES_FILE, overrides)


def update_category(cid: str, cfg: Dict) -> bool:
    """更新已有关注点（字段级合并）。"""
    if not cid:
        return False
    _ensure_file()
    overrides = safe_read_json(WATCH_CATEGORIES_FILE) or {}
    existing = overrides.get(cid, {})
    if not isinstance(existing, dict):
        existing = {}
    existing.update(cfg)
    overrides[cid] = existing
    return safe_write_json(WATCH_CATEGORIES_FILE, overrides)


def remove_category(cid: str) -> bool:
    """移除用户覆盖（恢复默认，或彻底删除自定义类目）。"""
    _ensure_file()
    overrides = safe_read_json(WATCH_CATEGORIES_FILE) or {}
    if cid in overrides:
        del overrides[cid]
    else:
        # 默认类目无法物理删除，标记为禁用
        overrides[cid] = {"enabled": False}
    return safe_write_json(WATCH_CATEGORIES_FILE, overrides)


def get_disabled_default_ids() -> List[str]:
    """列出被禁用的默认关注点 ID（供 UI 提供"恢复默认"入口）。

    判定标准：ID 在代码默认 WATCH_CATEGORIES 中，且用户覆盖文件里
    enabled 显式为 False。
    """
    _ensure_file()
    defaults = _default_categories()
    overrides = safe_read_json(WATCH_CATEGORIES_FILE) or {}
    disabled = []
    for cid in defaults:
        ov = overrides.get(cid)
        if isinstance(ov, dict) and ov.get("enabled", True) is False:
            disabled.append(cid)
    return disabled


def restore_default(cid: str) -> bool:
    """恢复一个被禁用的默认关注点：移除禁用覆盖，回到代码默认配置。"""
    if cid not in _default_categories():
        return False
    _ensure_file()
    overrides = safe_read_json(WATCH_CATEGORIES_FILE) or {}
    if cid in overrides:
        del overrides[cid]
    return safe_write_json(WATCH_CATEGORIES_FILE, overrides)
