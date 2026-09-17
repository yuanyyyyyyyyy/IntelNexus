"""授权声明入口回归：UI → kwargs → 闸门 → 报告/结果区 的完整透传链。

背景：`assess_authorization(authorization_declared=...)` 参数已存在，
但 UI/CLI 没有任何入口 —— 用户无法声明授权，闸门对针对性侦察请求
只能永远按「未声明授权」降级，授权状态在结果区也不可见。
"""

import inspect

import pytest


class TestGateAcceptsDeclaration:
    def test_declared_flag_authorizes(self):
        from intelnexus.core.search.authorization import assess_authorization
        r = assess_authorization("对某某公司办公网开展渗透测试",
                                 authorization_declared=True)
        assert r["authorized"] is True
        assert r["requires_authorization"] is True

    def test_scope_note_uses_user_scope(self):
        from intelnexus.core.search.authorization import assess_authorization
        r = assess_authorization(
            "对某某公司办公网开展渗透测试",
            authorization_declared=True,
            authorization_scope="内网 10.0.0.0/8，2026-09-16 至 2026-09-20",
        )
        assert "10.0.0.0/8" in r["scope_note"]

    def test_scope_ignored_when_not_declared(self):
        from intelnexus.core.search.authorization import assess_authorization
        r = assess_authorization("对某某公司办公网开展渗透测试",
                                 authorization_scope="随便写的范围")
        assert r["authorized"] is False


class TestSearchWorkerWiring:
    def test_computation_accepts_authorization_params(self):
        from intelnexus.ui.search_worker import run_search_computation
        params = inspect.signature(run_search_computation).parameters
        assert "authorization_declared" in params
        assert "authorization_scope" in params
        assert params["authorization_declared"].default is False
        assert params["authorization_scope"].default == ""

    def test_safe_helper_passes_declaration(self):
        from intelnexus.ui.search_worker import _assess_authorization_safe
        r = _assess_authorization_safe("对某某公司办公网开展渗透测试",
                                       authorization_declared=True,
                                       authorization_scope="内网 10.0.0.0/8")
        assert r["authorized"] is True
        assert "10.0.0.0/8" in r["scope_note"]

    def test_safe_helper_defaults_to_undeclared(self):
        from intelnexus.ui.search_worker import _assess_authorization_safe
        r = _assess_authorization_safe("对某某公司办公网开展渗透测试")
        assert r["authorized"] is False


def _start_task_for_apptest(query):
    """AppTest 入口：设置 session_state 后触发 _start_search_task。"""
    import streamlit as st
    from intelnexus.ui import search_pipeline
    search_pipeline._start_search_task(query, "smart", "m", 4)


class TestPipelineWiring:
    """授权声明必须真实透传到 run_search_computation 的 kwargs。"""

    def _capture_kwargs(self, monkeypatch, declared, scope):
        from streamlit.testing.v1 import AppTest
        from intelnexus.ui import search_pipeline
        captured = {}
        state = {"runs": 0}

        class _FakeRunner:
            def is_running(self, _task_id):
                # 第二次 script run 时返回 True，阻断 st.rerun 造成的外层循环
                state["runs"] += 1
                return state["runs"] > 1

            def start(self, task_id, fn, kwargs=None):
                captured.update(kwargs or {})
                return True

        monkeypatch.setattr(search_pipeline, "get_task_runner", lambda: _FakeRunner())
        # resolve_mode / run_search_computation 均为函数体内 from ... import，
        # 需打补丁到定义模块
        import intelnexus.core.search.modes as _modes
        import intelnexus.ui.search_worker as _worker
        monkeypatch.setattr(_modes, "resolve_mode", lambda q: "smart_general")
        monkeypatch.setattr(_worker, "run_search_computation", lambda **kw: {})

        at = AppTest.from_function(_start_task_for_apptest,
                                   args=("对某某公司办公网开展渗透测试",))
        at.session_state["authorization_declared"] = declared
        at.session_state["authorization_scope"] = scope
        at.run()
        assert not at.exception, getattr(at, "exception", None)
        return captured

    def test_session_state_reaches_computation_kwargs(self, monkeypatch):
        captured = self._capture_kwargs(monkeypatch, True, "内网 10.0.0.0/8")
        assert captured["authorization_declared"] is True
        assert captured["authorization_scope"] == "内网 10.0.0.0/8"

    def test_defaults_when_untouched(self, monkeypatch):
        captured = self._capture_kwargs(monkeypatch, False, "")
        assert captured["authorization_declared"] is False
        assert captured["authorization_scope"] == ""


# AppTest 会把被测函数源码写入临时脚本执行：函数必须是模块级的，
# 且依赖的数据只能通过 args 传入（无法引用测试模块的全局变量/导入）
def _render_stats_for_apptest(data):
    from intelnexus.ui.results_view import ResultsView, render_query_stats_cards
    render_query_stats_cards(ResultsView(data))


class TestResultsViewAuthorizationHint:
    """结果统计卡之后必须呈现授权状态（实时与历史回放共用同一实现）。"""

    def _run(self, data):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_render_stats_for_apptest, args=(data,))
        at.run()
        return at

    def test_unauthorized_shows_warning(self):
        at = self._run({
            "query": "q", "results": [], "source_info": "", "source_stats": {},
            "authorization": {"requires_authorization": True,
                              "authorized": False,
                              "scope_note": "未声明授权：降级为纯 OSINT。"},
        })
        assert any("未声明授权" in w.value for w in at.warning)

    def test_authorized_shows_info(self):
        at = self._run({
            "query": "q", "results": [], "source_info": "", "source_stats": {},
            "authorization": {"requires_authorization": True,
                              "authorized": True,
                              "scope_note": "已声明授权：范围 10.0.0.0/8。"},
        })
        assert any("已声明授权" in i.value for i in at.info)

    def test_no_authorization_data_no_hint(self):
        at = self._run({"query": "q", "results": [], "source_info": "",
                        "source_stats": {}})
        assert not any("授权" in w.value for w in at.warning)
