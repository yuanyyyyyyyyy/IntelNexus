"""
首次使用向导 - 引导新用户完成初始设置
======================================
- 检测是否首次使用
- 提供订阅模式/分析模式选择
- 订阅模式：选择关注领域 → 设置推送时间 → 完成
- 分析模式：直接进入系统
"""
import streamlit as st
from datetime import datetime, time
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon
from intelnexus.core.ui.styles import render_onboarding_css


def _check_onboarding_needed() -> bool:
    """检查是否需要显示向导"""
    # 如果用户已标记完成，不再显示
    if st.session_state.get("onboarding_completed"):
        return False
    # 如果已有订阅者配置，认为已设置过
    try:
        from intelnexus.config.subscriptions import get_all_subscribers
        subscribers = get_all_subscribers()
        if subscribers:
            st.session_state.onboarding_completed = True
            return False
    except Exception:
        pass
    return True


def render_onboarding() -> bool:
    """
    渲染首次使用向导。
    返回 True 表示向导正在显示（调用方应跳过主界面），
    返回 False 表示向导已完成或不需要（调用方应正常渲染主界面）。
    """
    if not _check_onboarding_needed():
        return False

    # 渲染向导CSS
    render_onboarding_css()

    # 获取当前步骤
    step = st.session_state.get("onboarding_step", 1)
    total_steps = 4

    # 渲染向导容器
    st.markdown('<div class="ob-wizard">', unsafe_allow_html=True)

    # 标题
    st.markdown(f'<div class="ob-title">{get_text("ob_welcome")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ob-subtitle">{get_text("ob_subtitle")}</div>', unsafe_allow_html=True)

    # 步骤指示器
    if step > 1:
        step_text = get_text("ob_step").format(current=step - 1, total=total_steps)
        st.markdown(f'<div class="ob-step-indicator">{step_text}</div>', unsafe_allow_html=True)

    # 根据步骤渲染内容
    if step == 1:
        _render_step_choice()
    elif step == 2:
        _render_step_categories()
    elif step == 3:
        _render_step_schedule()
    elif step == 4:
        _render_step_complete()

    st.markdown('</div>', unsafe_allow_html=True)
    return True


def _render_step_choice():
    """Step 1: 选择使用模式"""
    st.markdown(f'<div class="ob-prompt">{get_text("ob_choose_mode")}</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            <div class="ob-choice-card">
                <div class="ob-choice-icon">""" + icon('briefing', 'lg', 'blue') + """</div>
                <div class="ob-choice-title">""" + get_text("ob_subscribe_mode") + """</div>
                <div class="ob-choice-desc">""" + get_text("ob_subscribe_desc") + """</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(get_text("ob_select_this"), key="ob_subscribe_btn", use_container_width=True):
                st.session_state.ob_mode = "subscribe"
                st.session_state.onboarding_step = 2
                st.rerun()

        with c2:
            st.markdown("""
            <div class="ob-choice-card">
                <div class="ob-choice-icon">""" + icon('search', 'lg', 'blue') + """</div>
                <div class="ob-choice-title">""" + get_text("ob_analyze_mode") + """</div>
                <div class="ob-choice-desc">""" + get_text("ob_analyze_desc") + """</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(get_text("ob_select_this"), key="ob_analyze_btn", use_container_width=True):
                _complete_onboarding()

    # 跳过选项
    st.markdown('<div class="ob-skip">', unsafe_allow_html=True)
    if st.button(get_text("ob_skip"), key="ob_skip_btn"):
        _complete_onboarding()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_step_categories():
    """Step 2: 选择关注领域"""
    st.markdown(f'<div class="ob-prompt">{get_text("ob_select_categories")}</div>', unsafe_allow_html=True)

    # 获取预设类别
    try:
        # single source of truth: merged watch categories (incl. user-defined)
        from intelnexus.config.watch_categories import get_all_categories as _gac
        WATCH_CATEGORIES = _gac()
    except ImportError:
        WATCH_CATEGORIES = {}

    # 初始化已选类别
    if "ob_categories" not in st.session_state:
        st.session_state.ob_categories = list(WATCH_CATEGORIES.keys())

    # render checkboxes (names come from category config itself)
    categories = []
    for cat_id, cfg in WATCH_CATEGORIES.items():
        default = cat_id in st.session_state.ob_categories
        if st.checkbox(cfg.get("name", cat_id), value=default, key=f"ob_cat_{cat_id}"):
            categories.append(cat_id)
    st.session_state.ob_categories = categories

    # 导航按钮
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(get_text("ob_prev_step"), key="ob_back_step2"):
            st.session_state.onboarding_step = 1
            st.rerun()
    with col2:
        if st.button(get_text("ob_next_step"), key="ob_next_step2"):
            if categories:
                st.session_state.onboarding_step = 3
                st.rerun()
            else:
                st.warning(get_text("ob_pick_one_category"))


def _render_step_schedule():
    """Step 3: 设置推送时间"""
    st.markdown(f'<div class="ob-prompt">{get_text("ob_set_schedule")}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        freq_map = {
            "daily": get_text("ob_freq_daily"),
            "workday": get_text("ob_freq_workday"),
            "weekly": get_text("ob_freq_weekly"),
        }
        frequency = st.radio(
            get_text("ob_frequency"),
            list(freq_map.keys()),
            format_func=lambda v: freq_map[v],
            key="ob_frequency",
            horizontal=True
        )
    with col2:
        push_time = st.time_input(
            get_text("ob_push_time"),
            value=time(8, 0),
            key="ob_push_time"
        )

    # 导航按钮
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(get_text("ob_prev_step"), key="ob_back_step3"):
            st.session_state.onboarding_step = 2
            st.rerun()
    with col2:
        if st.button(get_text("ob_next_step"), key="ob_next_step3"):
            st.session_state.onboarding_step = 4
            st.rerun()


def _render_step_complete():
    """Step 4: 完成"""
    st.markdown(f'<div class="ob-success-icon">{icon("success", "xl", "sage")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ob-complete-title">{get_text("ob_complete")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ob-complete-desc">{get_text("ob_complete_desc")}</div>', unsafe_allow_html=True)

    if st.button(get_text("ob_enter_system"), key="ob_enter_btn", type="primary", use_container_width=True):
        _save_onboarding_config()
        _complete_onboarding()


def _save_onboarding_config():
    """保存向导配置"""
    mode = st.session_state.get("ob_mode", "subscribe")
    if mode != "subscribe":
        return

    categories = st.session_state.get("ob_categories", [])
    frequency = st.session_state.get("ob_frequency", "daily")
    push_time = st.session_state.get("ob_push_time", time(8, 0))

    # 转换推送时间为字符串
    if isinstance(push_time, time):
        push_time_str = push_time.strftime("%H:%M")
    else:
        push_time_str = "08:00"

    # 计算推送日
    if frequency == "daily":
        push_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    elif frequency == "workday":
        push_days = ["mon", "tue", "wed", "thu", "fri"]
    else:  # 每周
        push_days = ["mon"]  # 默认周一

    # 创建订阅者（schedule.enabled=False，避免被调度器拾取无实际推送能力的用户）
    try:
        from intelnexus.config.subscriptions import add_subscriber
        add_subscriber(
            name="默认用户",
            email="user@localhost",
            channels={},
            schedule={
                "time": push_time_str,
                "timezone": "Asia/Shanghai",
                "enabled": False,
                "days": push_days
            },
            categories=categories
        )
    except Exception as e:
        st.error(get_text("ob_save_failed").format(e=e))


def _complete_onboarding():
    """完成向导"""
    st.session_state.onboarding_completed = True
    st.rerun()
