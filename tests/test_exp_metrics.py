"""质量指标的离线测试：已知输入的已知输出。"""
from __future__ import annotations

import pytest

from experiments.metrics import entity_f1, rouge


def test_rouge_l_identical_text_is_one():
    text = "Apache HTTP Server 存在远程代码执行漏洞，影响 2.4.49 版本。"
    assert rouge.rouge_l(text, text) == pytest.approx(1.0)


def test_rouge_l_disjoint_is_zero():
    assert rouge.rouge_l("甲 乙 丙 丁", "戊 己 庚 辛") == 0.0


def test_rouge_l_empty_is_none_not_zero():
    """缺参考摘要时必须返回 None，让上层保留占位，而不是记 0。"""
    assert rouge.rouge_l("有内容", "") is None
    assert rouge.rouge_l("", "有内容") is None


def test_rouge_l_f1_is_symmetric():
    a = "CVE-2026-1234 缓冲区溢出 漏洞"
    b = "CVE-2026-1234 漏洞 修复"
    assert rouge.rouge_l(a, b) == pytest.approx(rouge.rouge_l(b, a))


def test_rouge_l_prf_components():
    r = rouge.rouge_l_prf("a b c", "a b c d e")
    assert r["precision"] == pytest.approx(1.0)
    assert 0 < r["recall"] < 1.0
    assert 0 < r["f1"] < 1.0


def test_entity_extraction_finds_cve_version_attack_product():
    ents = entity_f1.extract_entities("CVE-2026-1234 影响 Apache 2.4.49，可导致远程代码执行")
    types = {t for t, _ in ents}
    assert {"cve", "version", "attack", "product"} <= types


def test_entity_f1_perfect_match():
    gold = {("cve", "CVE-2026-1234"), ("version", "2.4.49")}
    assert entity_f1.prf(gold, gold)["f1"] == pytest.approx(1.0)


def test_entity_f1_empty_gold_is_none():
    assert entity_f1.prf({("cve", "x")}, set()) is None


def test_entity_f1_no_overlap():
    assert entity_f1.prf({("cve", "CVE-2026-0001")}, {("cve", "CVE-2026-9999")})["f1"] == 0.0
