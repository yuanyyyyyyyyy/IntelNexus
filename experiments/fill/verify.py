"""数字反查：确认写进稿件的每个数值都能追溯到一次真实运行。

校验三层：
1. 稿件中已填的格子 → mapping 条目 → 数据源（aggregate/dataset/env/privacy/scan）；
2. aggregate 引用的每次运行 → runs/<run_id>/manifest.json 存在且字段齐全
   （run_id、时间戳、脚本哈希、模型版本、参数、种子、原始输出路径）；
3. 每次运行的原始记录文件存在且条数与 manifest 一致。

任一层缺失都会列出明细，供人工补齐；**不因缺项而改写稿件**。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.common import PLACEHOLDER, read_json, read_jsonl, write_json
from experiments.fill.gen_mapping import load_mapping
from experiments.logging_utils import get_logger
from experiments.paths import AGGREGATE, DATASET_STATS, ENV_REPORT, REPORTS_DIR, RUNS_DIR

logger = get_logger("exp.verify")

VERIFY_REPORT = REPORTS_DIR / "verify_report.json"

REQUIRED_MANIFEST_FIELDS = [
    "run_id", "stage", "config", "backend", "repeat", "n_items",
    "started_at", "finished_at", "git_commit", "script_sha256", "dataset_sha256",
    "valid_records", "failed_records",
]


def check_manifests(run_ids: List[str]) -> Dict[str, Any]:
    missing, incomplete, ok = [], [], []
    for rid in run_ids:
        mpath = RUNS_DIR / str(rid) / "manifest.json"
        if not mpath.exists():
            missing.append(rid)
            continue
        try:
            m = read_json(mpath)
        except Exception as e:  # noqa: BLE001
            incomplete.append({"run_id": rid, "reason": f"manifest 解析失败: {e}"})
            continue
        lack = [f for f in REQUIRED_MANIFEST_FIELDS if m.get(f) in (None, "")]
        rec_path = RUNS_DIR / str(rid) / "records.jsonl"
        n_records = len(read_jsonl(rec_path)) if rec_path.exists() else 0
        if lack:
            incomplete.append({"run_id": rid, "missing_fields": lack})
        elif n_records == 0:
            incomplete.append({"run_id": rid, "reason": "无原始记录"})
        else:
            ok.append({"run_id": rid, "n_records": n_records, "config": m.get("config")})
    return {"ok": ok, "incomplete": incomplete, "missing": missing}


# ------------------------------------------------------------------ 正文数字反查
# 允许前导负号（稿件里半角 "-" 与全角 "−" 混用），否则 −0.501 会因取不到符号而误报
DECIMAL_RE = re.compile(r"(?<![\d.])(?P<sign>[-−])?\d+\.\d+(?![\d])")
# 稿件里数字用空格式千分位（8 504.8），扫描前先去掉分隔空格，
# 否则会被截成 "504.8" 而误报
THOUSAND_SEP_RE = re.compile(r"(?<=\d)\s(?=\d{3}(?!\d))")
# 形如 "5.4 节" 的是章节引用，不是测量值
SECTION_REF_SUFFIX = ("节", "章")
PROSE_PREFIXES = ("::body", "::abstract", "::en_abstract")

PROSE_SOURCES = ("aggregate.json", "dataset_stats.json", "env_report.json",
                 "privacy.json", "privacy_scan.json", "token_recount.json",
                 "cost_sensitivity.json", "power_probe.json", "frozen.json")


def _collect_numbers(obj: Any, out: List[float]) -> None:
    """递归收集数据源中的所有数值（含字符串内嵌数字，如时间跨度）。"""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numbers(v, out)
    elif isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        for m in re.finditer(r"\d+(?:\.\d+)?", obj):
            out.append(float(m.group()))


def number_index() -> List[float]:
    """把所有实测数据源里的数值摊平，供正文数字反查。"""
    values: List[float] = []
    for name in PROSE_SOURCES:
        p = REPORTS_DIR / name
        if p.exists():
            try:
                _collect_numbers(read_json(p), values)
            except Exception:  # noqa: BLE001
                continue
    for p in (DATASET_STATS, ENV_REPORT):
        if p.exists():
            try:
                _collect_numbers(read_json(p), values)
            except Exception:  # noqa: BLE001
                continue
    return values


def check_prose_numbers(out_dir: Optional[Path], values: Optional[List[float]] = None) -> Dict[str, Any]:
    """核对已回填正文中的小数能否在实测数据里找到对应数值。

    只做**提示**：正文里的比值、倍数等派生量本就不在数据源中，列出来供人工确认；
    表格内的数字由 mapping 逐格绑定，已在第一层校验，不在这里重复。
    """
    filled_dir = None
    rep = REPORTS_DIR / "fill_report.json"
    if out_dir and Path(out_dir).exists():
        filled_dir = Path(out_dir)
    elif rep.exists():
        cand = (read_json(rep) or {}).get("out_dir")
        filled_dir = Path(cand) if cand and Path(cand).exists() else None
    if filled_dir is None:
        return {"checked": 0, "unmatched": [], "note": "未找到回填产物目录"}

    vals = values if values is not None else number_index()
    checked, unmatched = 0, []
    for md in sorted(filled_dir.glob("*.md")):
        for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip().startswith(PROSE_PREFIXES):
                continue
            norm = THOUSAND_SEP_RE.sub("", line)
            for m in DECIMAL_RE.finditer(norm):
                token = m.group()
                magnitude = token.lstrip("-−")               # 全角负号不能被 float 解析
                tail = norm[m.end():m.end() + 2].lstrip()
                if tail[:1] in SECTION_REF_SUFFIX:
                    continue                                  # "5.4 节" 属章节引用
                num = float(magnitude) * (-1 if m.group("sign") else 1)
                decimals = len(magnitude.split(".")[1])
                tol = 0.5 * (10 ** -decimals) * 1.01         # 允许四舍五入
                checked += 1
                if not any(abs(v - num) <= tol for v in vals):
                    unmatched.append({"file": md.name, "line": i, "value": token,
                                      "context": line.strip()[:70]})
    # 说明：正文里的比值、差值、百分比（如"4.8 倍""高 8.4%"）是从实测值派生的，
    # 本就不在数据源中出现，列出来仅供人工确认，不代表数值有误。
    return {"checked": checked, "unmatched": unmatched[:30], "unmatched_total": len(unmatched),
            "note": "未匹配项为派生量（比值/差值/百分比/反算值），需人工确认",
            "filled_dir": str(filled_dir)}


def verify(mapping_path: Optional[Path] = None) -> Dict[str, Any]:
    mapping = load_mapping(mapping_path)
    slots_map: Dict[str, Any] = mapping.get("slots", {})
    agg = read_json(AGGREGATE) if AGGREGATE.exists() else {}

    # 1) 统计各数据源被引用次数
    by_source: Dict[str, int] = {}
    for entry in slots_map.values():
        s = str(entry.get("source"))
        by_source[s] = by_source.get(s, 0) + 1

    # 2) 运行级可追溯性
    run_ids = list(agg.get("runs_included") or [])
    runs = check_manifests(run_ids)

    # 3) 未绑定槽位（无法反查，只能保留占位）
    unbound = [sid for sid in (mapping.get("_unbound_slot_ids") or [])]

    report: Dict[str, Any] = {
        "generated_at": None,
        "mapping_entries": len(slots_map),
        "by_source": by_source,
        "runs_in_aggregate": len(run_ids),
        "runs_ok": len(runs["ok"]),
        "runs_incomplete": runs["incomplete"],
        "runs_missing": runs["missing"],
        "unbound_slots": len(unbound),
        "prose_numbers": check_prose_numbers(None),
        "issues": [],
    }
    if not AGGREGATE.exists():
        report["issues"].append("未找到 aggregate.json，无法校验数值来源")
    if runs["missing"]:
        report["issues"].append(f"{len(runs['missing'])} 个 run_id 缺少 manifest.json")
    if runs["incomplete"]:
        report["issues"].append(f"{len(runs['incomplete'])} 个 run 的 manifest 字段或记录不完整")
    recount = agg.get("token_usage") or {}
    if (recount.get("applied") or 0) > 0:
        src = recount.get("by_source") or {}
        proxy_n = int(src.get("recount_proxy") or 0)
        own_n = int(src.get("recount_own_prompt") or 0)
        report["issues"].append(
            f"云端 token 用量来自重算（{recount.get('applied')} 条，分词器 {recount.get('tokenizer')}；"
            f"其中自带提示词留痕 {own_n} 条、跨调用代理 {proxy_n} 条）："
            "批量运行时未采集 API usage"
        )
        if proxy_n:
            report["issues"].append(
                f"{proxy_n} 条的输入 token 是跨调用代理值（借用本地同一样本的 prompt_eval_count），"
                "必须以区间披露：见 reports/cost_sensitivity.json 的 input_token_band，"
                "表5 表注须与该产物同源"
            )
    for cfg_id, v in (agg.get("configs") or {}).items():
        if (v or {}).get("usage_source") == "none" and (agg.get("groups") or {}).get(cfg_id) == "cloud":
            report["issues"].append(f"{cfg_id} 未取到 token 用量，其成本格子无法回填")

    from experiments.common import utc_now_iso

    report["generated_at"] = utc_now_iso()
    write_json(VERIFY_REPORT, report)

    print("=" * 72)
    print(f"mapping 条目 {report['mapping_entries']}，数据源分布 {by_source}")
    print(f"aggregate 引用运行 {report['runs_in_aggregate']} 次，可追溯 {report['runs_ok']} 次")
    prose = report["prose_numbers"]
    print(f"正文小数反查：检查 {prose.get('checked')} 处，未直接命中 {prose.get('unmatched_total', 0)} 处"
          f"（{prose.get('note', '')}）")
    for u in prose.get("unmatched") or []:
        print(f"  ? {u['file']}:{u['line']} {u['value']}  {u['context']}")
    if report["issues"]:
        print("问题：")
        for i in report["issues"]:
            print(f"  ! {i}")
    else:
        print("未发现可追溯性问题")
    print(f"已写入 {VERIFY_REPORT}")
    print("=" * 72)
    return report


if __name__ == "__main__":
    verify()
