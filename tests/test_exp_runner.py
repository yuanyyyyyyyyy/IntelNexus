"""执行器测试：参数覆盖记录、错误统计与提示词留痕（离线，不调用模型）。"""
from __future__ import annotations

from dataclasses import asdict

from experiments.harness.runner import (
    RunRecord,
    _error_kinds,
    _param_overrides,
    _prompt_trace_summary,
)


def test_param_overrides_records_unit_input_limit():
    """统一的输入长度上限必须被记录，论文须说明与生产默认值(25000)的差异。"""
    exp_cfg = {"unit": {"input_max_chars": 8000}, "cloud": {}}
    ov = _param_overrides(exp_cfg, {"id": "qwen3:8b"})
    assert ov.get("input_max_chars") == 8000


def test_param_overrides_records_cloud_timeout_and_max_tokens():
    exp_cfg = {"unit": {}, "cloud": {"request_timeout": 300, "max_tokens": 1024, "input_max_chars": None}}
    ov = _param_overrides(exp_cfg, {"id": "cloud_flagship"})
    assert ov.get("request_timeout") == 300
    assert ov.get("max_tokens") == 1024
    assert "input_max_chars" not in ov  # 空值不记录


def test_param_overrides_records_streaming_false():
    """streaming=False 是显式覆盖（推理型模型流式静默会触发读超时），必须留痕。"""
    ov = _param_overrides({"unit": {}, "cloud": {"streaming": False}}, {"id": "cloud_flagship"})
    assert ov.get("streaming") is False


def test_param_overrides_skips_unset_streaming():
    ov = _param_overrides({"unit": {}, "cloud": {}}, {"id": "cloud_flagship"})
    assert "streaming" not in ov


def test_param_overrides_empty_when_nothing_overridden():
    assert _param_overrides({"unit": {}, "cloud": {}}, {"id": "x"}) == {}


def test_error_kinds_aggregates_counts():
    recs = [
        RunRecord(run_id="r", config="c", backend="ollama", sample_id="s1", repeat=1, latency_s=1.0,
                  error="llm_error_template:timeout", error_kind="timeout"),
        RunRecord(run_id="r", config="c", backend="ollama", sample_id="s2", repeat=1, latency_s=1.0,
                  error="llm_error_template:timeout", error_kind="timeout"),
        RunRecord(run_id="r", config="c", backend="ollama", sample_id="s3", repeat=1, latency_s=1.0),
    ]
    assert _error_kinds(recs) == {"timeout": 2}


# ---------------------------------------------------------------------------
# 提示词留痕：本次新增字段，旧记录（1800 条）没有，必须完全兼容
# ---------------------------------------------------------------------------
def _rec(sid, **kw):
    return RunRecord(run_id="r", config="c", backend="openai_compatible",
                     sample_id=sid, repeat=1, latency_s=1.0, **kw)


def test_run_record_tolerates_missing_prompt_fields():
    """旧记录读入/构造不得因为缺 prompt_* 字段而报错。"""
    rec = _rec("s1")
    assert rec.prompt_chars is None
    assert rec.prompt_calls == 0
    assert rec.prompt_sha256 is None
    assert _prompt_trace_summary([rec])["traced_records"] == 0


def test_run_record_serialises_prompt_fields():
    rec = _rec("s1", prompt_chars=1234, prompt_sha256="h" * 64, prompt_tokens=800,
               prompt_calls=1, prompt_render="chat_messages")
    d = asdict(rec)
    assert d["prompt_chars"] == 1234
    assert d["prompt_tokens"] == 800
    assert d["prompt_render"] == "chat_messages"


def test_prompt_trace_summary_reports_retries_and_coverage():
    recs = [
        _rec("s1", prompt_chars=100, prompt_sha256="a", prompt_tokens=50,
             prompt_calls=1, prompt_render="chat_messages"),
        _rec("s2", prompt_chars=120, prompt_sha256="a", prompt_tokens=60,
             prompt_calls=2, prompt_render="chat_messages"),   # 走了简化 prompt 重试
        _rec("s3"),
    ]
    s = _prompt_trace_summary(recs)
    assert s["traced_records"] == 2
    assert s["untraced_records"] == 1
    assert s["distinct_texts"] == 1
    assert s["retried_records"] == 1
    assert s["prompt_tokens_min"] == 50
    assert s["prompt_tokens_max"] == 60
    assert s["render"] == "chat_messages"
    # 分词器缺失时不得冒充分词器名（否则 manifest 会误导人工复核）
    assert s["tokenizer"] == ("Qwen/Qwen3-8B" if s["tokenizer_ready"] else None)


def test_prompt_trace_summary_counts_samples_whose_prompt_changed():
    """核心指标：同一样本在本 run 内出现多种提示词哈希。

    历史记录之所以只能"借用别次运行的值"，一是同样的样本在不同调用会拿到
    不同的提示词（运行期上下文注入 / 重试换用简化 prompt），二是代理值是
    各次调用之和而非单次值。distinct_texts 在正常情形下就约等于样本数，
    **不能**用它判断提示词是否稳定。
    """
    recs = [
        _rec("s1", prompt_chars=100, prompt_sha256="h1", prompt_tokens=50, prompt_calls=1),
        _rec("s1", prompt_chars=140, prompt_sha256="h2", prompt_tokens=70, prompt_calls=1),
        _rec("s2", prompt_chars=120, prompt_sha256="h3", prompt_tokens=60, prompt_calls=1),
        _rec("s2", prompt_chars=120, prompt_sha256="h3", prompt_tokens=60, prompt_calls=1),
    ]
    s = _prompt_trace_summary(recs)
    assert s["samples_with_multiple_texts"] == 1     # 只有 s1 的提示词变过
    assert s["distinct_texts"] == 3                  # 去重哈希数（≠ 稳定性指标）
    assert s["traced_records"] == 4
    assert s["retried_records"] == 0
