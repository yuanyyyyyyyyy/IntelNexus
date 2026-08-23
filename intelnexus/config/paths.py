"""
项目数据目录统一锚点
====================
修复：各配置模块原用 `dirname(__file__)/../../..` 锚定 data 目录，
实际解析到仓库外（D:\\Improve\\Project\\Python\\data）；而 BriefingHistory/
SearchHistory 用相对 CWD 的 "data"，落在仓库内。两套锚点并存导致数据分裂。

现全部收敛到仓库内 <repo>/data/：
- get_data_dir(): 唯一权威路径（intelnexus 包根的上一级 / data）
- migrate_legacy_data_files(): 一次性把旧目录中的既有数据文件搬到新位置。
  仅当目标不存在时复制（绝不覆盖仓库内更新的文件），搬完后旧文件加
  .migrated.bak 后缀保留作备份。可安全重复调用（幂等）。
"""

import os
import shutil

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# intelnexus/config/paths.py → 包根=intelnexus → 项目根=上一级
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# 旧的（仓库外）数据目录：仅用于一次性迁移读取
_LEGACY_DATA_DIR = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data"
))

# 曾被模块锚定写到旧目录的数据文件（迁移范围）
_MIGRATABLE_FILES = [
    "subscriptions.json",
    "sources.json",
    "watch_categories.json",
    "topics.json",
    "briefing_drafts.json",
    "email_settings.json",
    "knowledge_base.json",
    "feedback.json",
    "user_behavior.json",
]


def get_data_dir() -> str:
    """返回统一的仓库内 data 目录绝对路径。"""
    return DATA_DIR


def legacy_data_dir() -> str:
    """返回历史遗留的仓库外数据目录（诊断/迁移用）。"""
    return _LEGACY_DATA_DIR


def _copy_if_missing(src: str, dst: str) -> bool:
    """目标不存在时才复制；返回是否发生了复制。"""
    if os.path.exists(dst):
        return False
    shutil.copy2(src, dst)
    logger.info("Migrated %s -> %s", src, dst)
    return True


def migrate_legacy_data_files() -> dict:
    """把旧目录中的既有数据文件迁移到仓库内 data/（幂等，可重复调用）。

    规则：
      - 目标已存在 → 不动目标（仓库内文件优先，通常是更新或本就属于此处的数据）
      - 复制成功后 → 旧文件重命名为 *.migrated.bak（保留备份、退出活跃使用）
    Returns:
        dict: {"migrated": [文件名...], "skipped_existing": [...], "no_source": [...]}
    """
    result = {"migrated": [], "skipped_existing": [], "no_source": []}
    if not os.path.isdir(_LEGACY_DATA_DIR) or _LEGACY_DATA_DIR == DATA_DIR:
        return result

    os.makedirs(DATA_DIR, exist_ok=True)
    for name in _MIGRATABLE_FILES:
        src = os.path.join(_LEGACY_DATA_DIR, name)
        if not os.path.exists(src):
            result["no_source"].append(name)
            continue
        dst = os.path.join(DATA_DIR, name)
        if _copy_if_missing(src, dst):
            result["migrated"].append(name)
            try:
                os.replace(src, src + ".migrated.bak")
            except OSError as e:
                logger.warning("Could not rename legacy file %s: %s", src, e)
        else:
            result["skipped_existing"].append(name)

    if result["migrated"]:
        logger.info("Legacy data migration complete: %s", result["migrated"])
    return result
