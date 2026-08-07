"""
文件锁模块
==========
提供基于 portalocker 的 JSON 文件安全读写，防止并发损坏。
"""

import json
import os
from typing import Any, Dict
from pathlib import Path

import portalocker

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


def safe_read_json(file_path: str) -> Dict:
    """
    安全读取 JSON 文件，使用共享锁。

    Args:
        file_path: JSON 文件路径

    Returns:
        解析后的字典，失败时返回空字典
    """
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            portalocker.lock(f, portalocker.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                portalocker.unlock(f)
        return data
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return {}


def safe_write_json(file_path: str, data: Any) -> bool:
    """
    安全写入 JSON 文件，使用排他锁。写入通过临时文件 + 原子重命名实现。

    Args:
        file_path: JSON 文件路径
        data: 要序列化的数据

    Returns:
        是否写入成功
    """
    try:
        Path(os.path.dirname(file_path) or ".").mkdir(parents=True, exist_ok=True)
        tmp_path = file_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
            finally:
                portalocker.unlock(f)
        os.replace(tmp_path, file_path)
        return True
    except Exception as e:
        logger.error(f"Error writing {file_path}: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False
