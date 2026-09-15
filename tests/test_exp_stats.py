"""统计检验的离线测试：边界与已知性质。"""
from __future__ import annotations

from experiments.metrics import stats


def test_wilcoxon_all_zero_differences_yields_p_one():
    r = stats.wilcoxon_signed_rank([1, 2, 3], [1, 2, 3])
    assert r["p_value"] == 1.0
    assert r["statistic"] == 0.0


def test_wilcoxon_missing_pairs_are_dropped():
    r = stats.wilcoxon_signed_rank([1, 2, None, 4], [1, 3, 9, 4])
    assert r["n"] == 3


def test_wilcoxon_consistent_shift_is_significant_for_large_n():
    a = [i * 1.0 for i in range(20)]
    b = [i + 5.0 for i in range(20)]
    r = stats.wilcoxon_signed_rank(a, b)
    assert r["p_value"] < 0.01


def test_cliffs_delta_identical_is_zero():
    xs = [1, 2, 3, 4]
    assert stats.cliffs_delta(xs, list(xs)) == 0.0


def test_cliffs_delta_complete_dominance_is_one():
    assert stats.cliffs_delta([10, 11, 12], [1, 2, 3]) == 1.0
    assert stats.cliffs_delta([1, 2, 3], [10, 11, 12]) == -1.0


def test_cliffs_delta_none_when_no_overlap_data():
    assert stats.cliffs_delta([], [1]) is None


def test_holm_is_monotone_and_caps_at_one():
    adj = stats.holm([0.001, 0.02, 0.04, 0.9])
    values = [a["p_adj"] for a in adj]
    assert values == sorted(values)
    assert all(v <= 1.0 for v in values)


def test_holm_first_comparison_equals_bonferroni():
    adj = stats.holm([0.01, 0.02, 0.03])
    assert abs(adj[0]["p_adj"] - 0.03) < 1e-9


def test_holm_stops_after_first_non_significant():
    adj = stats.holm([0.001, 0.5, 0.5])
    assert adj[0]["significant"] is True
    assert adj[1]["significant"] is False
    assert adj[2]["significant"] is False


def test_holm_handles_none():
    adj = stats.holm([0.01, None])
    assert adj[1]["p_adj"] is None


def test_compare_family_adds_adjusted_fields():
    a = [1, 2, 3, 4, 5, 6]
    b = [2, 3, 4, 5, 6, 7]
    comps = [stats.compare_pair("x", "y", "rouge_l", a, b)]
    fam = stats.compare_family(comps)
    assert "p_adj" in fam[0] and "significant" in fam[0]
    assert fam[0]["cliffs_delta"] is not None


def test_effect_size_labels():
    assert stats.effect_size_label(None) == "not-yet-measured"
    assert stats.effect_size_label(0.01) == "negligible"
    assert stats.effect_size_label(0.9) == "large"
