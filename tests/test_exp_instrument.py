"""埋点与构造逻辑的离线测试（不依赖 Ollama / 云端 API）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

from experiments.common import PLACEHOLDER
from experiments.harness import instrument
from experiments.harness.instrument import (
    UsageAccumulator,
    _filter_params,
    common_llm_params,
)


class _FakeMsg:
    def __init__(self, usage=None, meta=None):
        self.usage_metadata = usage
        self.response_metadata = meta or {}


class _FakeGeneration:
    """模拟 LangChain 的 ChatGeneration（承载 .message）。"""

    def __init__(self, message):
        self.message = message


class _FakeResp:
    def __init__(self, msg, llm_output=None):
        self.generations = [[_FakeGeneration(msg)]]
        self.llm_output = llm_output or {}


def test_usage_from_usage_metadata():
    acc = UsageAccumulator()
    acc.on_end(_FakeResp(_FakeMsg(usage={"input_tokens": 120, "output_tokens": 30},
                                  meta={"model": "qwen-max-2026-01"})))
    d = acc.as_dict()
    assert d["tokens_in"] == 120
    assert d["tokens_out"] == 30
    assert d["usage_source"] == "api_usage"
    assert d["model_version"] == "qwen-max-2026-01"


def test_usage_from_ollama_response_metadata():
    acc = UsageAccumulator()
    acc.on_end(_FakeResp(_FakeMsg(usage=None, meta={"prompt_eval_count": 900, "eval_count": 150})))
    d = acc.as_dict()
    assert d["tokens_in"] == 900
    assert d["tokens_out"] == 150
    assert d["usage_source"] == "api_usage"   # 同属可计量来源，来源标签一致


def test_usage_none_when_missing():
    """取不到用量时必须标记 none，不得估算。"""
    acc = UsageAccumulator()
    acc.on_end(_FakeResp(_FakeMsg(usage=None, meta={})))
    d = acc.as_dict()
    assert d["tokens_in"] is None
    assert d["usage_source"] == "none"


def test_usage_from_llm_output_token_usage():
    acc = UsageAccumulator()
    acc.on_end(_FakeResp(_FakeMsg(usage=None, meta={}),
                         llm_output={"token_usage": {"prompt_tokens": 11, "completion_tokens": 7}}))
    d = acc.as_dict()
    assert (d["tokens_in"], d["tokens_out"]) == (11, 7)


def test_usage_accumulates_across_calls():
    acc = UsageAccumulator()
    acc.on_end(_FakeResp(_FakeMsg(usage={"input_tokens": 10, "output_tokens": 5})))
    acc.on_end(_FakeResp(_FakeMsg(usage={"input_tokens": 20, "output_tokens": 5})))
    assert acc.as_dict()["tokens_in"] == 30
    assert acc.calls == 2


def test_filter_params_keeps_only_declared_fields():
    class _Model:
        model_fields = {"temperature": None, "model": None}

    kept, dropped = _filter_params(_Model, {"temperature": 0, "model": "x", "bogus": 1})
    assert kept == {"temperature": 0, "model": "x"}
    assert dropped == ["bogus"]


def test_filter_params_without_introspection_keeps_all():
    class _Plain:
        pass

    kept, dropped = _filter_params(_Plain, {"a": 1})
    assert kept == {"a": 1} and dropped == []


def test_filter_params_keeps_pydantic_aliases():
    """ChatOpenAI 的字段真名是 openai_api_key / openai_api_base，
    api_key 与 base_url 只是别名。按字段名过滤会把它们丢掉，
    导致请求缺少凭据并打到默认的 api.openai.com（国内不可达）→ 超时。"""
    class _Field:
        def __init__(self, alias):
            self.alias = alias

    class _Model:
        model_fields = {
            "openai_api_key": _Field("api_key"),
            "openai_api_base": _Field("base_url"),
            "request_timeout": _Field("timeout"),
            "streaming": _Field(None),
        }

    kept, dropped = _filter_params(_Model, {
        "api_key": "k", "base_url": "https://example.invalid/v1",
        "request_timeout": 300, "streaming": True, "bogus": 1,
    })
    assert kept["api_key"] == "k"
    assert kept["base_url"] == "https://example.invalid/v1"
    assert kept["request_timeout"] == 300
    assert kept["streaming"] is True
    assert dropped == ["bogus"]


def test_build_llm_keeps_credentials_and_base_url(monkeypatch):
    """端到端防线：构造云端客户端时 api_key 与 base_url 必须真的传进去。"""
    import langchain_openai

    captured = {}

    class _F:
        def __init__(self, alias=None):
            self.alias = alias

    class _FakeChat:
        # 与真实 ChatOpenAI 一致：真名字段 + 别名
        model_fields = {"openai_api_key": _F("api_key"), "openai_api_base": _F("base_url"),
                        "model": _F(), "streaming": _F()}

        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChat)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "secret")
    exp_cfg = {"configs": [], "ollama": {"options": {}},
               "cloud": {"providers": [{"name": "qwen", "env_key": "DASHSCOPE_API_KEY",
                                        "base_url": "https://dashscope.example/v1"}]}}
    cfg = {"id": "cloud_flagship", "backend": "openai_compatible", "provider": "qwen",
           "tier": "flagship", "model": "qwen3-max"}
    instrument.build_llm(cfg, exp_cfg, seed=1)
    assert captured["api_key"] == "secret"
    assert captured["base_url"] == "https://dashscope.example/v1"


def test_common_llm_params_matches_paper_table2():
    """表2 声称的温度/超时/重试必须与代码一致。"""
    p = common_llm_params()
    assert p["temperature"] == 0
    assert p["request_timeout"] == 120
    assert p["max_retries"] == 3


def test_placeholder_constant():
    assert PLACEHOLDER == "not-yet-measured"


# ---------------------------------------------------------------------------
# 错误模板识别：generate_summary 吞掉异常后返回错误文本，必须判为失败
# ---------------------------------------------------------------------------
TIMEOUT_TEMPLATE = """## 一、执行摘要

报告生成请求超时，可能因网络延迟或模型响应过慢导致。

## 三、错误详情

API 请求超时，模型未能在规定时间内返回结果。
"""

GENERIC_TEMPLATE = """## 一、执行摘要

报告生成过程中遇到错误。

## 二、错误信息

Connection error.
"""

NORMAL_OUTPUT = """## TL;DR 情报速览
Apache HTTP Server 存在路径遍历漏洞（CVE-2021-41773），建议升级至 2.4.51。
"""


def test_is_error_template_detects_timeout():
    assert instrument.is_error_template(TIMEOUT_TEMPLATE) is True


def test_is_error_template_detects_generic_error():
    assert instrument.is_error_template(GENERIC_TEMPLATE) is True


def test_is_error_template_false_for_normal_output():
    assert instrument.is_error_template(NORMAL_OUTPUT) is False
    assert instrument.is_error_template("") is False


def test_generate_once_marks_error_template_as_failure(monkeypatch):
    """错误模板必须被判为失败：文本清空、error 置位、error_kind=timeout。"""
    monkeypatch.setattr("intelnexus.core.llm.core.generate_summary",
                        lambda *a, **k: TIMEOUT_TEMPLATE)
    res = instrument.generate_once(object(), {"id": "x", "url": "u", "content": "c", "title": "t"})
    assert res.text == ""
    assert res.error is not None
    assert res.error_kind == "timeout"


def test_generate_once_marks_generic_error_template(monkeypatch):
    monkeypatch.setattr("intelnexus.core.llm.core.generate_summary",
                        lambda *a, **k: GENERIC_TEMPLATE)
    res = instrument.generate_once(object(), {"id": "x", "url": "u", "content": "c", "title": "t"})
    assert res.text == ""
    assert res.error_kind == "generic"


def test_generate_once_reports_per_item_token_delta(monkeypatch):
    """同一 accumulator 跨条目复用时，必须返回本条的增量而非累计值。"""
    acc = instrument.UsageAccumulator()

    def fake(llm, q, content, search_mode="all", **kw):
        acc.on_end(_FakeResp(_FakeMsg(usage={"input_tokens": 10, "output_tokens": 5})))
        return NORMAL_OUTPUT

    monkeypatch.setattr("intelnexus.core.llm.core.generate_summary", fake)
    first = instrument.generate_once(object(), {"id": "a", "content": "c"}, usage=acc)
    second = instrument.generate_once(object(), {"id": "b", "content": "c"}, usage=acc)
    assert first.usage["tokens_in"] == 10
    assert second.usage["tokens_in"] == 10   # 增量，不是 20


def test_build_llm_merges_per_config_ollama_options(monkeypatch):
    """每配置的 options 需覆盖全局 options（如 qwen3:4b 关闭思考模式）。

    背景：qwen3:4b 默认开启思考，1024 token 预算被思考耗尽、content 为空，
    整档输出 0 字符。关闭思考是该模型在此任务上可用的必要条件。
    """
    import langchain_ollama

    captured = {}

    class _FakeOllama:
        model_fields = {"model": None, "base_url": None, "num_ctx": None,
                        "num_predict": None, "reasoning": None, "seed": None}

        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(langchain_ollama, "ChatOllama", _FakeOllama)
    exp_cfg = {"ollama": {"options": {"num_ctx": 4096, "num_predict": 1024}},
               "cloud": {}}
    cfg = {"id": "qwen3:4b", "backend": "ollama", "model": "qwen3:4b",
           "options": {"reasoning": False}}
    instrument.build_llm(cfg, exp_cfg, seed=1)
    assert captured["num_ctx"] == 4096          # 全局仍生效
    assert captured["num_predict"] == 1024
    assert captured["reasoning"] is False       # 每配置覆盖生效


def test_build_llm_applies_cloud_streaming_and_limits(monkeypatch):
    """cloud 段的 streaming/timeout/max_tokens 覆盖必须真正作用到客户端构造。"""
    import langchain_openai

    captured = {}

    class _FakeChat:
        model_fields = {"model": None, "api_key": None, "base_url": None, "temperature": None,
                        "streaming": None, "seed": None, "max_tokens": None,
                        "request_timeout": None, "max_retries": None}

        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChat)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    exp_cfg = {
        "configs": [],
        "ollama": {"options": {}},
        "cloud": {
            "providers": [{"name": "qwen", "env_key": "DASHSCOPE_API_KEY",
                           "base_url": "https://example.invalid/v1"}],
            "streaming": False, "request_timeout": 300, "max_tokens": 1024,
        },
    }
    cfg = {"id": "cloud_flagship", "backend": "openai_compatible", "provider": "qwen",
           "tier": "flagship", "model": "qwen3-max"}
    binding = instrument.build_llm(cfg, exp_cfg, seed=7)
    assert binding.model == "qwen3-max"
    assert captured["streaming"] is False        # False 必须生效，不能因 falsy 被跳过
    assert captured["request_timeout"] == 300
    assert captured["max_tokens"] == 1024


def test_generate_once_keeps_normal_output(monkeypatch):
    monkeypatch.setattr("intelnexus.core.llm.core.generate_summary",
                        lambda *a, **k: NORMAL_OUTPUT)
    res = instrument.generate_once(object(), {"id": "x", "url": "u", "content": "c", "title": "t"})
    assert res.error is None
    assert res.text == NORMAL_OUTPUT
    assert res.latency_s >= 0


# ---------------------------------------------------------------------------
# 提示词留痕：chat 模型触发的是 on_chat_model_start（langchain_core 1.6
# chat_models.py:762），只挂 on_llm_start 会完全抓不到；且该字段是"最后一次
# 调用的值"，必须按条清零，否则会串到上一条样本。
# ---------------------------------------------------------------------------
class _FakeMessage:
    def __init__(self, content, type_="human"):
        self.content = content
        self.type = type_


def test_render_prompts_handles_chat_messages():
    text, render = instrument.render_prompts(
        [[_FakeMessage("问题", "human"), _FakeMessage("正文", "system")]])
    assert render == instrument.PROMPT_RENDER_CHAT
    assert "human: 问题" in text
    assert "system: 正文" in text


def test_render_prompts_handles_plain_prompt_list():
    text, render = instrument.render_prompts(["hello", "world"])
    assert render == instrument.PROMPT_RENDER_TEXT
    assert text == "hello\nworld"


def test_render_prompts_extracts_text_blocks_only():
    """多模态内容块只取文本，避免把图片 URL 当成提示词长度。"""
    msg = _FakeMessage([{"type": "text", "text": "A"},
                        {"type": "image_url", "image_url": "http://x/y.png"}])
    text, _ = instrument.render_prompts([[msg]])
    assert "A" in text
    assert "y.png" not in text


def test_render_prompts_empty():
    assert instrument.render_prompts([])[0] == ""
    assert instrument.render_prompts(None)[0] == ""


def test_on_start_records_chars_hash_and_render():
    acc = UsageAccumulator()
    acc.on_start([[_FakeMessage("x" * 10, "human")]])
    d = acc.as_dict()
    assert d["prompt_calls"] == 1
    assert d["prompt_chars"] == len("human: " + "x" * 10)
    assert d["prompt_render"] == instrument.PROMPT_RENDER_CHAT
    assert len(d["prompt_sha256"]) == 64


def test_on_start_defers_token_encoding():
    """回调只做廉价操作：token 编码约 46 ms/次、首次装载分词器约 600 ms，
    若在回调里做就落进 generate_once 的计时窗，会抬高 P50/P95。"""
    from experiments.cost import token_recount

    acc = UsageAccumulator()
    acc.on_start([[_FakeMessage("提示词正文")]])
    assert acc.prompt_tokens is None            # 回调内不编码
    n = acc.finalize_prompt_tokens()            # 窗口外补算
    if token_recount.tokenizer_ready():
        assert isinstance(n, int) and n > 0
    else:
        assert n is None                        # 离线环境只降级，不抛错


def test_finalize_records_last_call_and_sum():
    """重试会发两次请求：最后一次的值与服务端"各次之和"是两件事，都必须留。

    计费口径（以及 API 累计上报的 tokens_in）是各次输入之和，只留最后一次
    会把重试那一次的输入漏掉。
    """
    from experiments.cost import token_recount

    if not token_recount.tokenizer_ready():
        pytest.skip("Qwen 分词器未下载，跳过")
    acc = UsageAccumulator()
    acc.on_start([[_FakeMessage("很长很长的原始提示词" * 20, "system"),
                   _FakeMessage("正文", "human")]])
    acc.on_start([[_FakeMessage("简化", "system"), _FakeMessage("正文", "human")]])
    acc.finalize_prompt_tokens()
    assert acc.prompt_calls == 2
    assert acc.prompt_tokens_sum > acc.prompt_tokens      # 之和大于最后一次
    assert acc.prompt_tokens > 0


def test_generate_once_fills_prompt_tokens_after_timing(monkeypatch):
    from experiments.cost import token_recount

    acc = instrument.UsageAccumulator()

    def fake(llm, q, content, search_mode="all", **kw):
        acc.on_start([[_FakeMessage("提示词" * 5)]])
        acc.on_end(_FakeResp(_FakeMsg(usage={"input_tokens": 7, "output_tokens": 3})))
        return NORMAL_OUTPUT

    monkeypatch.setattr("intelnexus.core.llm.core.generate_summary", fake)
    res = instrument.generate_once(object(), {"id": "a", "content": "c"}, usage=acc)
    if token_recount.tokenizer_ready():
        assert res.usage["prompt_tokens"] > 0
        assert res.usage["prompt_chars"] > 0


def test_generate_once_reports_missing_usage_instead_of_zero(monkeypatch):
    """上一条有用量、本条没有时，差值会算出 0：0 会被读成"实测为零"，
    且 usage_source 会沿留上一条的 api_usage，两者都必须归位为缺失。"""
    acc = instrument.UsageAccumulator()
    state = {"first": True}

    def fake(llm, q, content, search_mode="all", **kw):
        if state["first"]:
            state["first"] = False
            acc.on_end(_FakeResp(_FakeMsg(usage={"input_tokens": 10, "output_tokens": 5})))
        return NORMAL_OUTPUT

    monkeypatch.setattr("intelnexus.core.llm.core.generate_summary", fake)
    first = instrument.generate_once(object(), {"id": "a", "content": "c"}, usage=acc)
    second = instrument.generate_once(object(), {"id": "b", "content": "c"}, usage=acc)
    assert first.usage["tokens_in"] == 10
    assert first.usage["usage_source"] == "api_usage"
    assert second.usage["tokens_in"] is None
    assert second.usage["tokens_out"] is None
    assert second.usage["usage_source"] == "none"


def test_real_chain_triggers_chat_model_start_once(monkeypatch):
    """用与 core.py 同形的真链（ChatPromptTemplate | llm | 解析器）锁死不变量：

    chat 模型只触发 ``on_chat_model_start``（langchain_core 1.6 chat_models.py:762），
    只挂 ``on_llm_start`` 会一条都抓不到；两条都挂也不得翻倍。
    该不变量是本次改动的全部动机，升级 langchain 后最易静默失效。
    """
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.prompts import ChatPromptTemplate

    class _Echo(BaseChatModel):
        @property
        def _llm_type(self) -> str:  # noqa: D102
            return "echo-test"

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: D102
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="OK"))])

    acc = UsageAccumulator()
    llm = _Echo(callbacks=[instrument.make_callback_handler(acc)])
    chain = (ChatPromptTemplate([("system", "你是情报分析员"),
                                 ("user", "正文：{content}")]) | llm | StrOutputParser())
    assert chain.invoke({"content": "CVE-2026-12345"}) == "OK"
    assert acc.prompt_calls == 1
    assert acc.prompt_render == instrument.PROMPT_RENDER_CHAT
    assert "CVE-2026-12345" in (acc.prompt_text or "")


def test_prompt_sha256_stable_for_same_prompt():
    """同提示词必须同哈希：这是事后判断"提示词有没有变"的唯一手段。"""
    a, b = UsageAccumulator(), UsageAccumulator()
    for acc in (a, b):
        acc.on_start([[_FakeMessage("同一提示词")]])
    assert a.prompt_sha256 == b.prompt_sha256
    c = UsageAccumulator()
    c.on_start([[_FakeMessage("换过的提示词")]])
    assert c.prompt_sha256 != a.prompt_sha256


def test_on_start_keeps_last_call_and_counts_retries():
    """输出校验失败会用简化 prompt 重试：字段取最后一次，调用次数另记。"""
    acc = UsageAccumulator()
    acc.on_start([[_FakeMessage("很长" * 50)]])
    first = acc.prompt_chars
    acc.on_start([[_FakeMessage("短")]])
    assert acc.prompt_calls == 2
    assert acc.prompt_chars < first


def test_callback_handler_registers_chat_and_llm_start():
    acc = UsageAccumulator()
    cb = instrument.make_callback_handler(acc)
    assert cb is not None
    cb.on_chat_model_start({}, [[_FakeMessage("问题")]], invocation_params={})
    assert acc.prompt_calls == 1
    cb.on_llm_start({}, ["纯文本提示"])
    assert acc.prompt_calls == 2


def test_generate_once_resets_prompt_trace_between_items(monkeypatch):
    """本条没发请求时不得带回上一条的提示词（字段是"值"不是"计数"）。"""
    acc = instrument.UsageAccumulator()
    calls = {"n": 0}

    def fake(llm, q, content, search_mode="all", **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            acc.on_start([[_FakeMessage("第一条的提示词")]])
        acc.on_end(_FakeResp(_FakeMsg(usage={"input_tokens": 10, "output_tokens": 5})))
        return NORMAL_OUTPUT

    monkeypatch.setattr("intelnexus.core.llm.core.generate_summary", fake)
    first = instrument.generate_once(object(), {"id": "a", "content": "c"}, usage=acc)
    second = instrument.generate_once(object(), {"id": "b", "content": "c"}, usage=acc)
    assert first.usage["prompt_chars"] is not None
    assert first.usage["prompt_calls"] == 1
    assert second.usage["prompt_chars"] is None
    assert second.usage["prompt_calls"] == 0
    assert second.usage["prompt_sha256"] is None


def test_count_prompt_tokens_never_breaks_generation(monkeypatch):
    """计数依赖出问题只能降级为 None，不允许把实验跑挂。"""
    import experiments.cost.token_recount as tr

    def _boom(*a, **k):
        raise RuntimeError("tokenizer broken")

    monkeypatch.setattr(tr, "count_tokens", _boom)
    assert instrument.count_prompt_tokens("任意文本") is None
