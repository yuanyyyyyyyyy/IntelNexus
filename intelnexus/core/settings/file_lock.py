"""
文件锁模块
==========
提供基于 portalocker 的 JSON 文件安全读写，防止并发损坏。
"""

import json
import os
import shutil
import time
from typing import Any, Dict
from pathlib import Path

import portalocker

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 0.1


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
    for attempt in range(MAX_RETRIES):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                portalocker.lock(f, portalocker.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    portalocker.unlock(f)
            return data
        except PermissionError:
            # Windows文件被占用，跳过读取
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.debug(f"文件被占用，跳过读取: {file_path}")
                return {}
        except (json.JSONDecodeError, portalocker.exceptions.LockException) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"Error reading {file_path}: {e}")
                return {}
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return {}
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
    for attempt in range(MAX_RETRIES):
        try:
            Path(os.path.dirname(file_path) or ".").mkdir(parents=True, exist_ok=True)
            tmp_path = file_path + f".tmp.{os.getpid()}.{int(time.time()*1000)}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                try:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                finally:
                    portalocker.unlock(f)
            shutil.move(tmp_path, file_path)
            return True
        except PermissionError:
            # Windows文件被占用，跳过写入
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.debug(f"文件被占用，跳过写入: {file_path}")
                return False
        except (OSError, portalocker.exceptions.LockException) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"Error writing {file_path}: {e}")
                return False
        except Exception as e:
            logger.error(f"Error writing {file_path}: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            return False
    return False
