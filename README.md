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
| **暗网搜索** | 支持Ahmia(无需Tor) + OnionLink/TorDex(需Tor) + 自定义.onion站点 |
| **AI简报系统** | 自动采集、分析、推送每日AI情报简报 |

---

## 项目结构

```
IntelNexus/
├── main.py                     # CLI入口
├── ui.py                       # 统一 Streamlit Web 界面
├── config.py                   # 全局配置(环境变量)
├── requirements.txt            # 依赖清单
│
├── shared/                     # 共享库
│   ├── search/                 # 搜索(web.py, news.py, scraper.py)
│   ├── llm/                    # LLM核心(core.py, utils.py, models.py)
│   └── ui/                     # UI共享(styles.py, helpers.py)
│
├── intel-search/               # 搜索子项目
│   └── src/
│       ├── analysis/           # 分析(可信度/知识图谱/证据链)
│       ├── search/             # 暗网搜索(darkweb.py)
│       ├── export/             # 报告导出(MD/PDF/Word/Excel)
│       └── ui/                 # 搜索UI(i18n/sidebar/搜索流程/结果)
│
├── intel-briefing/             # 简报子项目
│   ├── ai_briefing/            # 简报核心(采集/分析/通知/调度/模板)
│   └── src/
│       ├── config/             # 简报配置(数据源/订阅者/历史)
│       ├── export/             # 简报PDF导出
│       └── ui/                 # 简报UI(i18n/简报预览/历史)
│
├── src/                        # 整合层
│   ├── config/                 # 配置壳(→子项目实源)
│   └── ui/                     # 合并版UI组件(整合搜索+简报)
│
└── data/                       # 数据目录
    ├── sources.json            # 数据源配置
    ├── subscriptions.json      # 订阅者配置
    └── briefings/              # 简报历史存档
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

### 推荐：使用 conda base 一键启动（无需手动激活）

项目依赖（torch / sentence-transformers / spaCy / streamlit 等）已随 Anaconda `base` 环境就绪，只需补全 spaCy 中英文模型：

```bash
setup.bat        # 一键初始化：激活 conda base + 下载 spaCy 模型（只需一次，已装会跳过）
run.bat ui       # 之后每次启动，双击 run.bat 即可，无需手动 activate
run.bat search -q "关键词"
```

`run.bat` 自动定位本机 Anaconda/Miniconda 并激活 `base` 环境后运行 `main.py`，彻底免去手动激活的麻烦。
若手动操作：`conda activate base` → `python -m spacy download en_core_web_sm zh_core_web_sm` → `python main.py ui`。

> 注意：spaCy 模型需从 GitHub 下载，若网络受限可参考 `setup.bat` 离线安装已下载好的 `zh_core_web_sm` wheel。

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
| 暗网 | Ahmia (公开访问，无需Tor) + OnionLink/TorDex (高级模式，需Tor)

---

## 声明

本工具仅用于教育和研究目的。使用时请遵守相关法律法规。

---

## 许可证

MIT License
