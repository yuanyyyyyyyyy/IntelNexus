"""Shared test fixtures for IntelNexus test suite."""

import os
import sys

# Add project dirs first (so `import config` resolves to root config.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
# Then add shared library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

# Inject config for shared library
from shared.settings import set as set_config
set_config({
    "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "OPENROUTER_BASE_URL": os.getenv("OPENROUTER_BASE_URL", ""),
    "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
    "NEWS_API_KEY": os.getenv("NEWS_API_KEY", ""),
})

import pytest


@pytest.fixture
def sample_search_results():
    """10 mock search results with varying quality."""
    return [
        {
            "title": "AI Regulation Overview - Reuters",
            "link": "https://www.reuters.com/technology/ai-regulation-2025",
            "description": "Comprehensive overview of AI regulation globally.",
            "source": "Reuters",
        },
        {
            "title": "New AI Model Released by OpenAI",
            "link": "https://techcrunch.com/2025/07/openai-new-model",
            "description": "OpenAI announces GPT-5 with improved reasoning.",
            "source": "TechCrunch",
        },
        {
            "title": "AI Safety Research Advances",
            "link": "https://www.bbc.com/news/technology-ai-safety",
            "description": "New breakthroughs in AI alignment research.",
            "source": "BBC",
        },
        {
            "title": "Machine Learning in Healthcare",
            "link": "https://example.com/ml-healthcare",
            "description": "How ML is transforming medical diagnostics.",
            "source": "Example",
        },
        {
            "title": "China AI Development Report",
            "link": "https://www.gov.cn/ai-report-2025",
            "description": "Official report on China's AI development.",
            "source": "gov.cn",
        },
        {
            "title": "AI Ethics Discussion",
            "link": "https://arxiv.org/abs/2025.12345",
            "description": "Academic paper on AI ethics frameworks.",
            "source": "arXiv",
        },
        {
            "title": "Tech Giants AI Investment",
            "link": "https://www.bloomberg.com/ai-investment",
            "description": "Major tech companies increase AI spending.",
            "source": "Bloomberg",
        },
        {
            "title": "Open Source AI Tools",
            "link": "https://github.com/awesome-ai-tools",
            "description": "Collection of open source AI tools.",
            "source": "GitHub",
        },
        {
            "title": "AI in Education",
            "link": "https://stanford.edu/ai-education",
            "description": "Stanford research on AI in classrooms.",
            "source": "Stanford",
        },
        {
            "title": "AI Startup Funding",
            "link": "https://techcrunch.com/2025/ai-startup-funding",
            "description": "Record funding for AI startups in Q2 2025.",
            "source": "TechCrunch",
        },
    ]


@pytest.fixture
def sample_scraped_content():
    """Mock scraped content dict {url: text}."""
    return {
        "https://www.reuters.com/technology/ai-regulation-2025": (
            "Artificial intelligence regulation has become a major focus for "
            "governments worldwide in 2025. The European Union's AI Act took "
            "effect in January, establishing risk-based classifications for AI "
            "systems. The United States has proposed bipartisan legislation to "
            "regulate high-risk AI applications. China continues to enforce "
            "its existing AI governance framework."
        ),
        "https://techcrunch.com/2025/07/openai-new-model": (
            "OpenAI has released GPT-5, its most advanced language model to "
            "date. The model features improved reasoning capabilities and "
            "better multilingual support. CEO Sam Altman described it as a "
            "significant step toward artificial general intelligence."
        ),
        "https://www.bbc.com/news/technology-ai-safety": (
            "Researchers at leading AI safety labs have made significant "
            "progress in alignment techniques. New methods for interpreting "
            "neural network internals could help prevent AI systems from "
            "behaving unexpectedly. The findings were published in Nature."
        ),
        "https://example.com/ml-healthcare": (
            "Machine learning is revolutionizing medical diagnostics. "
            "New AI systems can detect certain cancers with 95% accuracy, "
            "outperforming human radiologists in controlled studies."
        ),
        "https://www.gov.cn/ai-report-2025": (
            "China's AI industry reached a market size of 500 billion yuan "
            "in 2025, representing 30% growth year-over-year. The government "
            "has invested 100 billion yuan in AI research and development."
        ),
    }


@pytest.fixture
def sample_report():
    """Mock LLM-generated intelligence report."""
    return """## 一、执行摘要

人工智能领域在2025年经历了重大变革。监管框架逐步完善，技术突破持续涌现。

## 二、背景与概述

### 2.1 背景介绍
人工智能技术的发展已经进入了一个新的阶段。

## 三、核心发现

### 发现一：监管进展
全球多个国家已经出台了AI相关法规。欧盟AI法案于2025年1月生效。

### 发现二：技术突破
OpenAI发布了GPT-5模型，在推理能力方面取得了显著提升。

### 发现三：安全研究
AI安全领域的研究取得了重要进展，新的对齐技术可以帮助预防AI系统异常行为。

## 四、多角度分析

### 4.1 技术维度
大语言模型的能力持续提升，多模态融合成为趋势。

### 4.2 商业维度
AI创业公司在2025年第二季度获得了创纪录的融资。

## 五、关键数据

| 指标 | 数值 |
|------|------|
| 全球AI市场规模 | 5000亿美元 |
| 同比增长 | 30% |

## 六、风险与建议

### 6.1 主要风险
监管不确定性可能影响创新。

### 6.2 行动建议
密切关注各国AI政策动态。

## 七、信息来源

- Reuters: AI Regulation Overview
- TechCrunch: OpenAI Model Release
- BBC: AI Safety Research
"""


@pytest.fixture
def mock_llm():
    """Mock LLM instance that returns fixed content."""

    class MockLLM:
        def __init__(self):
            self.callbacks = []

        def invoke(self, *args, **kwargs):
            return "Mock intelligence report content."

        def __or__(self, other):
            return self

        def __ror__(self, other):
            return other

    return MockLLM()
