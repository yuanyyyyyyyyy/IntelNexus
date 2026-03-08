# IntelNexus - 智能体开发指南

本文档包含在IntelNexus项目中工作的智能体需要遵循的指南和规范。

## 项目概述

IntelNexus是一个AI驱动的多源网络情报分析平台，能够从学术论文、新闻、社交媒体和网页等多个来源搜索和分析数据，并利用LLM生成情报报告。

## 构建命令

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行应用

**命令行模式：**
```bash
python main.py search -q "你的查询" -s academic -m qwen2.5:7b
```

**Web界面模式：**
```bash
python main.py ui
# 然后打开 http://localhost:8501
```

### 常用命令
```bash
# 自定义线程数搜索
python main.py search -q "AI趋势" -s all -t 8 -o 输出报告

# 可用搜索模式: web, academic, news, social, darkweb, all
# 可用模型: qwen2.5:7b, deepseek-r1:7b, 或任意Ollama模型
```

## 测试命令

本项目目前没有正式的测试套件。如需添加测试：

```bash
# 安装pytest
pip install pytest pytest-cov

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_academic_search.py

# 带覆盖率运行
pytest --cov=. --cov-report=html
```

## 代码风格指南

### 导入规范
- 标准库导入放最前面
- 第三方导入放第二
- 本地导入放最后
- 各组之间用空行分隔

```python
# 正确的顺序：
import os
import re
from typing import List, Dict, Optional

import arxiv
from concurrent.futures import ThreadPoolExecutor

from config import OPENAI_API_KEY
from llm import get_llm
```

### 命名规范
- **类名**: PascalCase (例如：`AcademicSearch`, `TrendAnalyzer`)
- **函数/方法**: snake_case (例如：`get_academic_results`, `analyze_trends`)
- **常量**: UPPER_SNAKE_CASE (例如：`MAX_RESULTS`, `DEFAULT_TIMEOUT`)
- **变量**: snake_case (例如：`search_results`, `max_workers`)
- **私有方法**: 以下划线开头 (例如：`_extract_keywords`)

### 类型提示
- 所有函数参数和返回值使用类型提示
- 使用 `Optional[X]` 而非 `X | None` (Python 3.10兼容性)
- 使用 `List`, `Dict` 而非内置的 list/dict

```python
def search_arxiv(self, query: str, max_results: int = 10) -> List[Dict]:
    ...
```

### 错误处理
- 外部API调用使用try/except块
- 适当记录错误（当前使用print，生产环境推荐logging）
- 出错时返回空集合而非抛出异常
- 错误信息包含上下文

```python
try:
    client = arxiv.Client()
    search = arxiv.Search(query=query, max_results=max_results)
    # ... 处理结果
except Exception as e:
    print(f"ArXiv搜索错误: {e}")
    return []
```

### 代码结构

**文件组织：**
- 每个模块最好只包含一个类
- 将相关函数放在一起
- 每个文件最多约200行

**函数规范：**
- 函数应该只做一件事
- 函数最好在50行以内
- 使用清晰、描述性的名称

### 格式化
- 使用4个空格缩进（不使用tab）
- 最大行长度：100字符
- 公共函数添加文档字符串
- 使用空行分隔逻辑部分

### 项目结构
```
IntelNexus/
├── main.py              # CLI入口
├── ui.py                # Streamlit Web界面
├── config.py            # 配置管理
├── llm.py               # LLM集成
├── llm_utils.py         # LLM工具
├── web_search.py        # 网页搜索模块
├── academic_search.py   # 学术论文搜索
├── news_search.py       # 新闻搜索模块
├── social_search.py     # 社交媒体搜索
├── darkweb_search.py    # 暗网搜索(可选)
├── scrape.py            # 内容抓取
├── report_export.py     # 报告导出(PDF/Word)
├── search_history.py    # 搜索历史管理
├── trend_analysis.py    # 趋势分析
├── keyword_extraction.py # 关键词提取
├── multilang.py         # 多语言支持
└── requirements.txt    # 依赖
```

### 添加新的搜索模块

添加新的搜索源时：

1. 创建 `new_source_search.py`，包含 `get_new_source_results(query, max_results)` 函数
2. 在 `main.py` 中添加导入和模式选项
3. 在 `ui.py` 中添加UI选项
4. 测试：`python main.py search -q "test" -s new_source`

### LLM使用

- 使用LangChain进行LLM集成
- 同时支持本地(Ollama)和云端模型
- 本地测试默认使用qwen2.5:7b
- UI始终提供流式输出支持

### 数据存储

- 使用JSON文件进行简单存储(search_history.py)
- 数据存储在 `data/` 目录
- 创建不存在的目录

## 环境变量

创建 `.env` 文件：
```env
OPENAI_API_KEY=你的密钥
ANTHROPIC_API_KEY=你的密钥
GOOGLE_API_KEY=你的密钥
OLLAMA_BASE_URL=http://127.0.0.1:11434
OPENROUTER_API_KEY=你的密钥
SEMANTIC_SCHOLAR_API_KEY=你的密钥
NEWS_API_KEY=你的密钥
TWITTER_BEARER_TOKEN=你的令牌
ENABLE_DARKWEB=false
```

## 常见任务

### 添加新功能
1. 创建功能模块
2. 在main.py添加CLI选项
3. 在ui.py添加UI选项
4. 更新README.md

### 调试
```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 运行特定组件
```python
# 测试学术搜索
from academic_search import get_academic_results
results = get_academic_results("machine learning", 5)
print(results)
```
