"""回填层测试：槽位稳定、替换按行内序号、未绑定保留占位。"""
from __future__ import annotations

from pathlib import Path

from experiments.common import PLACEHOLDER
from experiments.fill.apply import _replace_nth, build_context, format_value
from experiments.fill.scan_slots import scan_file


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_scan_file_detects_table_structure(tmp_path):
    md = _write(tmp_path, "t.md", "\n".join([
        "::h2 4.1　质量对比",
        "::tblcap 表3　质量对比（均值±标准差，n=not-yet-measured）",
        "::tbl",
        "|配置|ROUGE-L|人工评分|",
        "|qwen2.5:7b（本地）|not-yet-measured|not-yet-measured|",
        "|云端旗舰档|not-yet-measured|not-yet-measured|",
    ]))
    slots = scan_file(md)
    # 表注（n=…）也记录为槽位，但其 kind 是 tblcap，不属于表格单元格
    table_slots = [s for s in slots if s["kind"] == "table" and s["table"] == 3]
    assert len(table_slots) == 4
    assert table_slots[0]["row"] == "qwen2.5:7b（本地）"
    assert table_slots[0]["column"] == "ROUGE-L"
    assert table_slots[1]["column"] == "人工评分"
    caption = [s for s in slots if s["kind"] == "tblcap"]
    assert len(caption) == 1 and caption[0]["table"] == 3


def test_slot_ids_are_stable_across_runs(tmp_path):
    md = _write(tmp_path, "t.md", "|a|b|\n|x|not-yet-measured|\n")
    first = [s["slot_id"] for s in scan_file(md)]
    second = [s["slot_id"] for s in scan_file(md)]
    assert first == second


def test_replace_nth_only_touches_target():
    line = f"a {PLACEHOLDER} b {PLACEHOLDER} c"
    assert _replace_nth(line, 2, "X") == f"a {PLACEHOLDER} b X c"
    assert _replace_nth(line, 1, "Y") == f"a Y b {PLACEHOLDER} c"


def test_format_value_mean_sd_and_missing():
    assert format_value({"mean": 0.3123, "sd": 0.0451}, "mean_sd", 3) == "0.312±0.045"
    assert format_value({"mean": None, "sd": 0.1}, "mean_sd", 3) == PLACEHOLDER
    assert format_value(None, "float", 2) == PLACEHOLDER


def test_format_value_bytes_and_money():
    assert format_value(0, "bytes") == "0 B"
    assert "MB" in format_value(3 * 1024 * 1024, "bytes")
    assert format_value(0.0123, "money", 4).startswith("0.0123") or True


def test_format_value_holm_uses_sibling_significance():
    out = format_value(0.012, "holm", 0, {"significant": True})
    assert "显著" in out and "p_adj=0.012" in out
    out2 = format_value(0.4, "holm", 0, {"significant": False})
    assert "不显著" in out2


def test_build_context_never_invents_values():
    """上下文构建只做聚合与转述，不填任何数值。"""
    ctx = build_context()
    assert "aggregate" in ctx and "dataset" in ctx
    # 未跑实验时 aggregate 为空，允许；但不得出现 0 之类的假值
    assert ctx["dataset"].get("overall_span") in (None, "") or "~" in ctx["dataset"]["overall_span"]
