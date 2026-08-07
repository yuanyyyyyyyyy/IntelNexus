"""BaseSearchSource 抽象契约与 normalize_result 测试。"""
from unittest.mock import patch

import pytest

from intelnexus.core.search.source import (
    BaseSearchSource, CATEGORY_WEB, CATEGORY_NEWS, CATEGORY_DARKWEB, CATEGORY_CUSTOM,
)


def test_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        BaseSearchSource()


def test_concrete_subclass_must_implement_search():
    class Bad(BaseSearchSource):
        pass

    with pytest.raises(TypeError):
        Bad()


def test_normalize_maps_url_to_link():
    class Dummy(BaseSearchSource):
        category = CATEGORY_WEB

        def search(self, query, max_results=20):
            return []

    src = Dummy(name="X")
    out = src.normalize_result({"title": "T", "url": "http://e.com", "description": "d"})
    assert out["link"] == "http://e.com"
    assert out["title"] == "T"
    assert out["description"] == "d"
    assert out["source"] == "X"
    assert out["category"] == CATEGORY_WEB


def test_normalize_fills_defaults():
    class Dummy(BaseSearchSource):
        category = CATEGORY_NEWS

        def search(self, query, max_results=20):
            return []

    src = Dummy(name="N")
    out = src.normalize_result({"title": "T", "link": "http://e.com"})
    assert out["source"] == "N"
    assert out["category"] == CATEGORY_NEWS
    assert out["description"] == ""


def test_normalize_results_drops_missing_link():
    class Dummy(BaseSearchSource):
        category = CATEGORY_CUSTOM

        def search(self, query, max_results=20):
            return []

    src = Dummy(name="C")
    out = src.normalize_results([
        {"title": "ok", "link": "http://a.com"},
        {"title": "no-link"},
        {},
    ])
    assert len(out) == 1
    assert out[0]["link"] == "http://a.com"


def test_get_proxies_uses_proxy_gating():
    class Dummy(BaseSearchSource):
        category = CATEGORY_WEB

        def search(self, query, max_results=20):
            return []

    # requires_proxy=False -> 永远直连（None），不读环境、不触达 get_http_proxies
    direct = Dummy(name="d", requires_proxy=False)
    with patch("shared.search.get_http_proxies", return_value={"http": "p"}) as mg:
        assert direct.get_proxies() is None
        mg.assert_not_called()

    # requires_proxy=True -> 转发 get_http_proxies 返回值（代理收口）
    proxied = Dummy(name="p", requires_proxy=True)
    with patch("shared.search.get_http_proxies", return_value={"http": "socks"}):
        assert proxied.get_proxies() == {"http": "socks"}
