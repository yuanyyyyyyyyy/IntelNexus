"""汇总层测试：失败记录必须被剔除，绝不能进入时延与质量统计。"""
from __future__ import annotations

from typing import Any, Dict, List


def _pair(config: str, sample: str, repeat: int, latency: float,
          error: str | None = None, rouge: float = 0.5) -> Dict[str, Any]:
    return {
        "run_id": f"run-{config}-{repeat}", "config": config, "repeat": repeat,
        "sample_id": sample, "text": "生成内容" if not error else "",
        "reference": "参考摘要", "rouge_l": None if error else rouge,
        "rouge_l_head": None if error else rouge, "entity_f1": None if error else 0.4,
        "bertscore": None,
        "record": {"latency_s": latency, "error": error, "error_kind": "timeout" if error else None,
                   "tokens_in": 100, "tokens_out": 50, "usage_source": "api_usage",
                   "peak_gpu_mb": 1000.0, "peak_rss_mb": 500.0, "model_version": "m"},
    }


def test_per_config_excludes_failed_records_from_latency():
    from experiments.metrics.aggregate import _per_config

    pairs: List[Dict[str, Any]] = [
        _pair("x", "s1", 1, 1.0),
        _pair("x", "s2", 1, 2.0),
        _pair("x", "s3", 1, 100.0, error="llm_error_template:timeout"),
    ]
    out = _per_config(pairs, [])["x"]
    # 失败记录的 100s 超时不得进入 P50/P95
    assert out["latency_p50"] is not None and out["latency_p50"] < 10
    assert out["latency_p95"] is not None and out["latency_p95"] < 10
    assert out["n_valid"] == 2
    assert out["n_failed"] == 1


def test_per_config_all_failed_yields_placeholders():
    from experiments.metrics.aggregate import _per_config

    pairs = [_pair("y", "s1", 1, 90.0, error="llm_error_template:timeout")]
    out = _per_config(pairs, [])["y"]
    assert out["n_valid"] == 0
    assert out["n_failed"] == 1
    assert out["latency_p50"] is None
    assert out["latency_p95"] is None
    # 无有效记录时指标为 None，回填时保留 not-yet-measured
    assert out["rouge_l"]["mean"] is None


def test_entity_f1_union_gold_covers_more_samples():
    """金标取"参考摘要∪正文"后，有实体的样本数应严格多于只用参考摘要。"""
    from experiments.metrics import entity_f1

    ref = "n8n: Expression Sandbox Escape via Class-Field Sanitizer Rebinding"
    content = "CVE-2026-86075 affects n8n 2.37.7 and 2.38.2; fix released."
    ref_only = entity_f1.gold_from_reference(ref)
    union = entity_f1.gold_from_reference(ref) | entity_f1.extract_entities(content)
    assert len(union) > len(ref_only)
    assert ("cve", "CVE-2026-86075") in union


def test_build_gold_supports_union_and_ref_only_modes():
    from experiments.metrics.entity_f1 import build_gold

    item = {"official_summary": "n8n vulnerability", "content": "CVE-2026-86075 in n8n 2.37.7"}
    union = build_gold(item, mode="union")
    ref_only = build_gold(item, mode="ref_only")
    assert ("cve", "CVE-2026-86075") in union
    assert ("cve", "CVE-2026-86075") not in ref_only
    assert len(union) >= len(ref_only)


def test_per_config_counts_repeats_and_items():
    from experiments.metrics.aggregate import _per_config

    pairs = [_pair("z", "s1", 1, 1.0), _pair("z", "s1", 2, 1.2), _pair("z", "s2", 1, 1.1)]
    out = _per_config(pairs, [])["z"]
    assert out["n_items"] == 2
    assert out["n_valid"] == 3
