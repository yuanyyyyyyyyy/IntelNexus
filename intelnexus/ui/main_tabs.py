"""主导航 Tab 层（radio-tab 方案）
====================================

背景：Streamlit 的 st.tabs 没有编程切换 API。简报条目「深入调查」按钮写入的
pending_forensic_* 任务由搜索 Tab 块内的代码消费——但 st.tabs 会把所有 Tab
内容都渲染，管线在用户看不见的后台 Tab 里跑完，用户视角是「点了没反应」。
session_state.switch_to_search 旗标自诞生起就没有任何读者（审计 P0#1）。

方案：用横向 radio 代替 st.tabs 作主导航。radio 的选中项可由 session_state
驱动（配合 index= 参数），从而实现真正的「跳转到搜索 Tab」。互斥渲染还顺带
消除了三 Tab 全量渲染的开销（简报中心 + 知识库不再同时注入各自的 workbench CSS）。

注意：本文件刻意不 import streamlit，保持纯函数以便无 st 会话环境下单测。
"""

# radio 选项值（内部键，显示标签由 ui.py 按 i18n 映射）
TAB_SEARCH = "search"
TAB_BRIEFING = "briefing"
TAB_KB = "kb"

_VALID_TABS = (TAB_SEARCH, TAB_BRIEFING, TAB_KB)

SWITCH_FLAG = "switch_to_search"


def resolve_active_tab(current: str, session_state) -> str:
    """计算本次 rerun 应激活的 Tab。

    规则：
    - ``session_state[SWITCH_FLAG]`` 为真值 → 返回 TAB_SEARCH 并就地清除标志
      （一次性语义：跳转只发生一次，之后用户可自由切走）；
    - 否则沿用 current（用户上次的选择）；
    - current 非法时兜底到 TAB_SEARCH。

    Args:
        current: 上一次选中的 tab 键。
        session_state: 任意支持 ``in`` / ``__getitem__`` / ``__setitem__`` /
            ``pop`` 的会话状态对象（st.session_state 或 dict 均可）。

    Returns:
        本次应渲染的 tab 键（search/briefing/kb 之一）。
    """
    has_flag = False
    try:
        has_flag = SWITCH_FLAG in session_state and bool(session_state[SWITCH_FLAG])
    except Exception:
        has_flag = False

    if has_flag:
        # pop 语义：消费即清零，防止后续每次 rerun 都强制跳回搜索
        try:
            session_state.pop(SWITCH_FLAG, None)
        except Exception:
            try:
                session_state[SWITCH_FLAG] = False
            except Exception:
                pass
        return TAB_SEARCH

    return current if current in _VALID_TABS else TAB_SEARCH
