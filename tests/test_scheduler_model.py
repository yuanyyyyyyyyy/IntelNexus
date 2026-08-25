"""定时链路模型解析（scheduler_model）+ 注册表状态（scheduler_registry）测试。

P0 修复背景：调度器构造 AIBriefingAnalyzer(llm=None) 后由 analyzer 硬编码
加载 qwen2.5:7b，失败只进日志——定时简报静默以降级模板文案推送。
修复后解析逻辑收拢在 scheduler_model.resolve_scheduler_llm：
候选来自真实可用列表、逐个尝试构建实例，失败返回面向管理员的中文原因；
状态经 scheduler_registry.set_model_status 上报，UI 横幅消费。
"""
import pytest

from intelnexus.briefing import scheduler_model, scheduler_registry
from intelnexus.briefing.scheduler_model import _ordered_candidates, make_status


class FakeLLM:
    pass


@pytest.fixture(autouse=True)
def reset_registry_status():
    """隔离注册表全局状态。"""
    scheduler_registry.set_model_status(None, degraded=False)
    yield
    scheduler_registry.set_model_status(None, degraded=False)


def _patch_choices(monkeypatch, choices, get_llm_impl=None):
    """把解析依赖的三个外部入口替换为可控 stub（与实现的延迟导入一致）。"""
    monkeypatch.setattr(
        "intelnexus.core.llm.utils.get_model_choices", lambda: choices)
    monkeypatch.setattr(
        "intelnexus.core.llm.core.get_llm",
        get_llm_impl or (lambda name: FakeLLM()),
    )
    # is_vision_model 用真实实现（纯关键字匹配），顺带覆盖其过滤行为


def test_no_models_reports_degradation_reason(monkeypatch):
    _patch_choices(monkeypatch, [])
    llm, name, reason = scheduler_model.resolve_scheduler_llm()
    assert llm is None and name == ""
    assert "未检测到任何可用模型" in reason


def test_vision_only_candidates_are_filtered(monkeypatch):
    _patch_choices(monkeypatch, ["llava:13b", "moondream"])
    llm, _, reason = scheduler_model.resolve_scheduler_llm()
    assert llm is None
    assert "未检测到任何可用模型" in reason


def test_preferred_model_keeps_priority(monkeypatch):
    tried = []
    _patch_choices(monkeypatch, ["llama3", "qwen2.5:7b"],
                   get_llm_impl=lambda n: tried.append(n) or FakeLLM())
    llm, name, _ = scheduler_model.resolve_scheduler_llm()
    assert isinstance(llm, FakeLLM)
    # 历史默认最优先，保持旧硬编码行为兼容
    assert tried[0] == "qwen2.5:7b"
    assert name == "qwen2.5:7b"


def test_falls_back_to_first_text_model_when_preferred_missing(monkeypatch):
    _patch_choices(monkeypatch, ["llava:13b", "deepseek-r1:8b"])
    llm, name, _ = scheduler_model.resolve_scheduler_llm()
    assert isinstance(llm, FakeLLM)
    assert name == "deepseek-r1:8b"  # 视觉模型被跳过


def test_all_candidates_failing_reports_each_error(monkeypatch):
    def broken(name):
        raise ConnectionError(f"ollama down for {name}")

    _patch_choices(monkeypatch, ["a-model", "b-model"], get_llm_impl=broken)
    llm, name, reason = scheduler_model.resolve_scheduler_llm()
    assert llm is None and name == ""
    assert "候选模型全部加载失败" in reason
    assert "a-model" in reason and "ConnectionError" in reason


def test_ordered_candidates_prefers_qwen():
    ordered = _ordered_candidates(["z-model", "QWEN2.5:7B ", "a-model"])
    assert ordered[0] == "QWEN2.5:7B "  # 大小写/空格不敏感匹配，保留原始名


def test_make_status_shape():
    ok = make_status(True, "qwen2.5:7b")
    bad = make_status(False, "", "原因")
    assert ok == {"ok": True, "model": "qwen2.5:7b", "reason": ""}
    assert bad == {"ok": False, "model": "", "reason": "原因"}


# ---- scheduler_registry 状态存取 ----

def test_registry_roundtrip_degraded():
    scheduler_registry.set_model_status(None, degraded=True, reason="Ollama 未启动")
    st = scheduler_registry.get_model_status()
    assert st == {"model": None, "degraded": True, "reason": "Ollama 未启动"}


def test_registry_roundtrip_ok():
    scheduler_registry.set_model_status("qwen2.5:7b", degraded=False)
    st = scheduler_registry.get_model_status()
    assert st == {"model": "qwen2.5:7b", "degraded": False, "reason": ""}
