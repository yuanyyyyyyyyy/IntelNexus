"""基线测试：确定性（重复运行结果一致）与输出非空。"""
from __future__ import annotations

from experiments.harness import baselines

SAMPLE = (
    "安全公告：Apache HTTP Server 2.4.49 存在路径遍历与远程代码执行漏洞（CVE-2021-41773）。"
    "攻击者可构造特制请求读取任意文件。官方已在 2.4.51 版本中修复，建议立即升级。"
    "该漏洞已被用于实际攻击，属于已知被利用漏洞。未修复系统面临信息泄露风险。"
)


def test_keyword_extract_returns_security_sentences():
    out = baselines.keyword_extract(SAMPLE, top_k=3)
    assert out
    assert "Apache" in out or "漏洞" in out


def test_textrank_is_deterministic():
    a = baselines.textrank(SAMPLE, max_sentences=3)
    b = baselines.textrank(SAMPLE, max_sentences=3)
    assert a == b and a


def test_tfidf_cluster_is_deterministic():
    a = baselines.tfidf_cluster(SAMPLE, clusters=4, max_sentences=3)
    b = baselines.tfidf_cluster(SAMPLE, clusters=4, max_sentences=3)
    assert a == b


def test_baselines_are_shorter_than_input():
    for kind in ("keyword", "textrank", "tfidf"):
        out = baselines.run_baseline(kind, SAMPLE, {})
        assert 0 < len(out) <= len(SAMPLE)


def test_run_baseline_unknown_kind_raises():
    import pytest

    with pytest.raises(ValueError):
        baselines.run_baseline("nope", SAMPLE, {})


def test_empty_input_returns_empty():
    assert baselines.keyword_extract("", top_k=3) == ""
    assert baselines.textrank("", max_sentences=3) == ""
    assert baselines.tfidf_cluster("", clusters=4) == ""
