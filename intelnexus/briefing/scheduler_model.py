"""定时简报模型解析
================
定时推送链路没有 UI 侧栏的模型选择器。旧实现构造
AIBriefingAnalyzer(llm=None) 后由 analyzer 兜底硬编码加载
"qwen2.5:7b"，失败只进日志——定时简报会全程以无 LLM 的
降级模板文案推送给订阅者，且管理员不可感知。

本模块提供确定性的解析入口：
1. 候选来自 get_model_choices()（用户自定义模型优先，其次 Ollama 探测），
   并过滤掉不适合长文本情报分析的视觉模型；
2. 逐个候选尝试构建 LLM 实例；
3. 全部失败时返回 None + 面向用户的中文原因（供状态横幅展示）。
"""

from typing import Optional, Tuple

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 最多尝试前 N 个候选，避免大量坏模型拖慢执行
_MAX_CANDIDATES = 3

# 历史默认模型：若可用则最优先（保持旧硬编码行为的兼容），否则取首个文本候选
_PREFERRED_MODEL = "qwen2.5:7b"


def _ordered_candidates(choices):
    """按尝试顺序排列候选：首选模型 → 其余（保持 get_model_choices 的排序）。"""
    from intelnexus.core.llm.utils import _normalize_model_name

    pref = next(
        (c for c in choices if _normalize_model_name(c) == _PREFERRED_MODEL),
        None,
    )
    if pref:
        return [pref] + [c for c in choices if c != pref]
    return list(choices)


def resolve_scheduler_llm(max_candidates: int = _MAX_CANDIDATES) -> Tuple[Optional[object], str, str]:
    """为定时链路解析一个可用的 LLM 实例。

    Returns:
        (llm, model_name, reason):
        - 成功：llm 实例、模型名、reason 为空串
        - 失败：(None, "", reason)，reason 为可直接展示给管理员的中文说明
    """
    try:
        from intelnexus.core.llm.utils import get_model_choices, is_vision_model
        choices = [c for c in get_model_choices() if not is_vision_model(c)]
    except Exception as e:
        return None, "", f"读取可用模型列表失败：{type(e).__name__}: {str(e)[:100]}"

    if not choices:
        return None, "", (
            "未检测到任何可用模型（本地 Ollama 未运行或未拉取模型，"
            "也未配置自定义模型）"
        )

    candidates = _ordered_candidates(choices)

    try:
        from intelnexus.core.llm.core import get_llm
    except Exception as e:
        return None, "", f"LLM 加载器不可用：{type(e).__name__}: {str(e)[:100]}"

    errors = []
    for name in candidates[:max(1, max_candidates)]:
        try:
            llm = get_llm(name)
            if llm is not None:
                return llm, name, ""
            errors.append(f"{name}：返回空实例")
        except Exception as e:
            errors.append(f"{name}：{type(e).__name__}: {str(e)[:80]}")

    return None, "", "候选模型全部加载失败 —— " + "；".join(errors)


def make_status(ok: bool, model: str = "", reason: str = "") -> dict:
    """统一的模型状态字典（供调度器持有、状态横幅消费）。"""
    return {"ok": bool(ok), "model": model or "", "reason": reason or ""}
