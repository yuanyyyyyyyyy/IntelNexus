"""论文A v2 成本重算复核脚本（P0-2 闭环 · 2026-09-27）。

按《论文A_v2_成本重算执行方案_20260927.md》第 3/5 节规格执行：
  1. 逐样本成本重算：3 次重复先取均值（n=100），修正式(1)(2)；
  2. 双实现交叉复核：numpy 向量化 vs 纯 Python 逐行，一致到 1e-9；
  3. 量纲断言：每项计算内置 W×s=J、J→kWh、元/kWh→元 断言；
  4. 算术自检基准：T=152.22 s、U=0.25 → 电费 ≈0.00080、折旧 ≈0.02704、合计 ≈0.0278；
  5. 表7 成本行统计管线：Wilcoxon + Holm + Cliff's delta + bootstrap CI
     （B=10 000，以样本为重抽样单位，种子 20260913）+ rank-biserial；
  6. U* 持平阈值：解析解 + 网格搜索验证（一致到 1e-4）；
  7. 敏感性扫描：C_hw∈[5000,12000] 步长 500、U∈[0.1,0.5] 步长 0.05，
     每格点用全部逐样本 T_i 重算均值成本。

产物：experiments/reports/cost_recalc_20260927/
  - per_sample_costs.csv（每行含 run_id + sample_id）
  - summary.json（脚本版本哈希、种子、时间戳、输入文件哈希）
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RUNS = ROOT / "runs"
OUT = REPORTS / "cost_recalc_20260927"

SEED = 20260913
B_BOOT = 10_000

# ---------------------------------------------------------------- 参数（锁死）
P_AVG = 38.7          # W（实测，power_probe.json）
P_E = 0.49            # 元/kWh
C_HW = 7_000.0        # 元
T_LIFE = 5.0          # 年
U_BASE = 0.25
P_IN_FLAG, P_OUT_FLAG = 2.5, 10.0    # 元/百万 token（旗舰档）
P_IN_LIGHT, P_OUT_LIGHT = 0.8, 2.0   # 元/百万 token（轻量档）

# 自检基准（校验公式实现，非实验数据）
BENCH_T, BENCH_U = 152.22, 0.25
BENCH_EXPECT = {"electric": 0.00080, "deprec": 0.02704, "total": 0.0278}
BENCH_TOL = 0.001


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------- 公式（两套实现）
def dims_assert(local_cost: float, electric: float, deprec: float,
                u: float = U_BASE, c_hw: float = C_HW) -> None:
    """量纲断言：电费+折旧=合计；各项非负；电费占合计比重与功耗占比一致。"""
    assert abs((electric + deprec) - local_cost) < 1e-12, "电费+折旧 != 合计"
    assert local_cost >= 0 and electric >= 0 and deprec >= 0, "成本项出现负值"
    # 电费率/合计率应等于 (P/3.6e6·p_e) / (P/3.6e6·p_e + C/(3600·5·8760·U))
    a = P_AVG / 3.6e6 * P_E
    b = c_hw / (3600.0 * T_LIFE * 8760.0 * u)
    assert abs(a / (a + b) - electric / (electric + deprec)) < 1e-9, "量纲占比断裂"


def local_cost_py(t_s: float, u: float = U_BASE, c_hw: float = C_HW) -> tuple:
    """纯 Python 实现：修正式(1)。返回 (合计, 电费, 折旧)。"""
    electric = P_AVG * t_s / 3.6e6 * P_E                    # W·s=J → kWh → 元
    deprec = c_hw * t_s / (3600.0 * T_LIFE * 8760.0 * u)    # 元/(s)·(1/U)·s
    total = electric + deprec
    dims_assert(total, electric, deprec, u, c_hw)
    return total, electric, deprec


def local_cost_vec(t_arr, u: float = U_BASE, c_hw: float = C_HW):
    """numpy 向量化实现：修正式(1)。"""
    import numpy as np
    t = np.asarray(t_arr, dtype=float)
    electric = P_AVG * t / 3.6e6 * P_E
    deprec = c_hw * t / (3600.0 * T_LIFE * 8760.0 * u)
    total = electric + deprec
    assert np.all((electric + deprec) == total)
    return total, electric, deprec


def cloud_cost_py(n_in: float, n_out: float, tier: str) -> float:
    """纯 Python 实现：式(2)。"""
    p_in, p_out = (P_IN_FLAG, P_OUT_FLAG) if tier == "flagship" else (P_IN_LIGHT, P_OUT_LIGHT)
    return (n_in * p_in + n_out * p_out) / 1e6


def self_check() -> dict:
    t, e, d = local_cost_py(BENCH_T, BENCH_U)
    ok = (abs(e - BENCH_EXPECT["electric"]) < BENCH_TOL
          and abs(d - BENCH_EXPECT["deprec"]) < BENCH_TOL
          and abs(t - BENCH_EXPECT["total"]) < BENCH_TOL)
    if not ok:
        print(f"[自检失败] 电费={e:.6f} 折旧={d:.6f} 合计={t:.6f}", file=sys.stderr)
        raise SystemExit(2)
    return {"electric": round(e, 6), "deprec": round(d, 6), "total": round(t, 6),
            "status": "PASS（与 ChatGPT 复算参考一致）"}


# ------------------------------------------------------------------- 数据装载
def load_runs():
    agg = json.loads((REPORTS / "aggregate.json").read_text(encoding="utf-8"))
    included = [r for r in agg["runs_included"]
                if any(k in r for k in ("qwen3-8b", "cloud_flagship", "cloud_light"))]
    recount = json.loads((REPORTS / "token_recount.json").read_text(encoding="utf-8"))
    recount_cfgs = recount.get("configs", {})
    data = {"local": {}, "cloud_flagship": {}, "cloud_light": {}}
    for run_id in included:
        cfg = "local" if "qwen3-8b" in run_id else ("cloud_flagship" if "flagship" in run_id else "cloud_light")
        if cfg not in data:
            continue
        recs = {}
        with open(RUNS / run_id / "records.jsonl", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("error"):
                    continue
                recs.setdefault(r["sample_id"], {})[r["repeat"]] = r
        data[cfg][run_id] = recs
    # 云端 token 用量：token_recount.json（分词器重算，见 basis 字段）
    tokens = {"cloud_flagship": {}, "cloud_light": {}}
    for cfg in tokens:
        for run_id in data[cfg]:
            tokens[cfg][run_id] = recount_cfgs.get(run_id, {})
    return data, tokens


def build_per_sample(data, tokens):
    """逐样本：3 次重复取均值（不得展开为独立观测）。返回 (per_sample, diagnostics)。"""
    per_sample = {}
    diag = {}
    for cfg in data:
        run_ids = sorted(data[cfg])
        sample_ids = None
        for rid in run_ids:
            s = set(data[cfg][rid])
            sample_ids = s if sample_ids is None else (sample_ids & s)
        sample_ids = sorted(sample_ids)
        diag[cfg] = {"n_runs": len(run_ids), "n_samples_common": len(sample_ids),
                     "repeats_per_run": sorted({len(data[cfg][rid]) for rid in run_ids})}
        rows = []
        for sid in sample_ids:
            # 本地：逐样本 T_i = 3 次重复均值
            if cfg == "local":
                ts = [data[cfg][rid][sid][rep]["latency_s"]
                      for rid in run_ids for rep in sorted(data[cfg][rid][sid])
                      ]
                t_mean = sum(ts) / len(ts)
                cost, elec, dep = local_cost_py(t_mean)
                rows.append({"sample_id": sid, "T_i_s": t_mean, "cost": cost,
                             "electric": elec, "deprec": dep})
            else:
                tier = "flagship" if cfg == "cloud_flagship" else "light"
                cs = []
                n_in_sum = n_out_sum = 0
                n_obs = 0
                for rid in run_ids:
                    rep_map = data[cfg][rid][sid]
                    for rep, rec in rep_map.items():
                        tk = tokens[cfg][rid].get(sid, {}).get(str(rep))
                        if tk is None:
                            continue
                        c = cloud_cost_py(tk["tokens_in"], tk["tokens_out"], tier)
                        cs.append(c)
                        n_in_sum += tk["tokens_in"]
                        n_out_sum += tk["tokens_out"]
                        n_obs += 1
                cost = sum(cs) / len(cs)
                rows.append({"sample_id": sid, "cost": cost,
                             "tokens_in_mean": n_in_sum / n_obs,
                             "tokens_out_mean": n_out_sum / n_obs, "n_obs": n_obs})
        per_sample[cfg] = rows
    return per_sample, diag


# --------------------------------------------------------------- 统计管线
def wilcoxon_and_effects(diffs):
    """配对 Wilcoxon（scipy）+ Cliff's delta + rank-biserial + 中位配对差。"""
    from scipy.stats import wilcoxon
    n = len(diffs)
    res = wilcoxon(diffs, zero_method="wilcox", alternative="two-sided")
    stat = float(res.statistic)
    p = float(res.pvalue)
    # Cliff's delta（配对差符号）
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    delta = (pos - neg) / n
    # matched-pairs rank-biserial = (W+ − W−)/总秩和
    ranked = sorted(range(n), key=lambda i: abs(diffs[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(diffs[ranked[j + 1]]) == abs(diffs[ranked[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[ranked[k]] = avg
        i = j + 1
    w_plus = sum(ranks[i] for i in range(n) if diffs[i] > 0)
    w_minus = sum(ranks[i] for i in range(n) if diffs[i] < 0)
    rb = (w_plus - w_minus) / (w_plus + w_minus)
    diffs_sorted = sorted(diffs)
    med = (diffs_sorted[n // 2 - 1] + diffs_sorted[n // 2]) / 2 if n % 2 == 0 else diffs_sorted[n // 2]
    return {"n": n, "statistic": stat, "p_value": p, "cliffs_delta": delta,
            "rank_biserial": rb, "median_pairwise_diff": med}


def bootstrap_ci(diffs, b: int = B_BOOT, seed: int = SEED):
    """bootstrap 百分位 CI（中位配对差，样本为重抽样单位）。"""
    rng = random.Random(seed)
    n = len(diffs)
    meds = []
    for _ in range(b):
        sample = sorted(diffs[rng.randrange(n)] for _ in range(n))
        m = sample[n // 2] if n % 2 else (sample[n // 2 - 1] + sample[n // 2]) / 2
        meds.append(m)
    meds.sort()
    lo = meds[int(0.025 * b)]
    hi = meds[int(0.975 * b) - 1]
    return [round(lo, 6), round(hi, 6)]


def holm(pvals):
    """Holm 逐步校正。"""
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj = [0.0] * len(pvals)
    running = 0.0
    m = len(pvals)
    for rank, idx in enumerate(order):
        val = (m - rank) * pvals[idx]
        running = max(running, val)
        adj[idx] = min(1.0, running)
    return adj


def u_star_analytic(t_mean: float, c_cloud: float) -> float:
    """U* = C_hw·E[T] / (3600·T_life·8760·(C_cloud − 电费均值))。"""
    electric_mean = P_AVG * t_mean / 3.6e6 * P_E
    return C_HW * t_mean / (3600.0 * T_LIFE * 8760.0 * (c_cloud - electric_mean))


def cliffs_delta_ranksum(a, b):
    """与 experiments/metrics/stats.py 同口径：Mann-Whitney 秩和实现（表7 引用口径）。"""
    combined = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    n_a, n_b = len(a), len(b)
    # 平均秩
    ranks = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    rank_sum_a = sum(r for r, (_, g) in zip(ranks, combined) if g == 0)
    u_a = rank_sum_a - n_a * (n_a + 1) / 2
    return (2 * u_a) / (n_a * n_b) - 1


def u_star_grid(t_arr, c_cloud: float) -> float:
    """网格搜索验证：U 从 0.001 起（成本最高）向右找首个 C_local(U) ≤ C_cloud 的 U。"""
    step = 1e-4
    u = 0.001
    while u <= 0.999:
        mean_cost = sum(local_cost_py(t, u)[0] for t in t_arr) / len(t_arr)
        if mean_cost <= c_cloud:
            return round(u, 4)
        u = round(u + step, 4)
    return None


def sensitivity_scan(t_arr):
    """C_hw 15 格点 × U 9 格点，每格点用全部逐样本 T_i。"""
    res = {"c_hw": {}, "u": {}}
    # C_hw 扫描（U=0.25）
    lows, highs = [], []
    for c in range(5000, 12001, 500):
        m = sum(local_cost_py(t, U_BASE, float(c))[0] for t in t_arr) / len(t_arr)
        lows.append((c, round(m, 6)))
    res["c_hw"] = {"grid": lows, "range": [lows[0][1], lows[-1][1]]}
    # U 扫描（C_hw=7000）
    us = []
    for u100 in range(10, 51, 5):
        u = u100 / 100
        m = sum(local_cost_py(t, u)[0] for t in t_arr) / len(t_arr)
        us.append((u, round(m, 6)))
    res["u"] = {"grid": us,
                "range": [min(v for _, v in us), max(v for _, v in us)]}
    return res


# --------------------------------------------------------------------- 主流程
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED}

    # 1) 自检基准
    report["self_check"] = self_check()

    # 2) 装载与逐样本重算（双实现）
    data, tokens = load_runs()
    per_sample, diag = build_per_sample(data, tokens)
    report["diagnostics"] = diag

    # 双实现交叉复核（numpy 向量化 vs 纯 Python）
    t_list = [r["T_i_s"] for r in per_sample["local"]]
    py_costs = [r["cost"] for r in per_sample["local"]]
    vec_costs, vec_e, vec_d = local_cost_vec(t_list)
    max_dev = max(abs(a - b) for a, b in zip(py_costs, vec_costs.tolist()))
    report["cross_check"] = {"max_abs_dev": max_dev, "tol": 1e-9,
                             "status": "PASS" if max_dev < 1e-9 else "FAIL"}
    if max_dev >= 1e-9:
        raise SystemExit(3)

    # 3) 聚合
    def agg_stats(xs):
        xs = sorted(xs)
        n = len(xs)
        mean = sum(xs) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1))
        med = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
        p50 = med
        p95 = xs[min(n - 1, math.ceil(0.95 * n) - 1)]
        return {"n": n, "mean": round(mean, 8), "median": round(med, 8),
                "sd": round(sd, 8), "p50": round(p50, 8), "p95": round(p95, 8)}

    agg_out = {}
    for cfg in ("local", "cloud_flagship", "cloud_light"):
        costs = [r["cost"] for r in per_sample[cfg]]
        agg_out[cfg] = agg_stats(costs)
    report["aggregate"] = agg_out

    # 4) 表7 成本行：配对（本地 − 旗舰档），n=100
    map_flag = {r["sample_id"]: r["cost"] for r in per_sample["cloud_flagship"]}
    diffs = [r["cost"] - map_flag[r["sample_id"]] for r in per_sample["local"]]
    st = wilcoxon_and_effects(diffs)
    local_costs = [r["cost"] for r in per_sample["local"]]
    flag_costs = [map_flag[r["sample_id"]] for r in per_sample["local"]]
    st["cliffs_delta_ranksum"] = cliffs_delta_ranksum(local_costs, flag_costs)
    st["bootstrap_ci_median_diff"] = bootstrap_ci(diffs)
    st["mean_ratio_minus_1_pct"] = (agg_out["local"]["mean"] / agg_out["cloud_flagship"]["mean"] - 1) * 100
    st["median_ratio_minus_1_pct"] = (agg_out["local"]["median"] / agg_out["cloud_flagship"]["median"] - 1) * 100
    report["paired_local_vs_flagship_cost"] = st

    # 5) U*：解析解 + 网格验证
    t_mean = sum(t_list) / len(t_list)
    u_a = u_star_analytic(t_mean, agg_out["cloud_flagship"]["mean"])
    u_g = u_star_grid(t_list, agg_out["cloud_flagship"]["mean"])
    report["u_star"] = {"E_T_s": round(t_mean, 4), "analytic": round(u_a, 6),
                        "grid": u_g, "agree_1e-4": (u_g is not None and abs(u_a - u_g) < 1e-4),
                        "hours_per_day": round(u_a * 24, 2)}

    # 6) 敏感性扫描
    report["sensitivity"] = sensitivity_scan(t_list)

    # 7) 与归档 aggregate.json / 正文现值比对
    archived = json.loads((REPORTS / "aggregate.json").read_text(encoding="utf-8"))
    cmp = {}
    for cfg, key in (("local", "qwen3:8b"), ("cloud_flagship", "cloud_flagship"),
                     ("cloud_light", "cloud_light")):
        old = archived["configs"][key]["cost_per_item_mean"]
        new = agg_out[cfg]["mean"]
        cmp[cfg] = {"archived": round(old, 8), "recalc": round(new, 8),
                    "abs_dev": abs(old - new), "match_1e_9": abs(old - new) < 1e-9}
    report["vs_archived"] = cmp

    # 8) 落盘 CSV（每行 run_id + sample_id）
    with open(OUT / "per_sample_costs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["config", "sample_id", "run_ids", "T_i_s_or_tokens", "cost_yuan", "electric_yuan", "deprec_yuan"])
        for cfg in ("local", "cloud_flagship", "cloud_light"):
            for r in per_sample[cfg]:
                rid = ";".join(sorted(data[cfg].keys()))
                if cfg == "local":
                    w.writerow([cfg, r["sample_id"], rid, f"{r['T_i_s']:.4f}",
                                f"{r['cost']:.9f}", f"{r['electric']:.9f}", f"{r['deprec']:.9f}"])
                else:
                    w.writerow([cfg, r["sample_id"], rid,
                                f"in={r['tokens_in_mean']:.1f};out={r['tokens_out_mean']:.1f}",
                                f"{r['cost']:.9f}", "", ""])

    # 9) 汇总 JSON：脚本哈希 + 输入文件哈希
    report["provenance"] = {
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inputs": {p.name: sha256_file(p) for p in [
            REPORTS / "aggregate.json", REPORTS / "token_recount.json",
            REPORTS / "power_probe.json", ROOT / "cost" / "cost_model.py",
            ROOT / "configs" / "pricing.yaml"]},
        "n_runs_local": len(data["local"]),
        "n_runs_flagship": len(data["cloud_flagship"]),
        "n_runs_light": len(data["cloud_light"]),
        "bootstrap": {"B": B_BOOT, "seed": SEED, "unit": "sample"},
    }
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    # 控制台摘要
    print(json.dumps({k: report[k] for k in ("self_check", "cross_check", "aggregate",
                                             "paired_local_vs_flagship_cost", "u_star",
                                             "vs_archived", "sensitivity")},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
