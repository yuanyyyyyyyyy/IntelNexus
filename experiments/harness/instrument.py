"""零侵入埋点：时延、token 用量、seed、模型版本、提示词留痕。

不修改 intelnexus 业务代码。生成调用走 ``intelnexus.core.llm.core.generate_summary``
（与主程序同一链路），调用参数以 ``_common_llm_params`` 为基准，
保证表2 描述与实验实际一致。

token 用量双路径：
- 云端 OpenAI 兼容：``usage_metadata`` / ``llm_output.token_usage``；
- 本地 Ollama：``response_metadata`` 的 ``prompt_eval_count`` / ``eval_count``。
两条路径都取不到时 ``usage_source="none"``，对应成本格保留 not-yet-measured，
**不用估算值顶替**。

提示词留痕（防复发）
--------------------
历史教训：批量运行时云端未回传 usage，只能"借用"本地同一样本的
``prompt_eval_count`` 作为输入 token 的代理，结果事后无法判断该代理是否
等于**那一次**调用真正发出的提示词。事后核查（2026-09-15）表明该代理
的两重口径问题：其一，它是**一条样本内各次调用之和**——``generate_summary``
在输出板块不足时会改用简化 prompt 重试（本地小模型常触发），一条样本
可能发 2 次请求；其二，提示词本身也会随运行期上下文（可信度 / 知识图谱 /
冲突 / 知识库）变化，同一样本的合计在不同调用间可差数千 token。

因此本模块把每次调用真正发出的提示词留下字符数、SHA-256 与分词器计数
（``prompt_chars`` / ``prompt_sha256`` / ``prompt_tokens``（最后一次）/
``prompt_tokens_sum``（各次之和，与计费口径及服务端累计用量可比）/
``prompt_render``），使"该次请求的提示词有多长"事后可查、可复算、可比对。

注意事项：
- chat 模型触发的是 ``on_chat_model_start``（``langchain_core`` 1.6：chat_models.py:762），
  不是 ``on_llm_start``；两者都挂，前者按消息渲染、后者按纯文本。
- 一条样本可能触发多次调用（``generate_summary`` 输出校验失败会用简化
  prompt 重试），故记录**最后一次**调用值并另记调用次数 ``prompt_calls``。
- 计数为离线行为：分词器缺失时只记 warning，**绝不联网下载**、不中断生成。
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from experiments.logging_utils import get_logger

logger = get_logger("exp.instrument")

# ------------------------------------------------------------------ 错误识别
# `intelnexus.core.llm.core.generate_summary` 会吞掉 LLM 异常并返回错误模板
# （core.py:635-641），不抛异常。若把这些模板当成正常输出，错误文本会进入
# 质量评分、超时耗时会进入 P50/P95，直接污染论文字段。因此实验侧必须识别。
ERROR_MARKERS = {
    "timeout": ("报告生成请求超时", "API 请求超时"),
    "generic": ("报告生成过程中遇到错误",),
}


def error_kind_of(text: str) -> Optional[str]:
    """判定文本是否为 generate_summary 的错误模板；正常输出返回 None。"""
    if not text:
        return None
    for kind, markers in ERROR_MARKERS.items():
        for m in markers:
            if m in text:
                return kind
    return None


def is_error_template(text: str) -> bool:
    return error_kind_of(text) is not None


# ------------------------------------------------------------------ 提示词留痕
# 计数用的分词器与表5 的输入 token 口径一致（见 experiments/cost/token_recount.py）
PROMPT_RENDER_CHAT = "chat_messages"
PROMPT_RENDER_TEXT = "text"


def _message_text(msg: Any) -> str:
    """把一条消息渲染为可计数文本（兼容 BaseMessage / dict / str）。"""
    if msg is None:
        return ""
    if isinstance(msg, str):
        return msg
    if isinstance(msg, dict):
        role = msg.get("type") or msg.get("role")
        content = msg.get("content")
    else:
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        content = getattr(msg, "content", None)
    if isinstance(content, list):        # 多模态内容块：只取文本部分
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        content = "".join(parts)
    return f"{role or 'message'}: {content if content is not None else ''}"


def render_prompts(prompts: Any) -> tuple[str, str]:
    """把回调入参归一为 ``(文本, 渲染方式)``。

    - ``on_chat_model_start``：``[[BaseMessage, ...]]``（批大小为 1）→ 按消息拼接；
    - ``on_llm_start``：``["prompt", ...]`` → 直接拼接。

    渲染文本不含 chat 模板的特殊 token，故其计数**略低于**服务端
    ``prompt_eval_count``（本地同调用实测偏差见 PROTOCOL.md）。
    """
    if prompts is None:
        return "", PROMPT_RENDER_TEXT
    if isinstance(prompts, str):
        return prompts, PROMPT_RENDER_TEXT
    if not isinstance(prompts, (list, tuple)):
        return str(prompts), PROMPT_RENDER_TEXT
    if prompts and isinstance(prompts[0], (list, tuple)):     # 消息批次
        text = "\n".join("\n".join(_message_text(m) for m in batch) for batch in prompts)
        return text, PROMPT_RENDER_CHAT
    return "\n".join(_message_text(p) for p in prompts), PROMPT_RENDER_TEXT


def count_prompt_tokens(text: str) -> Optional[int]:
    """用 Qwen 分词器数提示词 token（与表5 同口径）。

    离线安全：分词器本体缺失时返回 ``None``，**不触发下载**、不抛异常——
    埋点不得因为计数依赖缺失而影响实验运行。
    """
    if not text:
        return None
    try:
        from experiments.cost.token_recount import count_tokens

        return count_tokens(text, ensure=False)
    except Exception as e:  # noqa: BLE001
        logger.debug("提示词计数不可用: %s", e)
        return None


# ------------------------------------------------------------------ 用量回调
class UsageAccumulator:
    """累积一次或多次 LLM 调用的输入/输出 token、用量来源与提示词留痕。

    提示词字段为**最后一次调用**的值（不是累加值），语义差异见
    :meth:`reset_prompt` 与模块 docstring。
    """

    def __init__(self) -> None:
        self.tokens_in: Optional[int] = None
        self.tokens_out: Optional[int] = None
        self.usage_source: str = "none"
        self.calls: int = 0
        self.model_version: Optional[str] = None
        # ---- 提示词留痕（本条调用的原始请求侧）----
        self.prompt_calls: int = 0
        self.prompt_chars: Optional[int] = None
        self.prompt_sha256: Optional[str] = None
        self.prompt_tokens: Optional[int] = None
        self.prompt_tokens_sum: Optional[int] = None
        self.prompt_render: Optional[str] = None
        self.prompt_text: Optional[str] = None     # 瞬态：仅最后一次调用原文，不落盘
        self.prompt_texts: List[str] = []          # 瞬态：本条各次调用原文，不落盘

    def reset_prompt(self) -> None:
        """清空提示词留痕，供下一条样本重新记录。

        ``prompt_chars`` / ``prompt_tokens`` 是"最后一次调用的值"而非可累加的
        计数，做条目间增量时会串到上一条，故每开始一条样本必须显式清零
        （token 总量走 ``tokens_in/out`` 的差值口径，与此不同）。
        """
        self.prompt_calls = 0
        self.prompt_chars = None
        self.prompt_sha256 = None
        self.prompt_tokens = None
        self.prompt_tokens_sum = None
        self.prompt_render = None
        self.prompt_text = None
        self.prompt_texts = []

    def on_start(self, prompts: Any) -> None:
        """记录一次调用真正发出的提示词（``on_chat_model_start`` / ``on_llm_start``）。

        只做廉价操作（取长度与 SHA-256，实测 <0.2 ms）：token 编码约 46 ms/次、
        首次装载分词器约 600 ms，若在此处做就会落进 ``generate_once`` 的计时窗，
        抬高 P50/P95。故编码推迟到 :meth:`finalize_prompt_tokens` 在窗口外补算。
        """
        text, render = render_prompts(prompts)
        if not text:
            return
        self.prompt_calls += 1
        self.prompt_chars = len(text)
        self.prompt_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.prompt_render = render
        self.prompt_text = text
        self.prompt_texts.append(text)
        self.prompt_tokens = None          # 由 finalize_prompt_tokens 在窗口外补算

    def finalize_prompt_tokens(self) -> Optional[int]:
        """补算提示词 token 数（必须在计时窗口之外调用）。

        产出两个量，语义不同、都必须留：

        - ``prompt_tokens``：**最后一次**调用的提示词 token 数（即最终生效的那次请求）；
        - ``prompt_tokens_sum``：本条**各次调用之和**。``generate_summary`` 在输出
          格式校验失败时会用简化 prompt 重试，一条样本可能发两次请求，而"计费口径"
          是各次输入之和——与 API/服务端累计上报的 ``tokens_in`` 才可比。
        """
        if self.prompt_tokens is None and self.prompt_texts:
            counts = [count_prompt_tokens(t) for t in self.prompt_texts]
            valid = [c for c in counts if c is not None]
            self.prompt_tokens = counts[-1] if counts else None
            self.prompt_tokens_sum = sum(valid) if valid else None
        return self.prompt_tokens

    def _extract(self, message: Any) -> tuple[Optional[int], Optional[int], Optional[str]]:
        tin = tout = None
        model_version = None
        meta = getattr(message, "response_metadata", None) or {}
        usage = getattr(message, "usage_metadata", None) or {}
        if isinstance(usage, dict) and usage.get("input_tokens") is not None:
            tin = int(usage.get("input_tokens") or 0) or None
            tout = int(usage.get("output_tokens") or 0) or None
        if tin is None and isinstance(meta, dict):
            # Ollama：prompt_eval_count / eval_count
            if meta.get("prompt_eval_count") is not None or meta.get("eval_count") is not None:
                tin = int(meta.get("prompt_eval_count") or 0) or None
                tout = int(meta.get("eval_count") or 0) or None
            # OpenAI 兼容：token_usage (部分版本仍走 llm_output，见 on_llm_end)
        if isinstance(meta, dict):
            model_version = meta.get("model") or meta.get("model_name") or meta.get("model_version")
        return tin, tout, model_version

    def on_end(self, response: Any) -> None:
        """从 LangChain 的 LLMResult 中抽取用量。"""
        self.calls += 1
        tin = tout = None
        model_version = None
        try:
            gens = getattr(response, "generations", None) or []
            if gens and gens[0]:
                msg = gens[0][0].message
                tin, tout, model_version = self._extract(msg)
        except Exception as e:  # noqa: BLE001
            logger.debug("从 generations 抽取用量失败: %s", e)

        if tin is None:
            llm_output = getattr(response, "llm_output", None) or {}
            tu = llm_output.get("token_usage") or llm_output.get("usage") or {}
            if isinstance(tu, dict) and tu:
                tin = int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0) or None
                tout = int(tu.get("completion_tokens") or tu.get("output_tokens") or 0) or None
            if not model_version and isinstance(llm_output, dict):
                model_version = llm_output.get("model_name") or llm_output.get("model")

        if tin is not None:
            self.tokens_in = (self.tokens_in or 0) + (tin or 0)
            self.tokens_out = (self.tokens_out or 0) + (tout or 0)
            self.usage_source = "api_usage" if self.usage_source in ("none", "api_usage") else self.usage_source
            if model_version:
                self.model_version = model_version
        elif model_version:
            self.model_version = model_version

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "usage_source": self.usage_source,
            "llm_calls": self.calls,
            "model_version": self.model_version,
            "prompt_calls": self.prompt_calls,
            "prompt_chars": self.prompt_chars,
            "prompt_sha256": self.prompt_sha256,
            "prompt_tokens": self.prompt_tokens,
            "prompt_tokens_sum": self.prompt_tokens_sum,
            "prompt_render": self.prompt_render,
        }


def make_callback_handler(acc: UsageAccumulator):
    """构造 LangChain 回调处理器（不引入新依赖，duck typing 兼容不同版本）。"""
    try:
        from langchain_core.callbacks.base import BaseCallbackHandler
    except Exception:  # noqa: BLE001 - 无 LangChain 时返回 None，由调用方降级

        return None

    class _Handler(BaseCallbackHandler):
        def on_chat_model_start(self, serialized, messages, **kwargs) -> None:  # noqa: D102
            # chat 模型走这条（langchain_core 1.6：chat_models.py:762），
            # 只挂 on_llm_start 会完全抓不到提示词
            acc.on_start(messages)

        def on_llm_start(self, serialized, prompts, **kwargs) -> None:  # noqa: D102
            acc.on_start(prompts)

        def on_llm_end(self, response, **kwargs) -> None:  # noqa: D102
            acc.on_end(response)

    return _Handler()


# ------------------------------------------------------------------ 构造 LLM
def _model_fields(cls: Any) -> Optional[set]:
    """返回可接受的构造参数名集合（**字段名 + pydantic 别名**）。

    LangChain 的 ChatOpenAI 字段真名是 ``openai_api_key`` / ``openai_api_base`` /
    ``request_timeout``，而 ``api_key`` / ``base_url`` / ``timeout`` 只是别名
    （见 langchain_openai/chat_models/base.py 的 Field(alias=...)）。

    只按字段名过滤会把 ``api_key`` 与 ``base_url`` 当成未知参数丢弃，
    后果是请求缺少凭据、且打到默认的 ``api.openai.com``（国内不可达）→ 挂到读超时。
    这是"云端全部超时"的真正原因，故必须把别名一并纳入白名单。
    """
    fields = getattr(cls, "model_fields", None)
    if not isinstance(fields, dict):
        return None
    allowed = set(fields.keys())
    for f in fields.values():
        alias = getattr(f, "alias", None)
        if alias:
            allowed.add(alias)
    return allowed


def _filter_params(cls: Any, params: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    """只保留目标类实际声明的字段，返回 (保留, 丢弃)。"""
    declared = _model_fields(cls)
    if declared is None:
        return dict(params), []
    kept = {k: v for k, v in params.items() if k in declared}
    dropped = [k for k in params if k not in declared]
    return kept, dropped


def common_llm_params() -> Dict[str, Any]:
    """复用主程序生成参数，保证表2 与实验一致（禁止在实验里另立一套）。"""
    from intelnexus.core.llm.utils import _common_llm_params

    return dict(_common_llm_params)


@dataclass
class LLMBinding:
    """一次配置绑定的 LLM 实例及其可追溯元信息。"""

    config_id: str
    backend: str
    llm: Any
    model: Optional[str]
    seed: Optional[int]
    seed_supported: bool
    dropped_params: List[str] = field(default_factory=list)
    usage: UsageAccumulator = field(default_factory=UsageAccumulator)
    extra: Dict[str, Any] = field(default_factory=dict)


def build_llm(cfg: Dict[str, Any], exp_cfg: Dict[str, Any], seed: Optional[int] = None,
              request_overrides: Optional[Dict[str, Any]] = None) -> LLMBinding:
    """按配置构造 LLM 实例。

    Args:
        cfg: experiment.yaml 中 configs 的一项
        exp_cfg: 完整实验配置
        seed: 随机种子；不支持的后端会回退并标记 seed_supported=False
    """
    import os

    backend = str(cfg.get("backend"))
    config_id = str(cfg.get("id"))
    params = common_llm_params()
    params.update(request_overrides or {})

    if backend == "ollama":
        from langchain_ollama import ChatOllama

        url = os.getenv(
            (exp_cfg.get("ollama", {}) or {}).get("base_url_env", "OLLAMA_BASE_URL"),
            (exp_cfg.get("ollama", {}) or {}).get("default_base_url", "http://127.0.0.1:11434"),
        )
        opts = dict((exp_cfg.get("ollama", {}) or {}).get("options", {}) or {})
        # 每配置解码选项覆盖全局（如 qwen3:4b 需 reasoning=False，
        # 否则思考 token 耗尽预算导致 content 为空）
        opts.update(cfg.get("options", {}) or {})
        params.update({"model": cfg.get("model"), "base_url": url, **opts})
        params.update(request_overrides or {})   # 覆盖项最后生效（如计量代理地址）
        if seed is not None:
            params["seed"] = int(seed)
        usage = UsageAccumulator()
        cb = make_callback_handler(usage)
        if cb is not None:
            params["callbacks"] = [cb]
        kept, dropped = _filter_params(ChatOllama, params)
        llm = ChatOllama(**kept)
        return LLMBinding(
            config_id=config_id, backend=backend, llm=llm, model=cfg.get("model"),
            seed=seed, seed_supported=("seed" not in dropped), dropped_params=dropped,
            usage=usage, extra={"base_url": url, "options": opts},
        )

    if backend == "openai_compatible":
        from langchain_openai import ChatOpenAI

        provider_name = str(cfg.get("provider"))
        provider = next(
            (p for p in ((exp_cfg.get("cloud", {}) or {}).get("providers", []) or [])
             if p.get("name") == provider_name),
            {},
        )
        api_key = os.getenv(str(provider.get("env_key") or ""), "")
        if not api_key:
            raise RuntimeError(
                f"云端配置 {config_id} 缺少密钥：请设置环境变量 {provider.get('env_key')}"
            )
        tier = str(cfg.get("tier") or "flagship")
        model = cfg.get("model")
        if not model:
            from experiments.harness.env_probe import pick_model  # 延迟导入避免循环

            env_report: Dict[str, Any] = {}
            try:
                from experiments.common import read_json
                from experiments.paths import ENV_REPORT

                if ENV_REPORT.exists():
                    env_report = read_json(ENV_REPORT)
            except Exception:  # noqa: BLE001
                env_report = {}
            info = (env_report.get("cloud") or {}).get(provider_name) or {}
            model = (info.get("selected") or {}).get(tier) or pick_model(
                info.get("models") or [], provider.get(f"{tier}_hint", [])
            )
        if not model:
            raise RuntimeError(
                f"无法确定 {provider_name} 的 {tier} 档模型：请先在 experiment.yaml 指定 model，"
                f"或用 EXP_{provider_name.upper()}_{tier.upper()}_MODEL 环境变量指定"
            )
        params.update({"model": model, "base_url": provider.get("base_url"), "api_key": api_key})
        params.update({k: v for k, v in (request_overrides or {}).items() if v})
        # 云端参数覆盖（流式开关、超时、输出上限）。
        # 注意用 `is not None`：streaming=False 是显式覆盖（推理型模型流式静默
        # 会触发读超时），不能因 falsy 被跳过。
        cloud_cfg = exp_cfg.get("cloud", {}) or {}
        for key in ("streaming", "request_timeout", "max_tokens"):
            val = cloud_cfg.get(key)
            if val is not None:
                params[key] = val
        if seed is not None:
            params["seed"] = int(seed)
        usage = UsageAccumulator()
        cb = make_callback_handler(usage)
        if cb is not None:
            params["callbacks"] = [cb]
        kept, dropped = _filter_params(ChatOpenAI, params)
        llm = ChatOpenAI(**kept)
        return LLMBinding(
            config_id=config_id, backend=backend, llm=llm, model=model,
            seed=seed, seed_supported=("seed" not in dropped), dropped_params=dropped,
            usage=usage, extra={"provider": provider_name, "base_url": provider.get("base_url")},
        )

    raise ValueError(f"未知的 backend: {backend}")


# ------------------------------------------------------------------ 计时生成
@dataclass
class TimedResult:
    text: str
    latency_s: float
    usage: Dict[str, Any]
    error: Optional[str] = None
    error_kind: Optional[str] = None   # timeout | generic | exception


def generate_once(llm: Any, item: Dict[str, Any], search_mode: str = "all",
                  usage: Optional[UsageAccumulator] = None,
                  input_max_chars: Optional[int] = None) -> TimedResult:
    """对一条公告执行一次生成并计时（端到端，含提示词拼装与内部重试）。

    Args:
        input_max_chars: 输入正文上限。生产代码只对本地小模型截断；
            实验中若对云端也设置上限（消除长度不公平与时延放大），
            必须记录在 manifest 的 param_overrides 并在论文中说明。
    """
    from intelnexus.core.llm.core import generate_summary

    acc = usage if usage is not None else UsageAccumulator()
    acc.calls = 0
    # 提示词留痕是"最后一次调用的值"，非累加量：必须每条清零，
    # 否则本条的 usage 会带回上一条的提示词（token 总量仍走下面的差值口径）
    acc.reset_prompt()
    # accumulator 跨条目复用，内部是累计值；这里取调用前后的增量作为本条用量
    base_in = acc.tokens_in or 0
    base_out = acc.tokens_out or 0
    text_in = item.get("content", "") or ""
    if input_max_chars and len(text_in) > int(input_max_chars):
        text_in = text_in[: int(input_max_chars)]
    content = {item.get("url") or item.get("id"): text_in}
    start = time.perf_counter()
    error: Optional[str] = None
    kind: Optional[str] = None
    try:
        text = generate_summary(llm, item.get("title") or item.get("id"), content, search_mode=search_mode)
    except Exception as e:  # noqa: BLE001
        text = ""
        error = f"{type(e).__name__}: {str(e)[:200]}"
        kind = "exception"
        logger.error("生成失败 %s: %s", item.get("id"), error)
    latency = time.perf_counter() - start
    # 提示词 token 的编码开销必须落在计时窗口之外：时延是论文一等指标，
    # 埋点自己不得给它加 46 ms/条（首条还要加一次分词器装载）
    acc.finalize_prompt_tokens()

    # generate_summary 吞掉异常后返回错误模板：必须在此识别为失败，
    # 否则错误文本会被当作摘要评分、超时耗时会污染 P50/P95
    if not error and is_error_template(text):
        kind = error_kind_of(text)
        error = f"llm_error_template:{kind}"
        logger.error("生成 %s 返回错误模板（%s），记为失败，耗时 %.1fs 不计入时延统计",
                     item.get("id"), kind, latency)
        text = ""

    usage_dict = acc.as_dict()
    new_in = (acc.tokens_in - base_in) if acc.tokens_in is not None else None
    new_out = (acc.tokens_out - base_out) if acc.tokens_out is not None else None
    if not new_in and not new_out:
        # 本条没有取到任何新用量：差值会算出 0，而 0 会被读成"实测为零"，
        # 并且 usage_source 仍留着上一条的 api_usage —— 两者都必须归位为缺失
        new_in = new_out = None
        usage_dict["usage_source"] = "none"
    elif usage_dict.get("usage_source") in (None, "none"):
        usage_dict["usage_source"] = "api_usage"
    usage_dict["tokens_in"] = new_in
    usage_dict["tokens_out"] = new_out
    return TimedResult(text=text or "", latency_s=latency, usage=usage_dict,
                       error=error, error_kind=kind)
