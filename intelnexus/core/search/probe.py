"""源连通性主动探测模块
======================
为「数据源状态」面板提供真正的联网检测能力（2026-10-21 审计补齐）。

背景：健康表唯一数据源是真实检索的被动观测（``registry.collect`` →
``HealthBatch``/``update_health``），``stale``（待复核）只标记不复核——
复核动作依赖下一次真实检索。只跑特定模式的源（如暗网）长期不检索时，
面板永远停在旧结论。本模块把复核变成**用户主动发起**的最小成本真实检索。

判定口径与 ``registry._timed_search`` 完全对齐（唯一判定逻辑，避免两套口径）：
- 有结果 → ``ok``
- 空结果 + ``last_error`` 非空 → ``fail``（适配器吞异常返回 ``[]`` 时靠信号通道补记）
- 空结果 + 无错误 → ``empty``（连通但本次查询未命中）
- 异常 → ``fail``

与被动观测的语义差异（沿用 ``health.record_probe_result`` 的既有设计）：
- 探测是用户主动发起的连通性结论：失败一次即 degraded（封顶不到 down，
  不会把源从搜索管线剔除），成功立即恢复 healthy；
- ``ok`` / ``empty`` 均按成功落盘（与数据源管理「批量测试」的 HTTP 可达=成功
  同语义）；``skip_*`` 状态不落盘——跳过不是观测，不得改动健康统计。

超时模型：Python 无法中断正在运行的线程，故每源包一层单线程 executor
施加**独立超时**：超时后主流程按 ``timeout`` 记录并继续探测其他源，泄漏的
内层线程由各源自身的 socket 超时收尾（与 ``registry.collect`` 全局超时后
放弃慢线程的处理同构）。

- 普通源 25s：覆盖各源 requests 超时（10-30s）的正常波动区间；
- DarkWeb 90s：自定义 onion 站点首次建链实测 60-75s（2026-10-20 审计），
  20s 预算会把活站误判为死站；
- 全局预算 420s 兜底：即使逐源超时全部失效，探测也不会无限挂起。
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

#: 探测查询词：低噪声威胁类词，项目端到端验证（暗网/威胁情报/公开引擎）均有覆盖
PROBE_QUERY = "ransomware"
#: 单源探测取回条数上限：连通性判断只需少量结果，压低 API 成本
PROBE_MAX_RESULTS = 5
#: 普通源单源超时（秒）
DEFAULT_TIMEOUT_S = 25.0
#: DarkWeb 单源超时（秒）：自定义 onion 首链实测 60-75s，留余量
DARKWEB_TIMEOUT_S = 90.0
#: 全局预算兜底（秒）：全部 future 的总等待上限
GLOBAL_BUDGET_S = 420.0
#: 并发探测线程数
MAX_WORKERS = 6

#: 探测状态域
#: - ok / empty：连通（empty 表示连通但本次查询 0 条结果）
#: - fail / timeout：不连通或不可判定
#: - skip_no_proxy / skip_disabled：未探测（需代理未配置 / 源自身功能未启用），
#:   均不落盘、不计入进度失败
STATES = ("ok", "empty", "fail", "timeout", "skip_no_proxy", "skip_disabled")

#: 按 category 覆盖超时：暗网类源需要 Tor 建链预算
_CATEGORY_TIMEOUTS: Dict[str, float] = {"darkweb": DARKWEB_TIMEOUT_S}

#: 成功落盘的状态（连通即成功，沿用批量测试「可达=成功」语义）
_SUCCESS_STATES = ("ok", "empty")


@dataclass
class ProbeOutcome:
    """单个源的探测结论。"""
    source_name: str
    state: str
    latency_ms: float = 0.0
    result_count: int = 0
    error: str = ""

    @property
    def success(self) -> bool:
        """是否应按「成功」写入健康表（skip_* 不落盘，本属性对其无意义）。"""
        return self.state in _SUCCESS_STATES


def _timeout_for(src, overrides: Optional[Dict[str, float]]) -> float:
    """单源探测预算：显式 overrides（按源名）> category 映射 > 默认值。"""
    if overrides and src.name in overrides:
        return float(overrides[src.name])
    return _CATEGORY_TIMEOUTS.get(getattr(src, "category", ""), DEFAULT_TIMEOUT_S)


def _probe_one(src, query: str, overrides: Optional[Dict[str, float]]) -> ProbeOutcome:
    """探测单个源（在worker线程内执行）：最小成本真实检索 + 口径对齐判定。"""
    from intelnexus.core.search import get_http_proxies

    # 代理门控与 registry._timed_search 同款：需代理而未配置 → 跳过不落盘
    # （被动路径同样不记健康统计，只标记 no_proxy，保持口径一致）
    if getattr(src, "requires_proxy", False) and not get_http_proxies():
        return ProbeOutcome(src.name, "skip_no_proxy")

    # 暗网功能总开关未启用：源自身的门控会直接返回空且无错误，探测无法区分
    # 「连通但未命中」与「功能没开」。这里提前识别为 skip_disabled，不落盘——
    # 刻意关闭的功能不该被探测改写健康统计。
    if getattr(src, "category", "") == "darkweb":
        try:
            from intelnexus.search_app.darkweb import is_available as darkweb_available
            if not darkweb_available():
                return ProbeOutcome(src.name, "skip_disabled")
        except Exception:
            pass  # 探测器自身故障不伪装成源结论，继续按正常路径探测

    timeout = _timeout_for(src, overrides)
    t0 = time.monotonic()
    # 先清残留失败信号：保证随后读到的 last_error 只属于本次探测
    # （与 registry._timed_search 同款；桩可能无此属性，setattr 防御）
    setattr(src, "last_error", None)
    inner = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"probe-{src.name}")
    try:
        fut = inner.submit(src.search, query, PROBE_MAX_RESULTS)
        try:
            results = fut.result(timeout=timeout)
        except FuturesTimeoutError:
            return ProbeOutcome(
                src.name, "timeout", latency_ms=timeout * 1000.0,
                error=f"探测超时（>{timeout:.0f}s）。暗网源可能是 Tor 建链慢或站点已死；其余源多为网络不可达")
        elapsed = (time.monotonic() - t0) * 1000.0
        if results:
            return ProbeOutcome(src.name, "ok", elapsed, len(results))
        err = getattr(src, "last_error", None)
        if err:
            return ProbeOutcome(src.name, "fail", elapsed, error=str(err))
        return ProbeOutcome(src.name, "empty", elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000.0
        return ProbeOutcome(src.name, "fail", elapsed, error=f"{type(e).__name__}: {e}")
    finally:
        # 不等待可能已超时的内层线程：socket 超时最终会收尾它
        inner.shutdown(wait=False, cancel_futures=True)


def probe_registry(registry, query: str = PROBE_QUERY, on_result: Optional[Callable[[ProbeOutcome], None]] = None,
                   max_workers: int = MAX_WORKERS,
                   timeout_overrides: Optional[Dict[str, float]] = None,
                   persist: bool = True) -> List[ProbeOutcome]:
    """并发探测注册表中全部**已启用**源，返回探测结论列表（完成序）。

    Args:
        registry: ``SearchSourceRegistry``（UI 侧应按会话当前暗网配置构造，
            使探测忠实于真实检索链路）。
        query: 探测查询词。
        on_result: 每条结论落盘后的回调（主线程调用，供 UI 实时刷新进度）；
            回调异常不影响探测与落盘。
        max_workers: 并发线程数。
        timeout_overrides: 按源名覆盖单源超时（秒），测试与小众调优用。
        persist: 是否经 ``health.record_probe_result`` 写入健康表（测试置 False）。

    Returns:
        全部源的 ``ProbeOutcome``（含 skip_*）。顺序为完成序，展示由调用方自行定序。
    """
    from intelnexus.core.search.health import record_probe_result

    sources = [s for s in registry.all_sources() if getattr(s, "enabled", True)]
    if not sources:
        return []

    def _persist(outcome: ProbeOutcome) -> None:
        if not persist or outcome.state.startswith("skip"):
            return
        try:
            record_probe_result(
                outcome.source_name, outcome.success, outcome.latency_ms,
                error=outcome.error or None)
        except Exception as e:
            # 落盘失败不影响探测结论展示（record_probe_result 内部已兜底，双保险）
            logger.warning(f"探测结论落盘失败 [{outcome.source_name}]: {e}")

    outcomes: Dict[str, ProbeOutcome] = {}
    executor = ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(sources))),
                                  thread_name_prefix="source-probe")
    future_map = {executor.submit(_probe_one, src, query, timeout_overrides): src
                  for src in sources}
    t0 = time.monotonic()
    try:
        for fut in as_completed(future_map, timeout=GLOBAL_BUDGET_S):
            src = future_map[fut]
            try:
                outcome = fut.result()
            except Exception as e:  # _probe_one 已全兜底，此分支纯防御
                outcome = ProbeOutcome(src.name, "fail", error=f"{type(e).__name__}: {e}")
            outcomes[outcome.source_name] = outcome
            _persist(outcome)
            if on_result is not None:
                try:
                    on_result(outcome)
                except Exception as e:
                    logger.warning(f"探测进度回调异常（不影响探测）: {e}")
    except FuturesTimeoutError:
        # 全局预算兜底：未完成的源按超时记录（诚实——探测没有拿到结论）
        logger.warning(f"联网检测超出全局预算 {GLOBAL_BUDGET_S:.0f}s，"
                       f"剩余 {sum(1 for f in future_map if not f.done())} 个源按超时记录")
        for fut, src in future_map.items():
            if fut.done():
                continue
            outcome = ProbeOutcome(src.name, "timeout",
                                   latency_ms=(time.monotonic() - t0) * 1000.0,
                                   error=f"探测整体预算超时（>{GLOBAL_BUDGET_S:.0f}s）")
            outcomes[outcome.source_name] = outcome
            _persist(outcome)
            if on_result is not None:
                try:
                    on_result(outcome)
                except Exception:
                    pass
    finally:
        # 放弃仍在跑的线程：与 registry.collect 超时处理同构
        executor.shutdown(wait=False, cancel_futures=True)

    return list(outcomes.values())
