"""把 aggregate.json 等实测数据回填到稿件副本。

原则：
1. **绝不覆盖原稿**：输出到 ``content_filled/``，原目录保持只读；
2. **未绑定即保留占位**：没有实测支撑的格子仍是 not-yet-measured；
3. **幂等**：每次都从原稿重新生成，重复执行结果一致。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from experiments.common import PLACEHOLDER, read_json, write_json
from experiments.fill.gen_mapping import load_mapping
from experiments.logging_utils import get_logger
from experiments.paths import (
    AGGREGATE,
    DATASET_STATS,
    DEFAULT_CONTENT_DIR,
    ENV_REPORT,
    REPORTS_DIR,
)

logger = get_logger("exp.fill")

PRIVACY_JSON = REPORTS_DIR / "privacy.json"
SCAN_JSON = REPORTS_DIR / "privacy_scan.json"
FILL_REPORT = REPORTS_DIR / "fill_report.json"


# ------------------------------------------------------------------ 上下文
def _safe_get(data: Any, path: List[str]) -> Any:
    cur = data
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def build_context() -> Dict[str, Any]:
    """汇总所有实测数据源，供路径解析使用。"""
    ctx: Dict[str, Any] = {}

    agg = read_json(AGGREGATE) if AGGREGATE.exists() else {}
    ctx["aggregate"] = agg

    # 数据集：按类别索引 + 合计 + 总体时间跨度
    ds = read_json(DATASET_STATS) if DATASET_STATS.exists() else {}
    by_cat = {r.get("category"): r for r in (ds.get("table1") or [])}
    # 总体时间跨度：把各类的 "起~止" 拆开后取全体的最早与最晚
    dates: List[str] = []
    for r in (ds.get("table1") or []):
        for part in str(r.get("span") or "").split("~"):
            part = part.strip()
            if part:
                dates.append(part)
    ctx["dataset"] = {
        "table1_by_category": by_cat,
        "totals": ds.get("totals", {}),
        "overall_span": f"{min(dates)}~{max(dates)}" if dates else None,
    }

    env = read_json(ENV_REPORT) if ENV_REPORT.exists() else {}
    gpu = env.get("gpu") or {}
    dev = (gpu.get("devices") or [{}])[0]
    num_ctx = None
    try:
        from experiments import config_loader

        num_ctx = ((config_loader.experiment_config().get("ollama", {}) or {})
                   .get("options", {}) or {}).get("num_ctx")
    except Exception:  # noqa: BLE001
        num_ctx = None
    hw = dev.get("name") or "未检测到 GPU"
    mem = dev.get("memory_total") or ""
    ctx["env"] = {
        "local_hardware_context": f"{hw}（{mem}）/ 上下文 {num_ctx or '默认'}",
        "cloud": env.get("cloud", {}),
        "os": (env.get("platform") or {}).get("os_detail"),
        "driver": dev.get("driver_version"),
        "ollama_version": (env.get("ollama") or {}).get("version"),
        "python_version": (env.get("platform") or {}).get("python"),
    }
    ctx["env"]["os_driver"] = " / ".join(
        x for x in [ctx["env"].get("os"), (f"驱动 {ctx['env']['driver']}" if ctx["env"].get("driver") else None)]
        if x
    ) or None

    # 本地组合计成本（表5 本地行：按各本地配置取均值）
    locals_ = {k: v for k, v in (agg.get("configs") or {}).items()
               if (agg.get("groups") or {}).get(k) == "local"}
    ctx["aggregate"]["local_cost_summary"] = {
        "cost_local": _mean_of([v.get("cost_local") for v in locals_.values()]),
        "cost_per_item": _mean_of([v.get("cost_per_item_mean") for v in locals_.values()]),
    }
    ctx["aggregate"]["n_quality_items"] = _first_n(locals_)

    try:
        from experiments import config_loader

        ctx["pricing"] = config_loader.pricing_config()
    except Exception:  # noqa: BLE001
        ctx["pricing"] = {}

    ctx["privacy"] = read_json(PRIVACY_JSON).get("configs", {}) if PRIVACY_JSON.exists() else {}
    ctx["scan"] = read_json(SCAN_JSON) if SCAN_JSON.exists() else {}
    return ctx


def _mean_of(values: List[Optional[float]]) -> Optional[float]:
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def _first_n(cfg_values: Dict[str, Any]) -> Optional[int]:
    """表3 表注的 n：取每个配置的**观测数**（有效记录条数），
    而不是测试样本数——表内每格是 100 条样本 × 3 次重复共 300 个观测的均值。"""
    for v in cfg_values.values():
        n = v.get("n_valid") or v.get("n_items")
        if n:
            return int(n)
    return None


# ------------------------------------------------------------------ 格式化
def format_value(value: Any, fmt: str, digits: Optional[int] = None,
                 sibling: Optional[Dict[str, Any]] = None) -> str:
    d = 3 if digits is None else int(digits)
    if value is None:
        return PLACEHOLDER
    if fmt == "mean_sd":
        if not isinstance(value, dict):
            return PLACEHOLDER
        m, s = value.get("mean"), value.get("sd")
        if m is None or s is None:
            return PLACEHOLDER
        return f"{float(m):.{d}f}±{float(s):.{d}f}"
    if fmt == "float":
        return f"{float(value):.{d}f}"
    if fmt == "int":
        # 与正文一致：千分位用空格（1 000 / 4 176），避免与公式和单位混淆
        return f"{int(round(float(value))):,}".replace(",", " ")
    if fmt == "bytes":
        v = int(value)
        if v <= 0:
            return "0 B"
        for unit, base in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
            if v >= base:
                return f"{v:,} B（{v / base:.1f} {unit}）".replace(",", " ")
        return f"{v:,} B".replace(",", " ")
    if fmt == "money":
        v = float(value)
        # 同一张表的金额必须同精度：显式 digits 优先，否则按量级自适应
        dd = int(digits) if digits else (4 if v >= 0.01 else 6)
        return f"{v:.{dd}f}"
    if fmt == "holm":
        sig = (sibling or {}).get("significant")
        p = float(value)
        # p 值统一三位有效数字表达，极小值用科学计数法，避免整列显示成 0.000
        ps = f"{p:.3f}" if p >= 1e-3 else f"{p:.2e}"
        return f"{'显著' if sig else '不显著'}（p_adj={ps}）"
    return str(value)


# ------------------------------------------------------------------ 填充
def _replace_nth(line: str, n: int, text: str) -> str:
    """把第 n 个占位（1-based）替换为 text。"""
    idx = -1
    for _ in range(n):
        idx = line.find(PLACEHOLDER, idx + 1)
        if idx == -1:
            return line
    return line[:idx] + text + line[idx + len(PLACEHOLDER):]


def apply(content_dir: Optional[Path] = None, out_dir: Optional[Path] = None,
          mapping_path: Optional[Path] = None, require_zero: bool = False) -> Dict[str, Any]:
    src = Path(content_dir) if content_dir else DEFAULT_CONTENT_DIR
    if not src.exists():
        raise FileNotFoundError(f"稿件目录不存在: {src}")
    dst = Path(out_dir) if out_dir else src.parent / "content_filled"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)

    mapping = load_mapping(Path(mapping_path) if mapping_path else None)
    slots_map: Dict[str, Any] = mapping.get("slots", {})
    ctx = build_context()

    filled, missing = 0, 0
    unresolved: List[Dict[str, Any]] = []
    per_file: Dict[str, Dict[str, int]] = {}

    for md in sorted(src.glob("*.md")):
        lines = md.read_text(encoding="utf-8").splitlines()
        out_lines = list(lines)
        count = {"filled": 0, "missing": 0}
        # 每个文件内按 slot 顺序替换（第 n 个占位）
        file_slots = [s for s in (slots_map.items()) if s[0].startswith(md.name + ":")]
        # 按 (line, nth) 排序，保证 nth 与原文一致（从后往前替换更安全，但 nth 基于原始计数，
        # 因此按行分组、每行从后往前替换）
        by_line: Dict[int, List[Tuple[int, str, Dict[str, Any]]]] = {}
        for slot_id, entry in file_slots:
            try:
                _, line_s, nth_s = slot_id.rsplit(":", 2)
                by_line.setdefault(int(line_s), []).append((int(nth_s), slot_id, entry))
            except ValueError:
                continue
        for line_no, items in by_line.items():
            if line_no - 1 >= len(out_lines):
                continue
            line = out_lines[line_no - 1]
            # slot_id 的 nth 是「文件内全局计数」，而替换需要「行内序号」：
            # 这里按 nth 升序重新编号为行内序号，并从后往前替换
            ordered = [(i + 1, slot_id, entry)
                       for i, (_, slot_id, entry) in enumerate(sorted(items, key=lambda x: x[0]))]
            for nth, slot_id, entry in reversed(ordered):
                value = _resolve(entry, ctx)
                if value is None:
                    missing += 1
                    count["missing"] += 1
                    unresolved.append({"slot_id": slot_id, "entry": entry,
                                       "context": line.strip()[:80]})
                    continue
                line = _replace_nth(line, nth, value)
                filled += 1
                count["filled"] += 1
            out_lines[line_no - 1] = line
        per_file[md.name] = count
        (dst / md.name).write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    remaining = sum(p.count(PLACEHOLDER) for p in dst.glob("*.md")
                    for p in [p.read_text(encoding="utf-8")])
    report = {
        "content_dir": str(src),
        "out_dir": str(dst),
        "filled": filled,
        "unresolved_entries": missing,
        "remaining_placeholders_in_output": remaining,
        "per_file": per_file,
        "unresolved_sample": unresolved[:40],
    }
    write_json(FILL_REPORT, report)
    print("=" * 72)
    print(f"回填完成：填充 {filled} 处，绑定但无值 {missing} 处")
    print(f"输出目录: {dst}")
    print(f"剩余占位: {remaining}")
    if require_zero and remaining:
        print("  ! 仍有占位未回填（属未实测项，请核对上表）")
    print("=" * 72)
    return report


def _resolve(entry: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[str]:
    source = entry.get("source")
    if source == "const":
        return str(entry.get("value"))
    data = ctx.get(source or "")
    if data is None:
        return None
    value = _safe_get(data, list(entry.get("path") or []))
    if value is None:
        return None
    sibling = None
    if entry.get("fmt") == "holm":
        path = list(entry.get("path") or [])
        if path:
            path[-1] = "significant"
            sibling = {"significant": _safe_get(data, path)}
    return format_value(value, str(entry.get("fmt", "str")), entry.get("digits"), sibling)


def main(content_dir: Optional[str] = None, out_dir: Optional[str] = None,
         mapping: Optional[str] = None, require_zero: bool = False) -> Dict[str, Any]:
    return apply(Path(content_dir) if content_dir else None,
                 Path(out_dir) if out_dir else None,
                 Path(mapping) if mapping else None,
                 require_zero=require_zero)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="回填实测数据到稿件副本")
    ap.add_argument("--content-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--mapping", default=None)
    ap.add_argument("--require-zero", action="store_true")
    a = ap.parse_args()
    main(a.content_dir, a.out_dir, a.mapping, a.require_zero)
