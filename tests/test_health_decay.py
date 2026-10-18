"""健康判定的时间维度（stale / down 冷却）与读取 IO 回归。

背景见 ``health.py`` 模块 docstring：``status`` 是纯计数推导、没有时间概念，
于是有两个后果——

1. ``down`` 是**终态**：``registry.get_sources_by_mode`` 会剔除 down 源，
   被剔除 → 永不执行 → 永不成功 → 永远 down。真实健康表里
   arXiv / HuggingFace / AlienVault_OTX / CNVD 四个源已处于该状态。
2. ``degraded`` 会**冻结**：只在特定 mode 下运行的源，若该 mode 长期不用，
   失败链既不增长也不衰减，界面永久显示「降级」。

这里钉住两件事：派生规则本身，以及检索管线确实按派生结果放行/剔除。
"""

from datetime import datetime, timedelta
import threading
import time

import pytest

from intelnexus.core.search import health as health_mod
from intelnexus.core.search.health import (
    DOWN_COOLDOWN_MINUTES,
    STALE_AFTER_HOURS,
    SourceHealth,
    get_health_map,
    record_probe_result,
    save_health,
    signal_age,
    update_health,
    view_status,
)
from intelnexus.core.search.registry import SearchSourceRegistry
from intelnexus.core.search.source import BaseSearchSource

NOW = datetime(2026, 10, 18, 8, 0, 0)


def _mk(status="healthy", streak=0, *, attempt="__none__", success=None):
    h = SourceHealth(source_name="X")
    h.status = status
    h.consecutive_failures = streak
    h.last_success = success
    h.last_attempt = None if attempt == "__none__" else attempt
    return h


def _ago(**kwargs):
    return (NOW - timedelta(**kwargs)).isoformat()


# ---------------------------------------------------------------------------
# 1. 派生规则
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,entry,expected", [
    # 健康的源不需要复核，时间再久也不该变灰
    ("healthy 无时间戳", _mk("healthy"), "healthy"),
    ("healthy 很久以前", _mk("healthy", attempt=_ago(days=30)), "healthy"),
    # 无时间锚点 → 无法证明判定仍有效 → 待复核（而不是永久跳过）
    ("down 无时间戳（旧版数据）", _mk("down", 6), "stale"),
    ("degraded 无时间戳（旧版数据）", _mk("degraded", 3), "stale"),
    # down 冷却：期内剔除、期外放行
    ("down 冷却期内", _mk("down", 6, attempt=_ago(minutes=5)), "down"),
    ("down 刚好过冷却", _mk("down", 6, attempt=_ago(minutes=DOWN_COOLDOWN_MINUTES + 1)), "stale"),
    # degraded 的时钟是 24h
    ("degraded 1 小时前", _mk("degraded", 3, attempt=_ago(hours=1)), "degraded"),
    ("degraded 超 24 小时", _mk("degraded", 3, attempt=_ago(hours=STALE_AFTER_HOURS + 1)), "stale"),
    # 旧版只有 last_success 时退化使用它
    ("degraded 仅 last_success", _mk("degraded", 3, success=_ago(days=3)), "stale"),
    # 时钟回拨：未来时间按 0 处理，不产生「-3 天前」进而误判过期
    ("时钟回拨", _mk("degraded", 3, attempt=(NOW + timedelta(minutes=5)).isoformat()), "degraded"),
    # 损坏的状态值：按降级处理（与 ui.health_view 的兜底一致）
    ("未知状态", _mk("weird"), "degraded"),
])
def test_view_status_rules(label, entry, expected):
    assert view_status(entry, NOW) == expected, label


def test_signal_age_prefers_last_attempt():
    """last_attempt 比 last_success 更贴近「上一次观测」，必须优先。"""
    h = _mk("degraded", 3, attempt=_ago(hours=2), success=_ago(days=5))
    assert signal_age(h, NOW) == timedelta(hours=2)


def test_signal_age_none_when_no_timestamp():
    assert signal_age(_mk("down", 6), NOW) is None


# ---------------------------------------------------------------------------
# 2. 每次观测都要刷新 last_attempt
# ---------------------------------------------------------------------------

def test_record_success_and_failure_refresh_attempt():
    h = SourceHealth(source_name="X")
    assert h.last_attempt is None

    h.record_failure("boom")
    assert h.last_attempt is not None

    first = h.last_attempt
    h.record_success(120.0)
    assert h.last_attempt is not None
    assert h.last_attempt >= first


def test_note_observation_refreshes_attempt_without_touching_counts():
    """连通但零结果：不算成功也不算失败，但必须刷新时间戳。"""
    h = _mk("degraded", 3, attempt=_ago(days=2))
    h.note_observation(80.0)
    assert h.consecutive_failures == 3
    assert h.success_count == 0
    assert h.fail_count == 0
    assert view_status(h, datetime.now()) == "degraded"


def test_reset_clears_attempt(tmp_health_file):
    """清除标记回到全新起点：时间锚点一并清空，避免残留旧的 stale 判定。"""
    h = _mk("down", 6, attempt=_ago(days=3))
    h.reset()
    assert h.last_attempt is None
    assert view_status(h, NOW) == "healthy"


def test_probe_refreshes_attempt_on_both_branches(tmp_health_file):
    record_probe_result("P", success=False, latency_ms=0, error="x")
    assert signal_age(health_mod.get_health("P")) is not None

    record_probe_result("P", success=True, latency_ms=90.0)
    assert signal_age(health_mod.get_health("P")) is not None


# ---------------------------------------------------------------------------
# 3. 检索管线的放行判定
# ---------------------------------------------------------------------------

class _StubSource(BaseSearchSource):
    """最小源桩：只为 get_sources_by_mode 提供 name / category / enabled。"""

    category = "web"

    def __init__(self, name):
        super().__init__(name=name, category="web")

    def search(self, query, max_results=20):
        return []


@pytest.fixture
def tmp_health_file(tmp_path, monkeypatch):
    """健康表重定向到临时目录，避免污染真实 data/source_health.json。"""
    path = tmp_path / "source_health.json"
    monkeypatch.setattr(health_mod, "HEALTH_FILE", str(path), raising=True)
    return path


def _seed(name, status, streak, age_minutes=None):
    h = SourceHealth(source_name=name)
    h.status = status
    h.consecutive_failures = streak
    if age_minutes is not None:
        h.last_attempt = (datetime.now() - timedelta(minutes=age_minutes)).isoformat()
    save_health(h)


def _registry(*names):
    reg = SearchSourceRegistry(news_api_key=None)
    reg._builtin = [_StubSource(n) for n in names]
    reg._user_sources = []
    return reg


def test_registry_skips_down_within_cooldown(tmp_health_file):
    _seed("A", "down", 6, age_minutes=5)
    reg = _registry("A")
    assert reg.get_sources_by_mode("web") == []
    assert reg.last_skipped_down == ["A"]


def test_registry_admits_down_after_cooldown(tmp_health_file):
    """核心回归：冷却到期后必须放行，否则 down 是永不可逆的终态。"""
    _seed("A", "down", 6, age_minutes=DOWN_COOLDOWN_MINUTES + 1)
    reg = _registry("A")
    assert [s.name for s in reg.get_sources_by_mode("web")] == ["A"]
    assert reg.last_skipped_down == []


def test_registry_admits_legacy_down_without_timestamp(tmp_health_file):
    """旧版健康表没有 last_attempt：没有时间锚点就不能断言「仍然不可用」。"""
    _seed("A", "down", 6, age_minutes=None)
    reg = _registry("A")
    assert [s.name for s in reg.get_sources_by_mode("web")] == ["A"]


def test_registry_admits_frozen_degraded_after_a_day(tmp_health_file):
    _seed("A", "degraded", 3, age_minutes=25 * 60)
    reg = _registry("A")
    assert [s.name for s in reg.get_sources_by_mode("web")] == ["A"]


def test_registry_orders_healthy_degraded_stale(tmp_health_file):
    _seed("Ok", "healthy", 0, age_minutes=1)
    _seed("Deg", "degraded", 3, age_minutes=1)
    _seed("Old", "degraded", 3, age_minutes=30 * 60)
    reg = _registry("Old", "Deg", "Ok")
    assert [s.name for s in reg.get_sources_by_mode("web")] == ["Ok", "Deg", "Old"]


# ---------------------------------------------------------------------------
# 4. 读取 IO：一次批量读取代 N 次单读
# ---------------------------------------------------------------------------

def test_get_sources_by_mode_reads_file_once(tmp_health_file, monkeypatch):
    """回归：22 个源时旧实现要读 22 次文件（33.5ms/轮），现应只读 1 次。"""
    for i in range(22):
        _seed(f"S{i}", "healthy", 0, age_minutes=1)

    calls = {"n": 0}
    real = health_mod._load_health_data

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(health_mod, "_load_health_data", _counting)
    reg = _registry(*[f"S{i}" for i in range(22)])
    assert len(reg.get_sources_by_mode("web")) == 22
    assert calls["n"] == 1


def test_get_health_map_fills_unknown_names(tmp_health_file):
    """不存在的源名按全新条目补齐，调用方无需判空。"""
    _seed("Known", "healthy", 0, age_minutes=1)
    m = get_health_map(["Known", "Missing"])
    assert m["Known"].status == "healthy"
    assert m["Missing"].source_name == "Missing"
    assert m["Missing"].status == "healthy"


def test_get_health_map_all_entries(tmp_health_file):
    _seed("A", "healthy", 0, age_minutes=1)
    _seed("B", "degraded", 3, age_minutes=1)
    m = get_health_map()
    assert set(m) == {"A", "B"}


def test_update_health_still_writes_single_entry(tmp_health_file):
    """批量读改造不得影响写入语义：只改被点名的源。"""
    _seed("A", "healthy", 0, age_minutes=1)
    _seed("B", "degraded", 3, age_minutes=1)
    update_health("B", 2, 100.0)
    m = get_health_map()
    assert m["B"].status == "healthy"
    assert m["B"].consecutive_failures == 0
    assert m["A"].status == "healthy"


# ---------------------------------------------------------------------------
# 5. 手动解除冷却（面板「立即重试」按钮的后端）
# ---------------------------------------------------------------------------

def test_mark_for_retry_releases_cooldown_without_touching_counts(tmp_health_file):
    """核心：只清时间锚点，统计保持原样——重试仍失败会立刻回到 down。"""
    _seed("A", "down", 6, age_minutes=2)
    assert [s.name for s in _registry("A").get_sources_by_mode("web")] == []

    assert health_mod.mark_for_retry("A") is True

    h = health_mod.get_health("A")
    assert h.last_attempt is None
    assert h.consecutive_failures == 6
    assert h.status == "down"
    assert [s.name for s in _registry("A").get_sources_by_mode("web")] == ["A"]


def test_mark_for_retry_failure_returns_to_down_immediately(tmp_health_file):
    """放行后仍然失败：盖新时间戳，立刻回到 down 并重新冷却（不会假绿灯）。"""
    _seed("A", "down", 6, age_minutes=2)
    health_mod.mark_for_retry("A")
    update_health("A", 0, 0, error="still broken")

    h = health_mod.get_health("A")
    assert h.consecutive_failures == 7
    assert view_status(h) == "down"
    assert [s.name for s in _registry("A").get_sources_by_mode("web")] == []


def test_mark_for_retry_unknown_source_is_noop(tmp_health_file):
    assert health_mod.mark_for_retry("Nope") is False


# ---------------------------------------------------------------------------
# 6. 试探源不得拖住检索返回
# ---------------------------------------------------------------------------

def test_slow_stale_source_does_not_block_search(tmp_health_file, monkeypatch):
    """回归：stale 源只是「碰运气」，挂死时不能在正常源之后继续阻塞。

    旧行为：``as_completed`` 会一直等到它完成（各源 requests timeout 10～30s），
    15 个源 / threads=5 时整次检索从 5s 拖到 20s。
    现在：正常源全部返回后，试探源最多再等 ``_STALE_PROBE_BUDGET`` 秒。
    """
    monkeypatch.setattr("intelnexus.core.search.registry._STALE_PROBE_BUDGET", 0.2)
    _seed("Fast", "healthy", 0, age_minutes=1)
    _seed("Slow", "down", 6, age_minutes=60)  # 冷却已过 → stale

    # 用 Event 而不是 sleep：测试结束前必须放行这个被放弃的线程，
    # 否则它会在 fixture teardown 之后才写健康表（曾因此写进真实 data 目录）。
    release = threading.Event()

    reg = _registry("Fast", "Slow")
    reg._builtin[0].search = lambda q, max_results=20: [
        {"title": "t", "url": "http://fast/1", "description": "d", "source": "Fast"}]
    reg._builtin[1].search = lambda q, max_results=20: (release.wait(5) or [])

    t0 = time.time()
    try:
        out = reg.collect("web", "q", max_results=5, threads=2, global_timeout=30)
        elapsed = time.time() - t0
    finally:
        release.set()
        time.sleep(0.2)  # 等被放弃的试探线程收尾，避免其写盘晚于用例 teardown

    assert elapsed < 1.0, f"试探源不应拖住返回，实际 {elapsed:.2f}s"
    assert any(r["url"] == "http://fast/1" for r in out)


def test_healthy_sources_are_not_delayed_by_stale_budget(tmp_health_file, monkeypatch):
    """反向：没有 stale 源时不得引入额外等待（预算逻辑必须完全旁路）。"""
    monkeypatch.setattr("intelnexus.core.search.registry._STALE_PROBE_BUDGET", 5.0)
    _seed("A", "healthy", 0, age_minutes=1)
    reg = _registry("A")
    reg._builtin[0].search = lambda q, max_results=20: [
        {"title": "t", "url": "http://a/1", "description": "d", "source": "A"}]

    t0 = time.time()
    out = reg.collect("web", "q", max_results=5, threads=1, global_timeout=30)
    assert time.time() - t0 < 1.0
    assert out


# ---------------------------------------------------------------------------
# 7. 批量写盘（一次检索只写一次）
# ---------------------------------------------------------------------------

def test_health_batch_flushes_once_and_rejects_late_records(
        tmp_health_file, monkeypatch):
    """批量缓冲：N 条观测 → 1 次写盘；关闭后 record 返回 False 供调用方兜底。"""
    from intelnexus.core.search.health import HealthBatch

    calls = {"n": 0}
    real_save = health_mod._save_health_data

    def _counting(data):
        calls["n"] += 1
        return real_save(data)

    monkeypatch.setattr(health_mod, "_save_health_data", _counting)

    batch = HealthBatch()
    for i in range(10):
        assert batch.record(f"S{i}", 1, 100.0) is True
    assert batch.pending == 10

    assert batch.flush() == 10
    assert calls["n"] == 1
    assert health_mod.get_health("S9").success_count == 1

    # 已关闭：迟到线程必须被拒绝，调用方据此退回单条写，信号不丢
    assert batch.record("Late", 1, 100.0) is False
    assert batch.flush() == 0
    assert calls["n"] == 1


def test_apply_health_updates_mixes_success_and_failure(tmp_health_file):
    """一次批量写里同时含成功与失败，各自按语义落库。"""
    from intelnexus.core.search.health import apply_health_updates

    assert apply_health_updates([
        ("Ok", 3, 120.0, None, False),
        ("Bad", 0, 0.0, "boom", False),
        ("Empty", 0, 80.0, None, False),
    ]) == 3

    assert health_mod.get_health("Ok").status == "healthy"
    assert health_mod.get_health("Bad").status == "healthy"  # 1 次失败尚未到阈值
    assert health_mod.get_health("Bad").last_error == "boom"
    empty = health_mod.get_health("Empty")
    assert empty.success_count == 0 and empty.fail_count == 0
    assert empty.last_attempt is not None


def test_apply_health_updates_empty_is_noop(tmp_health_file, monkeypatch):
    calls = {"n": 0}
    real_save = health_mod._save_health_data
    monkeypatch.setattr(health_mod, "_save_health_data",
                        lambda d: (calls.__setitem__("n", calls["n"] + 1), real_save(d))[1])
    from intelnexus.core.search.health import apply_health_updates
    assert apply_health_updates([]) == 0
    assert calls["n"] == 0
