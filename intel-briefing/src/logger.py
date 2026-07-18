"""
统一日志模块
============
提供全项目一致的日志配置，替代分散的 print() 调用。
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    获取一个配置好的 logger 实例。

    Args:
        name: logger 名称，通常传 __name__

    Returns:
        配置好格式和级别的 Logger
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s %(levelname)s %(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
