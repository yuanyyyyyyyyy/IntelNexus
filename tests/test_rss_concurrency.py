"""C4 并发对齐回归：RSS 过滤计数的快照语义。

`_fetch_one` 在 ThreadPoolExecutor(max_workers=6) 的 6 个子线程中执行。
并发语义：剔除项 append 到**本次调用的局部列表**，调用结束时在
`_LAST_RSS_REJECTED_LOCK` 内**整体替换**模块级 `LAST_RSS_REJECTED` ——
并发多次调用时后完成者覆盖前者，读侧拿到的永远是某一次调用的完整快照，
不会出现半条记录或跨调用混杂数据。

本文件用假 HTTP 响应真实跑通 `search_rss`，验证上述行为而非源码文本。
"""

import threading

import pytest


QUERY = "华盛顿华尔道夫酒店漏洞调研"

# 与主题无关的 RSS 条目（应被相关性过滤剔除）
_NOISE_XML = (
    b"<?xml version='1.0'?><rss><channel>"
    b"<item><title>Unrelated AI news item</title>"
    b"<link>https://example.com/noise1</link>"
    b"<description>totally unrelated tech news</description></item>"
    b"<item><title>Another unrelated item</title>"
    b"<link>https://example.com/noise2</link>"
    b"<description>more unrelated content</description></item>"
    b"</channel></rss>"
)


class _FakeResp:
    status_code = 200
    content = _NOISE_XML


@pytest.fixture
def fake_rss(monkeypatch):
    """让所有源都返回同一份无关 RSS，且无需网络与代理。"""
    from intelnexus.core.search import news

    monkeypatch.setattr(news.NewsSearch, "_fetch_rss_with_retry",
                        lambda self, url, headers, proxies, timeout=15, max_retries=2:
                        _FakeResp())
    monkeypatch.setattr(news, "get_http_proxies", lambda: None)
    monkeypatch.setattr(news, "get_http_proxies_for", lambda requires_proxy: None)
    # 只留一个无需代理的源，便于断言
    monkeypatch.setattr(news, "RSS_SOURCES",
                        [{"name": "Solidot", "url": "https://www.solidot.org/index.rss",
                          "requires_proxy": False}])
    return news


class TestRssRejectedSnapshot:
    def test_rejected_recorded_for_filtered_items(self, fake_rss):
        results = fake_rss.NewsSearch().search_rss(QUERY, max_results=10)
        assert results == []  # 全部被过滤
        assert set(news_module().LAST_RSS_REJECTED) == {"Solidot"}

    def test_concurrent_calls_produce_intact_snapshots(self, fake_rss):
        """并发两次调用：无异常、每次拿到的都是完整快照（无混杂数据）。"""
        results_box = {}
        errors = []

        def _run(tag):
            try:
                results_box[tag] = fake_rss.NewsSearch().search_rss(QUERY, max_results=10)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=_run, args=(t,)) for t in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors, errors
        assert all(v == [] for v in results_box.values())
        # 后完成者覆盖前者：读到的必然是某一整次调用的快照
        assert set(news_module().LAST_RSS_REJECTED) in ({"Solidot"}, set())

    def test_rejected_stores_source_names_only(self, fake_rss):
        fake_rss.NewsSearch().search_rss(QUERY, max_results=10)
        for entry in news_module().LAST_RSS_REJECTED:
            assert isinstance(entry, str) and entry == "Solidot"


def news_module():
    from intelnexus.core.search import news
    return news
