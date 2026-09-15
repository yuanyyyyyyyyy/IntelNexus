"""实验配置加载。

只从 experiments/configs/ 读取 YAML。密钥一律走环境变量，
配置文件中不得出现任何凭据。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from experiments.paths import CONFIG_DIR


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as e:  # pragma: no cover - 依赖缺失时给出明确指引
        raise RuntimeError(
            "缺少依赖 PyYAML，请先安装：pip install pyyaml"
        ) from e
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load(name: str) -> Dict[str, Any]:
    """加载 configs/<name>.yaml（可省略扩展名）。"""
    path = CONFIG_DIR / (name if name.endswith(".yaml") else f"{name}.yaml")
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    return _load_yaml(path)


def experiment_config() -> Dict[str, Any]:
    return load("experiment")


def sources_config() -> Dict[str, Any]:
    return load("sources")


def pricing_config() -> Dict[str, Any]:
    return load("pricing")


def excluded_configs() -> Dict[str, str]:
    """被排除出汇总与论文的配置 → 排除原因。

    这些配置的定义仍保留在 ``configs`` 中（预注册矩阵完整留档），
    但汇总、图表与回填一律跳过；排除动作须记入 PROTOCOL.md 偏差记录。
    """
    data = experiment_config().get("exclude_configs") or {}
    if isinstance(data, list):          # 兼容只写 id 列表的写法
        return {str(x): "" for x in data}
    if isinstance(data, dict):
        return {str(k): str(v or "") for k, v in data.items()}
    return {}
