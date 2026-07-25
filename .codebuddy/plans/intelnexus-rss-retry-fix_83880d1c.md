---
name: intelnexus-rss-retry-fix
overview: 为 shared/search/news.py 的 search_rss 方法增加 RSS 请求重试机制（超时/异常自动重试 2 次含退避）并适度提高超时阈值，消除 36氪等直连源偶发 read timeout=8 告警，保留所有源。
todos:
  - id: add-rss-retry
    content: 在 news.py 为 search_rss 增加超时重试退避逻辑并提升超时阈值至 10s
    status: completed
  - id: add-retry-test
    content: 新增 test_news_rss_retry.py 验证重试次数与最终告警路径
    status: completed
    dependencies:
      - add-rss-retry
---

## 用户需求

执行 `.\run.bat briefing` 时，终端偶发非阻塞告警 `WARNING shared.search.news RSS search error from 36氪: Read timed out. (read timeout=8)`。该告警由 `search_rss` 当前单次直连请求（timeout=8、不经代理）在网络抖动时触发，被 except 捕获后本轮该源结果为空，但不影响整体采集与简报生成。

## 产品概述

对采集层 `shared/search/news.py` 的 `search_rss` 方法做健壮性增强：为所有 RSS 源的网络请求增加超时自动重试与退避，并适度提高超时阈值，消除偶发网络抖动导致的告警，同时保留 36氪 等全部源。

## 核心功能

- 新增超时重试机制：对 `search_rss` 内每个源的网络请求，在 `requests.exceptions.RequestException`（含 ConnectTimeout / ReadTimeout / ConnectionError）时自动重试 2 次，采用指数退避。
- 适度提高超时阈值：RSS 请求超时由 8s 提升至 10s，与同文件 `search_bing_news` / `search_google_news` 的 timeout=10 保持一致。
- 重试仅在请求异常时触发，对 4xx/5xx（返回响应但不抛异常）保持原有忽略逻辑；重试耗尽后行为与原一致（记 warning 并跳过该源）。
- 不改动 RSS 源分级、域名黑名单、相关性过滤等已稳定逻辑，不改变采集业务与结果质量。

## 技术栈

- 运行环境：Python 3（项目既有 conda base 环境）
- 采集层：Python 模块 `shared/search/news.py`，依赖 `requests`、`concurrent.futures`（既有）
- 重试退避：复用标准库 `time`（新增 `import time`），不引入任何新依赖
- 测试：pytest + `unittest.mock`（与 `tests/test_pipeline.py` 既有模式一致）

## 实现方案

### 总体策略

在 `NewsSearch` 类中新增一个私有的带重试封装方法 `_fetch_rss_with_retry`，将 `search_rss` 中第 97 行的单次 `requests.get` 替换为该封装调用。重试仅捕获 `requests.exceptions.RequestException`，指数退避，耗尽后抛出异常交由既有外层 `except Exception` 统一记 warning 并跳过该源；同时把超时阈值从 8s 提升至 10s（与 Bing/Google 检索一致）。

### 关键技术决策

1. **重试范围限定为 RequestException**：网络抖动表现为连接/读取超时与连接错误，均抛 `RequestException`；而 4xx/5xx 会正常返回 response 且不抛异常，原逻辑本就忽略非 200 状态，重试它们无意义且可能放大无效请求。故只对异常重试，避免对业务语义（如被限流返回的 429）做无意义重试。
2. **指数退避而非固定等待**：退避 `0.5 * 2**attempt`（0.5s、1.0s），单源重试累计阻塞 ≤ 1.5s，且 `search_rss` 本身运行于 `ThreadPoolExecutor(max_workers=4)` 中，各源并行，单源延迟不阻塞其他源，整体采集耗时可控。
3. **复用既有日志与异常结构**：重试中间态用 `logger.debug` 记录（避免日志刷屏），最终失败仍走原 `logger.warning(f"RSS search error from {source['name']}: {e}")`，保持告警文案与既有运维习惯一致，不影响下游去重合并。
4. **超时阈值对齐现有代码**：10s 与同文件 Bing/Google 检索一致，既"适度提高"又避免各源超时值发散、便于后续统一调参。

### 性能与可靠性

- 退避总时长有界（每源 ≤1.5s），并行线程隔离，不引入新的性能瓶颈。
- 重试使偶发抖动基本被吸收，预期告警频率显著下降；仅在目标源持续不可达时仍记 warning（符合预期）。
- 改动局部、向后兼容：有/无代理环境、各 RSS 源分级逻辑均不变。

## 实现要点

- `news.py` 顶部新增 `import time`；在 `RSS_SOURCES` 附近新增模块常量 `RSS_FETCH_TIMEOUT = 10`。
- 新增 `NewsSearch._fetch_rss_with_retry(self, url, headers, proxies, timeout=RSS_FETCH_TIMEOUT, max_retries=2)` 方法，内部循环 `max_retries+1` 次 `requests.get`，捕获 `requests.exceptions.RequestException` 时 `time.sleep(0.5 * 2**attempt)` 后退避重试，并用 `logger.debug` 记录重试；全部失败后 `raise` 最后一个异常。
- `search_rss` 第 97 行改为 `response = self._fetch_rss_with_retry(url, headers, get_http_proxies_for(source.get("requires_proxy")))`，移除原内联 `requests.get` 与内联 `timeout=8`；外层 `except Exception`（第 149–150 行）保持不变。
- 不触碰 `RSS_SOURCES`、`is_blocked_domain`、`relevance_passes`、相关性过滤等逻辑。

## 架构设计

本次为采集层局部健壮性优化，不涉及架构调整。改动点仅位于 `NewsSearch.search_rss` 的请求获取子步骤与新增的私有封装方法，不影响模块间调用关系与既有数据流向（查询 → 并发检索 → 去重合并 → 简报生成）。

## 目录结构

```
IntelNexus/
├── shared/search/
│   └── news.py                  # [MODIFY] 顶部新增 import time 与常量 RSS_FETCH_TIMEOUT=10；新增 _fetch_rss_with_retry 重试封装方法；search_rss 内将单次 requests.get 替换为该封装调用（移除内联 timeout=8）。外层 except 告警逻辑不变。
└── tests/
    └── test_news_rss_retry.py  # [NEW] 针对 _fetch_rss_with_retry / search_rss 的单元测试：用 mock 让 requests.get 前两次抛 RequestException、第三次成功，断言重试 2 次后返回响应；以及始终失败场景，断言最终走 warning 路径且不崩溃。遵循 tests/test_pipeline.py 的 pytest + unittest.mock 风格。
```

## 关键代码结构

`shared/search/news.py` 中新增的私有重试封装方法（接口级定义）：

```python
def _fetch_rss_with_retry(self, url, headers, proxies, timeout=10, max_retries=2):
    """带指数退避的 RSS 请求封装，仅在 requests 异常时重试。"""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < max_retries:
                logger.debug(f"RSS 请求重试 {attempt + 1}/{max_retries}: {e}")
                time.sleep(0.5 * (2 ** attempt))
                continue
    raise last_err
```