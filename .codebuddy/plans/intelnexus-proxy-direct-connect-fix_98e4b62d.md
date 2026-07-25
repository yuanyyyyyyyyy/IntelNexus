---
name: intelnexus-proxy-direct-connect-fix
overview: 修复 IntelNexus 采集层的「幽灵代理」问题：让国内源（requires_proxy=False）永远直连、仅境外源按需走代理；web 慢速引擎无代理时跳过；超时/重试收敛；run.bat 兜底清除 Shell 继承的代理变量，使 .env 代理配置能正确生效。
todos:
  - id: add-proxy-helper
    content: 在 shared/search/__init__.py 新增 get_http_proxies_for(requires_proxy) 收口代理选择
    status: completed
  - id: fix-news-proxy-routing
    content: 修改 news.py：search_rss 仅代理源传代理、search_bing_news 直连、search() 门控 search_google_news
    status: completed
    dependencies:
      - add-proxy-helper
  - id: fix-web-slow-skip
    content: 修改 web.py：get_web_results 无代理跳过 SLOW_ENGINES 并收敛 Retry/timeout
    status: completed
    dependencies:
      - add-proxy-helper
  - id: patch-runbat-proxy-clear
    content: 修改 run.bat：调用 python 前清除 Shell 继承的 HTTP_PROXY/HTTPS_PROXY/USE_TOR
    status: completed
  - id: verify-briefing-run
    content: 运行 .\run.bat briefing -m qwen3:8b 验证国内源直连、境外源跳过、耗时下降
    status: completed
    dependencies:
      - fix-news-proxy-routing
      - fix-web-slow-skip
      - patch-runbat-proxy-clear
---

## 用户需求

修复 IntelNexus「AI 简报」采集层的"幽灵代理"问题：系统/PowerShell Shell 环境变量残留指向不可达地址的 `HTTP_PROXY`/`HTTPS_PROXY`，导致本应直连或跳过的源全部超时（采集阶段空等约 4 分钟），且新闻 RSS 源几乎零贡献，简报素材几乎全靠 Bing 网页搜索撑着。

## 产品概述

在已落地的方案 A+B+C（代理接线 + 国内 RSS 源 `requires_proxy` 分级 + 域名黑名单/相关性噪声过滤）基础上，修正"代理误接国内源 + 慢速引擎无跳过 + Shell 幽灵代理干扰"三处缺陷，使采集层在「无代理（国内源直连、境外源跳过）」与「有代理（境外源全开）」两种模式下都正确、高效、零额外开销。

## 核心功能

- 国内源（36氪/量子位/IT之家/少数派/Bing News/Bing/百度）强制直连，绝不经过任何代理。
- 境外源（Google News/NewsAPI/Reuters 等）仅在配置代理时走代理；无代理时自动跳过，不再发起请求。
- web 慢速引擎（DuckDuckGo/Yahoo/Yandex）无代理时直接跳过，消除满屏 `ConnectTimeoutError`。
- `run.bat` 启动前清除 Shell 继承的代理变量，根治幽灵代理，同时确保 `.env` 中显式配置的代理仍能正确生效。
- 超时与重试收敛，避免单源拖垮整体采集耗时（4 分钟 → 几十秒）。

## 技术栈

- 运行时：Python 3.10+（conda base 环境，依赖已就绪）
- 采集层：`shared/search/__init__.py`、`shared/search/news.py`、`shared/search/web.py`
- 启动脚本：`run.bat`
- 依赖：requests + BeautifulSoup（保持现状，无新增依赖）

## 实现方案

### 整体策略

仅修正代理接线与源跳过门控逻辑，**不改动** `intel-briefing/ai_briefing/collector.py`、LLM 生成与邮件推送链，也不触碰已落地的噪声过滤（`BLOCKED_DOMAINS` / `relevance_passes`）。

### 关键决策与理由

1. **新增 `get_http_proxies_for(requires_proxy)` 统一收口（核心修复点）**：当前 `news.py:97` 给**所有**源（含 `requires_proxy=False` 的 36氪国内源）都传 `proxies=get_http_proxies()`，一旦存在幽灵代理，国内源也被拽进不可达代理而超时。新增函数：国内源返回 `None`（强制直连），代理源返回实际代理或 `None`（未配置）。一处收口，消除分散误接。
2. **`search_rss` 代理按源分级**：调用改为 `proxies=get_http_proxies_for(source.get("requires_proxy"))`；同时保留既有第 87-89 行跳过逻辑（无代理时境外源不发起请求）。
3. **`search_bing_news` 强制直连**：Bing News 为国内可直连源，第 161 行 `proxies` 显式置 `None`。
4. **`search()` 门控 `search_google_news`**：第 240 行目前无条件提交该 future，无代理时会单源 10s×重试超时。改为仅当 `get_http_proxies()` 非空时才提交，否则跳过（与 RSS 跳过逻辑一致）。
5. **`web.py get_web_results` 无代理跳过慢速引擎**：第 217-230 行当 FAST 结果不足 20 时补充 SLOW_ENGINES。新增门控：若 `get_http_proxies()` 为 `None`，直接跳过 SLOW 阶段（FAST_ENGINES 的 Bing/百度国内可直连照常运行）。
6. **`run.bat` 清除 Shell 代理兜底**：在 `python "%~dp0main.py" %*` 前加 `set "HTTP_PROXY="` / `set "HTTPS_PROXY="` / `set "USE_TOR="`。因 `config.py:4` 的 `load_dotenv()` 在进程内从 `.env` 重新写入且默认不覆盖已存在变量——清除 Shell 继承值后，`.env` 中用户明确配置的代理（如 `HTTP_PROXY=http://127.0.0.1:7890`）仍会生效，仅幽灵 Shell 值被清除。
7. **超时/重试收敛**：`web.py get_session` 的 `Retry` 由 `connect=2` 收敛为 `connect=1, read=1, total=2`；`session.get` 的 `timeout=10` 调整为 `(8, 15)`（连接 8s、读取 15s），将单源最坏等待从上百次重试的 ~4 分钟降至几十秒。`news.py` 的 RSS/Google `timeout=8~10` 保留（仅在代理配置路径触发）。

### 性能与可靠性

- 代理仅在「已配置且源需要」时使用；国内源永远零代理开销。
- 无代理模式下整体采集不再向任何境外地址发起请求，耗时从 ~4 分钟降至几十秒。
- 单源异常已有 `try/except` 容错，门控改动不会导致整体采集中断。
- 改动向后兼容：无代理时行为与原设计一致（国内源直连 + 境外源跳过 + 噪声过滤增强）。

## 架构设计

```mermaid
flowchart TD
    A[采集启动] --> B{get_http_proxies() 返回?}
    B -->|None 无代理| C[国内源 RSS/Bing/百度 强制直连]
    B -->|None 无代理| D[境外源 RSS/Google/NewsAPI 跳过]
    B -->|None 无代理| E[web 仅跑 FAST_ENGINES]
    B -->|有代理| F[国内源仍直连 None]
    B -->|有代理| G[境外源走代理成功获取]
    B -->|有代理| H[web FAST+SLOW 均走代理]
    C --> I[聚合去重 + 噪声过滤]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
```

## 目录结构

```
IntelNexus/
├── shared/search/
│   ├── __init__.py   # [MODIFY] 新增 get_http_proxies_for(requires_proxy) 收口代理选择逻辑
│   ├── news.py        # [MODIFY] search_rss 仅代理源传代理；search_bing_news 强制直连；
│   │                  #          search() 中 search_google_news 仅代理可用时执行
│   └── web.py         # [MODIFY] get_web_results 无代理跳过 SLOW_ENGINES；收敛 Retry 与 timeout
└── run.bat            # [MODIFY] 调用 python 前清除 Shell 继承的 HTTP_PROXY/HTTPS_PROXY/USE_TOR
```

## 关键代码结构

```python
# shared/search/__init__.py
def get_http_proxies_for(requires_proxy: bool) -> Optional[dict]:
    """
    代理收口：国内源(requires_proxy=False)强制直连返回 None；
    代理源(requires_proxy=True)返回实际代理或 None(未配置代理)。
    """
```