"""
文件锁模块
==========
提供基于 portalocker 的 JSON 文件安全读写，防止并发损坏。

两个入口的读取语义要分清：

- ``safe_read_json``（默认）：失败时返回 ``{}``。适合只读消费——
  读到失败只是界面显示为空，不丢数据。
- ``safe_read_json(..., strict=True)`` / ``JsonReadError``：失败时抛异常。
  适合读-改-写路径——读到失败必须能被区分出来，否则一次失败的读加一次
  成功的写就会把整个文件抹成只含本次修改的样子，且调用方毫无感知。
"""

import json
import os
import shutil
import time
from typing import Any, Dict, Optional
from pathlib import Path

import portalocker

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 0.1


class JsonReadError(Exception):
    """JSON 读取失败（文件被占用 / 锁竞争 / 内容损坏）。

    仅在 ``strict=True`` 时抛出。存在的意义是让读-改-写路径把
    「读取失败」与「文件本来是空的」区分开——后者是合法状态，前者不是。
    """


def safe_read_json(file_path: str, strict: bool = False) -> Dict:
    """
    安全读取 JSON 文件，使用共享锁。

    Args:
        file_path: JSON 文件路径
        strict: True 时读取失败抛 :class:`JsonReadError` 而不是返回空字典。
                读-改-写路径应使用 True，避免把失败伪装成空数据后整表写回。

    Returns:
        解析后的字典；非 strict 模式下失败时返回空字典

    Raises:
        JsonReadError: 仅 strict=True，且重试后仍无法读取时
    """
    if not os.path.exists(file_path):
        # 文件不存在是合法状态（首次运行），不算读取失败
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
            # Windows 文件被占用：写方正持有目标（shutil.move 会截断目标），退避后重试
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                reason = f"文件被占用: {file_path}"
                logger.warning(f"读取失败，{reason}")
                if strict:
                    raise JsonReadError(reason)
                return {}
        except (json.JSONDecodeError, portalocker.exceptions.LockException) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                # 文件已损坏或被长时间独占。注意：这里绝不能返回 {} 就完事——
                # 读-改-写路径会把这个 {} 当成合法空表写回去，造成抹除。
                reason = f"内容损坏或无法加锁 ({e}): {file_path}"
                logger.warning(f"读取失败，{reason}")
                if strict:
                    raise JsonReadError(reason)
                return {}
        except Exception as e:
            reason = f"读取异常 ({type(e).__name__}: {e}): {file_path}"
            logger.error(reason)
            if strict:
                raise JsonReadError(reason) from e
            return {}
    return {}


def read_for_update(file_path: str) -> Optional[Any]:
    """读-改-写路径专用读取：把「读取失败」变成一个可判定的返回值。

    与 ``safe_read_json`` 的唯一区别：失败（文件被占用 / 内容损坏 / 无法加锁、
    重试后仍不行）时返回 **None**，而不是空字典。

    为什么需要它：读-改-写的代码形如

        data = safe_read_json(FILE)      # 读到失败 → {}
        data.setdefault("items", []).append(new)
        safe_write_json(FILE, data)       # 把只有一条目的表写回去 → 整表被抹除

    调用方拿到 None 就可以中止写回，把「静默丢数据」降级成「本次操作失败」。
    文件不存在（首次运行）和「文件内容真的是空对象」都返回各自的合法值，
    不返回 None，因此 None 一定代表失败。

    用法::

        data = read_for_update(FILE)
        if data is None:
            logger.warning("读取失败，放弃本次写入（防止覆盖）")
            return False
    """
    try:
        return safe_read_json(file_path, strict=True)
    except JsonReadError:
        return None


def safe_write_json(file_path: str, data: Any) -> bool:
    """
    安全写入 JSON 文件，使用排他锁。写入通过临时文件 + 原子重命名实现。

    临时文件泄漏防护：所有失败分支（含 PermissionError / OSError）都会在
    ``finally`` 中清理 ``.tmp.<pid>.<ms>`` 文件。Windows 下 ``shutil.move``
    在目标被其他进程以共享锁打开时抛 ``PermissionError``，而这是「读多写多」
    文件（如 source_health.json）的常态竞态——此前只有最后一个 except 分支
    清理，导致每次失败泄漏一个临时文件。

    Args:
        file_path: JSON 文件路径
        data: 要序列化的数据

    Returns:
        是否写入成功
    """
    for attempt in range(MAX_RETRIES):
        tmp_path: Optional[str] = None
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
            tmp_path = None  # 已被 move 消费，无需清理
            return True
        except PermissionError:
            # Windows 文件被占用：目标可能正被读者持共享锁
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.warning(f"文件被占用，写入失败: {file_path}")
                return False
        except (OSError, portalocker.exceptions.LockException) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.warning(f"写入失败 {file_path}: {e}")
                return False
        except Exception as e:
            logger.error(f"写入异常 {file_path}: {e}")
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    return False
