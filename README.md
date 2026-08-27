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
| **本地+自定义LLM** | 支持Ollama本地部署与界面添加自定义模型，不内置任何云端预设 |
| **多格式导出** | 一键导出Markdown/PDF/Word/Excel |
| **暗网搜索** | 支持Ahmia(无需Tor) + OnionLink/TorDex(需Tor) + 自定义.onion站点 |
| **Topic 中枢** | 搜索与简报共享的关注点注册表，驱动采集与推送的统一数据源 |
| **AI简报系统** | 自动采集、分析、推送每日AI与网络安全情报简报 |
| **增量感知** | 对比历史存档输出本期新增/消失条目，缓解信息过载 |
| **个性化订阅** | 订阅者按兴趣过滤推送类目，只收关心方向 |
| **知识图谱复用** | 简报复用实体关系图谱生成本期关系缩略图 |

---

## 项目结构

单包架构：搜索（取证工作台）与简报（巡防引擎）共享唯一 `intelnexus` 包，
由 `topics` 中枢串联，消除旧版多处 `sys.path` hack 与重复模块。

```
IntelNexus/
├── main.py                     # CLI入口（搜索 / 简报 / 调度）
├── ui.py                       # 统一 Streamlit Web 界面（搜索 + 简报合一）
├── config.py                   # 全局配置（环境变量）
├── requirements.txt            # 依赖清单
│
├── intelnexus/                 # 唯一业务包（原 shared/src/intel-search/intel-briefing 归一）
│   ├── core/                   # 底层：搜索 / LLM / 配置 / 日志 / 样式
│   ├── analysis/               # 可信度评分 / 证据链 / 实体关系图谱
│   ├── search_app/             # 搜索取证工作台（含暗网真身 darkweb.py）
│   ├── briefing/               # 简报巡防引擎（采集/分析/通知/调度/模板/导出）
│   ├── topics/                 # ★ Topic Registry 中枢（registry/store/diff）
│   ├── config/                 # data/ 下 JSON 读写（搜索历史/订阅者/简报历史）
│   └── ui/                     # 统一壳：合并搜索 UI 与简报视图
│
└── data/                       # 数据目录（JSON 持久化）
    ├── sources.json            # 数据源配置
    ├── subscriptions.json      # 订阅者配置（含 interests 个性化字段）
    ├── topics.json             # ★ Topic 中枢持久化（preset + 用户搜索沉淀）
    └── briefings/              # 简报历史存档（Delta 增量对比源）
```

### 情报操作系统：双向飞轮

```
搜索结果 ──(一键固化)──> Topic 常驻关注点 ──> 驱动简报巡防
   ^                                         │
   └────────(高严重度反查取证任务)──────────┘
```

- **Topic 中枢**：系统预设 6 类关注点 + 用户搜索行为沉淀的常驻 Topic，是采集与推送的统一数据源。
- **增量感知（Delta）**：简报对比历史存档，输出较上期的新增 / 消失条目，缓解信息过载。
- **个性化订阅**：订阅者按 `interests` 过滤类目，只收自己关心的方向。
- **知识图谱复用**：简报复用 IntelligenceGraph 生成本期实体关系缩略图，与分析共享深度。

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

### 推荐：双击脚本一键启动（Windows，已入库）

项目提供通用 Windows 脚本（自动创建隔离的 `.venv` 虚拟环境，不污染系统 Python）：

```bash
setup.bat              # 一键初始化：创建 .venv -> 安装核心依赖 -> 生成 .env 模板（只需一次）
run.bat                # 之后每次启动：双击即可启动 Web 界面
run.bat search -q "关键词"   # CLI模式
```

`setup.bat` 自动探测系统 Python（3.10+），在项目目录创建独立 `.venv` 并安装 `requirements.txt` 核心依赖；可选扩展（Anthropic/Gemini SDK、语义分析、NLP）见 `requirements-extras.txt`，缺失时相关功能自动降级。国内网络安装慢可按脚本提示使用清华镜像。

`run.bat` 优先使用 `.venv`，缺失时回退系统 Python；启动前自检核心依赖，未安装会提示先运行 `setup.bat`。

**纯命令行等价操作**（适用于非 Windows）：

```bash
python -m venv .venv                    # 创建虚拟环境（可选但推荐）
.venv\Scripts\activate                  # Windows 激活 / source .venv/bin/activate (Linux/macOS)
pip install -r requirements.txt         # 安装核心依赖
copy .env.example .env                  # 生成环境配置模板（全可留空）
python main.py ui                       # 启动 Web 界面
```

**分发给别人**：运行 `make_release.bat` 生成干净的分发 zip——自动排除你的 `.env`（密钥）、`data/`（订阅者隐私与历史简报）、`.venv`、`.git`，并在打包前扫描密钥泄露。

### 安全说明

- `data/` 目录包含凭据与用户数据（API key、SMTP 密码、订阅者信息、历史简报等），已通过 `.gitignore` 整目录忽略，请勿手动提交入库或随包分发。
- `.env` 同样含密钥，仅保留在本地；分发请优先使用 `make_release.bat`（自动排除敏感文件并扫描密钥泄露）。
- 自定义数据源/暗网站点/模型端点等 URL 入库时会进行协议与目标地址校验，拒绝非 http/https 协议及指向回环/内网/链路本地的地址（本地模型端点如 Ollama 除外）。

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

### 关注点类别（Topic 中枢）

系统预设 6 类关注点（亦可在 Web UI 中将搜索结果一键固化为常驻 Topic）：

| 类别 | 说明 |
|------|------|
| ai_gov_usage | 美欧政府/机构AI应用动态 |
| ai_china_narrative | 涉我AI相关舆论 |
| ai_legislation | AI相关法规政策 |
| ai_data_leak | AI数据泄露事件 |
| cyber_vuln | 网络安全漏洞与威胁 |
| cyber_attack | 网络攻击与事件 |

---

## 配置

创建 `.env` 文件（参考 `.env.example`）：

```env
# 本地Ollama (推荐，必填)
OLLAMA_BASE_URL=http://127.0.0.1:11434

# 自定义模型兜底密钥（可选，仅当界面添加的 OpenRouter/Google 类型模型未填密钥时使用）
# GOOGLE_API_KEY=xxx
# OPENROUTER_API_KEY=xxx

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

> 不内置任何云端预设模型。模型下拉只显示「本地 Ollama 自动探测到的模型」与「你在界面添加的自定义模型」。

| 类型 | 说明 / 示例 |
|------|------|
| 本地(Ollama) | 自动探测：qwen2.5:7b, llama3.2, deepseek-r1 等 |
| 自定义模型 | 在侧栏「添加自定义模型」中添加（OpenAI/Anthropic/Google/Ollama/OpenRouter 等），持久化到 data/custom_models.json，重启不丢失 |

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
