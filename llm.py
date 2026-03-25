import re
import openai
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
import logging
import re

import warnings

warnings.filterwarnings("ignore")


def get_llm(model_choice):
    # Look up the configuration (cloud or local Ollama)
    config = resolve_model_config(model_choice)

    if config is None:  # Extra error check
        supported_models = get_model_choices()
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    # Extract the necessary information from the configuration
    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    # Combine common parameters with model-specific parameters
    # Model-specific parameters will override common ones if there are any conflicts
    all_params = {**_common_llm_params, **model_specific_params}

    # Create the LLM instance using the gathered parameters
    llm_instance = llm_class(**all_params)

    return llm_instance


def refine_query(llm, user_input):
    """
    查询优化 - 原始查询 + 多语言翻译
    返回: 原始查询 + 英文翻译 + 中文翻译（如果原文不是英文/中文）
    """
    user_input = user_input.strip()
    
    # 简单的拼写错误修复
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
    
    # 只对有意义的查询添加翻译（避免短查询被膨胀）
    if len(original) < 3:
        return [original]
    
    # 检测语言并生成翻译查询
    queries = [original]  # 原始查询
    
    # 使用简单的语言检测
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in original)
    has_english = any('a' <= c.lower() <= 'z' for c in original)
    
    # 如果有中文，添加英文翻译
    if has_chinese:
        queries.append(f"{original} English")
        queries.append(f"{original} news")
    
    # 如果有英文且长度足够，添加中文翻译
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


def filter_results(llm, query, results):
    if not results:
        return []

    # 过滤掉PDF链接（LLM无法读取PDF）
    filtered = []
    for r in results:
        link = r.get("link", "") or r.get("url", "") or r.get("pdf_url", "")
        if link.lower().endswith('.pdf') or '.pdf?' in link.lower():
            continue
        filtered.append(r)
    
    if not filtered:
        return []
    
    # 如果全部是PDF，返回空
    if len(filtered) == 0:
        return []

    # Extract key query terms for basic filtering
    query_terms = set(query.lower().split()) if isinstance(query, str) else set()
    
    # Pre-filter: remove results with NO relevance to query
    prefiltered = []
    for r in results:
        title = r.get("title", "").lower()
        desc = r.get("description", "").lower()
        summary = r.get("summary", "").lower()
        
        # Check if any query term appears in title or description
        has_match = any(term in title or term in desc or term in summary for term in query_terms)
        
        # Also check for Chinese character overlap
        if not has_match and any('\u4e00' <= c <= '\u9fff' for c in query):
            # For Chinese queries, check if any Chinese chars appear
            has_match = any(c in title or c in desc or c in summary for c in query)
        
        if has_match:
            prefiltered.append(r)
    
    # If pre-filtering removed too many, fall back to all results
    if len(prefiltered) < len(results) * 0.3:
        prefiltered = results[:min(len(results), 50)]
    
    # Use LLM to further refine
    system_prompt = """
You are a Network Intelligence Analyst. Given a search query and search results, select the MOST RELEVANT results.

CRITICAL RULES:
1. Only select results that are DIRECTLY related to the query topic
2. For query "九江", do NOT select results about "AI", "人工智能", "machine learning", etc.
3. Results must match the query's subject matter exactly
4. Output ONLY a comma-separated list of result indices (e.g., "1,3,5")

Search Query: {query}

Search Results:
"""

    final_str = _generate_final_string(prefiltered)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{results}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        print(f"Rate limit error: {e}")
        result_indices = ""

    # Parse indices
    parsed_indices = []
    for match in re.findall(r"\d+", result_indices):
        try:
            idx = int(match)
            if 1 <= idx <= len(prefiltered):
                parsed_indices.append(idx)
        except ValueError:
            continue

    # Remove duplicates while preserving order
    seen = set()
    parsed_indices = [
        i for i in parsed_indices if not (i in seen or seen.add(i))
    ]

    if not parsed_indices:
        # Fallback: use prefiltered results directly
        parsed_indices = list(range(1, min(len(prefiltered), 20) + 1))

    top_results = [prefiltered[i - 1] for i in parsed_indices[:20]]

    return top_results


def _generate_final_string(results, truncate=False):
    """
    Generate a formatted string from the search results for LLM processing.
    """

    if truncate:
        max_title_length = 30
        max_link_length = 0

    final_str = []
    for i, res in enumerate(results):
        title = res.get("title", "")
        link = res.get("link", "") or res.get("url", "") or res.get("pdf_url", "")
        
        title = re.sub(r"[^0-9a-zA-Z\-\.\s]", " ", str(title))
        link = re.sub(r"(?<=\.onion).*", "", str(link))
        
        if not link and not title:
            continue

        if truncate:
            title = title[:max_title_length] + "..." if len(title) > max_title_length else title
            link = link[:max_link_length] + "..." if len(link) > max_link_length else link

        final_str.append(f"{i+1}. {link} - {title}")

    return "\n".join(s for s in final_str)


def generate_summary(llm, query, content, search_mode="all"):
    """生成情报报告，根据搜索模式调整分析重点"""
    
    # 调试日志
    print(f"=== LLM INPUT DEBUG ===")
    print(f"Content type: {type(content)}")
    if isinstance(content, dict):
        print(f"Content keys count: {len(content)}")
        print(f"Content keys: {list(content.keys())[:5]}")
        if content:
            first_val = list(content.values())[0]
            print(f"First value length: {len(first_val)}")
            print(f"First value preview: {first_val[:300]}")
    elif isinstance(content, list):
        print(f"Content is list, length: {len(content)}")
    print(f"=======================")
    
    # 根据搜索模式设置不同的分析重点
    mode_descriptions = {
        "all": "综合所有来源：网页、新闻、暗网",
        "web": "主要来源：网页搜索结果",
        "news": "主要来源：新闻资讯",
        "darkweb": "主要来源：暗网资源（.onion网站）",
    }
    
    mode_desc = mode_descriptions.get(search_mode, mode_descriptions["all"])
    
    # 强制生成详细分析报告的提示词
    system_prompt = f"""
你是一位高级网络情报分析师。基于以下搜索结果，请生成一份结构清晰、内容全面的情报分析报告。

查询主题：{query}
数据来源：{mode_desc}

重要要求：
1. 报告要全面详细，涵盖所有搜索结果中的关键信息
2. 不要对话或提问，直接给出分析报告
3. 使用Markdown格式，以##标题组织内容
4. 核心发现部分用流畅的段落叙述，不要用列表
5. 每个部分都要有实质性的分析和内容

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
    
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "搜索结果内容:\n{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"content": content})
