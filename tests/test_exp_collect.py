"""采集层离线测试：robots 判定、限速、字段解析与归一化（不发起真实网络请求）。"""
from __future__ import annotations

import time
from urllib.robotparser import RobotFileParser

from experiments.collect.compliant_fetcher import CompliantFetcher
from experiments.collect.parsers import _pick_lang_value, get_by_path, normalize


def test_throttle_waits_min_interval(monkeypatch):
    slept = []

    def fake_sleep(x):
        slept.append(x)

    monkeypatch.setattr(time, "sleep", fake_sleep)
    f = CompliantFetcher(min_interval_s=2.0)
    f._last_request_ts = time.perf_counter()   # 刚请求过
    f._throttle("example.com")
    assert slept and 1.5 < slept[0] <= 2.0


def test_throttle_respects_per_host_larger_interval(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda x: slept.append(x))
    f = CompliantFetcher(min_interval_s=2.0, per_host_interval={"nvd.nist.gov": 6.0})
    f._last_request_ts = time.perf_counter()
    f._throttle("nvd.nist.gov")
    assert slept and 5.5 < slept[0] <= 6.0


def test_robots_disallow_is_respected():
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Disallow: /private"])
    f = CompliantFetcher()
    f._robots["https://example.com"] = parser
    allowed, source = f.robots_allows("https://example.com/private/data")
    assert allowed is False
    assert source == "cached"


def test_robots_missing_file_is_treated_as_allowed():
    f = CompliantFetcher()
    f._robots["https://example.com"] = None
    allowed, source = f.robots_allows("https://example.com/anything")
    assert allowed is True
    assert source in ("cached", "no-robots(404)", "fetch-failed") or "error" in source


def test_get_by_path_supports_index():
    data = {"cve": {"descriptions": [{"lang": "en", "value": "v1"}, {"lang": "zh", "value": "v2"}]}}
    assert get_by_path(data, "cve.descriptions.0.value") == "v1"
    assert get_by_path(data, "cve.descriptions.9.value") is None
    assert get_by_path(data, "cve.missing") is None


def test_pick_lang_value_prefers_english():
    items = [{"lang": "zh", "value": "中文"}, {"lang": "en", "value": "English"}]
    assert _pick_lang_value(items) == "English"
    assert _pick_lang_value("plain") == "plain"
    assert _pick_lang_value(None) is None


def test_normalize_rejects_short_summary():
    spec = {"id": "src", "name": "S", "category": "C"}
    entry = {"native_id": "1", "title": "t", "summary": "太短", "published": "2026-01-01", "link": ""}
    assert normalize(spec, entry, "正文" * 100, "inline") is None


def test_normalize_does_not_fallback_to_source_url():
    """无逐条 URL 时不得回退成信源 URL，否则同信源条目会被整体判重。"""
    spec = {"id": "src", "name": "S", "category": "C", "url": "https://example.com/feed"}
    entry = {"native_id": "1", "title": "t", "summary": "参考摘要" * 10, "published": None, "link": ""}
    item = normalize(spec, entry, "正文内容" * 50, "inline")
    assert item is not None
    assert item["url"] == ""


def test_normalize_sets_quality_eligible_flag():
    spec = {"id": "src", "name": "S", "category": "C", "quality_eligible": True}
    entry = {"native_id": "1", "title": "t", "summary": "参考摘要" * 10, "published": None,
             "link": "https://example.com/a"}
    item = normalize(spec, entry, "正文内容" * 50, "detail")
    assert item["quality_eligible"] is True
    assert item["content_from"] == "detail"
    assert len(item["content_sha256"]) == 64
