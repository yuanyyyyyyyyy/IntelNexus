"""CLI 授权声明入口回归（行为级）。

CLI（main.py）是独立于 Streamlit 管线的旧链路：`search` 子命令不经过
`run_search_computation`，此前 `generate_summary` 调用未传 `authorized`，
导致 CLI 产出的报告永远按已授权处理（攻击面章节照常生成）。

本文件通过 CliRunner + 打桩下游（检索/抓取/摘要生成），断言
`generate_summary` 实际收到的 `authorized` 值，而非源码文本。
"""

import pytest
from click.testing import CliRunner

TARGETED_QUERY = "对某某公司办公网开展渗透测试"
GENERIC_QUERY = "log4shell 漏洞原理与防护"

FAKE_RESULTS = [{"title": "t", "url": "https://example.com/a", "source": "Bing"}]


@pytest.fixture
def stubbed(monkeypatch):
    """打桩 LLM/检索/抓取/摘要生成，捕获 generate_summary 的关键字参数。"""
    import main
    captured = {"generate_summary": None}

    monkeypatch.setattr(main, "get_llm", lambda model: object())
    monkeypatch.setattr(main, "execute_search", lambda mode, q, t: FAKE_RESULTS)
    monkeypatch.setattr(main, "scrape_multiple",
                        lambda items, max_workers=5, resolved_map=None: {})

    def _fake_summary(llm, query, content, **kwargs):
        captured["generate_summary"] = kwargs
        return "# report"

    monkeypatch.setattr(main, "generate_summary", _fake_summary)
    return captured


def _invoke(query, extra=()):
    import main
    return CliRunner().invoke(
        main.intelnexus,
        ["search", "--query", query, "--mode", "web", "--no-credibility", *extra],
    )


class TestCliAuthorized:
    def test_targeted_query_without_flag_is_osint_only(self, stubbed):
        result = _invoke(TARGETED_QUERY)
        assert result.exit_code == 0, result.output
        assert "NOT DECLARED" in result.output
        assert stubbed["generate_summary"]["authorized"] is False

    def test_flag_declares_authorization(self, stubbed):
        result = _invoke(TARGETED_QUERY, ("--authorized",))
        assert result.exit_code == 0, result.output
        assert "DECLARED" in result.output
        assert stubbed["generate_summary"]["authorized"] is True

    def test_declaration_marker_in_query_self_declares(self, stubbed):
        """查询文本中的声明标记视为已声明（help 文案已说明）。"""
        result = _invoke(f"已获书面授权：{TARGETED_QUERY}")
        assert result.exit_code == 0, result.output
        assert stubbed["generate_summary"]["authorized"] is True

    def test_generic_query_has_no_gate_banner(self, stubbed):
        result = _invoke(GENERIC_QUERY)
        assert result.exit_code == 0, result.output
        assert "Authorization:" not in result.output
        assert stubbed["generate_summary"]["authorized"] is True

    def test_scope_used_only_when_declared(self, stubbed):
        result = _invoke(TARGETED_QUERY, ("--authorized", "--scope", "内网 10.0.0.0/8"))
        assert result.exit_code == 0, result.output
        assert "10.0.0.0/8" in result.output

    def test_help_lists_authorized(self):
        import main
        result = CliRunner().invoke(main.intelnexus, ["search", "--help"])
        assert result.exit_code == 0
        assert "--authorized" in result.output
