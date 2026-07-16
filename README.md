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
| **AI简报系统** | 自动采集、分析、推送每日AI情报简报 |

---

## 项目结构

```
IntelNexus/
├── main.py                 # CLI入口
├── ui.py                   # Streamlit Web界面入口
├── config.py               # 全局配置(环境变量)
├── requirements.txt        # 依赖清单
│
├── src/                    # 核心模块
│   ├── search/             # 搜索模块
│   │   ├── web.py          # 网页搜索(5个引擎)
│   │   ├── news.py         # 新闻搜索(RSS/Google/Bing)
│   │   ├── darkweb.py      # 暗网搜索(Ahmia)
│   │   └── scraper.py      # 内容抓取
│   ├── llm/                # LLM模块
│   │   ├── core.py         # LLM集成
│   │   ├── utils.py        # LLM工具函数
│   │   └── models.py       # 自定义模型管理
│   ├── analysis/           # 分析模块
│   │   ├── credibility.py  # 来源可信度评估
│   │   ├── intelligence_graph.py  # 知识图谱
│   │   └── evidence_tracer.py     # 证据链追踪
│   ├── export/             # 导出模块
│   │   └── report.py       # Markdown/PDF/Word/Excel导出
│   ├── config/             # 配置管理
│   │   ├── sources.py      # 数据源CRUD
│   │   ├── subscriptions.py # 订阅者CRUD
│   │   └── cache.py        # URL缓存
│   └── ui/                 # UI模块
│       ├── i18n.py         # 国际化(中/英)
│       ├── styles.py       # 样式
│       ├── sidebar.py      # 侧边栏
│       ├── search_pipeline.py  # 搜索流程
│       ├── results.py      # 结果展示
│       ├── download.py     # 下载功能
│       └── results_detail.py   # 结果详情
│
├── ai_briefing/            # AI简报模块
│   ├── config.py           # 简报配置(关注点/关键词)
│   ├── collector.py        # 数据采集器
│   ├── analyzer.py         # LLM分析生成器
│   ├── scheduler.py        # 定时调度器
│   ├── notifier.py         # 推送通知器(邮件/企微/钉钉)
│   ├── templates.py        # 简报模板(Markdown/HTML)
│   └── prompts.py          # LLM提示词
│
└── data/                   # 数据目录
    ├── sources.json        # 数据源配置
    └── subscriptions.json  # 订阅者配置
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

### AI简报系统

```bash
# 生成并推送简报给所有订阅者
python main.py briefing

# 启动后台调度器(按订阅者配置的时间自动推送)
python main.py scheduler
```

---

## AI简报系统

### 功能

- 自动采集4类AI情报：美欧机构AI应用、涉我AI舆论、AI新法案、AI数据泄露
- LLM分析生成结构化简报（TOP3亮点 + 分类详情 + 趋势洞察）
- 多渠道推送：邮件(SMTP)、企业微信(Webhook)、钉钉(Webhook)
- 定时调度：按订阅者配置推送时间和频率

### 快速开始

1. 配置 `.env` 文件（参考 `.env.example`）
2. 启动 Streamlit UI: `python main.py ui`
3. 侧边栏 → 订阅管理 → 添加订阅者（填写邮箱 + 选择推送渠道）
4. 侧边栏 → 邮件设置 → 配置 SMTP 服务器
5. 点击"立即生成简报"测试

### 关注点类别

| 类别 | 说明 |
|------|------|
| ai_gov_usage | 美欧政府/机构AI应用动态 |
| ai_china_narrative | 涉我AI相关舆论 |
| ai_legislation | AI相关法规政策 |
| ai_data_leak | AI数据泄露事件 |

---

## 配置

创建 `.env` 文件（参考 `.env.example`）：

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

# SMTP邮件推送 (可选)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your-password
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
