"""成本折算（R5 / 表5）。

云端：按输入、输出 token 单价分别计费（式 2）。
本地：电费 + 硬件折旧折算（式 1）。

关于式（1）的单位（**投稿前须与论文公式核对**）：
论文原文写作 ``C_local = P_avg·T/3 600·p_e + C_hw·T/(T_life·D)``。
本实现按量纲一致的方式解释并落参：

- ``P_avg`` 平均整机功耗（W），``T`` 推理耗时（**小时**）；
- 电费项 = ``P_avg/1000 × T × p_e``（kWh × 元/kWh）；
- 折旧项 = ``C_hw × T / (T_life × 365 × 24 × D)``
  （设备有效寿命内的可用小时数 = T_life×365×24×D）。

所有参数取自 ``configs/pricing.yaml``，**未填写即返回 None**，
对应表格保留 not-yet-measured，不用 TDP 或行业均值顶替。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from experiments import config_loader
from experiments.common import read_json, utc_now_iso, write_json
from experiments.logging_utils import get_logger
from experiments.paths import AGGREGATE, REPORTS_DIR

logger = get_logger("exp.cost")

# 5.3 节敏感性分析的归档产物：正文里引用的敏感区间必须能被反查
SENSITIVITY_PATH = REPORTS_DIR / "cost_sensitivity.json"


def _cfg_group(config_id: str) -> Dict[str, Any]:
    """从 experiment.yaml 取配置定义（后端/供应商/档位）。"""
    try:
        exp = config_loader.experiment_config()
    except Exception:  # noqa: BLE001
        return {}
    for c in list(exp.get("configs", [])) + list(exp.get("sensitivity", []) or []):
        if str(c.get("id")) == config_id:
            return c
    return {}


def cloud_cost(tokens_in: Optional[float], tokens_out: Optional[float],
               provider: str = "qwen", tier: str = "flagship") -> Optional[float]:
    """云端单次成本（元）。单价缺失返回 None。"""
    if tokens_in is None and tokens_out is None:
        return None
    try:
        pricing = config_loader.pricing_config()
    except Exception:  # noqa: BLE001
        return None
    block = ((pricing.get("cloud") or {}).get(provider) or {}).get(tier) or {}
    p_in = block.get("input_per_1m_tokens")
    p_out = block.get("output_per_1m_tokens")
    if p_in is None or p_out is None:
        logger.warning("云端单价未填写（%s/%s），成本保留占位", provider, tier)
        return None
    tin = float(tokens_in or 0)
    tout = float(tokens_out or 0)
    return (tin * float(p_in) + tout * float(p_out)) / 1_000_000.0


def local_cost(latency_s: Optional[float]) -> Optional[float]:
    """本地单次折算成本（元）。参数缺失或耗时缺失返回 None。"""
    if latency_s is None:
        return None
    try:
        pricing = config_loader.pricing_config()
    except Exception:  # noqa: BLE001
        return None
    loc = pricing.get("local") or {}
    need = ["P_avg_watt", "p_e_yuan_per_kwh", "C_hw_yuan", "T_life_years", "D_utilization"]
    if any(loc.get(k) is None for k in need):
        logger.warning("本地折算参数未填写完整，成本保留占位")
        return None
    hours = float(latency_s) / 3600.0
    energy = float(loc["P_avg_watt"]) / 1000.0 * hours * float(loc["p_e_yuan_per_kwh"])
    life_hours = float(loc["T_life_years"]) * 365 * 24 * float(loc["D_utilization"])
    deprec = float(loc["C_hw_yuan"]) * hours / life_hours if life_hours else 0.0
    return energy + deprec


def per_item_cost(config_id: str, tokens_in: Optional[float], tokens_out: Optional[float],
                  latency_s: Optional[float]) -> Optional[float]:
    """按配置分派到云端或本地成本模型。"""
    cfg = _cfg_group(config_id)
    backend = str(cfg.get("backend") or "")
    if backend == "openai_compatible":
        return cloud_cost(tokens_in, tokens_out, str(cfg.get("provider", "qwen")),
                          str(cfg.get("tier", "flagship")))
    if backend == "ollama":
        return local_cost(latency_s)
    # 基线无推理成本（仍可计其运行的电费，但论文口径里基线不参与成本对比）
    return None


def sensitivity(latency_s: float = 10.0, tokens_in: float = 2000.0,
                tokens_out: float = 500.0) -> Dict[str, Any]:
    """本地折算的敏感性分析（5.3 节用）：每个参数取低/高值看成本区间。"""
    try:
        pricing = config_loader.pricing_config()
    except Exception:  # noqa: BLE001
        return {"available": False}
    loc = dict(pricing.get("local") or {})
    sens = dict(pricing.get("sensitivity") or {})
    base = local_cost(latency_s)
    rows = []
    for key, bounds in sens.items():
        if not isinstance(bounds, list) or len(bounds) != 2 or any(b is None for b in bounds):
            continue
        lows, highs = [], []
        for val in bounds:
            trial = dict(loc)
            trial[key] = val
            # 直接按单参数变动重算
            hours = float(latency_s) / 3600.0
            energy = float(trial.get("P_avg_watt") or 0) / 1000.0 * hours * float(trial.get("p_e_yuan_per_kwh") or 0)
            life_hours = float(trial.get("T_life_years") or 0) * 365 * 24 * float(trial.get("D_utilization") or 0)
            deprec = float(trial.get("C_hw_yuan") or 0) * hours / life_hours if life_hours else 0.0
            (lows if val == bounds[0] else highs).append(energy + deprec)
        rows.append({"param": key, "low": bounds[0], "high": bounds[1],
                     "cost_low": lows[-1] if lows else None, "cost_high": highs[-1] if highs else None})
    return {"available": base is not None, "base_cost": base,
            "cloud_cost": cloud_cost(tokens_in, tokens_out), "rows": rows}


def local_mean_latency() -> Optional[float]:
    """取本地组实测的平均单条耗时（敏感性分析的自变量）。"""
    if not AGGREGATE.exists():
        return None
    agg = read_json(AGGREGATE) or {}
    for cfg, v in (agg.get("configs") or {}).items():
        if (agg.get("groups") or {}).get(cfg) == "local":
            lat = (v or {}).get("latency_mean") or (v or {}).get("latency_p50")
            if lat:
                return float(lat)
    return None


# ------------------------------------------------------------------ 输入侧区间
TOKEN_RECOUNT_PATH = REPORTS_DIR / "token_recount.json"


def cross_call_ratios() -> Dict[str, Any]:
    """``token-calib`` 的历史**跨调用**观测：重算值 vs 云调用 API usage 的比值。

    比值 < 1 表示重算值（借用本地同一样本 ``prompt_eval_count`` 的**合计**）高于
    那次云调用的真实输入。该差异来自**调用次数口径差**（本地含简化 prompt 重试、
    云端常为单次），不是计数误差——同调用实测：云端输入 ≤0.383%、输出 0.000%，
    本地 ≤0.751%。因此该比值只用于**为输入侧定界**。
    """
    if not TOKEN_RECOUNT_PATH.exists():
        return {"available": False, "reason": "缺少 reports/token_recount.json"}
    calib = (read_json(TOKEN_RECOUNT_PATH) or {}).get("calibration_cross_call") or {}
    obs, ratios = [], []
    for cid, v in (calib.get("configs") or {}).items():
        for r in (v or {}).get("rows") or []:
            api, rec = r.get("api_tokens_in"), r.get("recount_tokens_in")
            if api and rec:
                ratio = round(float(api) / float(rec), 4)
                ratios.append(ratio)
                obs.append({"config": cid, "sample_id": r.get("sample_id"),
                            "api_tokens_in": api, "recount_tokens_in": rec, "ratio": ratio})
    if not ratios:
        return {"available": False, "reason": "跨调用观测为空（token_recount.json 无 calibration_cross_call）"}
    return {"available": True, "min": min(ratios), "max": max(ratios),
            "n_observations": len(ratios),
            "n_samples": len({o["sample_id"] for o in obs}),
            "observations": obs}


def input_token_band() -> Dict[str, Any]:
    """云端**输入** token 计费的实测区间（表5 表注与 5.3 节引用；禁止手算）。

    输入侧只有两种来源：新记录用该次请求自己的提示词留痕（可信）；旧记录回退
    跨调用代理值——而代理值**口径不可比**：它是本地那条记录内**各次调用之和**
    （本地小模型常触发简化 prompt 重试），云端那一次则常为单次。代理值与
    同一样本另一次云调用的 API usage 之比实测为 ``[min, max]``，故代理值只能
    定界、不能再现真值——于是把云端输入计费与单次成本都给出区间，并断言区间内
    "本地是否更便宜"这一结论的方向。计数方法本身的误差不在此区间内：同调用
    实测为云端输入 ≤0.383%、输出 0.000%、本地 ≤0.751%。
    """
    ratios = cross_call_ratios()
    if not ratios.get("available"):
        return {"available": False, "reason": ratios.get("reason")}
    if not AGGREGATE.exists():
        return {"available": False, "reason": "缺少 reports/aggregate.json"}
    agg = read_json(AGGREGATE) or {}
    groups = agg.get("groups") or {}
    local = next(((v or {}).get("cost_per_item_mean")
                  for c, v in (agg.get("configs") or {}).items()
                  if groups.get(c) == "local" and (v or {}).get("cost_per_item_mean")), None)
    r_min, r_max = float(ratios["min"]), float(ratios["max"])
    configs: Dict[str, Any] = {}
    for cid, v in (agg.get("configs") or {}).items():
        if groups.get(cid) != "cloud":
            continue
        cin, cout = (v or {}).get("cost_token_in"), (v or {}).get("cost_token_out")
        if cin is None or cout is None:
            continue
        low, high = cin * r_min + cout, cin * r_max + cout
        entry: Dict[str, Any] = {
            "cost_token_in_point": round(cin, 6),
            "cost_token_in_range": [round(cin * r_min, 6), round(cin * r_max, 6)],
            "cost_per_item_point": (round(v["cost_per_item_mean"], 6)
                                    if v.get("cost_per_item_mean") else None),
            "cost_per_item_range": [round(low, 6), round(high, 6)],
        }
        if local:
            entry["local_cost_per_item"] = round(float(local), 6)
            entry["local_vs_cloud_pct_range"] = [
                round((float(local) - high) / high * 100, 2),
                round((float(local) - low) / low * 100, 2),
            ]
            # 论文结论"本地单次折算成本不低于云端"在该区间内是否始终成立
            entry["local_higher_throughout"] = bool(float(local) > high)
        configs[cid] = entry
    return {
        "available": bool(configs),
        "basis": ("token-calib 的跨调用观测：同一样本的「重算值（本地 prompt_eval_count 合计"
                  "的中位数）」与「另一次云调用的 API usage（单次）」之比"),
        "ratio_range": [r_min, r_max],
        "n_observations": ratios["n_observations"],
        "n_samples": ratios["n_samples"],
        "confound": ("口径不可比：本地记录的 tokens_in 是**一条样本内各次调用之和**"
                     "（本地小模型常因输出板块不足而改用简化 prompt 重试，一条发 2 次请求），"
                     "而云端那些调用均为单次（同调用校准 6/6 次 calls=1）。实测复算 "
                     "1820+559=2379 对旧记录 2397 只差 0.751%，即该差异源于调用次数而非"
                     "计数方法；次要成分是提示词自身长度亦会变化（proxy_spread）。"
                     "区间只界定**输入**侧：输出侧计数与 API 实测完全一致（0.000%），"
                     "云端输入侧同调用偏差 ≤0.383%"),
        "observations": ratios["observations"],
        "local_cost_per_item": round(float(local), 6) if local else None,
        "configs": configs,
    }


def sensitivity_report(latency_s: Optional[float] = None) -> Dict[str, Any]:
    """计算并**归档**敏感性分析，供正文引用与 verify 反查。

    正文 5.3 节引用的敏感区间（如硬件成本 5 000→12 000 元对应的成本区间）
    必须能从产物中反查，因此这里显式落盘。
    """
    if latency_s is None:
        latency_s = local_mean_latency() or 10.0
    data = sensitivity(latency_s=float(latency_s))
    data.update({"latency_s": float(latency_s), "generated_at": utc_now_iso(),
                 "source": "configs/pricing.yaml 的 local 与 sensitivity 段",
                 # 表5 表注引用的输入侧区间（同源产物，禁止在稿件里手算）
                 "input_token_band": input_token_band()})
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(SENSITIVITY_PATH, data)
    return data
