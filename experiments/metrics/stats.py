"""统计检验：Wilcoxon 符号秩、Cliff's delta、Holm 校正（表7）。

口径（与论文 3.5 节一致）：
- 配对设计：同一 (sample_id, repeat) 在两个配置下的取值构成一对；
- 报告统计量与 p 值，同时报告效应量 Cliff's delta；
- 多组两两比较用 Holm 逐步校正控制族错误率，α = 0.05。

缺失值成对剔除（任一侧为 None 的对不参与检验），并记录实际参与对数 n。
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from experiments.common import has_module

ALPHA = 0.05


def _pairs(a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> Tuple[List[float], List[float]]:
    xa, xb = [], []
    for u, v in zip(a, b):
        if u is None or v is None:
            continue
        xa.append(float(u))
        xb.append(float(v))
    return xa, xb


def wilcoxon_signed_rank(a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> Dict[str, Optional[float]]:
    """配对 Wilcoxon 符号秩检验（双侧）。"""
    xa, xb = _pairs(a, b)
    n = len(xa)
    if n == 0:
        return {"n": 0, "statistic": None, "p_value": None, "method": "wilcoxon"}
    diffs = [u - v for u, v in zip(xa, xb)]
    nonzero = [d for d in diffs if d != 0]
    if not nonzero:
        # 全部差值为 0：无法拒绝原假设
        return {"n": n, "statistic": 0.0, "p_value": 1.0, "method": "wilcoxon", "note": "all-zero-differences"}

    if has_module("scipy"):
        try:
            from scipy.stats import wilcoxon  # type: ignore

            res = wilcoxon(xa, xb, zero_method="wilcox", alternative="two-sided")
            return {"n": n, "statistic": float(res.statistic), "p_value": float(res.pvalue),
                    "method": "scipy.wilcoxon"}
        except Exception:  # noqa: BLE001 - 回退到内置实现
            pass

    # 内置实现（正态近似，含连续性校正与并列秩修正）
    abs_d = sorted((abs(d), i) for i, d in enumerate(diffs) if d != 0)
    ranks = _ranks([x[0] for x in abs_d])
    rank_map = {idx: r for (_, idx), r in zip(abs_d, ranks)}
    w_plus = sum(rank_map[i] for i, d in enumerate(diffs) if d > 0)
    w_minus = sum(rank_map[i] for i, d in enumerate(diffs) if d < 0)
    stat = min(w_plus, w_minus)
    m = len(nonzero)
    mu = m * (m + 1) / 4
    sigma = math.sqrt(m * (m + 1) * (2 * m + 1) / 24)
    if sigma == 0:
        return {"n": n, "statistic": stat, "p_value": 1.0, "method": "normal-approx"}
    z = (stat - mu + 0.5) / sigma
    p = 2 * (1 - _normal_cdf(abs(z)))
    return {"n": n, "statistic": stat, "p_value": min(1.0, max(0.0, p)), "method": "normal-approx"}


def _ranks(values: Sequence[float]) -> List[float]:
    """并列取平均秩。"""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def cliffs_delta(a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> Optional[float]:
    """Cliff's delta（a 相对 b 的优势度），范围 [-1, 1]。

    用秩和实现，复杂度 O(n log n)，避免 O(n^2) 的两两比较。
    """
    xa, xb = _pairs(a, b)
    if not xa or not xb:
        return None
    combined = [(v, 0) for v in xa] + [(v, 1) for v in xb]
    combined.sort(key=lambda t: t[0])
    ranks = _ranks([t[0] for t in combined])
    n_a, n_b = len(xa), len(xb)
    rank_sum_a = sum(r for r, (_, g) in zip(ranks, combined) if g == 0)
    # Mann-Whitney U
    u_a = rank_sum_a - n_a * (n_a + 1) / 2
    return (2 * u_a) / (n_a * n_b) - 1


def holm(p_values: Sequence[Optional[float]], alpha: float = ALPHA) -> List[Dict[str, Optional[float]]]:
    """Holm 逐步校正：返回 [{p_raw, p_adj, significant, rank}]，顺序与输入一致。"""
    indexed = [(i, float(p)) for i, p in enumerate(p_values) if p is not None]
    indexed.sort(key=lambda t: t[1])
    m = len(indexed)
    out: List[Dict[str, Optional[float]]] = [{"p_raw": p, "p_adj": None, "significant": None}
                                             for p in p_values]
    prev = 0.0
    still_rejecting = True
    for rank, (i, p) in enumerate(indexed, 1):
        adj = min(1.0, (m - rank + 1) * p)
        adj = max(adj, prev)  # 保证单调
        prev = adj
        sig = bool(still_rejecting and adj < alpha)
        if not sig:
            still_rejecting = False
        out[i] = {"p_raw": p, "p_adj": adj, "significant": sig, "rank": rank}
    return out


def compare_pair(name_a: str, name_b: str, metric: str,
                 a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> Dict[str, object]:
    """一次完整的组间比较：统计量 + 效应量 + 显著性。"""
    w = wilcoxon_signed_rank(a, b)
    d = cliffs_delta(a, b)
    return {
        "config_a": name_a, "config_b": name_b, "metric": metric,
        "n_pairs": w.get("n", 0),
        "statistic": w.get("statistic"),
        "p_value": w.get("p_value"),
        "method": w.get("method"),
        "cliffs_delta": d,
    }


def compare_family(comparisons: Sequence[Dict[str, object]], alpha: float = ALPHA) -> List[Dict[str, object]]:
    """对一组比较做 Holm 校正，补上 p_adj 与 significant 字段。"""
    adjs = holm([c.get("p_value") for c in comparisons], alpha=alpha)
    out = []
    for c, adj in zip(comparisons, adjs):
        row = dict(c)
        row["p_adj"] = adj.get("p_adj")
        row["significant"] = adj.get("significant")
        out.append(row)
    return out


def effect_size_label(delta: Optional[float]) -> str:
    """Cliff's delta 的惯例解释（Romano et al.）。"""
    if delta is None:
        return "not-yet-measured"
    a = abs(delta)
    if a < 0.147:
        return "negligible"
    if a < 0.33:
        return "small"
    if a < 0.474:
        return "medium"
    return "large"
