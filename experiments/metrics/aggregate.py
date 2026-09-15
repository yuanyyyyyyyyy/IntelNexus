"""汇总：原始记录 + 指标 → aggregate.json（回填的唯一事实源）。

禁止手填：回填脚本只读本文件。任何一格没有实测支撑，这里就是 null，
回填时保留 not-yet-measured。

配对口径：同一 (sample_id, repeat) 在不同配置下的取值构成一对；
出域字节数以"每次重复的总量"配对（n = 重复次数）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from experiments.common import (
    PLACEHOLDER,
    mean,
    percentile,
    percentile as _pct,
    read_json,
    stdev,
    utc_now_iso,
    write_json,
)
from experiments.logging_utils import get_logger
from experiments.metrics import entity_f1, rouge, stats
from experiments.paths import REPORTS_DIR, RUNS_DIR

logger = get_logger("exp.aggregate")

METRICS_LONG = REPORTS_DIR / "metrics_long.jsonl"
AGGREGATE = REPORTS_DIR / "aggregate.json"

# 论文主指标：实体 F1（CVE/GHSA、版本、产品名、攻击类型，与语言无关）。
# 生成物为中文、参考摘要多为英文，ROUGE-L 绝对值偏低且区分度差，仅作辅助指标。
PRIMARY_METRIC = "entity_f1"

# 表7 需要的比较对：(角色A, 角色B, 指标)
COMPARISON_SPEC = [
    ("best_local", "cloud_flagship", "rouge_l"),
    ("best_local", "cloud_flagship", "entity_f1"),
    ("best_local", "cloud_flagship", "human"),
    ("best_local", "cloud_flagship", "latency_p95"),
    ("best_local", "cloud_flagship", "cost_per_item"),
    ("best_local", "cloud_flagship", "egress_bytes"),
    ("cloud_flagship", "cloud_light", "human"),
    ("best_llm", "best_baseline", "human"),
]


def _discover_runs(stage: Optional[str] = None, configs: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    from experiments import config_loader

    # 被排除的配置不进入汇总/图表/回填（原因见 PROTOCOL 偏差记录）。
    # 显式用 --configs 指定时不再排除，便于对被撤配置做独立核查。
    excluded = {} if configs else config_loader.excluded_configs()
    runs = []
    for manifest in sorted(RUNS_DIR.glob("*/manifest.json")):
        try:
            m = read_json(manifest)
        except Exception:  # noqa: BLE001
            continue
        if stage and m.get("stage") != stage:
            continue
        if str(m.get("config")) in excluded:
            continue
        if configs and m.get("config") not in configs:
            continue
        records = []
        rec_path = manifest.parent / "records.jsonl"
        if rec_path.exists():
            with open(rec_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        m["_records"] = records
        m["_dir"] = str(manifest.parent)
        runs.append(m)
    return runs


def _load_references() -> Dict[str, Dict[str, str]]:
    from experiments.collect.snapshot import load

    snap = load()
    return {str(i.get("id")): {"summary": i.get("official_summary", ""), "content": i.get("content", "")}
            for i in snap.items}


def _head_section(text: str) -> str:
    """取生成简报的首个板块（到第二个 ## 标题为止），用于口径敏感性检验。"""
    if not text:
        return ""
    parts = text.split("\n## ")
    return parts[0] if len(parts) == 1 else "## " + parts[1]


def compute_metrics(runs: List[Dict[str, Any]], use_bertscore: bool = True,
                    gold_csv: Optional[Path] = None) -> List[Dict[str, Any]]:
    """逐条计算质量指标，写入 metrics_long.jsonl。"""
    refs = _load_references()
    gold = entity_f1.load_gold_csv(gold_csv) if gold_csv and Path(gold_csv).exists() else {}

    pairs: List[Dict[str, Any]] = []
    for m in runs:
        rdir = Path(m["_dir"])
        for r in m["_records"]:
            out_rel = r.get("output_path")
            text = ""
            if out_rel:
                p = rdir / out_rel
                if p.exists():
                    text = p.read_text(encoding="utf-8")
            ref = refs.get(str(r.get("sample_id")), {}).get("summary", "")
            pairs.append({"run_id": r.get("run_id"), "config": r.get("config"),
                          "repeat": r.get("repeat"), "sample_id": r.get("sample_id"),
                          "text": text, "reference": ref, "record": r})

    logger.info("计算 ROUGE-L（%d 条）", len(pairs))
    for p in pairs:
        if p["record"].get("error"):
            # 失败条目不参与任何质量指标（文本为空，硬算只会得到无意义的 0）
            p["rouge_l"] = None
            p["rouge_l_head"] = None
            p["entity_f1"] = None
            p["entity_f1_ref"] = None
            p["bertscore"] = None
            p["bertscore_head"] = None
            continue
        p["rouge_l"] = rouge.rouge_l(p["text"], p["reference"])
        # 生成物是完整简报；另按"首个板块"（TL;DR/核心摘要）算一版，
        # 供 6.4 节检验"评测口径是否影响结论"
        p["rouge_l_head"] = rouge.rouge_l(_head_section(p["text"]), p["reference"])
        # 实体 F1 为论文主指标（与语言无关）。
        # 主口径 gold = 参考摘要 ∪ 输入正文；ref_only 为敏感性口径。
        ref_item = refs.get(str(p["sample_id"]), {})
        manual = gold.get(str(p["sample_id"]))
        if manual:
            g_union = g_ref = manual
        else:
            g_union = entity_f1.build_gold({"official_summary": p["reference"],
                                            "content": ref_item.get("content", "")}, "union")
            g_ref = entity_f1.build_gold({"official_summary": p["reference"]}, "ref_only")
        ents = entity_f1.extract_entities(p["text"])
        prf_u = entity_f1.prf(ents, g_union)
        prf_r = entity_f1.prf(ents, g_ref)
        p["entity_f1"] = prf_u["f1"] if prf_u else None
        p["entity_f1_ref"] = prf_r["f1"] if prf_r else None
        p["bertscore"] = None
        p["bertscore_head"] = None

    valid_pairs = [p for p in pairs if not p["record"].get("error")]
    if use_bertscore and valid_pairs:
        try:
            from experiments.metrics import bertscore, bertscore_cache

            info = bertscore.available()
            if info.get("ready"):
                cfg = bertscore.config()
                base = str(cfg["model"])
                # 缓存键用"基座名 + idf 开关 + 权重指纹"，避免换基座/改口径后静默复用旧分数
                model = bertscore.cache_model_id()
                # 分块送算：1800 条在 CPU 上要几十分钟，分块既有进度也能中断续算
                chunk = max(1, int(cfg.get("batch_size") or 16) * 16)
                for key, texts in (
                    ("bertscore", [p["text"] for p in valid_pairs]),
                    # 首板块口径：模型按 512 token 截断长简报，用首板块做稳健性对照
                    ("bertscore_head", [_head_section(p["text"]) for p in valid_pairs]),
                ):
                    logger.info("计算 %s（%d 条，基座 %s，idf=%s，截断 %s token）",
                                key, len(valid_pairs), base, cfg["idf"], cfg["max_length"])
                    vals, stats = bertscore_cache.score_with_cache(
                        texts, [p["reference"] for p in valid_pairs], model,
                        lambda c, r: bertscore.score(c, r),
                        bertscore.cache_path(), chunk_size=chunk)
                    logger.info("  %s：缓存命中 %d，新算 %d", key, stats["hit"], stats["computed"])
                    for p, v in zip(valid_pairs, vals):
                        p[key] = v
            else:
                logger.warning("BERTScore 不可用：%s", info.get("hint"))
        except Exception as e:  # noqa: BLE001
            logger.warning("BERTScore 跳过: %s", e)

    with open(METRICS_LONG, "w", encoding="utf-8") as f:
        for p in pairs:
            rec = dict(p["record"])
            rec.update({k: p.get(k) for k in ("rouge_l", "rouge_l_head", "entity_f1",
                                              "entity_f1_ref", "bertscore", "bertscore_head")})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("已写入 %s", METRICS_LONG)
    return pairs


def _cfg_meta(config_id: str) -> Dict[str, Any]:
    try:
        from experiments.cost.cost_model import _cfg_group

        return _cfg_group(config_id) or {}
    except Exception:  # noqa: BLE001
        return {}


def _provider(config_id: str) -> str:
    return str(_cfg_meta(config_id).get("provider", "qwen"))


def _tier(config_id: str) -> str:
    return str(_cfg_meta(config_id).get("tier", "flagship"))


def groups_backend(config_id: str) -> str:
    return str(_cfg_meta(config_id).get("backend", ""))


def _per_config(pairs: List[Dict[str, Any]], runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_cfg: Dict[str, List[Dict[str, Any]]] = {}
    for p in pairs:
        by_cfg.setdefault(str(p["config"]), []).append(p)

    # 成本与隐私（缺失时保持 None）
    try:
        from experiments.cost.cost_model import cloud_cost, local_cost, per_item_cost

        cost_fn = per_item_cost
    except Exception:  # noqa: BLE001
        cost_fn = None
        cloud_cost = local_cost = None  # type: ignore[assignment]
    try:
        from experiments.privacy.capture import load_results

        privacy = load_results()
    except Exception:  # noqa: BLE001
        privacy = {}

    out: Dict[str, Any] = {}
    for cfg, all_rows in by_cfg.items():
        # 只统计有效记录：失败条目（含被识别为错误的模板输出）的耗时与文本
        # 一律不进入统计，否则超时耗时会污染 P50/P95、错误文本会被当作摘要评分
        n_failed = sum(1 for r in all_rows if r["record"].get("error"))
        rows = [r for r in all_rows if not r["record"].get("error")]
        lat = [r["record"].get("latency_s") for r in rows if r["record"].get("latency_s") is not None]
        costs = []
        for r in rows:
            c = None
            if cost_fn is not None:
                try:
                    c = cost_fn(cfg, r["record"].get("tokens_in"), r["record"].get("tokens_out"),
                                r["record"].get("latency_s"))
                except Exception:  # noqa: BLE001
                    c = None
            costs.append(c)
        tin = [r["record"].get("tokens_in") for r in rows if r["record"].get("tokens_in") is not None]
        tout = [r["record"].get("tokens_out") for r in rows if r["record"].get("tokens_out") is not None]
        mvs = [r.get("record", {}).get("model_version") for r in rows]
        model_version = next((m for m in mvs if m), None)
        througs = [m.get("throughput_per_min") for m in runs if m.get("config") == cfg
                   and m.get("throughput_per_min") is not None]
        peaks_gpu = [r["record"].get("peak_gpu_mb") for r in rows
                     if r["record"].get("peak_gpu_mb") is not None]
        peaks_rss = [r["record"].get("peak_rss_mb") for r in rows
                     if r["record"].get("peak_rss_mb") is not None]
        # LLM 运行是逐条落盘记录的，落盘时采样尚未结束，因此逐条记录里没有
        # peak_* 字段——实测值在 manifest.resource_peaks 里（随运行归档）。
        # 缺失时回落到 manifest，避免已实测的显存峰值被记为未测。
        if not peaks_gpu:
            peaks_gpu = [v for m in runs if m.get("config") == cfg
                         for v in [(m.get("resource_peaks") or {}).get("peak_gpu_mb")]
                         if v is not None]
        if not peaks_rss:
            peaks_rss = [v for m in runs if m.get("config") == cfg
                         for v in [(m.get("resource_peaks") or {}).get("peak_rss_mb")]
                         if v is not None]
        out[cfg] = {
            "n_items": len({r["sample_id"] for r in rows}),
            "n_records": len(rows),
            "n_valid": len(rows),
            "n_failed": n_failed,
            "n_repeats": len({r["repeat"] for r in rows}),
            "model_version": model_version,
            "rouge_l": {"mean": mean([r.get("rouge_l") for r in rows]),
                        "sd": stdev([r.get("rouge_l") for r in rows]),
                        "n": sum(1 for r in rows if r.get("rouge_l") is not None)},
            "bertscore": {"mean": mean([r.get("bertscore") for r in rows]),
                          "sd": stdev([r.get("bertscore") for r in rows]),
                          "n": sum(1 for r in rows if r.get("bertscore") is not None)},
            # 首板块口径：模型按 512 token 截断长简报，该口径几乎不受截断影响，
            # 用于检验 BERTScore 结论是否由截断造成（4.1/5.1 引用）
            "bertscore_head": {"mean": mean([r.get("bertscore_head") for r in rows]),
                               "sd": stdev([r.get("bertscore_head") for r in rows]),
                               "n": sum(1 for r in rows if r.get("bertscore_head") is not None)},
            "entity_f1": {"mean": mean([r.get("entity_f1") for r in rows]),
                          "sd": stdev([r.get("entity_f1") for r in rows]),
                          "n": sum(1 for r in rows if r.get("entity_f1") is not None)},
            "rouge_l_head": {"mean": mean([r.get("rouge_l_head") for r in rows]),
                             "sd": stdev([r.get("rouge_l_head") for r in rows]),
                             "n": sum(1 for r in rows if r.get("rouge_l_head") is not None)},
            "entity_f1_ref": {"mean": mean([r.get("entity_f1_ref") for r in rows]),
                              "sd": stdev([r.get("entity_f1_ref") for r in rows]),
                              "n": sum(1 for r in rows if r.get("entity_f1_ref") is not None)},
            "human": None,
            "latency_p50": percentile(lat, 50),
            "latency_p95": percentile(lat, 95),
            "latency_mean": mean(lat),
            "throughput_per_min": {"mean": mean(througs), "sd": stdev(througs), "n": len(througs)},
            "peak_gpu_mb": max(peaks_gpu) if peaks_gpu else None,
            "peak_rss_mb": max(peaks_rss) if peaks_rss else None,
            "tokens_in_mean": mean(tin) if tin else None,
            "tokens_out_mean": mean(tout) if tout else None,
            "usage_source": next((r["record"].get("usage_source") for r in rows
                                  if r["record"].get("usage_source") not in (None, "none")), "none"),
            "cost_per_item_mean": mean(costs) if any(c is not None for c in costs) else None,
            # 表5 的分项：云端输入/输出 token 计费、本地能耗与折旧折算
            "cost_token_in": (cloud_cost(mean(tin), 0, _provider(cfg), _tier(cfg))
                              if (cloud_cost and groups_backend(cfg) == "openai_compatible" and tin) else None),
            "cost_token_out": (cloud_cost(0, mean(tout), _provider(cfg), _tier(cfg))
                               if (cloud_cost and groups_backend(cfg) == "openai_compatible" and tout) else None),
            "cost_local": (local_cost(mean(lat))
                           if (local_cost and groups_backend(cfg) == "ollama" and lat) else None),
            "egress_bytes": (privacy.get(cfg) or {}).get("bytes_total"),
            "egress_destinations": (privacy.get(cfg) or {}).get("destinations"),
        }
    return out


def _resolve_role(role: str, per_cfg: Dict[str, Any], groups: Dict[str, str]) -> Optional[str]:
    """把角色标签解析成实际配置 id（如 best_local = ROUGE-L 最高的本地配置）。"""
    def metric(cfg: str, key: str) -> Optional[float]:
        v = (per_cfg.get(cfg) or {}).get(key)
        return (v or {}).get("mean") if isinstance(v, dict) else v

    if role in per_cfg:
        return role
    # 以主指标（实体 F1，与语言无关）选"最优配置"；
    # ROUGE-L 因生成语言与参考摘要不一致而绝对值偏低，不用于排序
    if role == "best_local":
        cands = [c for c in per_cfg if groups.get(c) == "local"]
        return max(cands, key=lambda c: (metric(c, PRIMARY_METRIC) or -1)) if cands else None
    if role == "best_llm":
        cands = [c for c in per_cfg if groups.get(c) in ("local", "cloud")]
        return max(cands, key=lambda c: (metric(c, PRIMARY_METRIC) or -1)) if cands else None
    if role == "best_baseline":
        cands = [c for c in per_cfg if groups.get(c) == "baseline"]
        return max(cands, key=lambda c: (metric(c, PRIMARY_METRIC) or -1)) if cands else None
    if role == "cloud_flagship":
        return next((c for c in per_cfg if groups.get(c) == "cloud" and "flagship" in c), None)
    if role == "cloud_light":
        return next((c for c in per_cfg if groups.get(c) == "cloud" and "light" in c), None)
    return None


def build_comparisons(per_cfg: Dict[str, Any], groups: Dict[str, str],
                      samples: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 COMPARISON_SPEC 做配对检验 + Holm 校正。"""
    raw = []
    for role_a, role_b, metric in COMPARISON_SPEC:
        a = _resolve_role(role_a, per_cfg, groups)
        b = _resolve_role(role_b, per_cfg, groups)
        if not a or not b or a == b:
            raw.append({"config_a": a or role_a, "config_b": b or role_b, "metric": metric,
                        "n_pairs": 0, "statistic": None, "p_value": None,
                        "cliffs_delta": None, "note": "配置缺失"})
            continue
        va = (samples.get(a) or {}).get(metric) or []
        vb = (samples.get(b) or {}).get(metric) or []
        if not va or not vb:
            raw.append({"config_a": a, "config_b": b, "metric": metric, "n_pairs": 0,
                        "statistic": None, "p_value": None, "cliffs_delta": None,
                        "note": "该指标未实测"})
            continue
        raw.append(stats.compare_pair(a, b, metric, va, vb))
    return stats.compare_family(raw)


def aggregate(stage: Optional[str] = None, configs: Optional[Sequence[str]] = None,
              use_bertscore: bool = True, gold_csv: Optional[Path] = None,
              human_csv: Optional[Path] = None) -> Dict[str, Any]:
    runs = _discover_runs(stage=stage, configs=configs)
    if not runs:
        raise RuntimeError("未找到任何运行记录，请先执行 run smoke/pilot/full")

    # 云端 token 用量重算叠加：LangChain 流式路径未回传 usage，
    # 重算依据是实际发生过的请求/响应文本（见 cost/token_recount.py）
    try:
        from experiments.cost import token_recount

        token_info = token_recount.overlay(runs)
    except Exception as e:  # noqa: BLE001
        logger.warning("token 重算未叠加: %s", e)
        token_info = {"applied": 0, "available": False}

    pairs = compute_metrics(runs, use_bertscore=use_bertscore, gold_csv=gold_csv)
    per_cfg = _per_config(pairs, runs)

    # 配置分组（用于角色解析）
    groups: Dict[str, str] = {}
    for m in runs:
        backend = str(m.get("backend"))
        groups[str(m.get("config"))] = "baseline" if backend == "baseline" else (
            "cloud" if backend == "openai_compatible" else "local")

    # 逐 (config) 的逐样本取值，供配对检验
    samples: Dict[str, Dict[str, List[Optional[float]]]] = {}
    for cfg in per_cfg:
        rows = [p for p in pairs if str(p["config"]) == cfg]
        rows.sort(key=lambda p: (str(p["sample_id"]), int(p["repeat"] or 0)))
        samples[cfg] = {
            "rouge_l": [p.get("rouge_l") for p in rows],
            "entity_f1": [p.get("entity_f1") for p in rows],
            "human": [],
            "latency_p95": [p["record"].get("latency_s") for p in rows],
            "cost_per_item": [None for _ in rows],
            "egress_bytes": [],
        }
    # 成本逐条（依赖 pricing.yaml）
    try:
        from experiments.cost.cost_model import per_item_cost

        for cfg in samples:
            costs = []
            for p in [x for x in pairs if str(x["config"]) == cfg]:
                try:
                    costs.append(per_item_cost(cfg, p["record"].get("tokens_in"),
                                               p["record"].get("tokens_out"),
                                               p["record"].get("latency_s")))
                except Exception:  # noqa: BLE001
                    costs.append(None)
            samples[cfg]["cost_per_item"] = costs
    except Exception as e:  # noqa: BLE001
        logger.warning("逐条成本未计算: %s", e)

    human_alpha = None
    if human_csv and Path(human_csv).exists():
        from experiments.metrics import human_eval

        human_alpha = human_eval.alpha_from_csv(Path(human_csv))
        # 人工评分按匿名标签回填到配置
        mapping = {}
        mp = Path(human_csv).with_suffix(".mapping.json")
        if mp.exists():
            mapping = (read_json(mp) or {}).get("anonymous_to_config", {})
        scores = human_eval._read_filled(Path(human_csv))
        by_cfg: Dict[str, List[float]] = {}
        for row in scores:
            cfg = mapping.get(str(row.get("config_anon")))
            if not cfg:
                continue
            vals = [float(row[d]) for d in human_eval.DIMENSIONS if (row.get(d) or "").strip()]
            if vals:
                by_cfg.setdefault(cfg, []).extend([sum(vals) / len(vals)])
        for cfg, vals in by_cfg.items():
            if cfg in per_cfg:
                per_cfg[cfg]["human"] = {"mean": mean(vals), "sd": stdev(vals), "n": len(vals)}
            samples.setdefault(cfg, {}).setdefault("human", []).extend(vals)

    comparisons = build_comparisons(per_cfg, groups, samples)

    agg: Dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "stage": stage,
        "runs_included": [m.get("run_id") for m in runs],
        "n_runs": len(runs),
        "configs": per_cfg,
        "groups": groups,
        "comparisons": comparisons,
        "human_alpha": human_alpha,
        "primary_metric": PRIMARY_METRIC,
        "token_usage": token_info,
        "metric_availability": {
            "rouge_l": True,
            "bertscore": any((per_cfg[c]["bertscore"] or {}).get("n") for c in per_cfg),
            "bertscore_head": any((per_cfg[c].get("bertscore_head") or {}).get("n") for c in per_cfg),
            "entity_f1": any((per_cfg[c]["entity_f1"] or {}).get("n") for c in per_cfg),
            "entity_f1_ref": any((per_cfg[c]["entity_f1_ref"] or {}).get("n") for c in per_cfg),
            "human": any(per_cfg[c].get("human") for c in per_cfg),
        },
    }
    write_json(AGGREGATE, agg)
    print("=" * 72)
    for cfg, v in per_cfg.items():
        print(f"  {cfg:<20} ROUGE-L {_fmt_msd(v['rouge_l'])}  实体F1 {_fmt_msd(v['entity_f1'])}  "
              f"P50 {v['latency_p50']}  P95 {v['latency_p95']}")
    print(f"比较 {len(comparisons)} 组；已写入 {AGGREGATE}")
    print("=" * 72)
    return agg


def _fmt_msd(d: Optional[Dict[str, Any]]) -> str:
    if not d or d.get("mean") is None or d.get("sd") is None:
        return PLACEHOLDER
    return f"{d['mean']:.3f}±{d['sd']:.3f}"


def main(stage: Optional[str] = None, configs: Optional[str] = None,
         no_bertscore: bool = False, gold_csv: Optional[str] = None,
         human_csv: Optional[str] = None) -> Dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return aggregate(stage=stage, configs=configs.split(",") if configs else None,
                     use_bertscore=not no_bertscore,
                     gold_csv=Path(gold_csv) if gold_csv else None,
                     human_csv=Path(human_csv) if human_csv else None)
