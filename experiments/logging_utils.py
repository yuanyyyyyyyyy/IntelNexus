"""实验管线日志。

只记录 run 级摘要（run_id、配置、耗时、token 数），
不打印完整 prompt 与响应正文，避免日志体积膨胀与内容外泄。
"""
from __future__ import annotations

import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s [exp] %(message)s"


def get_logger(name: str = "experiments") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
