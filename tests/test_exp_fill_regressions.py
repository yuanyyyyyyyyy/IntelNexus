"""回填链路的回归测试。

每个用例对应一个**真实发生过的缺陷**，不是假想的边界：

1. 同一句里三个占位全部绑定到了同一个参数（式(1) 的 P_avg / p_e / D）；
2. 表注（如"n=…"）被整行跳过，导致表3 的 n 永远填不上；
3. 表6 本地行的"外联目的地数"把回环地址也算作外联；
4. 金额列精度不一致（0.007206 与 0.0158 混排）；
5. p 值整列显示成 0.000，看不出量级；
6. 正文数字反查把"8 504.8"截成"504.8"、"5.4 节"当成测量值、全角负号解析失败。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.fill import apply as fill_apply
from experiments.fill import gen_mapping, scan_slots, verify


# ----------------------------------------------------------- 格式化
def test_format_int_uses_space_thousands_separator():
    assert fill_apply.format_value(4176, "int") == "4 176"
    assert fill_apply.format_value(1000, "int") == "1 000"


def test_format_money_keeps_same_decimals_across_magnitudes():
    """同一张表里 0.007206 与 0.015807 必须同精度，不能一个 4 位一个 6 位。"""
    assert fill_apply.format_value(0.00720625, "money", 6) == "0.007206"
    assert fill_apply.format_value(0.0158065, "money", 6) == "0.015807"


def test_format_holm_uses_scientific_notation_for_tiny_p():
    out = fill_apply.format_value(6.56e-08, "holm", 0, sibling={"significant": True})
    assert "6.56e-08" in out and "显著" in out
    out2 = fill_apply.format_value(0.042, "holm", 0, sibling={"significant": False})
    assert "0.042" in out2 and "不显著" in out2


# ----------------------------------------------------------- 表注占位
def test_scan_records_table_caption_placeholder(tmp_path: Path):
    """表注里的占位必须被扫到，否则表3 的 n=… 永远留着。"""
    p = tmp_path / "05_results.md"
    p.write_text("::tblcap 表3　质量对比（均值±标准差，n=not-yet-measured）\n"
                 "::tbl\n|配置|ROUGE-L|\n|a|not-yet-measured|\n", encoding="utf-8")
    slots = scan_slots.scan_file(p)
    kinds = {s["kind"] for s in slots}
    assert "tblcap" in kinds and "table" in kinds
    cap = next(s for s in slots if s["kind"] == "tblcap")
    assert cap["table"] == 3 and cap["line"] == 1


# ----------------------------------------------------------- 顺序绑定
def _slots(*items):
    return {"total": len(items), "content_dir": "x", "slots": list(items)}


def test_order_rule_binds_pricing_parameters_by_position(tmp_path, monkeypatch):
    """式(1) 说明句的三个占位必须分别绑到 P_avg / p_e / D，而不是都绑第一个。"""
    monkeypatch.setattr(gen_mapping, "MAPPING_PATH", tmp_path / "mapping.yaml")
    monkeypatch.setattr(gen_mapping, "_resolve_local_config", lambda: "qwen3:8b")
    line = ("::body 式（1）中 P_avg 为平均整机功耗（PH），p_e 为电价（PH），"
            "D 为日均利用率（PH）")
    slots = _slots(*[
        {"slot_id": f"04_expdesign.md:32:{n}", "file": "04_expdesign.md", "line": 32,
         "nth": n, "table": None, "row": None, "column": None, "kind": "body",
         "context": "式（1）中 P_avg 为平均整机功耗（PH），p_e 为电价（PH），D 为日均利用率（PH）"}
        for n in (1, 2, 3)
    ])
    out = gen_mapping.generate(slots)
    paths = [out["slots"][f"04_expdesign.md:32:{n}"]["path"][-1] for n in (1, 2, 3)]
    assert paths == ["P_avg_watt", "p_e_yuan_per_kwh", "D_utilization"]
    assert line  # 仅用于说明句子来源


def test_privacy_local_row_uses_external_destination_count(tmp_path, monkeypatch):
    """表6 本地行必须用剔除回环后的目的地数，否则本地会被记成 1 个外联。"""
    monkeypatch.setattr(gen_mapping, "MAPPING_PATH", tmp_path / "mapping.yaml")
    monkeypatch.setattr(gen_mapping, "_resolve_local_config", lambda: "qwen3:8b")
    slots = _slots(*[
        {"slot_id": f"05_results.md:38:{n}", "file": "05_results.md", "line": 38,
         "nth": n, "table": 6, "row": "本地（排除首次拉取）", "column": col,
         "kind": "table", "context": "|本地（排除首次拉取）|"}
        for n, col in enumerate(["出域字节数/单次", "外联目的地数", "本地明文残留条目数"], 1)
    ])
    out = gen_mapping.generate(slots)
    assert out["slots"]["05_results.md:38:1"]["path"] == ["qwen3:8b", "bytes_per_item"]
    assert out["slots"]["05_results.md:38:2"]["path"] == ["qwen3:8b", "external_destination_count"]


# ----------------------------------------------------------- 反查
def test_prose_check_handles_space_separator_and_negatives(tmp_path: Path):
    d = tmp_path
    (d / "05_results.md").write_text(
        "::body 出域为 8 504.8 字节，Cliff's delta=−0.501，详见 5.4 节，端到端为 4.8 倍。\n",
        encoding="utf-8")
    res = verify.check_prose_numbers(d, values=[8504.8, -0.501])
    vals = {u["value"] for u in res["unmatched"]}
    assert "504.8" not in vals        # 千分位空格不应导致截断
    assert "5.4" not in vals          # 章节引用不是测量值
    assert "0.501" not in vals        # 全角负号应能解析
    assert "4.8" in vals              # 派生量如实列出，供人工确认
