"""
共享配置模块
============
通过配置注入机制提供项目配置，避免循环依赖。
"""

_config = {}


def set(cfg: dict):
    """注入项目配置（在每个项目入口调用）"""
    global _config
    _config = cfg


def get(key: str, default=None):
    """获取配置值"""
    return _config.get(key, default)
