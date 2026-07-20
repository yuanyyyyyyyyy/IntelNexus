import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from shared.llm.utils import _common_llm_params, resolve_model_config, get_model_choices

from shared.logger import get_logger

logger = get_logger(__name__)

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


def get_llm(model_choice):
    config = resolve_model_config(model_choice)

    if config is None:
        supported_models = get_model_choices()
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    all_params = {**_common_llm_params, **model_specific_params}

    llm_instance = llm_class(**all_params)

    return llm_instance


def expand_query(user_input):
    """查询扩展 - 拼写修复 + 多语言变体生成"""
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

    if has_chinese:
        queries.append(f"{original} English")
        queries.append(f"{original} news")

    if has_english and len(original) >= 3:
        queries.append(f"{original} 中文")
        queries.append(f"{original} 新闻")

    return queries


def expand_query_for_search(query_variants):
    """
    将查询变体扩展为搜索字符串
    如果是列表，用 | 分隔多个查询
    """
    if isinstance(query_variants, list):
        return " | ".join(query_variants)
    return query_variants


def _get_mode_description(search_mode):
    """Return a description string for the given search mode."""
    mode_descriptions = {
        "all": "综合所有来源：网页、新闻、暗网",
        "web": "主要来源：网页搜索结果",
        "news": "主要来源：新闻资讯",
        "darkweb": "主要来源：暗网资源（.onion网站）",
    }
    return mode_descriptions.get(search_mode, mode_descriptions["all"])


def _build_system_prompt(query, search_mode):
    """Build the system prompt for the LLM."""
    mode_desc = _get_mode_description(search_mode)
    return f"""
你是一位高级网络情报分析师。基于以下搜索结果，请生成一份结构清晰、内容全面的情报分析报告。

查询主题：{query}
数据来源：{mode_desc}

重要要求：
1. 报告要全面详细，涵盖所有搜索结果中的关键信息
2. 不要对话或提问，直接给出分析报告
3. 使用Markdown格式，以##标题组织内容
4. 核心发现部分用流畅的段落叙述，不要用列表
5. 每个部分都要有实质性的分析和内容
6. 在报告中合理使用额外分析数据（来源可信度、知识图谱实体、跨源冲突信息）：
   - 在"核心发现"中标注信息来源的可信度等级
   - 在"关键数据"中引用提取到的关键实体
   - 用 ⚠️ 标记存在跨源冲突的信息

报告模板结构：

## 一、执行摘要

用3-5句话概括关于"{query}"的核心发现、当前状态和结论。


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

### 4.1 技术维度
[技术原理、现状、趋势、挑战]

### 4.2 商业维度
[市场、盈利模式、主要玩家、投资]

### 4.3 社会维度
[影响、公众态度、伦理]

### 4.4 政策与监管维度
[法规、监管、合规]

### 4.5 发展趋势
[短期、中期、长期预测]


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


def _build_augmented_content(content, credibility_context="", kg_context="", conflicts_context=""):
    """Build the augmented content string with context from analysis modules."""
    augmented_content = ""
    if isinstance(content, dict):
        for url, text in content.items():
            n = min(len(text), 2000)
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

    return augmented_content


def generate_summary(llm, query, content, search_mode="all",
                     credibility_context="", kg_context="", conflicts_context=""):
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
    augmented_content = _build_augmented_content(content, credibility_context, kg_context, conflicts_context)

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
