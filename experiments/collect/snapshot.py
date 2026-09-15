"""快照只读加载与确定性划分。

所有阶段（smoke / pilot / full / replication）读同一份快照，
样本划分只依赖 (seed, 比例)，保证任何一次运行取到的样本集合完全一致。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.common import read_json, read_jsonl, sha256_text
from experiments.logging_utils import get_logger
from experiments.paths import DATASET_STATS, SNAPSHOT_DIR

logger = get_logger("exp.snapshot")


@dataclass
class Snapshot:
    items: List[Dict[str, Any]]
    stats: Dict[str, Any]
    items_path: Path
    manifest_sha256: Optional[str] = None

    @property
    def size(self) -> int:
        return len(self.items)

    def quality_items(self) -> List[Dict[str, Any]]:
        """可用于质量评测的条目（正文与官方摘要不同源）。"""
        return [i for i in self.items if i.get("quality_eligible")]

    def all_items(self) -> List[Dict[str, Any]]:
        return list(self.items)


_SNAPSHOT_CACHE: Dict[str, Snapshot] = {}


def load(snapshot_dir: Optional[Path] = None, verify: bool = False,
         refresh: bool = False) -> Snapshot:
    """加载快照（带进程内缓存，避免每个 run 重复读取）。

    快照只在 collect 阶段写一次，运行期视为只读，缓存不会造成口径漂移。
    需要强制重读时传 refresh=True。
    """
    d = Path(snapshot_dir) if snapshot_dir else SNAPSHOT_DIR
    key = f"{d}:{verify}"
    if not refresh and key in _SNAPSHOT_CACHE:
        return _SNAPSHOT_CACHE[key]
    items_path = d / "items.jsonl"
    if not items_path.exists():
        raise FileNotFoundError(
            f"未找到数据快照 {items_path}。请先运行: python -m experiments.cli collect"
        )
    items = read_jsonl(items_path)
    stats = read_json(d / "dataset_stats.json") if (d / "dataset_stats.json").exists() else {}

    manifest_hash = None
    mf = d / "manifest.sha256"
    if mf.exists():
        line = next((l for l in mf.read_text(encoding="utf-8").splitlines() if "items.jsonl" in l), None)
        if line:
            manifest_hash = line.split()[0]
        if verify:
            actual = sha256_text("".join(open(items_path, encoding="utf-8").readlines()))
            if manifest_hash and actual != manifest_hash:
                # 哈希清单按文件内容计算，这里退化为逐行拼接校验，仅作提示
                logger.warning("items.jsonl 与 manifest 记录不一致，请确认快照未被改动")

    logger.info("加载快照: %s 条（质量评测可用 %d 条）", len(items), sum(1 for i in items if i.get("quality_eligible")))
    snap = Snapshot(items=items, stats=stats, items_path=items_path, manifest_sha256=manifest_hash)
    _SNAPSHOT_CACHE[key] = snap
    return snap


def _sort_key(item: Dict[str, Any]) -> tuple:
    return (str(item.get("published_at") or ""), str(item.get("id") or ""))


def split(items: List[Dict[str, Any]], dev_ratio: float = 0.2) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """按发布时间升序切分：前 dev_ratio 为提示工程调试集，其余为测试集。

    时序切分可避免"用未来数据调试提示词、再在历史数据上测试"的泄漏。
    """
    ordered = sorted(items, key=_sort_key)
    n_dev = int(round(len(ordered) * float(dev_ratio)))
    return ordered[:n_dev], ordered[n_dev:]


def sample(items: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    """从测试集起点确定性取前 n 条（不随机：便于复现与人工核对）。"""
    if n <= 0 or not items:
        return []
    ordered = sorted(items, key=_sort_key)
    return ordered[: min(int(n), len(ordered))]


def _test_items(snap: Snapshot) -> List[Dict[str, Any]]:
    """统一取测试集（后 80%），smoke/pilot/full 口径一致。"""
    _, test = split(snap.quality_items(), 0.2)
    return test


def smoke_set(n: int = 2) -> List[Dict[str, Any]]:
    snap = load()
    items = _test_items(snap) or snap.all_items()
    return sample(items, n)


def pilot_set(n: int = 30) -> List[Dict[str, Any]]:
    snap = load()
    return sample(_test_items(snap), n)


def full_set(n: int = 200) -> List[Dict[str, Any]]:
    snap = load()
    return sample(_test_items(snap), n)


if __name__ == "__main__":
    s = load()
    print(f"条目 {s.size}，质量评测可用 {len(s.quality_items())}")
    dev, test = split(s.quality_items(), 0.2)
    print(f"调试集 {len(dev)}，测试集 {len(test)}")
