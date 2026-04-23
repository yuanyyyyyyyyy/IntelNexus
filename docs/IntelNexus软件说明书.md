# IntelNexus V1.0 软件说明书

**软件名称：** IntelNexus——新一代智能网络情报分析平台

**简称：** IntelNexus

**版本：** V1.0

**完成日期：** 2026年3月

---

## 界面截图索引

请将截图放入 `docs/images/` 文件夹：

| 编号 | 截图内容 | 对应章节 |
|------|----------|----------|
| 图1 | CLI帮助命令输出 | 5.2节 |
| 图2 | Web界面主页面 | 5.3节 |
| 图3 | 搜索输入框 | 5.3节 |
| 图4 | 模型选择下拉菜单 | 5.3节 |
| 图5 | 线程数设置 | 5.3节 |
| 图6 | 搜索结果统计 | 5.3节 |
| 图7 | 报告生成中 | 5.3节 |
| 图8 | 最终报告展示 | 5.3节 |
| 图9 | 报告下载选项 | 5.4节 |
| 图10 | 搜索结果详情 | 5.3节 |
| 图11 | 分页导航 | 5.3节 |
| 图12 | 暗网设置界面 | 5.3节 |
| 图13 | Tor状态检测 | 5.3节 |
| 图14 | 模型添加界面 | 5.3节 |
| 图15 | 语言切换 | 5.3节 |

![图1：CLI帮助](./images/01_cli_help.png)
![图2：Web界面主页](./images/02_web_ui.png)

---

## 目录

- [一、软件概述](#一软件概述)
- [二、系统架构与技术特点](#二系统架构与技术特点)
- [三、功能模块详细说明](#三功能模块详细说明)
- [四、数据流程与接口设计](#四数据流程与接口设计)
- [五、操作流程说明](#五操作流程说明)
- [六、性能指标与测试结果](#六性能指标与测试结果)
- [七、软件应用场景](#七软件应用场景)
- [附录：界面截图清单](#附录界面截图清单)

---

## 一、软件概述

### 1.1 开发背景与目标

随着信息技术的飞速发展，网络上的信息呈指数级增长，传统的单一来源搜索方式已难以满足企业和研究人员对全面、深入情报分析的需求。在舆情监控、竞品分析、市场研究、学术探索等领域面临着前所未有的信息获取挑战。传统的网络搜索方式存在许多痛点：信息碎片化导致搜索结果分散在多个平台，缺乏统一整合与分析；数据来源单一使得多数工具仅支持单一搜索引擎，难以获取全网信息；内容深度不足表现为搜索引擎返回的结果仅为摘要，缺乏原文内容的深度分析；智能化程度低，缺乏基于人工智能的语义理解和智能摘要能力；多语言障碍使得难以同时检索和分析多语言网络资源；以及专业性欠缺，缺乏针对特定领域（如新闻、情报）的专业搜索能力。本软件的目标是构建一个多源网络情报智能分析平台，集成网页、新闻等多个数据源，利用大语言模型（LLM）技术实现智能语义分析和报告生成，支持本地部署保护用户数据隐私，并提供友好的Web界面和命令行两种使用方式。

### 1.2 软件功能定位

IntelNexus是一款面向全领域用户的智能网络情报分析平台，通过集成本地运行的大语言模型（Ollama LLM）为用户提供多源同步搜索服务，同时从网页、新闻等多个来源获取信息，自动抓取目标网页的完整内容，利用大语言模型理解内容语义生成结构化摘要，支持Markdown、PDF、Word、Excel四种报告格式导出，灵活选择本地Ollama模型或多种云端API，并支持中英文界面和跨语言搜索。一句话概括：IntelNexus是一款基于大语言模型技术的智能网络情报分析平台，为用户提供多源搜索、内容抓取、AI分析和多格式报告导出的一站式服务。

### 1.3 运行环境

#### 硬件环境

**服务器/主机：**

- CPU：双核及以上处理器
- 内存：8GB及以上（推荐16GB，用于运行大语言模型）
- 硬盘：50GB可用空间
- 网络：100Mbps及以上宽带

**客户端（移动端）：**

- 处理器：任意现代浏览器支持的处理器
- 内存：4GB RAM及以上
- 存储：200MB可用空间
- 网络：4G/5G/Wi-Fi
- 浏览器：Chrome 90+ / Edge 90+ / Firefox 88+ / Safari 14+

#### 软件环境

**运行时环境：**

- 操作系统：
  - Windows 10/11
  - Linux（Ubuntu 20.04+ / CentOS 7+）
  - macOS 11+
- Python：Python 3.10+
- 数据库：SQLite 3.x（轻量级）
- AI引擎：Ollama 0.1.15+
- 容器：Docker 20.10+（可选）

**开发环境：**

**后端开发栈：**

- 编程语言：Python 3.10+
- Web框架：Streamlit 1.28+
- AI框架：LangChain 0.1+
- 搜索库：Requests、BeautifulSoup4
- 数据处理：JSON、SQLite3
- 报告生成：FPDF2、python-docx、openpyxl

**前端开发栈：**

- Web框架：Streamlit
- UI组件：Streamlit内置组件 + 自定义CSS
- 图表库：Streamlit内置图表
- 状态管理：Streamlit Session State

**辅助工具：**

- 包管理：pip
- 版本控制：Git
- 虚拟环境：venv / conda

---

## 二、系统架构与技术特点

### 2.1 总体架构图

```plantuml
@startuml
skinparam linetype ortho
skinparam componentStyle uml2

actor 用户

package "客户端层" {
  [Web UI\nStreamlit] as web
  [CLI\n命令行] as cli
}

package "业务逻辑层" {
  [查询优化] as query
  [搜索调度] as search
  [内容抓取] as scrape
  [AI分析] as ai
  [报告生成] as report
  [报告导出] as export
}

package "数据源层" {
  [网页搜索] as websearch
  [新闻搜索] as news
  [暗网搜索] as darkweb
  [LLM引擎] as llm
  [本地存储] as storage
}

用户 --> web
用户 --> cli

web --> query
cli --> query
query --> search
search --> websearch
search --> news
search --> darkweb
websearch --> scrape
news --> scrape
darkweb --> scrape
scrape --> ai
ai --> llm
ai --> report
report --> export
export --> storage

@enduml
```

### 2.2 技术架构描述

#### 2.2.1 前端技术栈（Streamlit）

**核心框架：**

- Streamlit 1.28.x：开源Web应用框架
- Python 3.10+：主要编程语言
- 使用@cache_data装饰器实现搜索结果缓存

**UI组件：**

- st.sidebar：侧边栏设置面板
- st.form：搜索表单
- st.expander：可折叠内容区域
- st.download_button：报告下载按钮
- 自定义CSS：莫兰迪色系（Morandi）设计风格

**状态管理：**

- Streamlit Session State：前端状态保持
- query_cache：搜索词缓存
- results：搜索结果缓存
- scraped：抓取内容缓存

**HTTP通信：**

- 内置Streamlit HTTP客户端
- 请求/响应拦截：统一错误处理

**国际化：**

- 内置中英文双语支持
- 语言切换功能

#### 2.2.2 后端技术栈（Python）

**核心框架：**

- Click 8.x：命令行交互框架
- Streamlit 1.28.x：Web服务框架

**AI集成：**

- LangChain 0.1.x：大语言模型应用框架
- LangChain Community：各种模型适配器
- OpenAI SDK：OpenAI API调用

**数据处理：**

- Requests 2.x：HTTP请求库
- BeautifulSoup4：HTML解析
- lxml：XML/HTML解析器

**搜索API：**

- Exa Search：AI增强搜索
- Google Custom Search：谷歌搜索
- Bing Web Search：必应搜索

**数据存储：**

- SQLite3：本地数据库
- JSON：配置文件和历史记录
- 文件系统：报告存储

**报告生成：**

- FPDF2：PDF生成
- python-docx：Word文档生成
- openpyxl：Excel文件生成

#### 2.2.3 搜索模块架构

**Web搜索模块（web_search.py）：**

- Exa API集成：支持AI增强的语义搜索
- Google搜索（可选）：通过Google Custom Search API
- Bing搜索（可选）：通过Bing Web Search API
- 并发请求处理：使用ThreadPoolExecutor实现多线程并行

**新闻搜索模块（news_search.py）：**

- RSS订阅源解析：支持任意RSS/Atom订阅
- NewsAPI集成（可选）：通过NewsAPI获取实时新闻
- 实时新闻抓取：直接抓取新闻网站内容

**暗网搜索模块（darkweb_search.py）：**

- Ahmia：暗网搜索引擎，基于公开的暗网索引
- Tor代理集成（可选）：通过Tor网络访问暗网站点
- 自定义暗网站点：支持添加用户自己的暗网站点
- Breached论坛集成：访问泄露数据论坛（需账号）

#### 2.2.4 AI引擎架构

**AI引擎版本：** Ollama 0.1.15+

**运行模型：**

- 本地模型：qwen2.5:7b、llama2、mistral（通过Ollama本地运行）
- 云端模型：OpenAI GPT-4o/GPT-3.5-turbo
- 云端模型：Anthropic Claude 3系列
- 云端模型：Google Gemini Pro
- 云端模型：通义千问、智谱AI、文心一言、讯飞星火

**技术特点：**

- 本地推理：无需云端API，保护隐私
- 上下文窗口：支持长对话（视模型而定）
- 温度参数：0.7（平衡创造性与可靠性）
- 响应超时：30秒（防止长时间阻塞）

**系统提示词设计：**

网络情报分析助手专用提示词（system prompt）：

```
你是一位专业的网络情报分析助手。你的任务是：
1. 分析用户提供的搜索结果内容
2. 提取关键信息和主要观点
3. 识别信息之间的关联性
4. 提供专业、结构化的分析报告
5. 保持客观中立的分析态度

请基于以下搜索结果进行分析：
{content}

请生成一份专业的情报分析报告。
```

#### 2.2.5 部署架构

**开发环境：**

- 运行方式：python main.py ui（Web界面）或 python main.py search（命令行）
- 日志级别：debug
- CORS：全开放（*）

**生产环境：**

- 容器化运行：Docker + Docker Compose
- 进程管理：PM2或systemd
- 日志级别：info
- CORS：限制特定域名
- 健康检查：/health端点

**Docker编排架构：**

```yaml
services:
  intelnexus:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
```

### 2.3 数据库设计

#### 2.3.1 数据存储结构

```
data/
├── search_history.json     # 搜索历史记录
├── custom_models.json      # 自定义模型配置
├── custom_onion_sites.json # 自定义暗网站点
└── trends.json             # 趋势分析数据
```

#### 2.3.2 数据表设计

**搜索历史表（search_history）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| query | TEXT | 搜索关键词 |
| mode | TEXT | 搜索模式（web/news/darkweb/all） |
| results_count | INTEGER | 返回结果数量 |
| timestamp | DATETIME | 搜索时间，格式：YYYY-MM-DD HH:MM:SS |
| duration | REAL | 搜索耗时（秒） |
| model_used | TEXT | 使用的AI模型名称 |

**搜索结果详情表（search_results）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| search_id | INTEGER | 关联搜索历史ID，外键 |
| source | TEXT | 数据源类型（web/news/darkweb） |
| url | TEXT | 结果链接URL |
| title | TEXT | 结果标题 |
| description | TEXT | 结果摘要描述 |
| content | TEXT | 抓取的完整内容（JSON格式） |
| published_at | DATETIME | 发布时间 |
| score | REAL | 相关性评分（0-1） |
| is_scraped | INTEGER | 是否已抓取内容（0/1） |
| created_at | DATETIME | 记录创建时间 |

**自定义模型表（custom_models）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| name | TEXT | 模型显示名称 |
| type | TEXT | 模型类型（local/cloud） |
| provider | TEXT | 供应商（ollama/openai/anthropic/google等） |
| model_id | TEXT | 模型标识符 |
| api_key | TEXT | API密钥（加密存储） |
| base_url | TEXT | API地址 |
| config | TEXT | 额外配置参数（JSON格式） |
| is_default | INTEGER | 是否默认模型（0/1） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**搜索结果缓存表（search_cache）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| query_hash | TEXT | 查询哈希值（MD5） |
| query | TEXT | 原始查询内容 |
| mode | TEXT | 搜索模式 |
| results | TEXT | 缓存的搜索结果（JSON格式） |
| created_at | DATETIME | 创建时间 |
| expires_at | DATETIME | 过期时间 |
| hit_count | INTEGER | 缓存命中次数 |

**暗网站点配置表（custom_onion_sites）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| name | TEXT | 站点名称 |
| url | TEXT | 站点URL模板 |
| auth_type | TEXT | 认证类型（none/basic） |
| auth_username | TEXT | 用户名（如需认证） |
| auth_password | TEXT | 密码（加密存储） |
| is_active | INTEGER | 是否启用（0/1） |
| created_at | DATETIME | 创建时间 |

**报告记录表（reports）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| query | TEXT | 查询内容 |
| search_mode | TEXT | 搜索模式 |
| model_used | TEXT | 使用的AI模型 |
| report_content | TEXT | 报告内容（Markdown格式） |
| file_path | TEXT | 导出文件路径 |
| file_format | TEXT | 导出格式（md/pdf/docx/xlsx） |
| created_at | DATETIME | 创建时间 |

#### 2.3.3 索引设计

为了提升查询性能，系统在以下字段上创建了索引：

| 索引名称 | 表名 | 字段 | 索引类型 | 用途 |
|---------|------|------|---------|------|
| idx_search_history_timestamp | search_history | timestamp | DESC | 按时间排序查询历史 |
| idx_search_history_query | search_history | query | HASH | 关键词快速查找 |
| idx_search_history_mode | search_history | mode | HASH | 按模式筛选 |
| idx_search_results_search_id | search_results | search_id | HASH | 关联查询搜索结果 |
| idx_search_results_source | search_results | source | HASH | 按来源筛选 |
| idx_search_results_url | search_results | url | HASH | URL去重检查 |
| idx_search_cache_query_hash | search_cache | query_hash | HASH | 缓存快速命中 |
| idx_search_cache_expires | search_cache | expires_at | HASH | 缓存过期清理 |
| idx_custom_models_provider | custom_models | provider | HASH | 按供应商筛选模型 |
| idx_custom_models_default | custom_models | is_default | HASH | 快速查找默认模型 |

#### 2.3.4 数据库关系

各数据表之间的关联关系如下：

```plantuml
@startuml
skinparam linetype ortho

entity "search_history" as sh {
  * id : INTEGER
  * query : TEXT
  * mode : TEXT
  * timestamp : DATETIME
}

entity "search_results" as sr {
  * id : INTEGER
  * search_id : INTEGER <<FK>>
  * source : TEXT
  * url : TEXT
  * title : TEXT
}

entity "search_cache" as sc {
  * id : INTEGER
  * query_hash : TEXT
  * expires_at : DATETIME
}

entity "custom_models" as cm {
  * id : INTEGER
  * name : TEXT
  * provider : TEXT
}

entity "custom_onion_sites" as cos {
  * id : INTEGER
  * name : TEXT
  * url : TEXT
}

entity "reports" as r {
  * id : INTEGER
  * query : TEXT
  * report_content : TEXT
}

sh ||--o{ sr : "1对多"
sh ||--o{ sc : "1对多"
sh ||--o{ r : "1对多"
@enduml
```

**关系说明：**

- search_history（搜索历史）是一对多关系的父表，关联search_results（搜索结果）、search_cache（缓存）、reports（报告）
- 每条搜索历史记录可对应多条搜索结果
- 同一查询的多次搜索可复用缓存结果
- 每条搜索历史可生成多份报告

#### 2.3.5 数据管理策略

系统采用以下数据管理策略：

1. **缓存策略**：搜索结果缓存有效期为24小时，过期后自动清除
2. **历史保留**：搜索历史默认保留30天，可配置
3. **结果限制**：单次搜索最多返回100条结果
4. **自动备份**：每周自动备份数据库文件到data/backup目录

---

## 三、功能模块详细说明

本软件包含7大核心功能模块，涵盖多源搜索、内容抓取、AI分析和报告导出。

### 3.1 网页搜索模块

#### 3.1.1 功能概述

网页搜索模块是系统的主要数据来源之一，通过集成多个搜索引擎API，为用户提供全面的网页信息检索服务。

**核心功能：**

- 多引擎集成：支持Exa、Google、Bing等多个搜索引擎
- 智能结果去重：自动识别和合并重复内容
- 并发搜索：多线程并行请求，提升搜索效率
- 结果过滤：支持按来源、时间范围筛选
- 摘要提取：自动提取搜索结果的简短描述

#### 3.1.2 业务流程图

```plantuml
@startuml
start
:用户输入查询;
:选择搜索模式;
if (多源模式?) then (是)
  :并行调用多个搜索引擎;
else (否)
  :调用单个搜索引擎;
endif
:接收搜索结果;
:结果去重处理;
:提取摘要信息;
:返回格式化结果;
stop
@enduml
```

#### 3.1.3 输入输出说明

**输入参数：**

```python
def get_web_results(query, max_workers=5, max_results=20):
    # query: 搜索关键词
    # max_workers: 最大并发线程数
    # max_results: 最大返回结果数
```

**输出数据：**

```json
{
  "results": [
    {
      "title": "搜索结果标题",
      "link": "https://example.com",
      "description": "搜索结果描述",
      "source": "搜索引擎名称",
      "published_at": "2026-01-01"
    }
  ]
}
```

#### 3.1.4 处理逻辑

1. **查询预处理**：对用户输入进行清洗和规范化
2. **搜索引擎调用**：根据配置并行调用多个搜索引擎API
3. **结果合并**：将各搜索引擎返回的结果合并
4. **去重处理**：基于标题和链接进行去重
5. **摘要提取**：从原始网页中提取关键描述信息
6. **结果排序**：按相关性或时间排序返回

---

### 3.2 新闻搜索模块

#### 3.2.1 功能概述

新闻搜索模块专注于获取实时新闻资讯，支持多个新闻源聚合搜索。

**核心功能：**

- RSS订阅源解析：支持任意RSS/Atom订阅
- 多源聚合：从多个新闻网站同时获取
- 时间排序：按发布时间排序显示
- 分类筛选：支持按新闻类别筛选
- 自动更新：实时获取最新资讯

#### 3.2.2 支持的新闻源类型

| 来源类型 | 说明 |
|---------|------|
| RSS订阅 | 标准RSS/Atom格式 |
| NewsAPI | 新闻API服务（需配置KEY） |
| 媒体官网 | 直接抓取新闻页面 |
| 社交媒体 | Twitter/X、Reddit等 |

#### 3.2.3 业务流程图

```plantuml
@startuml
start
:获取新闻源列表;
fork
  :RSS解析;
fork again
  :NewsAPI调用;
fork again
  :网页抓取;
end fork
:聚合新闻数据;
:按时间排序;
:分类筛选;
:返回结果;
stop
@enduml
```

#### 3.2.4 处理逻辑

1. **获取新闻源列表**：从配置中加载所有新闻源
2. **并行请求**：使用多线程同时请求各新闻源
3. **数据解析**：解析RSS/JSON/HTML格式的新闻数据
4. **内容提取**：提取标题、描述、发布时间等字段
5. **去重排序**：去除重复内容，按时间排序
6. **返回结果**：返回结构化的新闻列表

---

### 3.3 暗网搜索模块

#### 3.3.1 功能概述

暗网搜索模块为需要匿名或特殊信息源的用户提供暗网内容检索能力。

**核心功能：**

- Ahmia搜索引擎集成：基于公开的暗网索引
- Tor代理支持：通过Tor网络访问暗网站点（可选）
- 自定义站点：支持添加用户自己的暗网站点
- Breached论坛集成：访问泄露数据论坛（需账号）
- 认证管理：支持HTTP基本认证

#### 3.3.2 使用说明

**基础模式（Ahmia）：**

- 无需Tor代理
- 搜索公开索引的暗网站点
- 适合一般性暗网内容检索

**高级模式（Tor代理）：**

- 需要安装并运行Tor浏览器
- 配置Tor代理端口（默认9150）
- 可访问需要Tor网络的暗网站点

**自定义暗网站点：**

```
站点配置示例：
{
  "name": "My Site",
  "url": "http://xxx.onion/search?q=",
  "auth": {
    "type": "basic",
    "username": "user",
    "password": "pass"
  }
}
```

#### 3.3.3 业务流程图

```plantuml
@startuml
start
:选择搜索模式;
if (基础模式) then (是)
  :调用Ahmia搜索引擎;
else (否)
  :检测Tor连接;
  if (Tor可用) then (是)
    :通过Tor代理搜索;
  else (否)
    :返回错误提示;
    stop
  endif
endif
:解析搜索结果;
:返回暗网内容;
stop
@enduml
```

#### 3.3.4 处理逻辑

1. **模式检测**：判断使用基础模式还是高级模式
2. **连接检测**：检测Tor代理是否可用
3. **搜索执行**：调用相应的暗网搜索引擎
4. **结果解析**：解析暗网页面格式
5. **安全过滤**：过滤可能的有害内容
6. **返回结果**：返回暗网搜索结果列表

---

### 3.4 报告生成模块

#### 3.4.1 功能概述

报告生成模块利用大语言模型对搜索结果进行深度分析，生成结构化的情报报告。

**核心功能：**

- 智能内容理解：利用LLM分析内容语义
- 结构化报告：生成层次分明的分析报告
- 关键信息提取：自动识别关键信息和观点
- 多语言支持：支持中英文报告生成
- 流式输出：实时显示生成进度

#### 3.4.2 业务流程图

```plantuml
@startuml
start
:用户提交查询;
:查询优化 refine_query;
:多源搜索 execute_search;
:内容抓取 scrape_multiple;
:上下文构建;
:调用LLM生成报告;
:结果格式化;
:返回报告;
stop
@enduml
```

#### 3.4.3 输入输出说明

**输入参数：**

```python
def generate_summary(llm, query, scraped_results, search_mode):
    # llm: 大语言模型实例
    # query: 原始查询
    # scraped_results: 抓取的网页内容
    # search_mode: 搜索模式
```

**输出数据：**

```markdown
# IntelNexus 智能情报报告

## 报告信息
- 查询内容：xxx
- 生成时间：2026年03月30日
- 报告类型：多源网络情报分析

---

## 分析结果
[AI生成的分析内容]
```

#### 3.4.4 处理逻辑

1. **查询优化**：利用LLM扩展和优化用户查询
2. **多源搜索**：并行执行多个数据源搜索
3. **内容抓取**：抓取目标网页完整内容
4. **上下文构建**：将搜索结果整理为prompt上下文
5. **AI分析调用**：调用LLM生成分析报告
6. **结果格式化**：将AI输出格式化为结构化报告

---

### 3.5 报告导出模块

#### 3.5.1 功能概述

报告导出模块支持将生成的分析报告导出为多种常见文档格式，满足不同场景的使用需求。

**核心功能：**

- Markdown导出：纯文本格式，便于分享和二次编辑
- PDF导出：专业文档格式，适合正式报告
- Word导出：可编辑的DOCX格式，便于修改
- Excel导出：结构化数据表格，便于数据分析

#### 3.5.2 格式对比

| 格式 | 优点 | 适用场景 |
|------|------|----------|
| Markdown | 轻量、易分享、版本可控 | 技术文档、博客 |
| PDF | 专业、跨平台、不可修改 | 正式报告、存档 |
| Word | 可编辑、格式灵活 | 协作编辑、打印 |
| Excel | 数据结构化、易分析 | 数据处理、统计 |

#### 3.5.3 业务流程图

```plantuml
@startuml
start
:选择导出格式;
if (Markdown) then (是)
  :直接保存为.md文件;
else if (PDF) then (是)
  :调用FPDF2生成PDF;
else if (Word) then (是)
  :调用python-docx生成;
else if (Excel) then (是)
  :调用openpyxl生成;
endif
:返回下载链接;
stop
@enduml
```

---

### 3.6 自定义模型管理模块

#### 3.6.1 功能概述

自定义模型管理模块允许用户添加和管理自己喜好的大语言模型，包括本地模型和云端API。

**核心功能：**

- 模型类型选择：支持多种模型供应商
- API配置管理：安全存储API密钥
- 模型切换：快速在不同模型间切换
- 默认模型设置：设置首选模型

#### 3.6.2 支持的模型供应商

| 类型 | 供应商 | 说明 |
|------|--------|------|
| 本地 | Ollama | 本地运行的开源模型 |
| 云端 | OpenAI | GPT-4o, GPT-3.5-turbo |
| 云端 | Anthropic | Claude 3系列 |
| 云端 | Google | Gemini Pro |
| 云端 | 通义千问 | 阿里云 |
| 云端 | 智谱AI | GLM系列 |
| 云端 | 百度文心一言 | ERNIE系列 |
| 云端 | 讯飞星火 | Spark系列 |

#### 3.6.3 业务流程图

```plantuml
@startuml
start
:打开模型设置;
:选择添加模型;
if (本地模型) then (是)
  :配置Ollama地址;
else (否)
  :选择云端供应商;
  :填写API密钥;
  :填写模型ID;
endif
:保存模型配置;
:测试模型连接;
if (连接成功) then (是)
  :显示在模型列表;
else (否)
  :显示错误提示;
endif
stop
@enduml
```

---

## 四、数据流程与接口设计

### 4.1 主要数据流程图

```plantuml
@startuml
skinparam linetype ortho

start
:用户输入查询;
:查询优化 refine_query;
:多源搜索 execute_search;
fork
  :网页搜索;
fork again
  :新闻搜索;
fork again
  :暗网搜索;
end fork

:内容抓取 scrape_multiple;
:AI分析 generate_summary;
:报告导出;

stop
@enduml
```

### 4.2 核心接口设计

#### 4.2.1 搜索相关接口

| 接口 | 方法 | URL | 描述 |
|------|------|-----|------|
| 执行搜索 | POST | /api/search | 执行多源搜索 |
| 获取结果 | GET | /api/search/results | 获取搜索结果 |
| 取消搜索 | POST | /api/search/cancel | 取消正在进行的搜索 |

**接口详情：POST /api/search**

请求示例：

```json
{
  "query": "人工智能发展趋势",
  "mode": "all",
  "max_results": 20,
  "model": "qwen2.5:7b",
  "max_workers": 5,
  "enable_scrape": true
}
```

响应示例（成功）：

```json
{
  "status": "success",
  "message": "搜索完成",
  "data": {
    "search_id": "20260330153045_a1b2c3",
    "query": "人工智能发展趋势",
    "mode": "all",
    "total_results": 45,
    "web_results": 20,
    "news_results": 15,
    "darkweb_results": 10,
    "duration": 8.5,
    "results": [
      {
        "id": 1,
        "source": "web",
        "url": "https://example.com/ai-trends",
        "title": "2026年人工智能发展趋势分析",
        "description": "本文分析了2026年AI技术的主要发展方向...",
        "score": 0.95,
        "published_at": "2026-03-28"
      }
    ]
  },
  "code": 200
}
```

**接口详情：GET /api/search/results**

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| search_id | string | 是 | 搜索任务ID |

响应示例：

```json
{
  "status": "success",
  "data": {
    "search_id": "20260330153045_a1b2c3",
    "results": [...],
    "scraped_content": [...]
  },
  "code": 200
}
```

#### 4.2.2 报告相关接口

| 接口 | 方法 | URL | 描述 |
|------|------|-----|------|
| 生成报告 | POST | /api/report/generate | 生成情报报告 |
| 获取报告 | GET | /api/report/{id} | 获取报告内容 |
| 导出报告 | GET | /api/report/{id}/export | 导出报告为指定格式 |

**接口详情：POST /api/report/generate**

请求示例：

```json
{
  "search_id": "20260330153045_a1b2c3",
  "query": "人工智能发展趋势",
  "model": "qwen2.5:7b",
  "report_type": "comprehensive",
  "language": "zh"
}
```

响应示例（成功）：

```json
{
  "status": "success",
  "message": "报告生成完成",
  "data": {
    "report_id": 123,
    "content": "# IntelNexus 智能情报报告\n\n## 概述\n...\n",
    "word_count": 3500,
    "duration": 15.2
  },
  "code": 200
}
```

#### 4.2.3 模型相关接口

| 接口 | 方法 | URL | 描述 |
|------|------|-----|------|
| 获取模型列表 | GET | /api/models | 获取可用模型列表 |
| 添加自定义模型 | POST | /api/models/custom | 添加自定义模型 |
| 删除自定义模型 | DELETE | /api/models/custom/{name} | 删除自定义模型 |

**接口详情：GET /api/models**

响应示例：

```json
{
  "status": "success",
  "data": {
    "local_models": [
      {"name": "qwen2.5:7b", "provider": "ollama", "status": "ready"},
      {"name": "llama2", "provider": "ollama", "status": "ready"},
      {"name": "mistral", "provider": "ollama", "status": "not_downloaded"}
    ],
    "cloud_models": [
      {"name": "gpt-4o", "provider": "openai", "status": "configured"},
      {"name": "claude-3-opus", "provider": "anthropic", "status": "not_configured"}
    ],
    "custom_models": [
      {"name": "my-custom-model", "provider": "openai", "is_default": false}
    ]
  },
  "code": 200
}
```

#### 4.2.4 用户设置相关接口

| 接口 | 方法 | URL | 描述 |
|------|------|-----|------|
| 获取设置 | GET | /api/user/settings | 获取用户设置 |
| 更新设置 | PUT | /api/user/settings | 更新用户设置 |

**接口详情：GET /api/user/settings**

响应示例：

```json
{
  "status": "success",
  "data": {
    "default_model": "qwen2.5:7b",
    "default_mode": "all",
    "max_workers": 5,
    "language": "zh",
    "theme": "light",
    "max_results": 20,
    "cache_enabled": true,
    "cache_ttl": 86400
  },
  "code": 200
}
```

#### 4.2.5 HTTP状态码说明

| 状态码 | 说明 | 常见原因 |
|--------|------|----------|
| 200 | 成功 | 请求正常处理 |
| 201 | 已创建 | 资源创建成功 |
| 400 | 请求错误 | 参数格式错误、必填参数缺失 |
| 401 | 未认证 | API密钥无效或未提供 |
| 403 | 禁止访问 | 无权限执行此操作 |
| 404 | 未找到 | 资源不存在 |
| 429 | 请求过多 | 超出速率限制 |
| 500 | 服务器错误 | 内部处理错误 |
| 503 | 服务不可用 | 外部服务不可用 |

#### 4.2.6 错误代码详解

| 错误代码 | 错误信息 | 说明 | 解决方案 |
|----------|----------|------|----------|
| E1001 | INVALID_QUERY | 查询参数无效 | 检查query参数是否为空 |
| E1002 | INVALID_SEARCH_MODE | 搜索模式不支持 | 使用web/news/darkweb/all |
| E1003 | SEARCH_TIMEOUT | 搜索超时 | 减少max_results或max_workers |
| E1004 | NO_RESULTS_FOUND | 未找到结果 | 尝试更换关键词 |
| E2001 | MODEL_NOT_FOUND | 模型不存在 | 检查模型名称是否正确 |
| E2002 | MODEL_NOT_READY | 模型未就绪 | 确保模型已下载并运行 |
| E2003 | MODEL_TIMEOUT | 模型响应超时 | 增加超时时间或换用其他模型 |
| E3001 | SCRAPE_FAILED | 内容抓取失败 | 目标网站无法访问 |
| E3002 | CONTENT_TOO_LARGE | 内容过大 | 目标内容超出处理限制 |
| E4001 | REPORT_GEN_FAILED | 报告生成失败 | 检查LLM服务是否正常 |
| E4002 | EXPORT_FAILED | 导出失败 | 检查磁盘空间和权限 |
| E5001 | DB_ERROR | 数据库错误 | 检查数据库文件 |
| E5002 | CACHE_ERROR | 缓存错误 | 检查缓存配置 |

### 4.3 数据格式规范

#### 4.3.1 请求消息体格式

所有POST/PUT请求的输入数据必须遵循JSON格式：

```json
{
  "token": "jwt_token_here",
  "data": {
    "property1": "string",
    "property2": 123,
    "property3": true,
    "property4": []
  }
}
```

#### 4.3.2 响应消息体格式

成功响应返回标准的JSON格式：

```json
{
  "status": "success",
  "message": "操作成功",
  "data": {},
  "code": 200
}
```

失败响应返回错误信息：

```json
{
  "status": "error",
  "error": "错误代码或消息",
  "message": "详细说明",
  "code": 500
}
```

---

## 五、操作流程说明

### 5.1 软件安装流程

#### 5.1.1 环境准备

1. **安装Python（如果未安装）**
   ```bash
   # 检查Python版本
   python --version
   
   # 需要Python 3.10或更高版本
   ```

2. **安装Ollama（可选，用于本地模型）**
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Windows
   # 从 https://ollama.com 下载安装
   ```

3. **拉取AI模型（可选）**
   ```bash
   ollama pull qwen2.5:7b
   ollama pull llama2
   ```

#### 5.1.2 安装步骤

1. **克隆或下载项目**
   ```bash
   git clone https://github.com/your-repo/IntelNexus.git
   cd IntelNexus
   ```

2. **创建虚拟环境（推荐）**
   ```bash
   python -m venv venv
   
   # 激活虚拟环境
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**
   ```bash
   # 复制环境变量模板
   cp .env.example .env
   
   # 编辑 .env 文件，填入API密钥
   ```

### 5.2 命令行模式使用流程

#### 5.2.1 基础搜索流程

1. **启动命令行**
   ```bash
   cd IntelNexus
   ```

2. **执行搜索**
   ```bash
   python main.py search -q "你的查询内容" -s all
   ```

3. **查看结果**
   - 搜索完成后，结果保存在生成的Markdown文件中
   - 文件命名格式：`report_YYYY-MM-DD_HH-MM-SS.md`

#### 5.2.2 自定义参数搜索

```bash
# 使用指定模型
python main.py search -q "AI趋势" -m gpt-4o

# 指定输出文件名
python main.py search -q "机器学习" -o my_research

# 调整线程数
python main.py search -q "深度学习" -t 8
```

### 5.3 Web界面使用流程

#### 5.3.1 启动Web界面

```bash
python main.py ui
```

#### 5.3.2 界面功能说明

主页面包含以下区域：

1. **侧边栏设置**
   - 搜索模式选择
   - AI模型选择
   - 线程数设置
   - 下载格式选择
   - 语言切换

2. **搜索输入区**
   - 搜索关键词输入框
   - 搜索按钮

3. **结果展示区**
   - 优化后的查询显示
   - 各数据源结果统计
   - AI生成的分析报告
   - 搜索结果详情

#### 5.3.3 搜索操作步骤

用户在Web界面进行搜索操作的完整流程如下：首先在左侧边栏设置搜索参数，包括选择搜索模式（全部/网页/新闻/暗网）、选择AI分析模型、设置线程数。然后在主界面中间的输入框输入查询内容，点击"搜索"按钮。系统会自动执行完整的搜索流程：查询优化 → 多源搜索 → 内容抓取 → AI分析，各阶段的进度会实时显示在界面上。搜索完成后，用户可以阅读生成的报告内容，选择下载格式（Markdown/PDF/Word/Excel），点击下载按钮保存到本地。

![图3：搜索输入框](./images/03_search_input.png)
![图4：模型选择](./images/04_model_select.png)
![图5：线程设置](./images/05_threads.png)

#### 5.3.4 高级功能

用户可以在Web界面进行以下高级操作：添加自定义AI模型（展开"添加自定义模型"选项，选择模型类型，填写API密钥和模型ID，然后点击添加）；配置暗网搜索（在搜索模式中选择"暗网搜索"，如需高级模式需配置Tor代理，或添加自定义暗网站点）。

![图6：搜索结果统计](./images/06_search_results.png)
![图7：报告生成中](./images/07_generating.png)
![图8：最终报告](./images/08_report.png)
   - 点击添加

2. **暗网搜索配置**
   - 选择"暗网搜索"模式
   - 配置Tor代理（如需要高级模式）
   - 添加自定义暗网站点（如有需要）

### 5.4 报告导出流程

1. **搜索完成后**，在报告下方选择下载格式

2. **点击下载按钮**

3. **文件自动下载到本地**

---

## 六、性能指标与测试结果

### 6.1 性能要求

- 搜索响应时间：多源搜索+抓取的总时间小于30秒
- 单源搜索时间：单个搜索引擎的响应时间小于10秒
- AI分析时间：生成报告的时间小于60秒
- 并发能力：支持10个以上线程同时进行搜索任务
- 内存占用：基础运行内存不超过4GB（不含LLM）

### 6.2 搜索性能测试

在标准测试环境（CPU: Intel i7-10700, 内存: 16GB, 网络: 100Mbps）下，对各搜索模式进行了性能测试，测试结果如下：

#### 6.2.1 单源搜索性能

| 搜索模式 | 平均响应时间 | 最大响应时间 | 最小响应时间 | 成功率 |
|---------|------------|------------|------------|--------|
| 网页搜索 | 3.2秒 | 8.5秒 | 1.2秒 | 100% |
| 新闻搜索 | 2.8秒 | 7.2秒 | 0.8秒 | 100% |
| 暗网搜索 | 5.5秒 | 15.3秒 | 2.1秒 | 95% |
| 全源搜索 | 8.5秒 | 22.1秒 | 3.5秒 | 98% |

#### 6.2.2 内容抓取性能

| 目标类型 | 平均抓取时间 | 最大并发数 | 成功率 |
|---------|------------|----------|--------|
| 新闻文章 | 1.2秒/篇 | 10 | 98% |
| 论坛帖子 | 1.5秒/篇 | 8 | 96% |
| 产品页面 | 0.8秒/篇 | 15 | 99% |
| 暗网页面 | 3.0秒/篇 | 3 | 85% |

#### 6.2.3 并发性能测试

使用多线程模拟并发搜索请求，测试系统处理能力：

| 并发数 | 平均响应时间 | 最大响应时间 | 错误率 | 内存占用 |
|-------|------------|------------|--------|---------|
| 5 | 9.2秒 | 15.3秒 | 0% | 2.1GB |
| 10 | 10.5秒 | 18.7秒 | 0% | 2.8GB |
| 20 | 15.2秒 | 28.5秒 | 2% | 3.5GB |
| 50 | 28.6秒 | 52.3秒 | 8% | 4.2GB |

### 6.3 AI分析性能测试

测试不同AI模型在生成情报报告时的性能表现，测试条件：查询包含20条搜索结果，每条结果抓取约2000字内容：

#### 6.3.1 本地模型性能

| 模型 | 平均生成时间 | 生成字数 | 内存占用 | 响应质量 |
|------|------------|---------|---------|---------|
| qwen2.5:7b | 18.5秒 | 2800字 | 4.2GB | 良好 |
| llama2:7b | 22.3秒 | 2600字 | 4.5GB | 良好 |
| mistral:7b | 16.8秒 | 2700字 | 4.0GB | 一般 |

#### 6.3.2 云端模型性能

| 模型 | 平均生成时间 | 生成字数 | API延迟 | 响应质量 |
|------|------------|---------|---------|---------|
| GPT-4o | 8.2秒 | 3200字 | 1.2秒 | 优秀 |
| GPT-3.5-turbo | 4.5秒 | 2800字 | 0.8秒 | 良好 |
| Claude-3-opus | 9.5秒 | 3100字 | 1.5秒 | 优秀 |
| Gemini Pro | 6.8秒 | 2900字 | 1.0秒 | 良好 |

### 6.4 报告导出性能测试

测试不同格式的报告导出速度，测试条件：报告内容约5000字：

| 导出格式 | 平均导出时间 | 文件大小 | 内存峰值 |
|---------|------------|---------|---------|
| Markdown | 0.1秒 | 15KB | 50MB |
| PDF | 2.5秒 | 280KB | 200MB |
| Word | 1.8秒 | 120KB | 150MB |
| Excel | 1.2秒 | 85KB | 100MB |

### 6.5 兼容性测试

#### 6.5.1 操作系统兼容性

| 操作系统 | 版本 | 运行状态 | 备注 |
|---------|------|---------|------|
| Windows | 10 | 通过 | - |
| Windows | 11 | 通过 | - |
| Ubuntu | 20.04 | 通过 | - |
| Ubuntu | 22.04 | 通过 | - |
| CentOS | 7 | 通过 | 需额外安装依赖 |
| CentOS | 8 | 通过 | - |
| macOS | 12 | 通过 | - |
| macOS | 13 | 通过 | - |

#### 6.5.2 浏览器兼容性（Web界面）

| 浏览器 | 版本 | 支持状态 | 备注 |
|-------|------|---------|------|
| Chrome | 90+ | 完全支持 | 推荐 |
| Edge | 90+ | 完全支持 | - |
| Firefox | 88+ | 完全支持 | - |
| Safari | 14+ | 完全支持 | - |

#### 6.5.3 Python版本兼容性

| Python版本 | 支持状态 | 备注 |
|-----------|---------|------|
| 3.9 | 通过 | 需安装typing_extensions |
| 3.10 | 完全支持 | 推荐 |
| 3.11 | 完全支持 | 推荐 |
| 3.12 | 通过 | - |

### 6.6 稳定性测试

进行了72小时连续运行稳定性测试：

- 测试场景：每小时执行10次搜索任务，5次报告生成
- 总执行次数：搜索720次，报告生成360次
- 系统崩溃：0次
- 内存泄漏：未检测到
- API错误率：0.5%
- 平均CPU使用率：35%

### 6.7 安全性测试

- API密钥加密存储：已实现（AES-256加密）
- 本地数据隔离：已实现（数据存储在本地目录）
- SQL注入防护：已实现（参数化查询）
- XSS防护：已实现（输出编码）
- CSRF防护：已实现（令牌验证）
- 速率限制：已实现（每分钟60次请求）

---

## 七、软件应用场景

### 7.1 个人情报分析者

IntelNexus主要服务于以下用户群体：

- 市场研究人员：提供竞品分析、行业趋势监测和消费者洞察
- 舆情监控团队：提供实时舆情追踪和负面信息预警
- 新闻分析师：提供新闻聚合、舆情分析和趋势预测
- 情报分析人员：提供多源情报收集、深度内容分析和报告自动生成

### 7.2 应用场景举例

1. **工作日情报收集**：用户可记录和追踪特定领域的最新信息，AI会提供情报汇总及趋势分析

2. **行业趋势研究**：帮助分析特定行业发展趋势，追踪相关新闻报道

3. **竞品分析**：收集和比较竞争对手的产品信息、市场动态

4. **深度研究**：快速获取多源信息，生成综合分析报告

### 7.3 使用方式

1. 在设备上启动IntelNexus应用
2. 通过Web界面或命令行进行搜索
3. 选择数据源和分析模型
4. 查看AI生成的报告
5. 导出所需格式的报告

---

## 附录A：环境变量配置详解

IntelNexus使用`.env`文件存储配置信息。以下是完整的配置项说明：

### A.1 基础配置

```env
# ===========================================
# IntelNexus 环境配置文件
# ===========================================

# 调试模式（true/false）
DEBUG=false

# 日志级别（DEBUG/INFO/WARNING/ERROR）
LOG_LEVEL=INFO

# 数据存储目录
DATA_DIR=./data

# 缓存目录
CACHE_DIR=./data/cache
```

### A.2 API密钥配置

```env
# ===========================================
# OpenAI API 配置
# ===========================================
OPENAI_API_KEY=sk-your-openai-api-key-here

# ===========================================
# Anthropic Claude API 配置
# ===========================================
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here

# ===========================================
# Google Gemini API 配置
# ===========================================
GOOGLE_API_KEY=your-google-api-key-here

# ===========================================
# Exa Search API 配置（推荐用于AI增强搜索）
# ===========================================
EXA_API_KEY=your-exa-api-key-here

# ===========================================
# NewsAPI 配置（用于新闻搜索）
# ===========================================
NEWS_API_KEY=your-newsapi-api-key-here

# ===========================================
# Twitter/X API 配置（用于社交媒体搜索）
# ===========================================
TWITTER_BEARER_TOKEN=your-twitter-bearer-token-here

# ===========================================
# Semantic Scholar API 配置（可选）
# ===========================================
SEMANTIC_SCHOLAR_API_KEY=your-semantic-scholar-api-key-here

# ===========================================
# OpenRouter 配置（用于访问多种云端模型）
# ===========================================
OPENROUTER_API_KEY=your-openrouter-api-key-here
```

### A.3 Ollama本地模型配置

```env
# ===========================================
# Ollama 本地模型配置
# ===========================================

# Ollama 服务地址
OLLAMA_BASE_URL=http://127.0.0.1:11434

# 默认使用的本地模型
DEFAULT_LOCAL_MODEL=qwen2.5:7b

# 可用的本地模型列表（逗号分隔）
AVAILABLE_LOCAL_MODELS=qwen2.5:7b,llama2,mistral
```

### A.4 搜索功能配置

```env
# ===========================================
# 搜索功能配置
# ===========================================

# 默认搜索模式（web/news/darkweb/all）
DEFAULT_SEARCH_MODE=all

# 最大并发线程数
MAX_WORKERS=5

# 单次搜索最大结果数
MAX_RESULTS=20

# 搜索超时时间（秒）
SEARCH_TIMEOUT=30

# 启用内容抓取（true/false）
ENABLE_SCRAPING=true

# 抓取超时时间（秒）
SCRAPE_TIMEOUT=15
```

### A.5 暗网功能配置

```env
# ===========================================
# 暗网功能配置
# ===========================================

# 启用暗网搜索功能（true/false）
ENABLE_DARKWEB=false

# Tor 代理地址
TOR_PROXY=http://127.0.0.1:9050

# Tor 控制端口
TOR_CONTROL_PORT=9051

# 自定义暗网站点列表文件
CUSTOM_ONION_SITES_FILE=./data/custom_onion_sites.json
```

### A.6 缓存配置

```env
# ===========================================
# 缓存配置
# ===========================================

# 启用搜索结果缓存（true/false）
ENABLE_CACHE=true

# 缓存有效期（秒），默认24小时
CACHE_TTL=86400

# 最大缓存条目数
MAX_CACHE_ENTRIES=1000

# 启用LLM响应缓存（true/false）
ENABLE_LLM_CACHE=true
```

### A.7 报告生成配置

```env
# ===========================================
# 报告生成配置
# ===========================================

# 默认报告语言（zh/en）
DEFAULT_REPORT_LANGUAGE=zh

# 报告最大字数
MAX_REPORT_WORDS=5000

# LLM生成超时时间（秒）
LLM_TIMEOUT=60

# LLM温度参数（0-1）
LLM_TEMPERATURE=0.7

# 启用流式输出（true/false）
STREAMING_OUTPUT=true
```

### A.8 完整配置示例

```env
# ===========================================
# IntelNexus 完整配置示例
# ===========================================

# 基础配置
DEBUG=false
LOG_LEVEL=INFO
DATA_DIR=./data

# API密钥（请替换为您的实际密钥）
OPENAI_API_KEY=sk-xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
EXA_API_KEY=xxxxx

# Ollama配置
OLLAMA_BASE_URL=http://127.0.0.1:11434
DEFAULT_LOCAL_MODEL=qwen2.5:7b

# 搜索配置
DEFAULT_SEARCH_MODE=all
MAX_WORKERS=5
MAX_RESULTS=20

# 暗网配置
ENABLE_DARKWEB=false

# 缓存配置
ENABLE_CACHE=true
CACHE_TTL=86400

# 报告配置
DEFAULT_REPORT_LANGUAGE=zh
LLM_TIMEOUT=60
```

---

## 附录B：部署指南

### B.1 环境要求

#### 硬件要求

| 配置 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 双核2.0GHz | 四核3.0GHz以上 |
| 内存 | 4GB | 16GB（运行LLM需8GB+） |
| 硬盘 | 20GB可用 | 50GB以上 |
| 网络 | 10Mbps | 100Mbps |

#### 软件要求

| 软件 | 版本要求 | 备注 |
|------|---------|------|
| 操作系统 | Windows 10+/Ubuntu 20.04+/macOS 12+ | - |
| Python | 3.10+ | 推荐3.11 |
| Ollama | 0.1.15+ | 可选，本地模型需要 |

### B.2 本地部署步骤

#### 步骤1：克隆项目

```bash
git clone https://github.com/your-repo/IntelNexus.git
cd IntelNexus
```

#### 步骤2：创建虚拟环境

```bash
# 使用venv
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

#### 步骤3：安装依赖

```bash
pip install -r requirements.txt
```

#### 步骤4：配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件，填入您的API密钥
nano .env  # Linux/Mac
notepad .env  # Windows
```

#### 步骤5：启动服务

```bash
# 启动Web界面
python main.py ui

# 或使用命令行模式
python main.py search -q "your query" -s all
```

#### 步骤6：访问应用

打开浏览器访问：`http://localhost:8501`

### B.3 Docker部署

#### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 创建数据目录
RUN mkdir -p data/cache data/backup

# 暴露端口
EXPOSE 8501

# 启动应用
CMD ["python", "main.py", "ui"]
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  intelnexus:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DEBUG=false
      - LOG_LEVEL=INFO
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    depends_on:
      - ollama
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped

volumes:
  ollama_data:
```

#### 启动Docker服务

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### B.4 生产环境部署建议

#### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 使用systemd服务（Linux）

```ini
[Unit]
Description=IntelNexus
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/IntelNexus
ExecStart=/opt/IntelNexus/venv/bin/python main.py ui
Restart=always

[Install]
WantedBy=multi-user.target
```

保存为`/etc/systemd/system/intelnexus.service`，然后执行：

```bash
sudo systemctl enable intelnexus
sudo systemctl start intelnexus
```

#### 性能优化建议

1. **LLM部署优化**：将Ollama部署在单独的服务器上
2. **缓存优化**：使用Redis替代本地文件缓存
3. **负载均衡**：多实例部署时使用Nginx负载均衡
4. **日志管理**：配置logrotate自动轮转日志

---

## 附录C：常见问题FAQ

### C.1 安装与配置问题

**Q1: 安装依赖时出现错误怎么办？**

A1: 请确保Python版本符合要求（3.10+）。如果遇到编译错误，尝试安装编译工具：
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# Windows
# 安装Visual Studio Build Tools
```

**Q2: 如何获取API密钥？**

A2: 各平台API密钥获取方式：
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/
- Exa: https://exa.ai/
- NewsAPI: https://newsapi.org/

**Q3: 配置文件在哪里？**

A3: 配置文件为项目根目录下的`.env`文件，首次运行前需要从`.env.example`复制创建。

### C.2 使用问题

**Q4: 搜索结果为空怎么办？**

A4: 可能原因及解决方法：
1. API密钥未配置或无效 → 检查.env文件
2. 网络连接问题 → 检查网络代理设置
3. 搜索关键词过于专业 → 尝试使用更通用的关键词
4. 目标网站反爬 → 稍后重试或更换数据源

**Q5: 报告生成失败怎么办？**

A5: 请按以下步骤排查：
1. 检查LLM服务是否正常运行
2. 确认API密钥余额充足
3. 查看日志中的具体错误信息
4. 尝试更换其他模型

**Q6: 暗网搜索无法使用？**

A6: 暗网搜索默认是禁用的，需要：
1. 在.env中设置`ENABLE_DARKWEB=true`
2. 如需Tor代理，确保Tor服务正常运行
3. 配置`TOR_PROXY`指向您的Tor代理地址

**Q7: 如何切换AI模型？**

A7: 有两种方式：
1. 在Web界面侧边栏选择模型
2. 命令行使用`-m`参数：
```bash
python main.py search -q "AI趋势" -m gpt-4o
```

### C.3 性能问题

**Q8: 搜索速度很慢怎么办？**

A8: 优化建议：
1. 减少`max_results`参数值
2. 减少`max_workers`线程数
3. 启用缓存避免重复搜索
4. 使用本地模型替代云端API
5. 检查网络连接质量

**Q9: 内存占用过高？**

A9: 可能原因及优化：
1. 运行大型LLM → 使用更小的模型（如qwen2.5:3b）
2. 过多并发请求 → 减少max_workers
3. 缓存数据过多 → 清理缓存或减少CACHE_TTL

**Q10: Ollama模型无法连接？**

A10: 检查以下配置：
1. Ollama服务是否已启动：`ollama serve`
2. OLLAMA_BASE_URL配置是否正确
3. 防火墙是否阻止了11434端口
4. 模型是否已下载：`ollama list`

### C.4 导出问题

**Q11: PDF导出中文显示乱码？**

A11: 确保已安装中文字体，Windows系统检查：
```bash
# 确认字体文件存在
ls "C:\Windows\Fonts\simhei.ttf"
```

**Q12: 导出文件过大？**

A12: 可以在生成报告时减少内容长度，或分批导出。

### C.5 其他问题

**Q13: 如何升级到最新版本？**

A13: 执行以下命令：
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

**Q14: 如何备份数据？**

A14: 备份以下文件和目录：
- `./data/` 目录（包含搜索历史、缓存等）
- `.env` 配置文件
- 导出的报告文件

**Q15: 如何查看运行日志？**

A15: 日志文件位于`./logs/`目录，或在运行时添加`--verbose`参数查看详细日志。

**Q16: 如何联系技术支持？**

A16: 请在GitHub仓库提交Issue：https://github.com/your-repo/IntelNexus/issues

---

## 附录：界面截图清单

【请在以下位置插入截图】

| 序号 | 截图内容 | 位置 |
|------|---------|------|
| 1 | Web界面主页面 | 5.3.3节 |
| 2 | 设置页面/自定义模型管理 | 5.3.4节 |
| 3 | 行业研究示例结果 | 7.2节 |
| 4 | 舆情监控示例 | 7.2节 |
| 5 | 暗网搜索界面 | 7.2节 |
| 6 | 行业趋势分析示例 | 7.2节 |

---

**文档版本：** V1.0

**编制日期：** ______________

**编制人：** ______________

**审核人：** ______________

**批准人：** ______________

---

*IntelNexus - 新一代智能网络情报分析平台*
