"""
status_metrics 聚合层单元测试
============================
覆盖三个纯采集函数的正常计数与空数据/异常兜底，
以及 invalidate_status_metrics() 的幂等安全性。

底层读取函数全部经 monkeypatch 替换，不触碰真实 data 目录。
"""

from datetime import datetime, timedelta

import pytest

from intelnexus.ui import status_metrics as sm


# ---------------------------------------------------------------------------
# collect_health_summary
# ---------------------------------------------------------------------------

class _FakeHealth:
    def __init__(self, status):
        self.status = status


def test_health_summary_counts(monkeypatch):
    monkeypatch.setattr(
        "intelnexus.core.search.health.get_all_health",
        lambda: [_FakeHealth("healthy"), _FakeHealth("healthy"),
                 _FakeHealth("degraded"), _FakeHealth("down")],
    )
    assert sm.collect_health_summary() == {
        "healthy": 2, "degraded": 1, "down": 1, "total": 4,
    }


def test_health_summary_empty_default(monkeypatch):
    monkeypatch.setattr("intelnexus.core.search.health.get_all_health", lambda: [])
    assert sm.collect_health_summary() == {
        "healthy": 0, "degraded": 0, "down": 0, "total": 0,
    }


def test_health_summary_exception_returns_default(monkeypatch):
    def _boom():
        raise RuntimeError("corrupted source_health.json")
    monkeypatch.setattr("intelnexus.core.search.health.get_all_health", _boom)
    assert sm.collect_health_summary() == {
        "healthy": 0, "degraded": 0, "down": 0, "total": 0,
    }


# ---------------------------------------------------------------------------
# collect_scheduler_summary
# ---------------------------------------------------------------------------

class _FakeJob:
    def __init__(self, next_run_time):
        self.next_run_time = next_run_time


class _FakeScheduler:
    """模拟 scheduler_registry 中的调度器实例（.scheduler.get_jobs()）。"""

    def __init__(self, jobs=None, raise_on_jobs=False):
        self._jobs = jobs or []
        self._raise = raise_on_jobs

    @property
    def scheduler(self):
        return self

    def get_jobs(self):
        if self._raise:
            raise RuntimeError("jobstore unavailable")
        return self._jobs


def test_scheduler_not_running(monkeypatch):
    monkeypatch.setattr(
        "intelnexus.briefing.scheduler_registry.get_scheduler", lambda: None)
    assert sm.collect_scheduler_summary() == {
        "running": False, "job_count": 0, "next_run_str": None,
    }


def test_scheduler_running_no_jobs(monkeypatch):
    monkeypatch.setattr(
        "intelnexus.briefing.scheduler_registry.get_scheduler",
        lambda: _FakeScheduler(jobs=[]),
    )
    assert sm.collect_scheduler_summary() == {
        "running": True, "job_count": 0, "next_run_str": None,
    }


def test_scheduler_job_counts_and_next_run(monkeypatch):
    now = datetime.now()
    later = now + timedelta(hours=2)
    monkeypatch.setattr(
        "intelnexus.briefing.scheduler_registry.get_scheduler",
        lambda: _FakeScheduler(jobs=[
            _FakeJob(later),
            _FakeJob(now + timedelta(minutes=5)),
            _FakeJob(None),  # 无下次运行时间的任务应被过滤
        ]),
    )
    s = sm.collect_scheduler_summary()
    assert s["running"] is True
    assert s["job_count"] == 2
    assert s["next_run_str"] == (now + timedelta(minutes=5)).strftime("%m-%d %H:%M")


def test_scheduler_exception_returns_default(monkeypatch):
    monkeypatch.setattr(
        "intelnexus.briefing.scheduler_registry.get_scheduler",
        lambda: _FakeScheduler(raise_on_jobs=True),
    )
    assert sm.collect_scheduler_summary() == {
        "running": False, "job_count": 0, "next_run_str": None,
    }


# ---------------------------------------------------------------------------
# collect_today_stats
# ---------------------------------------------------------------------------

class _FakeBriefingHistory:
    def __init__(self, briefings):
        self._briefings = briefings

    def get_briefings(self, limit=20):
        return self._briefings[:limit]


class _FakeHistoryManager:
    def __init__(self, entries):
        self._entries = entries

    def get_history(self, limit=20):
        return self._entries[:limit]


def _patch_today_sources(monkeypatch, briefings=None, push_entries=None,
                         searches=None):
    """统一替换三个底层读取函数。

    push_entries 为推送日志原始条目（自然日口径，取代旧的
    get_push_stats(days=1) 滚动 24 小时窗口）。
    """
    monkeypatch.setattr(
        "intelnexus.config.briefing_history.get_briefing_history",
        lambda: _FakeBriefingHistory(briefings or []),
    )
    monkeypatch.setattr(
        "intelnexus.config.push_log.get_push_entries",
        lambda limit=500: (push_entries or [])[-limit:],
    )
    monkeypatch.setattr(
        "intelnexus.config.history.get_history_manager",
        lambda: _FakeHistoryManager(searches or []),
    )


def test_today_stats_counts(monkeypatch):
    now_iso = datetime.now().isoformat()
    yesterday_iso = (datetime.now() - timedelta(days=1)).isoformat()
    _patch_today_sources(
        monkeypatch,
        briefings=[
            {"filename": "briefing_b.md", "created_at": now_iso,
             "organization": "安全部", "categories": ["cyber_vuln"]},
            {"filename": "briefing_a.md", "created_at": now_iso,
             "organization": "", "categories": []},
            {"filename": "briefing_old.md", "created_at": yesterday_iso,
             "organization": "", "categories": []},
        ],
        push_entries=[
            # 3 条今日至少一渠道成功 + 1 条今日全失败 + 1 条昨日成功（不计入）
            {"timestamp": now_iso, "channels": {"email": True}},
            {"timestamp": now_iso, "channels": {"email": False, "wecom": True}},
            {"timestamp": now_iso, "channels": {"email": True, "wecom": True}},
            {"timestamp": now_iso, "channels": {"email": False}},
            {"timestamp": yesterday_iso, "channels": {"email": True}},
        ],
        searches=[
            {"timestamp": now_iso, "query": "log4j"},
            {"timestamp": now_iso, "query": "apt"},
            {"timestamp": yesterday_iso, "query": "old"},
        ],
    )
    s = sm.collect_today_stats()
    assert s["briefings_today"] == 2
    assert s["pushes_today"] == 3  # 自然日口径：今日至少一渠道成功
    assert s["searches_today"] == 2
    # last_briefing 取最新一条（索引首条）
    lb = s["last_briefing"]
    assert lb is not None
    assert lb["filename"] == "briefing_b.md"
    assert lb["title"] == "安全部"  # organization 非空时作为显示标题
    assert lb["created_at"] == now_iso


def test_today_stats_title_falls_back_to_filename(monkeypatch):
    now_iso = datetime.now().isoformat()
    _patch_today_sources(
        monkeypatch,
        briefings=[{"filename": "briefing_x.md", "created_at": now_iso,
                    "organization": "", "categories": []}],
    )
    lb = sm.collect_today_stats()["last_briefing"]
    assert lb["title"] == "briefing_x.md"


def test_today_stats_empty_default(monkeypatch):
    _patch_today_sources(monkeypatch)
    assert sm.collect_today_stats() == {
        "briefings_today": 0, "pushes_today": 0,
        "searches_today": 0, "last_briefing": None,
    }


def test_today_stats_partial_failure_isolated(monkeypatch):
    """简报来源抛错时，推送/搜索字段仍正常采集。"""
    now_iso = datetime.now().isoformat()

    def _broken_history():
        raise RuntimeError("briefing_history.json corrupted")

    monkeypatch.setattr(
        "intelnexus.config.briefing_history.get_briefing_history",
        _broken_history,
    )
    monkeypatch.setattr(
        "intelnexus.config.push_log.get_push_entries",
        lambda limit=500: [{"timestamp": now_iso, "channels": {"email": True}}],
    )
    monkeypatch.setattr(
        "intelnexus.config.history.get_history_manager",
        lambda: _FakeHistoryManager([{"timestamp": now_iso}]),
    )
    s = sm.collect_today_stats()
    assert s["briefings_today"] == 0
    assert s["last_briefing"] is None
    assert s["pushes_today"] == 1
    assert s["searches_today"] == 1


def test_today_stats_all_sources_broken_default(monkeypatch):
    def _broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "intelnexus.config.briefing_history.get_briefing_history", _broken)
    monkeypatch.setattr("intelnexus.config.push_log.get_push_entries", _broken)
    monkeypatch.setattr(
        "intelnexus.config.history.get_history_manager", _broken)
    assert sm.collect_today_stats() == {
        "briefings_today": 0, "pushes_today": 0,
        "searches_today": 0, "last_briefing": None,
    }


# ---------------------------------------------------------------------------
# invalidate_status_metrics
# ---------------------------------------------------------------------------

def test_invalidate_does_not_raise():
    """连续调用两次亦不得抛错（幂等安全）。"""
    sm.invalidate_status_metrics()
    sm.invalidate_status_metrics()


def test_cached_wrappers_callable_and_match_pure_functions(monkeypatch):
    """缓存包装与纯函数返回同一口径；调用后缓存可被失效。"""
    monkeypatch.setattr(
        "intelnexus.core.search.health.get_all_health",
        lambda: [_FakeHealth("healthy")],
    )
    assert sm.get_health_summary_cached()["total"] == 1
    sm.invalidate_status_metrics()
    assert sm.get_health_summary_cached() == {
        "healthy": 1, "degraded": 0, "down": 0, "total": 1,
    }
