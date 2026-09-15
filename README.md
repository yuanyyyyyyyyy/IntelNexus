<div align="center">
<h1>IntelNexus: AI驱动的多源网络情报分析平台</h1>
<p>以可信度评估、证据链追溯与冲突检测为分析内核，上接多源采集、下接增量简报——让每一条情报结论都可评分、可溯源、可核验。</p>
<a href="#安装">安装</a> &bull; <a href="#使用">使用</a> &bull; <a href="#配置">配置</a><br>
<p><strong>非技术用户？</strong> 请阅读 <a href="USER_GUIDE.md"> 用户使用指南</a>（无需编程知识）</p>
</div>

---

## 核心特性

系统的能力分为三层：**分析内核**是本项目真正要解决的部分，采集层是它的输入端，分发层是它的输出端。

### 分析内核（平台核心）

| 特性 | 说明 |
|------|------|
| **可信度评估** | 域名权威度 / 时效性 / 内容深度 / 跨源语义一致性多因子评分，划分主证源·佐证源·孤证源 |
| **证据链追溯** | 报告结论与原文语义对齐，内联角标一键回溯出处，形成"结论—证据—来源"链路 |
| **冲突检测** | 数值 / 时间 / 立场三类跨源冲突识别，如实呈现分歧而非强行统一 |
| **知识图谱** | 中英文实体抽取 + 共现关系建图，中心度与社区发现识别核心实体，可交互可视化 |
| **结构化摘要** | 事实 / 分析 / 推测三级拆分 + 整体置信度，派生 TL;DR 速览与行动建议 |
| **知识库 RAG** | 语义检索收藏条目，经编码后注入搜索管线与简报分析，历史情报可复用 |
| **AI 分析管线** | LLM 优化查询、筛选弱相关结果、流式生成结构化情报报告 |

### 采集层（分析的上游）

| 特性 | 说明 |
|------|------|
| **多源并发检索** | 网页(Bing/DDG/Yahoo/Yandex/百度)、新闻、威胁情报(NVD/CISA KEV/CNVD/OTX/ExploitDB)、小红书 UGC、RSS 等数据源统一调度 |
| **暗网检索** | Ahmia(无需Tor) + OnionLink/TorDex(需Tor) + 自定义.onion站点，默认关闭 |
| **健康面板** | 数据源可达性实时监控，连续失败的源自动降级，不拖慢整体检索 |

### 分发层（分析的下游）

| 特性 | 说明 |
|------|------|
| **Topic 中枢** | 搜索与简报共享的关注点注册表，驱动"搜索发现→简报追踪"双向飞轮 |
| **增量感知** | 对比历史存档输出本期新增 / 消失条目，缓解长期信息过载 |
| **个性化订阅** | 订阅者按兴趣类目过滤，只收关心方向；支持邮件 / 企业微信 / 钉钉 |

### 通用能力

| 特性 | 说明 |
|------|------|
| **本地+自定义LLM** | 支持Ollama本地部署与界面添加自定义模型，不内置任何云端预设 |
| **多格式导出** | 一键导出Markdown/PDF/Word/Excel，专业排版含中日韩字体 |

---

## 与现有工具的区别

搜索与简报本身不是目的，它们分别是分析内核的输入端与输出端。这决定了本系统与三类现有工具的边界：

| 对比对象 | 它做什么 | IntelNexus 多做了什么 |
|---------|---------|---------------------|
| 通用搜索引擎 / 元搜索聚合器<br>（百度、SearxNG） | 返回排序后的结果列表 | 对每条来源做可信度量化、检测跨源冲突、把报告结论回链到原文证据；交付的是可核验的分析报告而非链接列表 |
| 答案引擎<br>（Perplexity、New Bing） | 归纳公开网页并直接给出答案 | 额外接入威胁情报与暗网源；生成前有可信度与冲突上下文约束，生成后有证据链标注；并支持 Topic 持续追踪 |
| 定时爬虫 + 邮件群发 / RSS 订阅 | 定期抓取并推送链接 | 简报内容经同一套分析内核处理（LLM 分析 + 可信度评分 + 实体图谱），并与历史存档做增量对比，只推本期新增与消失 |

---

## 项目结构

单包架构：分析内核（`analysis`）居中，搜索（采集入口）与简报（分发出口）分居两侧并共享唯一 `intelnexus` 包，
由 `topics` 中枢串联，消除旧版多处 `sys.path` hack 与重复模块。

```
IntelNexus/
├── main.py                     # CLI入口（搜索 / 简报 / 调度）
├── ui.py                       # 统一 Streamlit Web 界面（首页 + 搜索 + 简报 + 知识库）
├── config.py                   # 全局配置（环境变量 + 功能开关）
├── requirements.txt            # 核心依赖清单
├── requirements-extras.txt     # 可选扩展（Anthropic/Gemini/NLP/图表）
├── requirements-build.txt      # EXE 构建依赖（排除重型可选包）
│
├── intelnexus/                 # 唯一业务包
│   ├── core/                   # 底层：搜索 / LLM / 配置 / 日志 / 安全 / 样式
│   │   ├── search/             #   搜索框架：注册表 / 源抽象 / 并发调度
│   │   │   └── sources/        #     各数据源实现（15+ 源）
│   │   ├── llm/                #   LLM 客户端（Ollama/OpenAI/自定义模型）
│   │   ├── security/           #   URL 安全校验（防 SSRF）
│   │   └── settings/           #   JSON 配置读写 + 文件锁 + 结果缓存
│   ├── analysis/               # 【分析内核】可信度评分 / 证据链 / 冲突检测 / 实体关系图谱 / 结构化摘要
│   ├── briefing/               # 【分发层】简报巡防引擎（采集/分析/通知/调度/模板/导出）
│   ├── topics/                 # Topic Registry 中枢（registry/store/diff）
│   ├── knowledge/              # 知识库语义检索（RAG 注入搜索与简报）
│   ├── export/                 # 报告导出（PDF/Word/Excel + CJK 字体注册）
│   ├── config/                 # data/ 下 JSON 读写（搜索历史/订阅者/邮件/代理）
│   ├── search_app/             # 暗网搜索真身（darkweb.py）
│   └── ui/                     # 统一壳：首页概览/搜索/简报中心/知识库/侧边栏/图标
│
├── static/fonts/               # 自托管 Web 字体（Inter/Playfair/Noto Serif SC 等）
├── lib/                        # 前端库（vis-network/tom-select）
├── presets/                    # 预设数据（OPML 订阅源）
├── hooks/                      # PyInstaller 运行时钩子
├── tests/                      # 测试套件（60+ 测试文件）
│
└── data/                       # 数据目录（JSON 持久化，.gitignore 忽略）
    ├── sources.json            # 数据源配置
    ├── subscriptions.json      # 订阅者配置（含 interests 个性化字段）
    ├── topics.json             # Topic 中枢持久化（preset + 用户搜索沉淀）
    ├── knowledge_base.json     # 知识库条目
    └── briefings/              # 简报历史存档（Delta 增量对比源）
```

### 双向飞轮：从搜索发现到简报追踪

采集层与分发层通过 Topic 中枢闭环，两端共用同一套分析内核——简报不是另一套分析，而是同一分析能力在周期性场景下的复用。

```
搜索结果 ──(一键固化)──> Topic 常驻关注点 ──> 驱动简报巡防
   ^                                         │
   └────────(高严重度反查取证任务)──────────┘
```

- **Topic 中枢**：系统预设 6 类关注点 + 用户搜索行为沉淀的常驻 Topic，是采集与推送的统一数据源。
- **增量感知（Delta）**：简报对比历史存档，输出较上期的新增 / 消失条目，缓解信息过载。
- **个性化订阅**：订阅者按 `interests` 过滤类目，只收自己关心的方向。
- **知识图谱复用**：简报复用 IntelligenceGraph 生成本期实体关系缩略图，与分析共享深度。
- **知识库 RAG**：收藏条目经语义编码后注入搜索管线与简报分析，让历史情报可复用。

---

## 安装

### 前置要求

- Python 3.10+（源码版需要；EXE 版不需要）
- Ollama (本地模型，可选): https://ollama.com
- Tor (暗网搜索，可选): https://torproject.org

### 快速开始

#### EXE 版本（推荐，无需安装 Python）

1. 从 [Releases](https://github.com/yuanyyyyyyyyy/IntelNexus/releases) 下载 `IntelNexus-Windows-*.zip`
2. 解压后双击 **`launcher.bat`**
3. 浏览器自动打开，按界面引导配置 AI 模型即可

#### 源码版本

```bash
# 1. 克隆项目
git clone <your-repo>
cd IntelNexus

# 2. 一键启动（自动安装依赖）
start.bat              # Windows：双击即可
# 或手动安装：
pip install -r requirements.txt
python main.py ui      # Web界面 -> http://localhost:8501
```

`start.bat` 自动检测是否需要首次安装依赖，完成后启动 Web 界面并自动打开浏览器。

> 也保留传统的 `setup.bat` + `run.bat` 两步方式，适合需要更细粒度控制的场景。

**纯命令行等价操作**（适用于非 Windows）：

```bash
python -m venv .venv                    # 创建虚拟环境（可选但推荐）
.venv/Scripts/activate                  # Windows 激活 / source .venv/bin/activate (Linux/macOS)
pip install -r requirements.txt         # 安装核心依赖
copy .env.example .env                  # 生成环境配置模板（全可留空）
python main.py ui                       # 启动 Web 界面（自动打开浏览器）
```

### 分发给别人

**EXE 分发**（推荐）：从 Releases 下载构建好的 EXE 包，或本地运行 `python build_exe.py` 构建。接收者双击 `launcher.bat` 即可使用。

**源码分发**：运行 `make_release.bat` 生成干净的源码 zip——自动排除 `.env`（密钥）、`data/`（隐私数据）、`.venv`、`.git`，校验关键资源完整性，并在打包前扫描密钥泄露。接收者双击 `start.bat` 一键启动。

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
python main.py search -q "CVE漏洞" -s threat

# 参数说明
# -m: 选择模型 (默认 qwen2.5:7b)
# -s: 搜索模式 (web/news/darkweb/threat/all)
# -t: 线程数 (默认5)
# -o: 输出文件名
```

### Web界面

```bash
python main.py ui
# 打开 http://localhost:8501
# 界面包含四个主 Tab：首页概览 / 情报搜索 / 简报中心 / 知识库
```

### AI简报系统

```bash
# 生成并推送简报给所有订阅者
python main.py briefing

# 启动后台调度器(按订阅者配置的时间自动推送)
python main.py scheduler
```

---

## AI简报系统（分发层）

> 简报不是独立于搜索的第二个产品：它复用同一套分析内核（LLM 分析 + 可信度评分 + 实体图谱 + 知识库 RAG），
> 把"一次性查询"变成"周期性巡防"，并额外提供与历史存档的增量对比。

### 功能

- 按 Topic 中枢周期性采集 6 类关注点：美欧机构AI应用、涉我AI舆论、AI新法案、AI数据泄露、漏洞与威胁、攻击事件与合规
- 复用分析内核：LLM 生成结构化简报（TOP3亮点 + 分类详情 + 趋势洞察），条目附带可信度评分与冲突标记
- 增量感知：对比历史存档标注新增/消失条目
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
| cyber_attack | 网络攻击事件与合规 |

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

# 功能开关 (可选，全部有默认值，详见 .env.example)
# ENABLE_CREDIBILITY=true        # 可信度评估与知识图谱
# ENABLE_VISUALIZATION=true      # 搜索结果图表可视化
# ENABLE_OTX=false               # AlienVault OTX 威胁情报
# ENABLE_NVD=false               # NVD 国家漏洞数据库（无 API key 时限速 6s/请求）
# ENABLE_EXPLOITDB=false         # Exploit-DB 利用代码（首次约 10MB CSV，缓存 24h）
# ENABLE_CNVD=false              # CNVD 国内漏洞库（站点有反爬校验，常返回空）
# ENABLE_XIAOHONGSHU=false       # 小红书（需先配置站内检索后端；见「站内检索后端」小节）
```

站内检索后端也可用环境变量配置（详见 `.env.example`）：`SITE_SEARCH_PROVIDER`、`BOCHA_API_KEY`、`BRAVE_API_KEY`、`GOOGLE_CSE_API_KEY`、`GOOGLE_CSE_ID`。

完整的环境变量模板见 `.env.example`，包含所有功能开关的默认值。

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
| 威胁情报 | HackerNews, ExploitDB, OTX, NVD, CISA KEV, CNVD, 安全社区 |
| 暗网 | Ahmia (公开访问，无需Tor) + OnionLink/TorDex (高级模式，需Tor) |
| 自定义 | 小红书（SOCMINT 源，经站内检索后端按站内限定语义取数；需先配置博查 / Brave / Google CSE 的 Key，默认关闭，见下方「站内检索后端」）；用户通过 UI 添加的自定义搜索源 |

### 站内检索后端（小红书等站内源）

小红书源需要「站内检索后端」按站内限定语义取数。实测公共网页引擎全部不可用，因此必须自备 Key：

| 引擎 | 实测结果（2026-09-15） |
|------|------------------------|
| `cn.bing.com` | 完全忽略 `site:` 算子（`log4j` / `site:github.com log4j` / `site:csdn.net log4j` 返回同一结果集） |
| `www.baidu.com` | 返回「百度安全验证」反爬页，解析不到条目 |
| `html.duckduckgo.com` | HTTP 202 挑战页，0 个结果块 |
| `bing.com/search?format=rss` | 200 但有 RSS 同样忽略 `site:` |

在侧栏「搜索服务设置」→「站内检索后端」填写即可（也可用环境变量兜底）：

| Provider | 所需凭证 | 额度 / 计费 | 超限表现 | 网络 |
|----------|----------|-------------|----------|------|
| **博查 Bocha（推荐）** | `BOCHA_API_KEY` | 充值制（注册后请自行确认赠送额度） | HTTP 403（据第三方资料为 `You do not have enough money`，也可能为权限/策略拒绝）→ 源报「余额不足或权限受限」并降级 | **国内可直连，无需代理** |
| Brave Web Search API | `BRAVE_API_KEY` | 据第三方资料已改按量计费（约 $5 / 1000 次）且需绑卡 —— **请自行核实** | HTTP 429 → 源报「频率限制」并降级 | 需代理 |
| Google Custom Search JSON API | `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID`（CX） | **官方已「不再向新客户开放」**，仅存量 Key 可用（存量客户须 2027-01-01 前迁移） | HTTP 403 `dailyLimitExceeded` | 需代理 |

申请步骤：

1. **博查（推荐）**：到 [open.bochaai.com](https://open.bochaai.com/) 注册 → 进入**控制台** → **API KEY 管理** → 创建密钥，填入 `BOCHA_API_KEY`。国内可直连、无需代理；注意为充值制。
2. **Brave**：到 [api.search.brave.com](https://api.search.brave.com/) 注册并订阅 → 复制令牌填入 `BRAVE_API_KEY`。2026 年起条款有变动，**请在官网核实当前额度与是否需绑卡**。
3. **Google CSE（仅存量客户）**：Google 官方文档（2026-02 更新）已声明该 API *「不再向新客户开放」*，存量客户须在 **2027-01-01** 前迁移，因此**新用户无法再申请**；本源保留该 Provider 仅为兼容已有 Key。

`SITE_SEARCH_PROVIDER` 可取 `auto`（默认，按 **博查 > Brave > Google CSE** 择一）、`bocha`、`brave`、`google_cse`。三者都未配置时，小红书源会给出「未配置站内检索后端」的明确失败提示，**不会静默返回空**。

> 实现说明：博查的站内限定参数字段名（`include`）、`count`/`summary` 参数与**错误码语义**均来自第三方文档、**官方文档尚未证实**；即使 `include` 不生效，结果仍会被站内域名白名单后置过滤，**正确性不受影响，仅召回量下降**。错误文案刻意不写死单一原因（如 403 只说「余额可能不足或权限受限」，原始 `message` 会一并带出）。

该后端是**通用能力**（输入「域名 + 查询」），后续要接入微博 / 知乎 / CSDN 等站点，只需复用 `SiteScopedSource`（或再叠一个薄子类），无需改动核心系统。

### 如何验证小红书源有效

配置完 Key 后，按这三步确认（都在侧栏「搜索服务设置」→「站内检索后端」）：

1. **看凭证状态**：面板按 Provider 显示「已配置（`sk-9***4b21`）/ 未配置」。输入框**恒为空白**是刻意的——密码框不回填明文；要确认 Key 是否已保存，看这一行。
2. **点「测试连接」**：发起 1 次最小查询（1 条结果、不取摘要），回答「后端能不能通、Key 有没有效」。凭证有效时消耗 1 次查询额度，凭证无效（HTTP 401）不产生有效检索。结论会写入健康表。
3. **点「试搜小红书」**：真实跑一次站内检索，回答「能不能取到小红书站内内容」。结果会显示「后端返回 N 条，过滤后保留 M 条」。出现 0 条时分两种情况，面板会分别提示：
   - **后端返回 0 条** → 索引未命中该词；
   - **后端有返回、过滤后 0 条** → 相关性过滤生效（正常行为），说明该词在小红书内没有相关内容，**不是源故障**。

若小红书源在「数据源健康」面板显示为**降级/停用**：那是历史失败留下的**陈旧状态**，不代表当前不可用——保存 Key 时会自动重置，也可在该行点「重置」手动清除。

> 已知并已修复的陷阱：旧版「查到 0 条」既不计成功也不计失败，导致连续未命中后失败计数永不下降，源被长期钉在降级、攒满 6 次后转停用并被停止投递（无自愈路径）。现由源**自述**语义——站内源（`SiteScopedSource`）零结果按成功计，其余源保持原有保守语义不变。

### 小红书源的适用边界（重要）

实测结论：小红书是**生活方式平台**，对「漏洞 / CVE / 技术型」查询几乎没有相关内容。一次试搜的 10 条结果经项目评分器打分 **10/10 均为 0.0**（低于阈值 `RELEVANCE_THRESHOLD=0.3`），其中还混有商业平台页（`pgy.`）与登录页（`ipp.`）。

- **适用**：品牌名、产品名、事件名等**舆情 / 事件型**关键词（SOCMINT 线索发现）；
- **不适用**：CVE 编号、漏洞技术细节、攻击手法等技术情报——请用 NVD / ExploitDB / CNVD / 安全媒体源。

去噪策略：只拦**已知非笔记**页面（黑名单：非笔记子域 + 索引页路径），**刻意不用路径白名单**——白名单会误杀 `/user/profile/`、`/search_result`、带 `xsec_token` 等笔记 URL 形态；其余交给与网页源一致的相关性过滤（同一阈值常量），宁可返回 0 条也不返回噪声。

### SOCMINT 定位与合规边界

小红书在本项目中定位为 **SOCMINT（社交媒体情报）数据源**：与 NVD / ExploitDB（技术证据）、新闻与博客（公开报道）并置，由可信度评估（`analysis/credibility.py`）、证据链与知识图谱完成多源交叉印证；小红书结果按「内容平台」计分，来源归因显示为 `Xiaohongshu`。

本项目**不内置**小红书登录态采集：不直连其接口、不模拟登录/签名、不绕过任何反爬，也不内置 MediaCrawler / 浏览器自动化 / 图片 OCR / 评论采集。理由是小红书无面向公开开发者的笔记搜索 API（开放平台面向品牌方与企业授权），第三方采集依赖登录态且违反平台协议，同时会引入 Chromium 等重型依赖、显著抬高打包成本。若确需原生采集，请自行实现 `SiteSearchBackend` 并通过工厂挂载为**外部可选 Provider**，并自行承担合规责任。

---

## 声明

本工具仅用于教育和研究目的。使用时请遵守相关法律法规。

---

## 许可证

MIT License
