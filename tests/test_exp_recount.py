"""云端 token 重算与配置排除的测试（离线，不调用任何 API）。

重算的依据是"实际发生过的请求/响应文本"，因此必须保证：
1. 只填 ``tokens_in is None`` 的**云端**记录，绝不覆盖已有的 API usage；
2. 叠加后 ``usage_source`` 明确标为 ``recount``，使回填与 verify 显示真实来源；
3. 失败记录不参与（错误文本不是生成物）；
4. 被排除的配置（qwen3:4b）不进入汇总，但显式指定时仍可单独核查。
"""
from __future__ import annotations

import json

import pytest

from experiments import config_loader
from experiments.cost import token_recount
from experiments.metrics import aggregate


# ------------------------------------------------------------------ 配置排除
def test_excluded_configs_lists_withdrawn_arm():
    excluded = config_loader.excluded_configs()
    assert "qwen3:4b" in excluded
    assert "思考" in excluded["qwen3:4b"] or "1024" in excluded["qwen3:4b"]


def _write_run(root, run_id: str, config: str, backend: str, records):
    d = root / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "stage": "full", "config": config, "backend": backend,
        "repeat": 1, "n_items": len(records),
    }, ensure_ascii=False), encoding="utf-8")
    with open(d / "records.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_discover_runs_skips_excluded_config(tmp_path, monkeypatch):
    _write_run(tmp_path, "r-8b", "qwen3:8b", "ollama", [{"sample_id": "s1", "repeat": 1}])
    _write_run(tmp_path, "r-4b", "qwen3:4b", "ollama", [{"sample_id": "s1", "repeat": 1}])
    monkeypatch.setattr(aggregate, "RUNS_DIR", tmp_path)

    kept = {m.get("config") for m in aggregate._discover_runs(stage="full")}
    assert kept == {"qwen3:8b"}

    # 显式指定被撤配置时不排除，便于独立核查
    forced = {m.get("config") for m in aggregate._discover_runs(stage="full", configs=["qwen3:4b"])}
    assert forced == {"qwen3:4b"}


# ------------------------------------------------------------------ 叠加逻辑
def _recount_payload(**kwargs):
    base = {
        "usage_source": "recount",
        "tokenizer": {"model": "Qwen/Qwen3-8B"},
        "configs": {"run-cloud": {"s1": {"1": {"tokens_in": 2000, "tokens_out": 300}}}},
    }
    base.update(kwargs)
    return base


def test_overlay_fills_empty_cloud_tokens(monkeypatch):
    monkeypatch.setattr(token_recount, "load", lambda: _recount_payload())
    runs = [{
        "run_id": "run-cloud", "backend": "openai_compatible", "config": "cloud_flagship",
        "_records": [{"sample_id": "s1", "repeat": 1, "tokens_in": None, "tokens_out": None,
                      "usage_source": "none", "error": None}],
    }]
    info = token_recount.overlay(runs)
    rec = runs[0]["_records"][0]
    assert info["applied"] == 1
    assert rec["tokens_in"] == 2000 and rec["tokens_out"] == 300
    assert rec["usage_source"] == token_recount.SRC_RECOUNT_OWN


def test_overlay_labels_proxy_source(monkeypatch):
    """代理值（借用别次运行的提示词）必须与"该次请求自己的留痕"区分开，
    否则论文无法说明哪一格可信、哪一格只是区间中心。"""
    payload = _recount_payload()
    payload["configs"]["run-cloud"]["s1"]["1"]["tokens_in_source"] = token_recount.SRC_RECOUNT_PROXY
    monkeypatch.setattr(token_recount, "load", lambda: payload)
    runs = [{
        "run_id": "run-cloud", "backend": "openai_compatible", "config": "cloud_flagship",
        "_records": [{"sample_id": "s1", "repeat": 1, "tokens_in": None, "error": None}],
    }]
    info = token_recount.overlay(runs)
    assert runs[0]["_records"][0]["usage_source"] == token_recount.SRC_RECOUNT_PROXY
    assert info["by_source"][token_recount.SRC_RECOUNT_PROXY] == 1


def test_overlay_never_overwrites_existing_api_usage(monkeypatch):
    monkeypatch.setattr(token_recount, "load", lambda: _recount_payload())
    runs = [{
        "run_id": "run-cloud", "backend": "openai_compatible", "config": "cloud_flagship",
        "_records": [{"sample_id": "s1", "repeat": 1, "tokens_in": 111, "tokens_out": 22,
                      "usage_source": "api_usage", "error": None}],
    }]
    info = token_recount.overlay(runs)
    assert info["applied"] == 0
    assert runs[0]["_records"][0]["tokens_in"] == 111
    assert runs[0]["_records"][0]["usage_source"] == "api_usage"


def test_overlay_ignores_local_backend(monkeypatch):
    monkeypatch.setattr(token_recount, "load", lambda: _recount_payload())
    runs = [{
        "run_id": "run-cloud", "backend": "ollama", "config": "qwen3:8b",
        "_records": [{"sample_id": "s1", "repeat": 1, "tokens_in": None, "error": None}],
    }]
    assert token_recount.overlay(runs)["applied"] == 0
    assert runs[0]["_records"][0]["tokens_in"] is None


def test_overlay_skips_failed_records(monkeypatch):
    monkeypatch.setattr(token_recount, "load", lambda: _recount_payload())
    runs = [{
        "run_id": "run-cloud", "backend": "openai_compatible", "config": "cloud_flagship",
        "_records": [{"sample_id": "s1", "repeat": 1, "tokens_in": None, "error": "timeout"}],
    }]
    assert token_recount.overlay(runs)["applied"] == 0


def test_overlay_without_recount_file_is_noop(monkeypatch):
    monkeypatch.setattr(token_recount, "load", lambda: {})
    runs = [{"run_id": "x", "backend": "openai_compatible",
             "_records": [{"sample_id": "s1", "repeat": 1, "tokens_in": None}]}]
    info = token_recount.overlay(runs)
    assert info["available"] is False and info["applied"] == 0


# ------------------------------------------------------------------ 偏差计算
@pytest.mark.parametrize("api,rec,expected", [
    (1000, 1000, 0.0),
    (1000, 1100, 10.0),
    (1000, 900, -10.0),
    (None, 5, None),
    (0, 5, None),
    (1000, None, None),
])
def test_dev_percent(api, rec, expected):
    val = token_recount._dev(api, rec)
    if expected is None:
        assert val is None
    else:
        assert val == pytest.approx(expected)


# ------------------------------------------------------------------ 分词器
def test_count_tokens_returns_none_for_empty_text():
    assert token_recount.count_tokens("") is None
    assert token_recount.count_tokens(None) is None


def test_count_tokens_uses_qwen_tokenizer():
    """分词器缺失则跳过（离线环境不该因缺模型而失败）。"""
    if not token_recount.tokenizer_path().exists():
        pytest.skip("Qwen 分词器未下载，跳过")
    n = token_recount.count_tokens("CVE-2026-12345 是一处远程代码执行漏洞。")
    assert isinstance(n, int) and n > 0


def test_tokenizer_file_is_pinned_model():
    assert token_recount.TOKENIZER_MODEL == "Qwen/Qwen3-8B"


# ------------------------------------------------------------------ 代理口径
def test_proxy_spread_measures_within_sample_variation(tmp_path, monkeypatch):
    """同一提示词在不同调用间会变长：这是"输入侧只能给区间"的直接证据。"""
    _write_run(tmp_path, "r-8b", "qwen3:8b", "ollama", [
        {"sample_id": "s1", "repeat": 1, "tokens_in": 1857},
        {"sample_id": "s1", "repeat": 2, "tokens_in": 4850},
        {"sample_id": "s2", "repeat": 1, "tokens_in": 2397},
    ])
    monkeypatch.setattr(token_recount, "RUNS_DIR", tmp_path)
    sp = token_recount.proxy_spread()
    assert sp["samples"] == 2
    assert sp["samples_with_spread"] == 1
    assert sp["max_spread"] == 2993
    assert sp["rows"][0]["sample_id"] == "s1"          # 极差最大的排最前
    # 重复间中位数 = (1857+4850)/2：两个观测差 2993 token，中位数落在中间，
    # 对"某一次调用到底发了多少"没有任何保证 —— 这正是需要区间的原因
    assert token_recount.local_prompt_tokens()["s1"] == 3353


def test_same_call_agreement_compares_our_count_with_server(tmp_path, monkeypatch):
    """同一次生成内的口径对照：比的是"计数方法"，不是"提示词是否变化"。"""
    _write_run(tmp_path, "r-8b", "qwen3:8b", "ollama", [
        {"sample_id": "s1", "repeat": 1, "prompt_tokens_sum": 2379, "prompt_calls": 2,
         "tokens_in": 2397},
        {"sample_id": "s2", "repeat": 1, "prompt_tokens_sum": 1000, "prompt_calls": 1,
         "tokens_in": 1000},
        {"sample_id": "s3", "repeat": 1, "tokens_in": 1200},      # 无留痕：跳过
        {"sample_id": "s4", "repeat": 1, "prompt_tokens_sum": 5, "tokens_in": 9, "error": "x"},
    ])
    monkeypatch.setattr(token_recount, "RUNS_DIR", tmp_path)
    out = token_recount.same_call_agreement()
    assert out["n_records"] == 2
    assert out["max_abs_dev_pct"] == pytest.approx(0.751, abs=0.01)
    assert out["rows"][0]["prompt_calls"] == 2


def test_same_call_agreement_unavailable_without_traces(tmp_path, monkeypatch):
    _write_run(tmp_path, "r-8b", "qwen3:8b", "ollama", [{"sample_id": "s1", "tokens_in": 100}])
    monkeypatch.setattr(token_recount, "RUNS_DIR", tmp_path)
    out = token_recount.same_call_agreement()
    assert out["available"] is False
    assert out["n_records"] == 0


def test_build_prefers_own_prompt_over_proxy(tmp_path, monkeypatch):
    """新记录用自己留痕的提示词，旧记录才回退代理值，两者来源必须分开计数。"""
    if not token_recount.tokenizer_ready():
        pytest.skip("Qwen 分词器未下载，跳过")
    _write_run(tmp_path, "r-cloud", "cloud_flagship", "openai_compatible", [
        {"sample_id": "s1", "repeat": 1, "prompt_tokens": 1234},
        {"sample_id": "s2", "repeat": 1},
    ])
    monkeypatch.setattr(token_recount, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(token_recount, "RECOUNT_PATH", tmp_path / "token_recount.json")
    monkeypatch.setattr(token_recount, "local_prompt_tokens", lambda: {"s2": 999})
    data = token_recount.build(force=True)
    cells = data["configs"]["r-cloud"]
    assert cells["s1"]["1"]["tokens_in"] == 1234
    assert cells["s1"]["1"]["tokens_in_source"] == token_recount.SRC_RECOUNT_OWN
    assert cells["s2"]["1"]["tokens_in"] == 999
    assert cells["s2"]["1"]["tokens_in_source"] == token_recount.SRC_RECOUNT_PROXY
    assert data["stats"]["tin_own_prompt"] == 1
    assert data["stats"]["tin_proxy"] == 1


# ------------------------------------------------------------------ 校准语义
def test_legacy_calibration_is_relabelled_as_cross_call(monkeypatch):
    """历史 32.237% 必须被写成"跨调用比较"，不能被当作分词器计数误差。"""
    legacy = {"measured_at": "2026-09-15T20:00:00Z", "n_items": 3, "configs": {
        "cloud_flagship": {"model": "qwen3-max", "max_abs_dev_pct": 32.237,
                           "rows": [{"sample_id": "s1", "api_tokens_in": 1827,
                                     "recount_tokens_in": 2397}]}}}
    monkeypatch.setattr(token_recount, "proxy_spread", lambda ids=None: {
        "config": "qwen3:8b", "samples": 1, "samples_with_spread": 1, "max_spread": 570,
        "median_spread": 570, "rows": [{"sample_id": "s1", "spread": 570}]})
    out = token_recount.relabel_legacy_calibration({"calibration": legacy})
    assert out["comparison_type"] == "cross-call"
    # 归因必须是"调用次数口径不可比"，并明确否定计数误差（实测复算 0.751%）
    assert "口径不可比" in out["confound"]
    assert "调用次数" in out["confound"] and "分词器误差" in out["confound"]
    assert "0.751%" in out["confound"]
    assert out["configs"]["cloud_flagship"]["max_abs_dev_pct"] == 32.237
    assert out["proxy_spread_evidence"]["max_spread"] == 570


def test_relabel_refreshes_note_but_keeps_observations(monkeypatch):
    """已重标注过的记录也要跟着常量刷新，且观测行不得丢失。

    否则核查结论更新后重建产物会因幂等短路留下旧文案（实测踩到过）。
    """
    prev = {"calibration_cross_call": {
        "comparison_type": "cross-call", "confound": "旧文案",
        "configs": {"cloud_flagship": {"rows": [{"sample_id": "s1"}]}}}}
    monkeypatch.setattr(token_recount, "proxy_spread", lambda ids=None: {"samples": 0})
    out = token_recount.relabel_legacy_calibration(prev)
    assert out["comparison_type"] == "cross-call"
    assert out["confound"] == token_recount.CROSS_CALL_NOTE
    assert out["configs"]["cloud_flagship"]["rows"] == [{"sample_id": "s1"}]


def test_relabel_ignores_same_call_calibration():
    same_call = {"comparison_type": "same-call", "configs": {}}
    assert token_recount.relabel_legacy_calibration({"calibration": same_call}) is None
    assert token_recount._same_call_calibration({"calibration": same_call}) is same_call


def test_tokenizer_ready_does_not_download(monkeypatch, tmp_path):
    monkeypatch.setattr(token_recount, "TOKENIZER_DIR", tmp_path)
    assert token_recount.tokenizer_ready() is False


def test_count_tokens_without_tokenizer_does_not_download(monkeypatch):
    """``ensure=False`` 是实验运行期埋点的口径：缺分词器只返回 None。

    埋点不得因为计数依赖缺失就联网下载或把实验跑挂（见 PROTOCOL 偏差记录）。
    """
    monkeypatch.setattr(token_recount, "_TOKENIZER", None)
    monkeypatch.setattr(token_recount, "tokenizer_ready", lambda: False)

    def _boom(*a, **k):
        raise AssertionError("ensure=False 时不应触发分词器下载")

    monkeypatch.setattr(token_recount, "ensure_tokenizer", _boom)
    assert token_recount.count_tokens("文本", ensure=False) is None
