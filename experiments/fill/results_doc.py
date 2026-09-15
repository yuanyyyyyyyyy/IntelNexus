"""生成人读的结果汇总（paper_A/experiments_results.md）。

用途：让每一格数值旁边都写着"来自哪一次运行"，供作者与审稿人抽查。
内容与 aggregate.json 同源，不做任何二次加工或四舍五入之外的处理。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.common import PLACEHOLDER, read_json, utc_now_iso, write_json
from experiments.metrics.aggregate import AGGREGATE
from experiments.paths import DATASET_STATS, ENV_REPORT, REPORTS_DIR, ROOT


def _fmt_msd(d: Optional[Dict[str, Any]], digits: int = 3) -> str:
    if not d or d.get("mean") is None or d.get("sd") is None:
        return PLACEHOLDER
    return f"{d['mean']:.{digits}f}±{d['sd']:.{digits}f}"


def _fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return PLACEHOLDER
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def build(out_path: Optional[Path] = None) -> Path:
    agg = read_json(AGGREGATE) if AGGREGATE.exists() else {}
    ds = read_json(DATASET_STATS) if DATASET_STATS.exists() else {}
    env = read_json(ENV_REPORT) if ENV_REPORT.exists() else {}
    fill_report = read_json(REPORTS_DIR / "fill_report.json") if (REPORTS_DIR / "fill_report.json").exists() else {}
    verify_report = read_json(REPORTS_DIR / "verify_report.json") if (REPORTS_DIR / "verify_report.json").exists() else {}

    lines: List[str] = []
    lines.append("# 论文 A 实验结果汇总（回填用）")
    lines.append("")
    lines.append(f"> 生成时间：{utc_now_iso()}　数据源：`experiments/reports/aggregate.json`")
    lines.append("> 未实测项一律保留 `not-yet-measured`，其产生条件见各表下方说明。")
    lines.append("")

    # ---- 数据集 ----
    lines.append("## 表1　数据集构成")
    lines.append("")
    lines.append("| 信源类别 | 代表信源 | 条数 | 时间跨度 | 去重后条数 |")
    lines.append("|---|---|---|---|---|")
    for r in (ds.get("table1") or []):
        lines.append(f"| {r.get('category')} | {r.get('representative')} | {r.get('raw_count')} | "
                     f"{r.get('span')} | {r.get('dedup_count')} |")
    t = ds.get("totals") or {}
    lines.append(f"| 合计 | — | {t.get('collected', PLACEHOLDER)} | — | {t.get('kept', PLACEHOLDER)} |")
    lines.append("")
    lines.append(f"去重移除 {t.get('dedup_removed', PLACEHOLDER)} 条；"
                 f"可用于质量评测（正文与官方摘要不同源）{t.get('quality_eligible', PLACEHOLDER)} 条。")
    lines.append("")

    # ---- 环境 ----
    lines.append("## 实验环境")
    lines.append("")
    plat = env.get("platform") or {}
    gpu = (env.get("gpu") or {}).get("devices") or [{}]
    lines.append(f"- 硬件：{gpu[0].get('name', PLACEHOLDER)}（显存 {gpu[0].get('memory_total', PLACEHOLDER)}），"
                 f"内存 {plat.get('memory_total_mb', PLACEHOLDER)} MB")
    lines.append(f"- 系统：{plat.get('os_detail', PLACEHOLDER)}，Python {plat.get('python', PLACEHOLDER)}")
    lines.append(f"- Ollama：{(env.get('ollama') or {}).get('version', PLACEHOLDER)}")
    for name, info in (env.get("cloud") or {}).items():
        sel = info.get("selected") or {}
        lines.append(f"- 云端[{name}]：可达={info.get('reachable')}，旗舰档={sel.get('flagship') or PLACEHOLDER}，"
                     f"轻量档={sel.get('light') or PLACEHOLDER}")
    lines.append("")

    # ---- 各配置 ----
    lines.append("## 各配置实测结果")
    lines.append("")
    lines.append("| 配置 | ROUGE-L | BERTScore | 实体 F1 | 人工评分 | P50 时延/s | P95 时延/s | 吞吐/(条/min) | 显存峰值/MB | 单次成本/元 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for cfg, v in (agg.get("configs") or {}).items():
        lines.append(
            f"| {cfg} | {_fmt_msd(v.get('rouge_l'))} | {_fmt_msd(v.get('bertscore'))} | "
            f"{_fmt_msd(v.get('entity_f1'))} | {_fmt_msd(v.get('human'))} | "
            f"{_fmt(v.get('latency_p50'), 2)} | {_fmt(v.get('latency_p95'), 2)} | "
            f"{_fmt_msd(v.get('throughput_per_min'), 2)} | {_fmt(v.get('peak_gpu_mb'), 0)} | "
            f"{_fmt(v.get('cost_per_item_mean'), 6)} |"
        )
    lines.append("")

    # ---- 统计 ----
    lines.append("## 表7　组间显著性检验与效应量（Holm 校正后）")
    lines.append("")
    lines.append("| 比较 | 指标 | n | 统计量 | Cliff's delta | 校正后显著性 |")
    lines.append("|---|---|---|---|---|---|")
    for c in (agg.get("comparisons") or []):
        sig = c.get("significant")
        sig_txt = PLACEHOLDER if c.get("p_adj") is None else (
            f"{'显著' if sig else '不显著'}（p_adj={c['p_adj']:.3f}）")
        lines.append(f"| {c.get('config_a')} vs {c.get('config_b')} | {c.get('metric')} | "
                     f"{c.get('n_pairs')} | {_fmt(c.get('statistic'))} | {_fmt(c.get('cliffs_delta'))} | {sig_txt} |")
    lines.append("")

    # ---- 可追溯 ----
    lines.append("## 可追溯性")
    lines.append("")
    lines.append(f"- aggregate 引用运行 {verify_report.get('runs_in_aggregate', 0)} 次，"
                 f"可完整追溯 {verify_report.get('runs_ok', 0)} 次")
    runs = agg.get("runs_included") or []
    if runs:
        lines.append("- run_id 清单：")
        for rid in runs[:60]:
            lines.append(f"  - `{rid}`")
        if len(runs) > 60:
            lines.append(f"  - …… 其余 {len(runs) - 60} 条见 aggregate.json")
    lines.append("")

    # ---- 未回填 ----
    lines.append("## 尚未回填的占位")
    lines.append("")
    lines.append(f"- 输出稿剩余占位：{fill_report.get('remaining_placeholders_in_output', PLACEHOLDER)}")
    lines.append(f"- 已绑定但缺实测值：{fill_report.get('unresolved_entries', PLACEHOLDER)}")
    lines.append("")
    lines.append("补齐条件：")
    lines.append("1. 云端与本地模型跑批（表3/4 全部、表5 云端部分）；")
    lines.append("2. `configs/pricing.yaml` 填写官方单价与本地折算参数（表5 本地部分、式1 参数）；")
    lines.append("3. 出域测量与明文残留扫描（表6）；")
    lines.append("4. 人工盲评回收 ≥3 人（表3 人工评分列与 α）。")

    out = Path(out_path) if out_path else (ROOT / "paper_A" / "experiments_results.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成: {out}")
    return out


if __name__ == "__main__":
    build()
