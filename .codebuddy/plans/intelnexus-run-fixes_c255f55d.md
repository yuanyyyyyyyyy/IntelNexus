---
name: intelnexus-run-fixes
overview: 修复运行 IntelNexus 时暴露的两个遗留问题：① run.bat 中文注释在 cmd 下乱码报"不是内部或外部命令"；② NewsAPI 在无代理时傻等 30s 连接超时拖累采集。
todos:
  - id: fix-runbat-comments
    content: run.bat 中文注释替换为 ASCII 英文，消除乱码命令报错
    status: completed
  - id: gate-newsapi-proxy
    content: news.py NewsAPI 增加 get_http_proxies 门控，无代理时跳过
    status: completed
  - id: verify-run
    content: 运行 run.bat briefing 验证无乱码且 NewsAPI 超时消失
    status: completed
    dependencies:
      - fix-runbat-comments
      - gate-newsapi-proxy
---

## 用户需求

执行 `.\run.bat briefing -m qwen3:8b` 主流程已能生成简报并邮件推送，但终端暴露两处运行异常，需定位并修复：

1. cmd 启动时报乱码 `'屾晠鍏堟竻鎺夋墠鑳戒娇' 不是内部或外部命令`，中文注释被误读为命令。
2. 采集阶段 NewsAPI 反复 `ConnectTimeoutError ... connect timeout=30`，每次傻等约 30s，拖累整体采集耗时。

## 产品概述

对现有采集层与启动脚本做两处精准修复，不改变业务逻辑与采集结果质量，仅消除启动乱码报错与境外源无代理时的无效超时。

## 核心功能

- run.bat 全量中文注释替换为 ASCII 英文注释，消除 GBK/UTF-8 编码错配导致的乱码命令报错。
- news.py 中 NewsAPI 检索与 Google News 一致，增加代理可用性门控；无代理时打印"跳过 NewsAPI 检索"并跳过，避免 30s 级无效超时。

## 技术栈

- 启动脚本：Windows 批处理（.bat），Python 3 + conda base 环境
- 采集层：Python 模块 `shared/search/news.py`，依赖 `requests`、`concurrent.futures`、`newsapi`
- 代理判断：`shared/search/__init__.py` 中既有 `get_http_proxies()`（已在 news.py 第 14 行导入，返回 None 表示无代理）

## 实现方案

### 总体策略

两处独立且明确的修复，复用既有 `get_http_proxies()` 与 Google News 门控模式，不引入新依赖、不改动业务数据流。

### 关键技术决策

1. run.bat 编码问题：Windows `cmd.exe` 默认按系统代码页（GBK/936）逐字节解析 `.bat`；中文注释以 UTF-8 无 BOM 保存时被误读成命令。根治方式是批处理内仅保留 ASCII 字符（英文注释），逻辑与 `set "HTTP_PROXY="` 等清代理动作完全不变。
2. NewsAPI 门控：newsapi.org 属需代理的境外源，与 Google News 同性质。将提交 `search_newsapi` 任务的条件从仅判断 `self.news_client`（api_key 存在）升级为 `self.news_client and get_http_proxies()`，与第 240 行 Google News 门控保持完全一致；无代理时打印 `logger.info("跳过 NewsAPI 检索（未配置代理）")`。这样无代理环境不再发起无效连接，采集耗时由"每查询 30s × N 次"降为秒级；配了代理时 NewsAPI 底层 `requests` 自动读取 `HTTPS_PROXY` 仍正常拉取。

### 性能与可靠性

- NewsAPI 超时根因是连接级阻塞（connect timeout=30 × 重试），无代理时彻底跳过即消除该瓶颈，整体采集进入秒级。
- 改动局部、向后兼容：有代理配置时行为不变；无代理时仅少一个境外源，与既有"跳过 Google News"一致。

## 实现要点

- run.bat 仅替换第 3–8 行、第 21 行、第 28–29 行的中文为等价英文，第 30–32 行清代理变量与第 34 行调用 python 保持不变。
- news.py 仅修改 `search()` 方法第 235–236 行门控逻辑，沿用已导入的 `get_http_proxies` 与既有 `logger`，日志文案风格与 Google News 跳过提示对齐。
- 不触碰 RSS 源分级、域名黑名单、相关性过滤等已稳定逻辑，控制改动影响面。

## 架构设计

本次为局部修复，不涉及架构调整。改动点位于采集层 `NewsSearch.search()` 的任务分发逻辑与启动脚本注释层，不影响模块间调用关系与数据流向（查询 → 并发检索 → 去重合并 → 简报生成）。

## 目录结构

```
IntelNexus/
├── run.bat                       # [MODIFY] 将全部中文 REM 注释替换为 ASCII 英文注释，消除启动乱码命令报错；清代理与调用 python 逻辑不变。
└── shared/search/
    └── news.py                   # [MODIFY] search() 中 NewsAPI 任务提交增加 get_http_proxies() 门控，无代理时跳过并打印提示，与 Google News 门控一致。
```

## 关键代码结构

`shared/search/news.py` 中 `search()` 方法任务分发修改（其余不变）：

```python
# 修改前
if self.news_client:
    futures.append(executor.submit(self.search_newsapi, query, max_results))

# 修改后
if self.news_client and get_http_proxies():
    futures.append(executor.submit(self.search_newsapi, query, max_results))
elif self.news_client:
    logger.info("跳过 NewsAPI 检索（未配置代理）")
```

`run.bat` 注释修改示意（仅注释，逻辑不变）：

```
REM Clear ghost proxy vars inherited from the Shell. load_dotenv() will not
REM overwrite existing env vars, so clearing them lets .env proxy settings apply.
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "USE_TOR="
python "%~dp0main.py" %*
```