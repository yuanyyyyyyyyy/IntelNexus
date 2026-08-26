"""main_tabs 导航解析逻辑单测（纯函数 + 普通 dict，无需 Streamlit 会话）。"""

from intelnexus.ui import main_tabs
from intelnexus.ui.main_tabs import (
    REQUEST_FLAG,
    SWITCH_FLAG,
    TAB_BRIEFING,
    TAB_HOME,
    TAB_KB,
    TAB_SEARCH,
    request_tab,
    resolve_active_tab,
)


# ---------- resolve_active_tab ----------

def test_resolve_keeps_current_valid_tab():
    """正常沿用：无旗标时沿用用户当前选择。"""
    for tab in (TAB_HOME, TAB_SEARCH, TAB_BRIEFING, TAB_KB):
        assert resolve_active_tab(tab, {}) == tab


def test_resolve_falls_back_to_home_on_invalid_current():
    """非法值兜底：current 不在合法集合时兜底到首页。"""
    assert resolve_active_tab("nonsense", {}) == TAB_HOME
    assert resolve_active_tab("", {}) == TAB_HOME
    assert resolve_active_tab(None, {}) == TAB_HOME


def test_resolve_consumes_request_flag_once():
    """REQUEST_FLAG 消费即清零：跳转只发生一次。"""
    state = {REQUEST_FLAG: TAB_BRIEFING}
    assert resolve_active_tab(TAB_SEARCH, state) == TAB_BRIEFING
    # 旗标已被清除
    assert REQUEST_FLAG not in state
    # 下一次调用沿用 current，不再强制跳转
    assert resolve_active_tab(TAB_SEARCH, state) == TAB_SEARCH


def test_resolve_ignores_invalid_request_target():
    """非法目标忽略：清除脏旗标并沿用 current（非法则兜底首页）。"""
    state = {REQUEST_FLAG: "bogus_tab"}
    assert resolve_active_tab(TAB_KB, state) == TAB_KB
    assert REQUEST_FLAG not in state  # 脏值同样被清除，防止残留

    state = {REQUEST_FLAG: None}
    assert resolve_active_tab("bad", state) == TAB_HOME


def test_resolve_switch_flag_compat():
    """SWITCH_FLAG 兼容：旧旗标视为请求跳到搜索页，同样消费即清零。"""
    state = {SWITCH_FLAG: True}
    assert resolve_active_tab(TAB_KB, state) == TAB_SEARCH
    assert SWITCH_FLAG not in state
    # 消费后不再强制跳转
    assert resolve_active_tab(TAB_KB, state) == TAB_KB


def test_resolve_switch_flag_falsy_ignored():
    """SWITCH_FLAG 假值不触发跳转。"""
    assert resolve_active_tab(TAB_BRIEFING, {SWITCH_FLAG: False}) == TAB_BRIEFING
    assert resolve_active_tab(TAB_BRIEFING, {SWITCH_FLAG: None}) == TAB_BRIEFING


def test_resolve_request_flag_wins_over_switch_flag():
    """两旗标并存时 REQUEST_FLAG 优先。"""
    state = {REQUEST_FLAG: TAB_HOME, SWITCH_FLAG: True}
    assert resolve_active_tab(TAB_SEARCH, state) == TAB_HOME
    assert REQUEST_FLAG not in state
    # REQUEST 消费后旧旗标仍在（本次已被其覆盖），下一次按旧逻辑跳搜索
    assert resolve_active_tab(TAB_KB, state) == TAB_SEARCH
    assert SWITCH_FLAG not in state


# ---------- request_tab ----------

def test_request_tab_writes_flag():
    state = {}
    request_tab(state, TAB_SEARCH)
    assert state[REQUEST_FLAG] == TAB_SEARCH


def test_request_tab_rejects_invalid_target():
    state = {}
    request_tab(state, "not_a_tab")
    assert REQUEST_FLAG not in state


def test_request_tab_roundtrip_with_resolve():
    """写入→消费闭环：request_tab 后下一次解析跳到目标页且旗标清零。"""
    state = {}
    request_tab(state, TAB_KB)
    assert resolve_active_tab(TAB_HOME, state) == TAB_KB
    assert REQUEST_FLAG not in state
