import re
import threading
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from intelnexus.core.llm.utils import _common_llm_params, resolve_model_config, get_model_choices

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 模块级 LLM 实例缓存（按 model_choice），避免每次搜索都重建模型连接
_llm_cache = {}
_llm_cache_lock = threading.Lock()

_ERROR_TEMPLATE_TIMEOUT = """## 一、执行摘要

报告生成请求超时，可能因网络延迟或模型响应过慢导致。

## 二、建议

1. 请检查网络连接状态
2. 尝试切换至其他可用的 AI 模型
3. 减少搜索范围后重试

## 三、错误详情

API 请求超时，模型未能在规定时间内返回结果。
"""

_ERROR_TEMPLATE_GENERIC = """## 一、执行摘要

报告生成过程中遇到错误。

## 二、错误信息

{error_msg}

## 三、建议

1. 请检查 API 密钥配置是否正确
2. 尝试切换至其他可用的 AI 模型
3. 检查 Ollama 服务是否正常运行（如使用本地模型）
"""


def get_llm(model_choice, use_cache=True):
    config = resolve_model_config(model_choice)

    if config is None:
        supported_models = get_model_choices()
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    if use_cache:
        with _llm_cache_lock:
            cached = _llm_cache.get(model_choice)
        if cached is not None:
            return cached

    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    all_params = {**_common_llm_params, **model_specific_params}

    llm_instance = llm_class(**all_params)

    if use_cache:
        with _llm_cache_lock:
            _llm_cache[model_choice] = llm_instance

    return llm_instance


def expand_query(user_input):
    """查询扩展 - 拼写修复 + 最多1个跨语言变体（避免请求爆炸）"""
    user_input = user_input.strip()

    common_typos = {
        "sarch": "search",
        "serach": "search",
        "seaech": "search",
        "reuslt": "result",
        "resutl": "result",
    }

    words = user_input.split()
    fixed_words = []
    for word in words:
        if word.lower() in common_typos:
            fixed_words.append(common_typos[word.lower()])
        else:
            fixed_words.append(word)

    original = " ".join(fixed_words)

    if len(original) < 3:
        return [original]

    queries = [original]

    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in original)
    has_english = any('a' <= c.lower() <= 'z' for c in original)

    # Only add ONE cross-language variant to avoid search engine overload
    if has_chinese:
        queries.append(f"{original} English")
    elif has_english and len(original) >= 3:
        queries.append(f"{original} 中文")

    return queries


def expand_query_for_search(query_variants):
    """
    将查询变体扩展为搜索字符串。

    修正（方案B）：不再把多语言变体用 ``|`` 拼成 OR 查询一次性塞给搜索引擎。
    OR 拼接会稀释查询意图（如中文"九江" + "九江 English" 会拉回大量无关的英文全局新闻），
    "搜不准"的根因之一。

    改为：仅取第一个（最贴近原意的）变体作为搜索串，其余语言变体由管线层在
    聚合后再做语义排序/过滤处理。若传入单个字符串则原样返回。
    """
    if isinstance(query_variants, list):
        if not query_variants:
            return ""
        return query_variants[0]
    return query_variants


def _get_mode_description(search_mode):
    """Return a description string for the given search mode."""
    # 单一事实源：与 core.search.modes.MODE_DESCRIPTIONS 保持一致（此前本地副本漂移，
    # 缺 threat 条目导致威胁情报模式下 LLM 被告知"综合所有来源：网页、新闻、暗网"）
    try:
        from intelnexus.core.search.modes import MODE_DESCRIPTIONS
        return MODE_DESCRIPTIONS.get(search_mode, MODE_DESCRIPTIONS["all"])
    except ImportError:
        return "综合所有可用来源"


# ---------------------------------------------------------------------------
# 查询主题分类（方案 A：模板分层）
# 安全情报类查询沿用完整四维分析；非安全类（实体/城市/产品/人物等）
# 自动替换为自适应维度，避免"技术维度硬凑 VR 景区"式的模板错配。
_SECURITY_HINTS = (
    "漏洞", "攻击", "勒索", "恶意", "木马", "病毒", "钓鱼", "入侵", "渗透",
    "exploit", "ransomware", "malware", "apt", "cve", "0day", "zero-day",
    "数据泄露", "泄密", "暗网", "hacked", "breach", "botnet", "ddos",
    "网络攻击", "安全事件", "威胁情报", "后门", "挂马", "webshell",
)


def classify_query_topic(query: str) -> str:
    """返回 'security' 或 'general'。规则匹配，零 LLM 开销。"""
    if not query:
        return "general"
    q = query.lower()
    return "security" if any(h in q for h in _SECURITY_HINTS) else "general"


_ADAPTIVE_DIMENSIONS = """
### 4.1 发展现状与格局
[该主体的当前状态、规模数据、行业地位、近期变化]

### 4.2 优势与挑战
[核心优势/竞争力；面临的问题、短板或争议]

### 4.3 相关方视角
[政府/监管态度、行业影响、公众关注点（仅当搜索结果有支撑时展开）]

### 4.5 发展趋势
[短期、中期、长期预测]
"""


def _build_system_prompt(query, search_mode):
    """Build the system prompt for the LLM."""
    mode_desc = _get_mode_description(search_mode)
    topic_kind = classify_query_topic(query)
    if topic_kind == "general":
        dimensions_block = _ADAPTIVE_DIMENSIONS
        dim_note = ("注意：本次查询不是安全事件类主题，「多角度分析」章节请使用下方自适应维度骨架，"
                    "不要输出技术/商业/社会/政策四个固定小节；若搜索结果对某维度无支撑，直接省略该小节。")
    else:
        dimensions_block = None
        dim_note = ""
    return f"""
你是一位高级网络情报分析师。基于以下搜索结果，请生成一份结构清晰、内容全面的情报分析报告。

查询主题：{query}
数据来源：{mode_desc}{(chr(10) + dim_note) if dim_note else ''}

重要要求：
1. 报告要全面详细，涵盖所有搜索结果中的关键信息
2. 不要对话或提问，直接给出分析报告
3. 使用Markdown格式，以##标题组织内容
4. 核心发现部分用流畅的段落叙述，不要用列表
5. 每个部分都要有实质性的分析和内容
6. 在报告中合理使用额外分析数据（来源可信度、知识图谱实体、跨源冲突信息）：
   - 在"核心发现"中标注信息来源的可信度等级
   - 在"关键数据"中引用提取到的关键实体
    - 用 ! 标记存在跨源冲突的信息

报告模板结构：

## TL;DR 情报速览

在报告最开头生成结构化速览卡片（用粗体和换行保持视觉紧凑）：

**威胁等级**: 🔴 高危 / 🟠 中高危 / 🟡 中危 / 🟢 低危 / ℹ️ 监控
（判定标准——🔴：正在发生的重大攻击/大规模数据泄露/关键基础设施沦陷；🟠：高危漏洞在野利用或勒索事件；🟡：高危漏洞披露但未确认利用；🟢：一般漏洞或低影响事件；ℹ️：无明显威胁信号，仅为常规监测主题。按事件实际严重度独立判定，不随查询主题拔高）
**核心判断**: 一句话概括当前最大风险或核心态势
- 关键发现1（具体、可量化）
- 关键发现2
- 关键发现3
**行动建议**: 一句话最高优先级建议

（速览卡内容必须基于搜索结果，不得编造）

---

## 一、执行摘要

面向决策者的 2 分钟版摘要，分三段输出（每段以粗体小标题开头）：

**发生了什么**：围绕"{query}"的核心事实与最新动态（2-3 句，含时间/主体/事件）。
**为什么重要**：这些事实的影响面与意义（2-3 句，关联行业/政策/风险格局）。
**下一步关注**：未来值得跟踪的信号点或时间窗口（1-2 句）。

硬性约束：本节不得复述 TL;DR 速览卡中的要点原句；必须提供速览卡没有的增量信息（具体数据、因果链、对比基准或时间线）。禁止使用列表，全部段落叙述。


## 二、背景与概述

### 2.1 背景介绍
[领域背景、发展历程、为什么重要]

### 2.2 基本概念
[核心定义、关键术语解释]


## 三、核心发现

[这是报告主体部分，应该占据最多篇幅，用流畅的段落叙述]

### 发现一：[主题]
[详细叙述，包括：时间、地点、人物、事件、影响等]

### 发现二：[主题]
[详细叙述]

### 发现三：[主题]
[详细叙述]


## 四、多角度分析

{dimensions_block if dimensions_block else """### 4.1 技术维度
[技术原理、现状、趋势、挑战]

### 4.2 商业维度
[市场、盈利模式、主要玩家、投资]

### 4.3 社会维度
[影响、公众态度、伦理]

### 4.4 政策与监管维度
[法规、监管、合规]

### 4.5 发展趋势
[短期、中期、长期预测]"""}


## 五、关键数据

[汇总表格形式的硬数据]


## 六、风险与建议

### 6.1 主要风险
[1-3个核心风险及影响]

### 6.2 行动建议
[1-3条可执行的建议]


## 七、信息来源

[链接列表]

请直接生成报告，不要有任何对话或提问。
"""


def _build_augmented_content(content, credibility_context="", kg_context="", conflicts_context="", kb_context=""):
    """Build the augmented content string with context from analysis modules."""
    augmented_content = ""
    if isinstance(content, dict):
        for url, text in content.items():
            n = min(len(text), 4000)
            text_clean = re.sub(r'!\[.*?\]\(.*?\)', '', text[:n])
            text_clean = re.sub(r'<img[^>]*>', '', text_clean)
            text_clean = re.sub(r'\b\S+\.(png|jpg|jpeg|gif|webp|svg)\b', '', text_clean)
            augmented_content += f"\n---\n来源: {url}\n{text_clean}\n"
    else:
        augmented_content = str(content)

    if credibility_context:
        augmented_content += f"\n\n=== 来源可信度评估 ===\n{credibility_context}\n"
    if kg_context:
        augmented_content += f"\n\n=== 关键实体 ===\n{kg_context}\n"
    if conflicts_context:
        augmented_content += f"\n\n=== 跨源冲突信息 ===\n{conflicts_context}\n"
    if kb_context:
        augmented_content += f"\n\n=== 历史知识库参考（用户既往收藏，供关联分析） ===\n{kb_context}\n"

    return augmented_content


def generate_summary(llm, query, content, search_mode="all",
                     credibility_context="", kg_context="", conflicts_context="", kb_context=""):
    """生成情报报告，根据搜索模式调整分析重点"""

    logger.debug(f"Content type: {type(content)}")
    if isinstance(content, dict):
        logger.debug(f"Content keys count: {len(content)}")
        logger.debug(f"Content keys: {list(content.keys())[:5]}")
        if content:
            first_val = list(content.values())[0]
            logger.debug(f"First value length: {len(first_val)}")
            logger.debug(f"First value preview: {first_val[:300]}")
    elif isinstance(content, list):
        logger.debug(f"Content is list, length: {len(content)}")

    system_prompt = _build_system_prompt(query, search_mode)
    augmented_content = _build_augmented_content(content, credibility_context, kg_context, conflicts_context, kb_context)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "搜索结果内容:\n{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        return chain.invoke({"content": augmented_content})
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM API error ({type(e).__name__}): {error_msg}")
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return _ERROR_TEMPLATE_TIMEOUT
        else:
            return _ERROR_TEMPLATE_GENERIC.format(error_msg=error_msg)
