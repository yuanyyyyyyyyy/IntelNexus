"""实验管线的路径常量与目录管理。

所有产物集中在 ``experiments/`` 下，与 intelnexus 业务数据目录隔离，
便于整体归档到论文的 04_实验/。
"""
from __future__ import annotations

from pathlib import Path

# 仓库根（IntelNexus/）
ROOT = Path(__file__).resolve().parents[1]
# experiments/ 包目录
EXP_DIR = Path(__file__).resolve().parent

CONFIG_DIR = EXP_DIR / "configs"
RUNS_DIR = EXP_DIR / "runs"
DATA_DIR = EXP_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshot"
REPORTS_DIR = EXP_DIR / "reports"
FIGURES_DIR = EXP_DIR / "figures"

ENV_REPORT = REPORTS_DIR / "env_report.json"
DATASET_STATS = SNAPSHOT_DIR / "dataset_stats.json"
AGGREGATE = REPORTS_DIR / "aggregate.json"
SLOTS = REPORTS_DIR / "slots.json"

# 稿件正文目录（默认指向期刊投稿工作目录；可用 --content-dir 覆盖）
DEFAULT_CONTENT_DIR = Path(r"D:\Edge\信息安全与通信保密期刊－20260911\_build\content")


def ensure_dirs() -> None:
    """创建实验所需的全部输出目录。"""
    for d in (RUNS_DIR, DATA_DIR, SNAPSHOT_DIR, REPORTS_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def run_dir(run_id: str) -> Path:
    p = RUNS_DIR / run_id
    p.mkdir(parents=True, exist_ok=True)
    return p
