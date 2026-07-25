---
name: intelnexus-content-quality-improvement
overview: 针对 IntelNexus「AI 简报」内容被百度百科/词典/电竞赛事等低质结果污染的问题，实施 A+B+C 三合一改进：A=让境外源(DuckDuckGo/Google News/Reuters/NewsAPI)可走 HTTP 代理；B=新增国内可直连的高质量 RSS(36氪等)并给所有源加 requires_proxy 分级；C=增加域名黑名单+关键词相关性评分的噪声过滤。优先让 B+C 在无代理下立即改善内容，A 作为可选增强并附配置指引。
todos:
  - id: proxy-infra
    content: 在 shared/search/__init__.py 新增 get_http_proxies()，并在 config.py 读取 HTTP_PROXY/HTTPS_PROXY/USE_TOR 环境变量
    status: completed
  - id: wire-proxy
    content: 将代理接入 web.py 的 get_session() 与 news.py 全部 requests.get 调用，仅配置时生效
    status: completed
    dependencies:
      - proxy-infra
  - id: domestic-sources
    content: 在 news.py 给 RSS_SOURCES 增加 requires_proxy 分级并加入已验证的 36氪源，探测后补入其他可达国内源
    status: completed
  - id: noise-filter
    content: 在 web.py 与 news.py 增加域名黑名单与关键词相关性过滤，剔除百度百科/词典/赛事等噪声
    status: completed
    dependencies:
      - domestic-sources
  - id: env-guide
    content: 用 [mcp:filesystem] 在 .env 追加代理配置指引（Clash/v2rayN 与 Tor 两种示例）
    status: completed
    dependencies:
      - proxy-infra
  - id: verify-run
    content: 无代理运行 briefing 验证噪声过滤生效，再说明配代理后境外源启用的验证步骤
    status: completed
    dependencies:
      - wire-proxy
      - noise-filter
      - env-guide
---

## 用户需求

IntelNexus 的「AI 简报」命令已能跑通生成与推送链路，但采集阶段存在内容质量问题：用户网络环境无法访问全部境外源（DuckDuckGo / Yahoo / Yandex / Google News / Reuters / NewsAPI 均连接超时或 SSL 错误），系统退化为仅用百度兜底，导致返回结果混入百度百科、爱词霸词典、CS:GO 赛事等无关噪声，最终 qwen3:8b 生成的简报与 AI / 网络安全主题严重偏离（TOP3 出现「反恐精英锦标赛」「PENTAGON 韩国男子组合」等）。

用户明确选择同时实施以下三套方案：

## 核心要点

- **A（代理启用境外源）**：让 web / news 采集客户端支持 HTTP/HTTPS 代理或 Tor，从而可用 Google News / NewsAPI / Reuters / DuckDuckGo 等境外一手情报源。用户当前无代理，需提供配置指引（Clash/v2rayN 本地代理或 Tor）。
- **B（国内高质量源）**：在 `RSS_SOURCES` 中增加国内可访问的 RSS（已实测 36氪 `https://36kr.com/feed` 有效；机器之心 RSS 被登录墙拦截已剔除），并对源做 `requires_proxy` 分级，境外源在无代理时自动跳过，避免无效超时。
- **C（噪声过滤）**：在 web / news 采集结果入库前加域名黑名单（baike/iciba/5eplay/csgo 等）+ 关键词相关性评分，剔除与查询无关的百度噪声结果。

## 预期效果

- 无代理状态下：简报内容来自 Bing News + 36氪等国内可达源，且百度噪声被过滤，AI / 安全分类有真实相关条目（不再出现百科/词典/赛事）。
- 配代理后：境外源自动启用，内容更丰富、更国际化。
- 代码改动向后兼容：无代理配置时行为与原版一致（仅有过滤增强），代理仅在使用时生效、零额外开销。

## 技术栈

- 运行时：Python 3.10+（conda base 环境，依赖已就绪）
- 采集层：`shared/search/web.py`（网页搜索，FAST/BING/BAIDU/SLOW 引擎）、`shared/search/news.py`（RSS + Bing News + NewsAPI）
- 消费层：`intel-briefing/ai_briefing/collector.py` 用 `WATCH_CATEGORIES.search_queries` 驱动采集
- 代理：`requests` Session `proxies` 参数；Tor 走 `socks5h://127.0.0.1:<port>`（复用既有 `get_tor_proxy_port()` 约定）

## 实现方案

### 整体策略

在**不改动 collector / LLM / 推送链**的前提下，仅增强采集层的「源分级 + 代理接线 + 噪声过滤」三能力，使数据源在「无代理（国内源兜底）」与「有代理（境外源全开）」两种模式下都产出高质量结果。

### 关键决策与理由

1. **新增 `get_http_proxies()`（A 的核心接线点）**：项目已有 `get_tor_session()` 仅供暗网，web/news 的 `get_session()` 与 `requests.get` 完全未接代理。在 `shared/search/__init__.py` 新增统一函数，按 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量或 `USE_TOR=true` 解析出代理字典；返回 `None` 时不影响原逻辑（零开销）。
2. **Bing 前置为首选 + 百度降级（B+C 协同）**：`FAST_ENGINES` 改为 `["Bing","Baidu"]`。Bing 国内可直连、噪声少；百度仅作补充，且经 C 的黑名单过滤后基本只保留有效结果。
3. **源分级 `requires_proxy`（B）**：`RSS_SOURCES` 每项加 `requires_proxy` 标记，把 Google News / Yahoo News / Reuters / TechCrunch / The Verge / Wired / BBC / CNN 标记为需代理；无代理时 `search_rss` 直接跳过，消除满屏 timeout 与无谓等待。Bing News 国内可直连、保留；新增已验证的 36氪。
4. **探测后写入（B 的稳健性约束）**：其他国内候选源（FreeBuf / 嘶吼 / 安全内参 / 量子位 / 新智元）实施时**逐个发起 HTTP 探测**，仅保留返回 200 且能解析出 `<item>`/`<entry>` 的源写入 `RSS_SOURCES`，避免引入死链（jiqizhixin 登录墙教训）。
5. **域名黑名单 + 相关性评分（C）**：`web.py` 与 `news.py` 在结果入库前过滤。`BLOCKED_DOMAINS` 覆盖 `baike.baidu.com`、`iciba.com`、`5eplay.com`、`*.csgo*`、`wikipedia.org`、词典类域名等；相关性函数要求结果 title+description 至少命中查询中任一非停用词 token（大小写不敏感），否则丢弃，从而剔除百度返回的无关中文网页。

### 性能与可靠性

- 代理仅在配置存在时生效，`None` 分支无额外网络/计算开销。
- 噪声过滤**减少下游喂给 qwen3:8b 的垃圾 token**，间接降低 LLM 耗时与跑题概率。
- 源探测在**实现期**完成（一次性），不进入运行时，保证 `briefing` 命令运行速度不受损。
- `search_rss` 单源异常已有 `try/except` 容错，新增源不会导致整体中断。

## 实现要点

### 目录结构（改动文件）

```
IntelNexus/
├── shared/
│   └── search/
│       ├── __init__.py   # [MODIFY] 新增 get_http_proxies()：读取 HTTP_PROXY/HTTPS_PROXY/USE_TOR
│       ├── web.py        # [MODIFY] get_session() 接代理；FAST_ENGINES 改 ["Bing","Baidu"]；新增 BLOCKED_DOMAINS + _passes_filter；get_web_results 返回前过滤
│       └── news.py       # [MODIFY] RSS_SOURCES 加 requires_proxy 分级 + 新增 36氪；search_rss 无代理跳过境外源；所有 requests.get 传 proxies；search_rss/search_bing_news 加域名黑名单过滤
├── config.py             # [MODIFY] 新增 HTTP_PROXY / HTTPS_PROXY / USE_TOR 环境变量读取
└── .env                  # [MODIFY] 末尾追加代理配置指引（Clash/v2rayN 与 Tor 两种示例，注释说明）
```

### 关键代码结构（接口级）

```python
# shared/search/__init__.py
def get_http_proxies() -> Optional[dict]:
    """返回 {'http':..., 'https':...} 或 None；优先 HTTP_PROXY/HTTPS_PROXY，其次 USE_TOR=true 走 Tor socks5"""
```

```python
# shared/search/web.py
BLOCKED_DOMAINS: List[str] = ["baike.baidu.com", "iciba.com", "5eplay.com", "csgo", "wikipedia.org", ...]

def _passes_filter(result: dict, queries) -> bool:
    """域名黑名单命中即丢弃；再要求 title+description 至少命中查询中一个非停用词 token"""
```

```python
# shared/search/news.py
RSS_SOURCES = [
    {"name": "Bing News", "url": "...", "requires_proxy": False},
    {"name": "36氪", "url": "https://36kr.com/feed", "requires_proxy": False},
    {"name": "Google News", "url": "...", "requires_proxy": True},
    # ... 其余境外源标记 requires_proxy=True
]
```

## 验证方式

1. **无代理先跑一次**：`python main.py briefing -m qwen3:8b`，确认 `data/briefings/` 下生成的 MD 中不再出现 baike/iciba/CSGO 噪声，AI 与网络安全分类出现 Bing News + 36氪 相关条目。
2. **配代理再跑一次**：在 `.env` 配置 `HTTP_PROXY` 或 `USE_TOR=true` 后重跑，日志应出现 Google News / NewsAPI 成功获取（不再是满屏 timeout）。
3. 检查邮件收件箱与 `data/briefings/` 存档，确认 HTML/PDF 排版正常、内容相关。

## Agent Extensions

### MCP

- **filesystem**
- Purpose: 编辑配置类文件 `.env`（追加代理配置指引）与在探测国内 RSS 源时读取/写入 `RSS_SOURCES` 相关配置，以及读取 `data/briefings/` 下生成的简报做验证核对。
- Expected outcome: `.env` 代理示例正确写入；实施期探测通过的国内源被稳定落地到 `news.py`；验证阶段可读取生成的简报 Markdown 确认噪声已被过滤。