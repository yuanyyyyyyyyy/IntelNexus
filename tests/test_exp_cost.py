"""成本折算测试：单价缺失必须返回 None（不得用估算值顶替）。"""
from __future__ import annotations

import json

import pytest

from experiments.cost import cost_model


@pytest.fixture
def pricing(monkeypatch):
    data = {
        "currency": "CNY",
        "cloud": {"qwen": {"flagship": {"input_per_1m_tokens": 2.0, "output_per_1m_tokens": 8.0},
                           "light": {"input_per_1m_tokens": None, "output_per_1m_tokens": None}}},
        "local": {"P_avg_watt": 120, "p_e_yuan_per_kwh": 0.6, "C_hw_yuan": 8000,
                  "T_life_years": 5, "D_utilization": 0.5},
    }
    monkeypatch.setattr(cost_model.config_loader, "pricing_config", lambda: data)
    return data


def test_cloud_cost_formula(pricing):
    # (2000 * 2 + 500 * 8) / 1e6 = 0.008 元
    assert cost_model.cloud_cost(2000, 500, "qwen", "flagship") == pytest.approx(0.008)


def test_cloud_cost_missing_price_is_none(pricing):
    assert cost_model.cloud_cost(2000, 500, "qwen", "light") is None


def test_cloud_cost_no_tokens_is_none(pricing):
    assert cost_model.cloud_cost(None, None) is None


def test_local_cost_matches_documented_formula(pricing):
    """电费 P/1000*T_h*p_e + 折旧 C_hw*T_h/(T_life*365*24*D)。"""
    hours = 10 / 3600
    energy = 120 / 1000 * hours * 0.6
    deprec = 8000 * hours / (5 * 365 * 24 * 0.5)
    assert cost_model.local_cost(10) == pytest.approx(energy + deprec)


def test_local_cost_none_without_latency(pricing):
    assert cost_model.local_cost(None) is None


def test_local_cost_none_when_params_missing(monkeypatch):
    monkeypatch.setattr(cost_model.config_loader, "pricing_config",
                        lambda: {"local": {"P_avg_watt": None}})
    assert cost_model.local_cost(10) is None


# ---------------------------------------------------------------------------
# 输入侧区间：云端输入 token 只有"自带提示词留痕"时才可信，旧记录是跨调用
# 代理值，必须以实测比值区间披露（表5 表注与 5.3 节引用该产物，禁止手算）
# ---------------------------------------------------------------------------
def _band_agg():
    return {
        "groups": {"cloud_flagship": "cloud", "cloud_light": "cloud", "qwen3:8b": "local"},
        "configs": {
            "cloud_flagship": {"cost_token_in": 0.0072, "cost_token_out": 0.0158,
                               "cost_per_item_mean": 0.023},
            "cloud_light": {"cost_token_in": 0.0023, "cost_token_out": 0.0043,
                            "cost_per_item_mean": 0.0066},
            "qwen3:8b": {"cost_per_item_mean": 0.025},
        },
    }


def test_input_token_band_uses_measured_ratios(tmp_path, monkeypatch):
    agg_path = tmp_path / "aggregate.json"
    agg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cost_model, "AGGREGATE", agg_path)
    monkeypatch.setattr(cost_model, "read_json", lambda _p: _band_agg())
    monkeypatch.setattr(cost_model, "cross_call_ratios",
                        lambda: {"available": True, "min": 0.75, "max": 1.0,
                                 "n_observations": 6, "n_samples": 3, "observations": []})
    band = cost_model.input_token_band()
    assert band["available"] is True
    entry = band["configs"]["cloud_flagship"]
    # 输入项按比值缩放，输出项不动
    assert entry["cost_token_in_range"] == [pytest.approx(0.0072 * 0.75), pytest.approx(0.0072)]
    low, high = entry["cost_per_item_range"]
    assert low == pytest.approx(0.0072 * 0.75 + 0.0158)
    assert high == pytest.approx(0.0072 * 1.0 + 0.0158)
    assert entry["local_higher_throughout"] is True
    assert entry["local_vs_cloud_pct_range"][0] < entry["local_vs_cloud_pct_range"][1]


def test_input_token_band_missing_aggregate(tmp_path, monkeypatch):
    monkeypatch.setattr(cost_model, "AGGREGATE", tmp_path / "nope.json")
    monkeypatch.setattr(cost_model, "cross_call_ratios",
                        lambda: {"available": True, "min": 0.75, "max": 1.0,
                                 "n_observations": 1, "n_samples": 1, "observations": []})
    band = cost_model.input_token_band()
    assert band["available"] is False
    assert "aggregate" in band["reason"]


def test_input_token_band_unavailable_without_cross_call_obs(monkeypatch):
    monkeypatch.setattr(cost_model, "cross_call_ratios",
                        lambda: {"available": False, "reason": "缺少 reports/token_recount.json"})
    band = cost_model.input_token_band()
    assert band["available"] is False
    assert "token_recount" in band["reason"]


def test_cross_call_ratios_reads_relabelled_legacy_calibration(tmp_path, monkeypatch):
    """区间只能来自被标注为跨调用的观测，不得读同调用校准段。"""
    payload = {
        "calibration": {"comparison_type": "same-call", "configs": {
            "cloud_flagship": {"rows": [{"sample_id": "s1", "api_tokens_in": 100,
                                         "prompt_tokens_in": 100}]}}},
        "calibration_cross_call": {"comparison_type": "cross-call", "configs": {
            "cloud_flagship": {"rows": [{"sample_id": "s1", "api_tokens_in": 1827,
                                         "recount_tokens_in": 2397},
                                        {"sample_id": "s2", "api_tokens_in": 1855,
                                         "recount_tokens_in": 2453}]}}},
    }
    p = tmp_path / "token_recount.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cost_model, "TOKEN_RECOUNT_PATH", p)
    out = cost_model.cross_call_ratios()
    assert out["available"] is True
    assert out["n_observations"] == 2 and out["n_samples"] == 2
    assert out["min"] == pytest.approx(0.7562, abs=1e-4)
    assert out["max"] == pytest.approx(0.7623, abs=1e-4)
