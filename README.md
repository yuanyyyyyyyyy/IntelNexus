<div align="center">
<h1>IntelNexus: AI驱动的多源网络情报分析平台</h1>
<p>从网页、新闻和暗网等多个来源搜索和分析信息，利用LLM生成专业的情报报告。</p>
<a href="#安装">安装</a> &bull; <a href="#使用">使用</a> &bull; <a href="#配置">配置</a><br><br>
</div>

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **多源搜索** | 同时搜索网页(Bing/DDG/Yahoo/Yandex/Baidu)、新闻和暗网 |
| **AI智能分析** | LLM自动优化查询、筛选结果、生成专业报告 |
| **本地+云端LLM** | 支持Ollama本地部署(GPT-4o/Claude/Gemini等云端模型) |
| **多格式导出** | 一键导出Markdown/PDF/Word/Excel |
| **暗网搜索** | 支持Ahmia暗网搜索引擎 |

---

## 项目结构

```
IntelNexus/
├── main.py              # CLI入口 (python main.py search/ui)
├── ui.py                # Streamlit Web界面
├── config.py            # 配置管理
├── requirements.txt      # 依赖清单
│
├── llm/                 # LLM模块
│   ├── llm.py           # LLM集成
│   ├── llm_utils.py      # LLM工具函数
│   └── custom_models.py  # 自定义模型管理
│
├── search/              # 搜索模块
│   ├── web_search.py    # 网页搜索(5个引擎)
│   ├── news_search.py   # 新闻搜索(RSS/Google/Bing)
│   └── darkweb_search.py # 暗网搜索(Ahmia)
│
├── scrape.py            # 内容抓取
├── report_export.py     # 报告导出
└── search_history.py    # 搜索历史
```

---

## 安装

### 前置要求

- Python 3.10+
- Ollama (本地模型，可选): https://ollama.com
- Tor (暗网搜索，可选): https://torproject.org

### 快速开始

```bash
# 1. 克隆项目
git clone <your-repo>
cd IntelNexus

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 (可选)
cp .env.example .env
# 编辑 .env 填入API密钥

# 4. 运行
python main.py ui          # Web界面 -> http://localhost:8501
python main.py search -q "关键词" -m qwen2.5:7b  # CLI模式
```

---

## 使用

### 命令行模式

```bash
# 搜索所有来源
python main.py search -q "人工智能趋势" -m qwen2.5:7b

# 搜索特定来源
python main.py search -q "机器学习" -s web
python main.py search -q "AI新闻" -s news
python main.py search -q "暗网情报" -s darkweb

# 参数说明
# -m: 选择模型 (默认 qwen2.5:7b)
# -s: 搜索模式 (web/news/darkweb/all)
# -t: 线程数 (默认5)
# -o: 输出文件名
```

### Web界面

```bash
python main.py ui
# 打开 http://localhost:8501
```

---

## 配置

创建 `.env` 文件：

```env
# 本地Ollama (推荐)
OLLAMA_BASE_URL=http://127.0.0.1:11434

# 云端模型 (可选)
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_API_KEY=xxx
OPENROUTER_API_KEY=xxx

# 暗网搜索 (可选)
ENABLE_DARKWEB=false
```

---

## 支持的模型

| 类型 | 示例 |
|------|------|
| 本地(Ollama) | qwen2.5:7b, llama3.2, deepseek-r1 |
| 云端 | GPT-4o, Claude Sonnet, Gemini Flash |
| OpenRouter | 各种免费模型 |

---

## 支持的搜索源

| 类型 | 来源 |
|------|------|
| 网页 | Bing, DuckDuckGo, Yahoo, Yandex, Baidu |
| 新闻 | Google News, Bing News, RSS订阅 |
| 暗网 | Ahmia (无需Tor) |

---

## 声明

本工具仅用于教育和研究目的。使用时请遵守相关法律法规。

---

## 许可证

MIT License