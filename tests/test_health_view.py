"""源健康视图数据层与两处面板渲染的回归测试。

覆盖审计发现的六类问题，逐条钉住：

1. 口径不一致 —— ``summary["total"]`` 必须恒等于明细行数，且各状态计数之和
   不超过 total（未知状态不落桶但计入 total）。
2. 排序不一致 —— 统一 ``down → degraded → healthy``，同级按名称字典序。
3. 僵尸条目 —— 白名单外的条目不进明细、不计数；注册表不可用（None）时
   跳过过滤而不是把整个面板清空。
4. 重置后假绿灯 —— 无样本时成功率必须是 "—"，不能是 100%。
5. 状态与后果不可解释 —— 规则文案在两种语言下都存在。
6. 渲染崩溃 —— 两处面板都能在无异常情况下渲染出来。
"""

from datetime import datetime, timedelta

import pytest

from intelnexus.core.search.health import SourceHealth
from intelnexus.ui import health_view as hv


# ---------------------------------------------------------------------------
# 构造样本
# ---------------------------------------------------------------------------

def _entry(name, status="healthy", *, success=0, fail=0, streak=0,
           latency=0.0, last_success=None, last_error=None,
           last_attempt="__now__"):
    """构造健康条目。

    ``last_attempt`` 默认给「刚刚」：``health.view_status`` 会把超过 24 小时
    无观测的失败判定转为 stale，不显式给时间戳的话，degraded/down 样本
    全都会被判为 stale，用例意图随之失效。传 ``None`` 可显式测「无时间戳」。
    """
    h = SourceHealth(source_name=name)
    h.status = status
    h.success_count = success
    h.fail_count = fail
    h.consecutive_failures = streak
    h.avg_latency_ms = latency
    h.last_success = last_success
    h.last_error = last_error
    h.last_attempt = (datetime.now().isoformat()
                      if last_attempt == "__now__" else last_attempt)
    return h


# ---------------------------------------------------------------------------
# 1. 口径一致性
# ---------------------------------------------------------------------------

def test_summary_total_equals_row_count():
    entries = [
        _entry("A", "healthy"),
        _entry("B", "degraded"),
        _entry("C", "down"),
        _entry("D", "healthy"),
    ]
    snap = hv.build_snapshot(entries, ["A", "B", "C", "D"])
    assert snap.summary["total"] == len(snap.entries) == 4
    assert snap.summary["healthy"] == 2
    assert snap.summary["degraded"] == 1
    assert snap.summary["down"] == 1
    assert sum(snap.summary[k] for k in ("healthy", "degraded", "down")) == 4


def test_unknown_status_falls_back_to_degraded():
    """状态字段损坏时按「降级」处理：不静默绿灯，也不宣称已被检索剔除。

    旧实现把未知状态渲染成红色 error 点，却仍按 healthy 计数——排序、计数、
    文案三处口径不一致。
    """
    snap = hv.build_snapshot([_entry("X", "weird")], ["X"])
    assert snap.summary["total"] == 1
    assert snap.summary["degraded"] == 1
    assert snap.summary["healthy"] == 0
    assert hv.status_of(snap.entries[0]) == "degraded"


def test_summary_is_derived_from_filtered_entries():
    """汇总必须只统计白名单内的条目（旧实现走未过滤的缓存，会虚高）。"""
    entries = [_entry("Real", "healthy"), _entry("Zombie", "down")]
    snap = hv.build_snapshot(entries, ["Real"])
    assert snap.summary == {"healthy": 1, "degraded": 0, "down": 0,
                            "stale": 0, "total": 1}
    assert snap.dropped == 1


def test_stale_counts_separately_and_sorts_after_degraded():
    """信号过期（24h 无观测）单独成桶，排序位于 degraded 之后、healthy 之前。"""
    old = (datetime.now() - timedelta(days=3)).isoformat()
    entries = [
        _entry("Fresh", "degraded"),
        _entry("Old", "down", streak=6, last_attempt=old),
        _entry("Ok", "healthy"),
    ]
    snap = hv.build_snapshot(entries, None)
    assert snap.summary["degraded"] == 1
    assert snap.summary["stale"] == 1
    assert snap.summary["down"] == 0
    assert [e.source_name for e in snap.entries] == ["Fresh", "Old", "Ok"]
    assert hv.status_of(entries[1]) == "stale"
    assert hv.dot_class(entries[1]) == "muted"


# ---------------------------------------------------------------------------
# 2. 排序
# ---------------------------------------------------------------------------

def test_sort_is_severity_then_name():
    entries = [
        _entry("zeta", "healthy"),
        _entry("alpha", "down"),
        _entry("Beta", "degraded"),
        _entry("Alpha", "degraded"),
    ]
    names = [e.source_name for e in hv.build_snapshot(entries, None).entries]
    # down 最前；degraded 内部按小写名称序（alpha 在 beta 前）；healthy 最后
    assert names == ["alpha", "Alpha", "Beta", "zeta"]


def test_problems_and_healthy_partition():
    entries = [_entry("A", "healthy"), _entry("B", "degraded"), _entry("C", "down")]
    snap = hv.build_snapshot(entries, None)
    assert [e.source_name for e in snap.problems] == ["C", "B"]
    assert [e.source_name for e in snap.healthy] == ["A"]
    assert snap.all_ok is False


def test_all_ok_requires_entries():
    """空表不能算「全部正常」——那会让侧边栏标题显示误导性的绿灯。"""
    assert hv.build_snapshot([], None).all_ok is False
    assert hv.build_snapshot([_entry("A")], None).all_ok is True


# ---------------------------------------------------------------------------
# 3. 白名单过滤
# ---------------------------------------------------------------------------

def test_active_names_none_skips_filtering():
    """注册表不可用时不做过滤：宁可多显示几行，也不要把面板静默成空。"""
    entries = [_entry("A"), _entry("B")]
    snap = hv.build_snapshot(entries, None)
    assert len(snap.entries) == 2
    assert snap.dropped == 0


def test_dropped_counts_filtered_out():
    entries = [_entry("A"), _entry("Z1"), _entry("Z2")]
    snap = hv.build_snapshot(entries, ["A"])
    assert snap.dropped == 2
    assert [e.source_name for e in snap.entries] == ["A"]


# ---------------------------------------------------------------------------
# 4. 假绿灯回归
# ---------------------------------------------------------------------------

def test_rate_is_dash_without_samples():
    """刚重置（零样本）不得显示 100%——这是审计发现的假绿灯来源。"""
    h = _entry("A")
    assert hv.sample_count(h) == 0
    assert hv.format_rate(h) == "—"


def test_rate_after_reset_is_dash_not_full_marks():
    h = _entry("A", "degraded", success=1, fail=2, streak=3)
    assert hv.format_rate(h) == "33%"
    h.reset()  # 清零全部计数，status 回到 healthy
    assert hv.format_rate(h) == "—"


def test_rate_normal_cases():
    assert hv.format_rate(_entry("A", success=3, fail=1)) == "75%"
    assert hv.format_rate(_entry("A", success=0, fail=2)) == "0%"


# ---------------------------------------------------------------------------
# 5. 格式化
# ---------------------------------------------------------------------------

def test_latency_formatting():
    assert hv.format_latency(_entry("A", latency=0)) == "—"
    assert hv.format_latency(_entry("A", latency=820)) == "820ms"
    assert hv.format_latency(_entry("A", latency=1234)) == "1.2s"


def test_streak_formatting():
    assert hv.format_streak(_entry("A", streak=0)) == "—"
    assert hv.format_streak(_entry("A", streak=4)) == "4"


def test_ago_parts_units():
    now = datetime(2026, 10, 17, 22, 0, 0)
    assert hv.ago_parts((now - timedelta(seconds=10)).isoformat(), now) == ("now", 0)
    assert hv.ago_parts((now - timedelta(minutes=3)).isoformat(), now) == ("m", 3)
    assert hv.ago_parts((now - timedelta(hours=5)).isoformat(), now) == ("h", 5)
    assert hv.ago_parts((now - timedelta(days=2)).isoformat(), now) == ("d", 2)


def test_ago_parts_invalid_inputs():
    assert hv.ago_parts(None) is None
    assert hv.ago_parts("") is None
    assert hv.ago_parts("not-a-timestamp") is None


def test_ago_parts_future_is_now_not_negative():
    """时钟回拨导致的未来时间按「刚刚」处理，不出现「-3 分钟前」。"""
    now = datetime(2026, 10, 17, 22, 0, 0)
    future = (now + timedelta(minutes=5)).isoformat()
    assert hv.ago_parts(future, now) == ("now", 0)


def test_last_error_text_truncates():
    h = _entry("A", last_error="x" * 300)
    out = hv.last_error_text(h, limit=10)
    assert out == "x" * 10 + "…"
    assert hv.last_error_text(_entry("A")) == ""


# ---------------------------------------------------------------------------
# 6. 文案（两种语言都得有，否则英文界面会直接露出 key）
# ---------------------------------------------------------------------------

_HEALTH_KEYS = [
    "health_state_rule", "health_down_effect",
    "health_reload", "health_reload_hint", "health_probe_hint",
    "health_clear_flag", "health_clear_flag_help",
    "health_retry_now", "health_retry_now_help",
    "health_title_with_problems", "health_title_all_ok",
    "health_only_problems", "health_show_healthy", "health_all_ok",
    "health_full_panel_hint", "health_metrics_line", "health_last_error",
    "health_col_source", "health_col_state", "health_col_rate",
    "health_col_latency", "health_col_streak", "health_col_last_ok",
    "health_col_action",
    "health_ago_now", "health_ago_minutes", "health_ago_hours", "health_ago_days",
    "health_empty", "health_summary_line",
    "health_card_stale", "health_stale_hint", "sb_health_stale",
    "source_healthy", "source_degraded", "source_down", "source_stale",
]


@pytest.mark.parametrize("key", _HEALTH_KEYS)
def test_health_copy_present_in_both_languages(key):
    from intelnexus.ui.i18n import _BRIEFING_EN, _BRIEFING_ZH
    assert key in _BRIEFING_ZH, f"中文缺词条: {key}"
    assert key in _BRIEFING_EN, f"英文缺词条: {key}"


def test_removed_misleading_keys_are_gone():
    """旧文案「刷新」暗示会重新检测，实际只重读本地文件——已移除。"""
    from intelnexus.ui.i18n import _BRIEFING_EN, _BRIEFING_ZH
    for key in ("health_refresh", "health_refresh_hint",
                "health_reset_hint", "source_reset"):
        assert key not in _BRIEFING_ZH
        assert key not in _BRIEFING_EN


# ---------------------------------------------------------------------------
# 7. 渲染冒烟（两处面板都不得抛异常）
# ---------------------------------------------------------------------------

def _render_compact_script():
    import streamlit as st
    from intelnexus.core.search.health import SourceHealth
    from intelnexus.ui.health_dashboard import compact_title, render_health_compact
    from intelnexus.ui.health_view import build_snapshot

    ok = SourceHealth(source_name="Bing")
    ok.record_success(320)
    bad = SourceHealth(source_name="DarkWeb")
    for _ in range(3):
        bad.record_failure("Tor SOCKS 不可达 (127.0.0.1:2080)")
    snap = build_snapshot([ok, bad], ["Bing", "DarkWeb"])
    st.write(compact_title(snap))
    render_health_compact(snap)


def _render_overview_script():
    from intelnexus.core.search.health import SourceHealth
    from intelnexus.ui import health_dashboard
    from intelnexus.ui.health_view import build_snapshot

    ok = SourceHealth(source_name="Bing")
    ok.record_success(1200)
    bad = SourceHealth(source_name="DarkWeb")
    for _ in range(6):
        bad.record_failure("Tor 未连接")
    snap = build_snapshot([ok, bad], ["Bing", "DarkWeb"])
    # 绕过真实健康表读取，直接渲染表头与行（render_health_overview 内部会读盘）
    health_dashboard._render_table_header()
    for entry in snap.entries:
        health_dashboard._render_table_row(entry)


def test_compact_panel_renders_without_exception():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_function(_render_compact_script, default_timeout=60)
    at.run()
    assert not at.exception, at.exception


def test_overview_table_renders_without_exception():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_function(_render_overview_script, default_timeout=60)
    at.run()
    assert not at.exception, at.exception


# ---------------------------------------------------------------------------
# 8. 首页点阵：源名 vs 类名（旧实现的静默空列表）
# ---------------------------------------------------------------------------

class _FakeSource:
    """源名与类名不同——真实情况就是如此（Web / WebSearchSource）。"""

    name = "Web"


class _FakeRegistry:
    def all_sources(self):
        return [_FakeSource()]


def _render_home_dots_script():
    from intelnexus.ui.overview import _render_source_status_bar
    _render_source_status_bar()


def test_home_dot_bar_filters_by_source_name_not_class_name(monkeypatch):
    """回归：旧实现用 ``s.__class__.__name__`` 做白名单，与 ``s.name`` 永不相交，
    过滤后恒为空 → 首页点阵从未显示，且异常被 ``except: pass`` 吞掉。
    """
    from streamlit.testing.v1 import AppTest
    from intelnexus.ui import _caches

    h = _entry("Web", "degraded", success=1, fail=2, streak=3)
    monkeypatch.setattr(_caches, "cached_all_health", lambda: [h])
    monkeypatch.setattr(_caches, "cached_registry",
                        lambda news_api_key=None: _FakeRegistry())

    at = AppTest.from_function(_render_home_dots_script, default_timeout=60)
    at.run()

    assert not at.exception, at.exception
    rendered = "".join(m.value for m in at.markdown)
    assert "ov-status-bar" in rendered
    assert "Web" in rendered


def test_home_dot_bar_empty_when_no_health(monkeypatch):
    """健康表为空时不渲染空壳容器（避免首页多出一条空白）。"""
    from streamlit.testing.v1 import AppTest
    from intelnexus.ui import _caches

    monkeypatch.setattr(_caches, "cached_all_health", lambda: [])
    monkeypatch.setattr(_caches, "cached_registry",
                        lambda news_api_key=None: _FakeRegistry())

    at = AppTest.from_function(_render_home_dots_script, default_timeout=60)
    at.run()

    assert not at.exception, at.exception
    assert "ov-status-bar" not in "".join(m.value for m in at.markdown)
