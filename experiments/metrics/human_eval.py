"""人工评分：盲评表生成 + Krippendorff's α（表3 人工评分列与一致性）。

流程：
1. ``make_sheet`` 生成盲评 CSV（配置名被匿名化为 A/B/C，映射单独存档）；
2. 评审人按 5 分制填写三维度：事实准确性、信息完整性、可用性；
3. ``alpha_from_csv`` 计算总体与各维度的 Krippendorff's α。

未填写或评审人不足 2 人时返回 None，由上层保留占位。
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from experiments.common import write_json
from experiments.logging_utils import get_logger

logger = get_logger("exp.human_eval")

DIMENSIONS = ["factuality", "completeness", "usability"]
CSV_HEADER = ["eval_id", "sample_id", "config_anon", "rater", "output_path",
              "factuality", "completeness", "usability", "note"]
DEFAULT_RATERS = ["r1", "r2", "r3"]


def make_sheet(rows: List[Dict[str, Any]], out_csv: Path, raters: Sequence[str] = DEFAULT_RATERS) -> Path:
    """生成盲评表。

    Args:
        rows: [{sample_id, config, output_path, repeat}]
    """
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    configs = sorted({str(r.get("config")) for r in rows})
    anon = {c: chr(ord("A") + i) for i, c in enumerate(configs)}
    mapping = {v: k for k, v in anon.items()}
    write_json(out_csv.with_suffix(".mapping.json"),
               {"anonymous_to_config": mapping, "generated_rows": len(rows)})

    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        n = 0
        for r in rows:
            for rater in raters:
                n += 1
                w.writerow([
                    f"E{n:05d}", r.get("sample_id", ""), anon.get(str(r.get("config")), "?"),
                    rater, r.get("output_path", ""), "", "", "", "",
                ])
    logger.info("盲评表已生成: %s（%d 行，%d 个配置）", out_csv, n, len(configs))
    return out_csv


def _read_filled(path: Path) -> List[Dict[str, str]]:
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if any((row.get(d) or "").strip() for d in DIMENSIONS):
                rows.append(row)
    return rows


def krippendorff_alpha(ratings: Dict[str, Dict[str, float]], level: str = "ordinal") -> Optional[float]:
    """Krippendorff's α。

    Args:
        ratings: {unit_id: {rater_id: value}}，每个 unit 至少 2 个评分
        level: nominal（0/1 差异）或 ordinal（秩差平方）
    """
    units = {u: r for u, r in ratings.items() if len(r) >= 2}
    if not units:
        return None
    values = sorted({v for r in units.values() for v in r.values()})
    if len(values) < 2:
        return 0.0  # 无变异
    rank = {v: i for i, v in enumerate(values)}

    def delta(a: float, b: float) -> float:
        if level == "nominal":
            return 0.0 if a == b else 1.0
        return float(rank[a] - rank[b]) ** 2

    # 一致矩阵 o[c][k]
    o: Dict[float, Dict[float, float]] = defaultdict(lambda: defaultdict(float))
    pairable = 0
    for r in units.values():
        m = len(r)
        vals = list(r.values())
        pairable += m
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                o[vals[i]][vals[j]] += 1.0 / (m - 1)
    n = pairable
    if n < 2:
        return None

    keys = sorted(o.keys())
    n_c = {c: sum(o[c].values()) for c in keys}
    total = sum(n_c.values())
    if total <= 1:
        return None

    do = sum(o[c][k] * delta(c, k) for c in keys for k in keys if o[c].get(k))
    de = sum(n_c[c] * n_c[k] * delta(c, k) for c in keys for k in keys)
    do /= n
    de /= (total * (total - 1))
    if de == 0:
        return 1.0
    return 1.0 - do / de


def alpha_from_csv(path: Path, level: str = "ordinal") -> Dict[str, Optional[float]]:
    """从已填写的盲评表计算总体与各维度 α。"""
    rows = _read_filled(path)
    if not rows:
        return {"overall": None, **{d: None for d in DIMENSIONS}, "n_units": 0, "raters": 0}

    overall: Dict[str, Dict[str, float]] = defaultdict(dict)
    per_dim: Dict[str, Dict[str, Dict[str, float]]] = {d: defaultdict(dict) for d in DIMENSIONS}
    raters = set()
    for r in rows:
        unit = f"{r.get('sample_id')}|{r.get('config_anon')}"
        rater = str(r.get("rater") or "")
        raters.add(rater)
        vals = [float(r[d]) for d in DIMENSIONS if (r.get(d) or "").strip()]
        if vals:
            overall[unit][rater] = sum(vals) / len(vals)
        for d in DIMENSIONS:
            v = (r.get(d) or "").strip()
            if v:
                per_dim[d][unit][rater] = float(v)

    out: Dict[str, Optional[float]] = {
        "overall": krippendorff_alpha(overall, level),
        "n_units": len(overall),
        "raters": len(raters),
    }
    for d in DIMENSIONS:
        out[d] = krippendorff_alpha(per_dim[d], level)
    return out
