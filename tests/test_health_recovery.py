"""健康自愈：零结果语义修正 + 凭证保存后的健康重置。

覆盖：
- ``update_health(..., empty_is_healthy=...)``：默认 False 保持既有语义（防
  DarkWeb 「Tor 未连却刷出 100% 成功」的失真回归）；置真时零结果按成功计。
- ``empty_is_healthy`` 默认 False、``SiteScopedSource`` 置真。
- ``reset_health_for`` 批量重置并落盘、不误伤其它源、不凭空造条目。
- registry 端到端：站内源零结果后能自愈回 healthy（此前会被永久钉在 degraded）。
"""
import json

import pytest

from intelnexus.core.search import health as health_mod
from intelnexus.core.search.health import (
    SourceHealth, get_health, save_health, update_health, reset_health_for,
)
from intelnexus.core.search.source import BaseSearchSource
from intelnexus.core.search.registry import SearchSourceRegistry
from intelnexus.core.search.sources.site_scoped_source import SiteScopedSource


class _EmptyBackend:
    """永远返回零结果的后端桩（模拟站内检索未命中）。"""

    name = "Stub"

    def is_configured(self):
        return True

    def search(self, query, domain, max_results=10):
        return []


@pytest.fixture
def health_file(tmp_path, monkeypatch):
    """把健康表重定向到临时目录，避免污染真实 data/source_health.json。"""
    path = tmp_path / "source_health.json"
    monkeypatch.setattr(health_mod, "HEALTH_FILE", str(path), raising=True)
    return path


def _seed(name, failures):
    """造一个已累计 failures 次连续失败的条目并落盘。"""
    h = SourceHealth(source_name=name)
    for _ in range(failures):
        h.record_failure("boom")
    save_health(h)
    return h


def _file_sources(path):
    with open(path, "r", encoding="utf-8") as f:
        return (json.load(f) or {}).get("sources", {})


# ---------------------------------------------------------------------------
# 零结果语义（默认保守 vs 源自述置真）
# ---------------------------------------------------------------------------

def test_zero_result_keeps_failure_streak_by_default(health_file):
    """默认语义不变：零结果既不计成功也不计失败。

    这是 DarkWeb 的既有契约（Tor 未连接时返回空列表，不能被刷成成功），
    改动必须保持默认 False，否则成功率失真回归。
    """
    _seed("Src", 5)

    update_health("Src", 0, 12.0)

    h = get_health("Src")
    assert h.status == "degraded"
    assert h.consecutive_failures == 5


def test_zero_result_clears_streak_when_empty_is_healthy(health_file):
    """empty_is_healthy=True：零结果按成功计，清零连续失败并回到 healthy。"""
    _seed("Src", 5)

    update_health("Src", 0, 12.0, empty_is_healthy=True)

    h = get_health("Src")
    assert h.consecutive_failures == 0
    assert h.status == "healthy"
    assert h.last_error is None


def test_real_error_still_fails_when_empty_is_healthy(health_file):
    """empty_is_healthy 只放宽「无错误且零结果」，不得吞掉真实失败。"""
    update_health("Src", 0, 10.0, error="boom", empty_is_healthy=True)

    h = get_health("Src")
    assert h.consecutive_failures == 1
    assert h.last_error == "boom"


def test_empty_is_healthy_flag_defaults():
    """基类默认保守；只有 SiteScopedSource 明确宣称「零结果＝未命中」。"""
    assert BaseSearchSource.empty_is_healthy is False
    assert SiteScopedSource.empty_is_healthy is True


# ---------------------------------------------------------------------------
# reset_health_for（凭证保存后调用）
# ---------------------------------------------------------------------------

def test_reset_health_for_resets_and_persists(health_file):
    _seed("Xiaohongshu", 5)
    _seed("Other", 5)

    n = reset_health_for(["Xiaohongshu"])

    assert n == 1
    assert get_health("Xiaohongshu").status == "healthy"
    assert get_health("Xiaohongshu").consecutive_failures == 0
    # 全新起点：历史计数一并清零（success_rate 回到 1.0，不再「healthy 却低成功率」）
    xhs = get_health("Xiaohongshu")
    assert xhs.fail_count == 0
    assert xhs.success_count == 0
    assert xhs.avg_latency_ms == 0.0
    assert xhs.last_success is None
    assert xhs.success_rate == 1.0
    # 不误伤未点名的源
    assert get_health("Other").status == "degraded"
    # 必须落盘（跨进程可见），否则重启后又变回 degraded
    assert _file_sources(health_file)["Xiaohongshu"]["status"] == "healthy"


def test_reset_health_for_unknown_name_creates_nothing(health_file):
    """未知源名不凭空造条目（健康面板会渲染所有条目，凭空造即失真）。"""
    _seed("Real", 5)

    assert reset_health_for(["NoSuch"]) == 0
    assert "NoSuch" not in _file_sources(health_file)


def test_reset_health_for_returns_zero_when_persist_fails(health_file, monkeypatch):
    """写盘失败必须返回 0（而不是「重置成功」）。

    否则调用方会照常失效缓存，用户重绘后读回旧值 —— 表现为「明明重置了却仍是
    降级」，且界面上没有任何提示。
    """
    _seed("Src", 5)
    monkeypatch.setattr(health_mod, "_save_health_data", lambda data: False)

    assert reset_health_for(["Src"]) == 0


def test_reset_health_for_empty_list(health_file):
    _seed("Real", 5)

    assert reset_health_for([]) == 0
    assert get_health("Real").status == "degraded"


# ---------------------------------------------------------------------------
# 端到端：registry 透传标志（回归：站内源零结果会被永久钉在 degraded）
# ---------------------------------------------------------------------------

def test_registry_zero_result_recovers_site_scoped_source(health_file):
    """回归：小红书连续未命中时，consecutive_failures 永不下降 → 永久 degraded。

    站内源零结果不是故障，registry 必须透传 empty_is_healthy 让它自愈。
    """
    _seed("Xiaohongshu", 5)
    src = SiteScopedSource(name="Xiaohongshu", domains=("xiaohongshu.com",),
                           allowed_hosts=("xiaohongshu.com",),
                           backend=_EmptyBackend())
    reg = SearchSourceRegistry(news_api_key=None)
    reg._builtin = [src]
    reg._user_sources = []

    out = reg.collect("all", "某个冷门查询", max_results=5, threads=1)

    assert out == []
    assert get_health("Xiaohongshu").status == "healthy"


def test_registry_zero_result_keeps_plain_source_degraded(health_file):
    """对照：普通源（empty_is_healthy 默认 False）零结果不触发自愈。"""
    _seed("Plain", 5)

    class _PlainSrc(BaseSearchSource):
        name = "Plain"
        category = "custom"

        def search(self, query, max_results=20):
            return []

    reg = SearchSourceRegistry(news_api_key=None)
    reg._builtin = [_PlainSrc()]
    reg._user_sources = []

    reg.collect("all", "q", max_results=5, threads=1)

    assert get_health("Plain").status == "degraded"
