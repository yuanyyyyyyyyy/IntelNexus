"""网页引擎代理收口测试：国内引擎（Bing/Baidu）强制直连，境外引擎走代理。"""
from unittest.mock import patch, MagicMock

from intelnexus.core.search import web


FAKE_PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}


def _run_fetch_with_session_capture(engine_names):
    """按顺序对各引擎调用 _fetch_engine，返回共享 session 工厂收到的参数序列。

    网络层被 mock：session.get 返回 503，拿到会话后即短路，不产生真实请求。
    代理收口函数被替换：requires_proxy=False → None（直连），True → 假代理。
    """
    proxied_calls = []

    def fake_shared_session(proxies):
        proxied_calls.append(proxies)
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 503
        session.get.return_value = resp
        return session

    def fake_proxies_for(requires_proxy):
        return FAKE_PROXY if requires_proxy else None

    with patch.object(web, "get_http_proxies_for", side_effect=fake_proxies_for), \
         patch.object(web, "_get_shared_session", side_effect=fake_shared_session):
        for name in engine_names:
            web._fetch_engine(name, "openrouter")
    return proxied_calls


def test_domestic_engines_use_direct_connection():
    """即使配置了代理，Bing/Baidu 也必须强制直连（proxies=None）。"""
    calls = _run_fetch_with_session_capture(["Bing", "Baidu"])
    assert calls == [None, None]


def test_overseas_engines_use_proxy():
    """DuckDuckGo 等境外引擎应使用实际代理配置。"""
    calls = _run_fetch_with_session_capture(["DuckDuckGo"])
    assert calls == [FAKE_PROXY]


def test_get_session_requires_proxy_funnel():
    """get_session(requires_proxy) 必须经由 get_http_proxies_for 收口。"""
    with patch.object(web, "get_http_proxies_for", return_value=None) as m, \
         patch.object(web, "_get_shared_session", side_effect=lambda p: p):
        assert web.get_session(False) is None
        m.assert_called_once_with(False)

    with patch.object(web, "get_http_proxies_for", return_value=FAKE_PROXY) as m, \
         patch.object(web, "_get_shared_session", side_effect=lambda p: p):
        assert web.get_session(True) == FAKE_PROXY
        m.assert_called_once_with(True)


def test_get_session_default_is_direct():
    """默认参数（不传）应保持直连语义，兼容旧调用点。"""
    with patch.object(web, "get_http_proxies_for", return_value=None) as m, \
         patch.object(web, "_get_shared_session", side_effect=lambda p: p):
        assert web.get_session() is None
        m.assert_called_once_with(False)


def test_fetch_engine_records_last_web_errors():
    """引擎抓取异常时应把 '引擎名: 异常类型' 追加进 LAST_WEB_ERRORS。"""
    session = MagicMock()
    session.get.side_effect = ConnectionError("proxy unreachable")
    with patch.object(web, "get_http_proxies_for", return_value=None), \
         patch.object(web, "_get_shared_session", return_value=session):
        web.LAST_WEB_ERRORS.clear()
        out = web._fetch_engine("Bing", "openrouter")
    assert out == []
    assert any(msg.startswith("Bing:") for msg in web.LAST_WEB_ERRORS)


def test_get_web_results_clears_last_web_errors():
    """get_web_results 入口必须清空上一轮的引擎失败摘要。"""
    fake_funcs = {name: (lambda q, p: []) for name in web.FAST_ENGINES}
    with patch.object(web, "ENGINE_FUNCS", fake_funcs), \
         patch.object(web, "get_http_proxies_for", return_value=None):
        web.LAST_WEB_ERRORS.append("stale error")
        out = web.get_web_results("openrouter")
    assert isinstance(out, list)
    assert web.LAST_WEB_ERRORS == []


def test_last_web_errors_cleared_when_raw_results_produced():
    """失败口径：有引擎在过滤前产出过原始结果 → 清空错误信号，过滤后空结果不判失败。

    构造：检索期间 Bing 记录失败（锁内 append，晚于入口清空），Baidu 有产出，
    但结果全被黑名单过滤 → 最终返回 []，仍属「正常无结果」而非失败。
    """
    raw = [{"title": "openrouter docs", "url": "https://openrouter.ai/docs",
            "description": "d", "source": "Baidu"}]

    def failing_engine(q, p):
        with web._LAST_WEB_ERRORS_LOCK:
            web.LAST_WEB_ERRORS.append("Bing: ConnectionError")
        return []

    fake_funcs = {"Bing": failing_engine,
                  "Baidu": (lambda q, p: [dict(r) for r in raw])}
    with patch.object(web, "ENGINE_FUNCS", fake_funcs), \
         patch.object(web, "get_http_proxies_for", return_value=None), \
         patch.object(web, "is_blocked_domain", return_value=True):
        out = web.get_web_results("openrouter")
    # 过滤后全被拦截 → 返回空，但过滤前产出非空 → 错误信号不被采信
    assert out == []
    assert web.LAST_WEB_ERRORS == []
