<div align="center">
   <img src=".github/assets/logo.png" alt="Logo" width="300">
   <br><a href="https://github.com/yourusername/IntelNexus/actions/workflows/binary.yml"><img alt="Build" src="https://github.com/apurvsinghgautam/robin/actions/workflows/binary.yml/badge.svg"></a>
   <h1>IntelNexus: AI驱动的多源网络情报分析平台</h1>

   <p>IntelNexus是一个AI驱动的网络情报分析平台，能够从学术论文、新闻文章、社交媒体和网页等多个来源搜索和分析信息，并利用LLM生成情报报告。</p>
   <a href="#安装">安装</a> &bull; <a href="#使用">使用</a> &bull; <a href="#功能">功能</a><br><br>
</div>

---

## 功能特点

- **多源搜索** - 同时搜索学术论文、新闻、社交媒体和网页内容
- **AI智能分析** - 利用LLM优化查询、过滤结果、生成情报报告
- **模块化架构** - 各搜索模块之间清晰分离
- **多模型支持** - 支持OpenAI、Claude、Gemini或本地Ollama模型
- **命令行模式** - 为终端用户和自动化设计
- **Web界面** - 基于Streamlit的图形界面
- **自定义报告** - 将分析结果导出为Markdown文件
- **可扩展** - 轻松接入新的搜索源或模型

## 支持的搜索源

| 数据源 | 说明 | 状态 |
|--------|------|------|
| 学术 | ArXiv, Semantic Scholar | ✅ |
| 新闻 | RSS订阅, NewsAPI | ✅ |
| 社交 | Reddit | ✅ |
| 网页 | Bing, DuckDuckGo | ✅ |
| 暗网 | Tor网络(可选) | ⚙️ |

---

## 安装

### 前置要求

- Python 3.10+
- Ollama (用于本地LLM，可选)

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

4. 配置API密钥(可选)：
```bash
cp .env.example .env
# 编辑 .env 文件添加你的API密钥
```

5. 运行：
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
python main.py search -q "深度学习" -s academic -m llama3.2:3b
python main.py search -q "AI新闻" -s news

# 自定义线程数和输出
python main.py search -q "神经网络" -t 8 -o 我的报告
```

### Web界面模式

```bash
python main.py ui
# 打开 http://localhost:8501
```

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
SEMANTIC_SCHOLAR_API_KEY=你的密钥
NEWS_API_KEY=你的密钥
TWITTER_BEARER_TOKEN=你的令牌

# 功能开关
ENABLE_DARKWEB=false  # 设为true启用暗网搜索
```

---

## 支持的模型

### 本地(Ollama)
- qwen2.5:7b (推荐)
- llama3.2:3b
- llama3.2:7b
- 等等...

### 云端
- GPT-4o / GPT-4.1
- Claude Sonnet
- Gemini Flash
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
├── web_search.py        # 网页搜索模块
├── academic_search.py   # 学术论文搜索
├── news_search.py       # 新闻搜索模块
├── social_search.py     # 社交媒体搜索
├── darkweb_search.py    # 暗网搜索(可选)
├── scrape.py            # 内容抓取
├── report_export.py    # 报告导出
├── search_history.py    # 搜索历史
├── trend_analysis.py   # 趋势分析
├── keyword_extraction.py # 关键词提取
├── multilang.py        # 多语言支持
└── requirements.txt    # 依赖
```

---

## 比赛与毕设

本项目适用于：

1. **创新创业大赛** - 多源AI情报分析
2. **毕业论文** - 网络情报研究结合LLM

### 核心创新点
- 多源数据融合(学术+新闻+社交+网页)
- 本地+云端LLM混合架构
- 自动化情报报告生成
- 可扩展的插件架构

---

## 声明

> 本工具仅用于教育和研究目的。
> 使用搜索API时请遵守相关法律法规和服务条款。

---

## 许可证

MIT License

---

## 致谢

- 原始项目：[Robin](https://github.com/apurvsinghgautam/robin) by Apurv Singh Gautam
- LLM框架：LangChain
- Web界面：Streamlit
