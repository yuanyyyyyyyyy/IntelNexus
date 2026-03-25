<div align="center">
   <img src=".github/assets/logo.png" alt="Logo" width="300">
   <br><a href="https://github.com/yourusername/IntelNexus/actions/workflows/binary.yml"><img alt="Build" src="https://github.com/apurvsinghgautam/robin/actions/workflows/binary.yml/badge.svg"></a>
   <h1>IntelNexus: AI驱动的多源网络情报分析平台</h1>

   <p>IntelNexus是一个AI驱动的网络情报分析平台，能够从网页、新闻和暗网等多个来源搜索和分析信息，并利用LLM生成专业的情报报告。</p>
   <a href="#安装">安装</a> &bull; <a href="#使用">使用</a> &bull; <a href="#差异化优势">差异化优势</a> &bull; <a href="#导出格式">导出</a><br><br>
</div>

---

## 差异化优势

| 特性 | 说明 | 竞品对比 |
|------|------|---------|
| **暗网搜索** | 支持访问.onion暗网资源，需Tor网络 | 多数竞品不支持 |
| **多引擎聚合** | 同时调用5个主流搜索引擎 | 单一搜索引擎 |
| **AI智能处理** | LLM自动优化查询、筛选结果、生成报告 | 简单罗列结果 |
| **本地+云端LLM** | 支持Ollama本地部署保护隐私 | 依赖云端API |
| **多格式导出** | PDF/Word/Excel/Markdown一键生成 | 单一格式 |
| **商业级报告** | 专业情报报告格式，含分析结论 | 原始搜索结果 |

### 核心价值

1. **一键生成专业报告** - 输入关键词，自动搜索、分析、导出完整报告
2. **隐私保护** - 可完全本地部署，无数据外泄风险
3. **多维分析** - AI从不同角度分析搜索结果，不是简单堆砌
4. **暗网情报** - 独家支持暗网数据源（需Tor）

---

## 功能特点

- **多源搜索** - 同时搜索网页、新闻资讯和暗网内容
- **AI智能分析** - 利用LLM优化查询、过滤结果、生成专业情报报告
- **多种导出格式** - 支持导出为PDF、Word、Excel、Markdown格式
- **模块化架构** - 各搜索模块之间清晰分离
- **多模型支持** - 支持OpenAI、Claude、Gemini及本地Ollama等多种模型
- **自定义模型** - 支持添加第三方模型（通义千问、智谱AI、文心一言等）
- **命令行模式** - 为终端用户和自动化设计
- **Web界面** - 基于Streamlit的图形界面（Light主题）
- **搜索结果展示** - 详细展示每条搜索结果的内容和链接

## 支持的搜索源

| 数据源 | 说明 | 状态 |
|--------|------|------|
| 网页 | Bing, DuckDuckGo, Yahoo, Yandex, Baidu | ✅ |
| 新闻 | RSS订阅, Google News, Bing News, NewsAPI | ✅ |
| 暗网 | Tor网络 + Ahmia搜索引擎 | ⚙️ |

---

## 安装

### 前置要求

- Python 3.10+
- Ollama (用于本地LLM，可选)
- Tor浏览器 (用于暗网搜索，可选)

### 快速开始

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/IntelNexus.git
cd IntelNexus
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. (可选) 安装并运行Ollama：
```bash
# 从 https://ollama.com 安装Ollama
ollama pull qwen2.5:7b
ollama serve
```

4. (可选) 安装Tor用于暗网搜索：
```bash
# 下载 https://www.torproject.org/download/
# 启动Tor守护进程
tor
```

5. 配置API密钥(可选)：
```bash
cp .env.example .env
# 编辑 .env 文件添加你的API密钥
```

6. 运行：
```bash
# 命令行模式
python main.py search -q "人工智能趋势" -m qwen2.5:7b

# Web界面模式
python main.py ui
```

---

## 使用

### 命令行模式

```bash
# 搜索所有来源
python main.py search -q "机器学习" -m qwen2.5:7b

# 搜索特定来源
python main.py search -q "深度学习" -s web -m llama3.2:3b
python main.py search -q "AI新闻" -s news
python main.py search -q "暗网情报" -s darkweb

# 自定义线程数和输出
python main.py search -q "神经网络" -t 8 -o 我的报告
```

### Web界面模式

```bash
python main.py ui
# 打开 http://localhost:8501
```

---

## 导出格式

支持4种导出格式：
- **Markdown** - 纯文本格式，便于分享
- **PDF** - 专业文档格式，适合正式报告
- **Word** - 可编辑的文档格式
- **Excel** - 表格形式展示数据

---

## 配置

创建 `.env` 文件：

```env
# LLM配置
OPENAI_API_KEY=你的openai密钥
ANTHROPIC_API_KEY=你的anthropic密钥
GOOGLE_API_KEY=你的google密钥

# 本地Ollama(推荐保护隐私)
OLLAMA_BASE_URL=http://127.0.0.1:11434

# OpenRouter(免费模型)
OPENROUTER_API_KEY=你的openrouter密钥

# 搜索API(可选)
NEWS_API_KEY=你的密钥

# 功能开关
ENABLE_DARKWEB=true  # 设为true启用暗网搜索（需要Tor）
```

---

## 支持的模型

### 本地(Ollama)
- qwen2.5:7b (推荐)
- llama3.2:3b
- llama3.2:7b
- deepseek-r1
- 等等...

### 云端
- OpenAI: GPT-4o, GPT-4.1
- Anthropic: Claude Sonnet, Claude Opus
- Google: Gemini Flash, Gemini Pro
- 阿里: 通义千问
- 智谱: GLM系列
- 百度: 文心一言
- 讯飞: 星火认知
- OpenRouter模型

---

## 项目结构

```
IntelNexus/
├── main.py              # CLI入口点
├── ui.py                # Streamlit Web界面
├── config.py            # 配置
├── llm.py               # LLM集成
├── llm_utils.py         # LLM工具
├── custom_models.py     # 自定义模型管理
├── web_search.py        # 网页搜索模块(5个引擎)
├── news_search.py       # 新闻搜索模块
├── darkweb_search.py   # 暗网搜索模块(Tor+Ahmia)
├── scrape.py            # 内容抓取
├── report_export.py    # 报告导出(PDF/Word/Excel/Markdown)
├── search_history.py   # 搜索历史
└── requirements.txt    # 依赖
```

---

## 声明

> 本工具仅用于教育和研究目的。
> 使用搜索API时请遵守相关法律法规和服务条款。
> 暗网搜索需要Tor网络，请确保遵守当地法律法规。

---

## 许可证

MIT License

---

## 致谢

- 原始项目：[Robin](https://github.com/apurvsinghgautam/robin) by Apurv Singh Gautam
- LLM框架：LangChain
- Web界面：Streamlit
