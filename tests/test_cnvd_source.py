"""CNVD 搜索源测试：官方域名 + 反爬 JS 校验的优雅降级。

现场证据（2026-09-15 实测）：
- https://www.cvd.org.cn  → DNS 通(23.225.34.75) 但连接被 RST（非官方域名）
- https://www.cnvd.org.cn → HTTP 521 + __jsl_clearance JS 校验脚本（加速乐反爬）
"""
from unittest.mock import MagicMock, patch

from intelnexus.core.search.sources.cnvd_source import CNVDSource


def test_uses_official_cnvd_domain():
    """回归：BASE_URL 曾误写为非官方域名 cvd.org.cn（连接被重置）。"""
    assert CNVDSource.BASE_URL == "https://www.cnvd.org.cn"


def test_search_hits_flaw_list_endpoint_with_query_param():
    """检索走官方漏洞列表接口，关键字经 q 参数传递。"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = (
        "<html><ul class='list'><li>"
        "<a href='/flaw/show/CNVD-2025-0001'>CNVD-2025-0001 测试漏洞</a>"
        "<span class='desc'>远程代码执行</span>"
        "</li></ul></html>"
    )
    mock_resp.raise_for_status = MagicMock()
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    with patch("intelnexus.core.search.sources.cnvd_source.get_session",
               return_value=mock_session):
        out = CNVDSource().search("log4j", max_results=5)

    call = mock_session.get.call_args
    assert "/flaw/list" in call.args[0]
    assert call.kwargs["params"]["q"] == "log4j"
    assert len(out) == 1
    assert "CNVD-2025-0001" in out[0]["title"]


def test_antibot_challenge_sets_last_error_and_returns_empty():
    """站点启用 JS 反爬校验（HTTP 521 + __jsl_clearance）时不得静默返回空。"""
    mock_resp = MagicMock()
    mock_resp.status_code = 521
    mock_resp.text = "<script>document.cookie='__jsl_clearance=abc;path=/'</script>"
    mock_resp.raise_for_status = MagicMock()
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    with patch("intelnexus.core.search.sources.cnvd_source.get_session",
               return_value=mock_session):
        src = CNVDSource()
        out = src.search("log4j")

    assert out == []
    assert src.last_error
    assert len(src.last_error) <= 200
