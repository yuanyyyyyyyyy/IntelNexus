"""源健康面板（侧边栏紧凑版 + 简报中心完整版）
==============================================
同一份数据、同一套推导、同一套文案，两个入口只是密度不同：

- ``render_health_compact()`` —— 侧边栏「数据源状态」expander。
  默认只列**降级/不可用**的源（正常源收进「显示全部」），因为侧边栏宽度
  只有约 336px，逐行铺全量必然挤压换行。
- ``render_health_overview()`` —— 简报中心设置区第 5 个面板，全量明细 + 列头。

审计结论（为什么不再是旧样子）
------------------------------
1. **口径**：旧实现卡片走 ``get_health_summary_cached()``（15s 缓存、不按注册表
   过滤），明细走 ``get_all_health()``（实时、过滤白名单），二者可能对不上。
   现在一律由 ``health_view.build_snapshot`` 从过滤后的同一批条目推导，
   卡片数恒等于明细行数。
2. **排序**：旧侧边栏按 JSON 插入序，异常源会埋在中间。现在统一
   ``down → degraded → healthy`` + 名称序。
3. **「刷新」名不副实**：旧按钮叫「刷新」，实际只重读本地 JSON 不联网，用户
   以为会重新检测。改名为「重新读取」，并在同一处写明真正的连通性检测入口。
4. **「重置」造成假绿灯**：``reset()`` 清零全部计数后成功率回到 100%，界面变成
   满屏绿色。现在按钮叫「清除标记」，无样本时成功率显示 "—"，并明确提示
   「不清除失败根因，下次失败仍会降级」。
5. **不可用的后果未披露**：``registry.get_sources_by_mode()`` 会**直接跳过**
   down 源，用户只看到「异常」二字，不知道这个源已经不再参与检索。
   现在面板顶部常驻一行规则说明。
6. **失败原因看不到**：侧边栏旧版只有红点，``last_error`` 只在简报中心可见且
   无上下文。现在两处都显示最近错误 + 连续失败次数 + 最近成功时间。
7. **状态没有时间维度**：持久化状态只有 healthy/degraded/down，一个只在
   特定 mode 下运行的源一旦降级就永久冻结；``down`` 更因为被检索管线剔除而
   永远无法自愈。现在由 ``health.view_status`` 派生第 4 个状态 ``stale``
   （待复核），四张卡片 / 汇总行 / 点阵 / 底部状态栏口径一致。
8. **「联网检测」补齐（2026-10-21）**：此前面板只有「重新读取」（纯本地），
   真正的连通性探测只存在于「数据源管理 → 批量测试」，且那里测的是订阅 URL
   源、不覆盖注册表搜索引擎——面板上这批源没有任何主动检测入口。现在两处
   面板各加「联网检测」：并发逐源真实检索一次（``core.search.probe``），
   结论经 ``record_probe_result`` 落盘，进度用 ``st.status`` + 进度条 + 逐源
   状态行实时可见；暗网源按 Tor 建链预算单独放宽超时。

写操作纪律：本模块只在**用户点击**（重新读取 / 联网检测 / 清除标记）时写盘，
渲染路径只读；僵尸条目清理按会话一次性执行（``_health_purged_once``），
不再每帧写。
"""

import html

import streamlit as st

from intelnexus.core.logger import get_logger
from intelnexus.ui.health_view import (
    STATUS_DOT_CLASS,
    ago_parts,
    build_snapshot,
    format_latency,
    format_rate,
    format_streak,
    last_error_text,
    status_key,
    status_of,
)
from intelnexus.ui.i18n import get_text

logger = get_logger(__name__)

#: 僵尸条目清理的会话一次性旗标（两处面板共用，避免各清一遍）
_PURGED_FLAG = "_health_purged_once"


# ---------------------------------------------------------------------------
# 数据读取（唯一入口）
# ---------------------------------------------------------------------------

def _active_source_names():
    """注册表中的活跃源名列表；注册表不可用时返回 None（表示「不做过滤」）。"""
    try:
        from intelnexus.core.search.registry import get_registry
        from intelnexus.config.search_settings import get_news_api_key
        return [s.name for s in get_registry(news_api_key=get_news_api_key()).all_sources()]
    except Exception as e:
        logger.warning(f"健康面板：读取注册表失败，跳过白名单过滤: {e}")
        return None


def load_snapshot(purge: bool = False):
    """读取健康表并整理成快照（本模块唯一数据入口）。

    Args:
        purge: 是否顺带清理不属于任何注册源的僵尸条目。默认 False ——
            渲染路径只读，写盘只发生在会话首帧或用户点击时。
    """
    from intelnexus.core.search.health import get_all_health, purge_stale_entries

    active_names = _active_source_names()
    if purge and active_names is not None:
        try:
            purge_stale_entries(active_names)
        except Exception as e:
            logger.warning(f"健康面板：清理僵尸条目失败: {e}")
    try:
        entries = get_all_health()
    except Exception as e:
        logger.warning(f"健康面板：读取健康表失败: {e}")
        entries = []
    return build_snapshot(entries, active_names)


def purge_once(active_names) -> None:
    """会话首帧清理一次僵尸条目（写盘只发生一次，不阻塞切 Tab）。"""
    if st.session_state.get(_PURGED_FLAG):
        return
    # 先置旗标再写盘：写失败也不要在每帧重试
    st.session_state[_PURGED_FLAG] = True
    if active_names is None:
        return
    try:
        from intelnexus.core.search.health import purge_stale_entries
        purge_stale_entries(active_names)
    except Exception as e:
        logger.warning(f"健康面板：会话首帧清理失败: {e}")


def _invalidate_caches() -> None:
    """健康数据已变更：失效 UI 缓存，否则重绘后仍显示旧状态。"""
    try:
        from intelnexus.ui._caches import cached_all_health
        cached_all_health.clear()
    except Exception:
        pass
    try:
        from intelnexus.ui.status_metrics import invalidate_status_metrics
        invalidate_status_metrics()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 共用渲染原语
# ---------------------------------------------------------------------------

def _dot(status: str) -> str:
    return f'<span class="status-dot {STATUS_DOT_CLASS.get(status, "error")}"></span>'


def _ago_text(entry) -> str:
    """最近成功时间的相对表述（"3 分钟前"）；无记录返回 "—"。"""
    parts = ago_parts(getattr(entry, "last_success", None))
    if parts is None:
        return "—"
    unit, n = parts
    key = {
        "now": "health_ago_now",
        "m": "health_ago_minutes",
        "h": "health_ago_hours",
        "d": "health_ago_days",
    }.get(unit)
    if key is None:
        return "—"
    return get_text(key).format(n=n) if unit != "now" else get_text(key)


def _metrics_line(entry) -> str:
    """一行指标摘要：成功率 · 延迟 · 连续失败（侧边栏紧凑版用）。"""
    return get_text("health_metrics_line").format(
        rate=format_rate(entry),
        latency=format_latency(entry),
        streak=format_streak(entry),
    )


def _clear_button(entry, key_prefix: str) -> None:
    """「清除标记」按钮：只清历史统计，不做任何网络探测。"""
    if st.button(get_text("health_clear_flag"),
                 key=f"{key_prefix}_clear_{entry.source_name}",
                 help=get_text("health_clear_flag_help")):
        try:
            from intelnexus.core.search.health import save_health
            entry.reset()
            save_health(entry)
        except Exception as e:
            logger.warning(f"清除降级标记失败 [{entry.source_name}]: {e}")
        _invalidate_caches()
        st.rerun()


def _reload_button(key_prefix: str, snapshot, use_container_width: bool = True) -> None:
    """「重新读取」按钮：清僵尸条目 + 失效缓存 + 重绘，**不发起网络探测**。"""
    if st.button(get_text("health_reload"), key=f"{key_prefix}_reload",
                 use_container_width=use_container_width):
        try:
            from intelnexus.core.search.health import purge_stale_entries
            if snapshot.active_names is not None:
                purge_stale_entries(snapshot.active_names)
        except Exception as e:
            logger.warning(f"健康面板：重新读取时清理失败: {e}")
        _invalidate_caches()
        st.rerun()


# ---------------------------------------------------------------------------
# 联网检测（主动探测）
# ---------------------------------------------------------------------------

#: 探测状态 → 既有 status-dot 修饰类（skip 用 muted，与 stale 同视觉语言）
_PROBE_DOT = {
    "ok": "active",
    "empty": "active",
    "fail": "error",
    "timeout": "error",
    "skip_no_proxy": "muted",
    "skip_disabled": "muted",
}

#: session_state 键后缀：上次探测结果 / 完成时刻（重绘后仍展示）
_PROBE_RESULTS_SUFFIX = "_probe_results"
_PROBE_TS_SUFFIX = "_probe_ts"


def _probe_registry():
    """构造与会话当前配置一致的注册表（联网检测专用）。

    暗网探测必须复用检索页的 advanced_mode / tor_port / ui_sites：否则高级
    模式引擎或访客自定义 onion 站点在面板里根本不会被探测到，结论会与真实
    检索链路不一致（“面板说正常、检索却失败”的经典失真）。
    """
    from intelnexus.core.search.registry import get_registry
    from intelnexus.config.search_settings import get_news_api_key

    try:
        tor_port = int(st.session_state.get("tor_port_sel") or 9150)
    except (TypeError, ValueError):
        tor_port = 9150
    return get_registry(
        news_api_key=get_news_api_key(),
        darkweb_advanced=bool(st.session_state.get("advanced_mode", False)),
        tor_port=tor_port,
        ui_sites=list(st.session_state.get("custom_onion_sites") or []),
        web_threads=5,
    )


def _probe_row_html(row: dict) -> str:
    """单条探测结果行：状态点 + 源名 + 结论 + 耗时 + 错误摘要。"""
    state = str(row.get("state", "fail"))
    dot = _PROBE_DOT.get(state, "muted")
    label = get_text(f"health_probe_state_{state}")
    try:
        latency = float(row.get("latency_ms") or 0.0)
    except (TypeError, ValueError):
        latency = 0.0
    lat_text = f"{latency / 1000:.1f}s" if latency > 0 else "—"
    line = (f'<span class="status-dot {dot}"></span> '
            f'{html.escape(str(row.get("name", "")))} — {label} · {lat_text}')
    err = str(row.get("error") or "").strip()
    if err:
        line += (f'<br><span class="hc-inline-metric">'
                 f'{html.escape(err[:110])}</span>')
    return line


def _render_last_probe_results(key_prefix: str, max_rows: int = 6) -> None:
    """上次联网检测的摘要 + 非连通行（rerun 后仍在，直到下次检测覆盖）。

    只列失败/超时行：连通源的状态、延迟、最近错误已经由上方快照就地展示，
    逐行重铺 20+ 行只会淹没侧边栏真正需要关注的信息。
    """
    rows = st.session_state.get(f"{key_prefix}{_PROBE_RESULTS_SUFFIX}") or []
    if not rows:
        return
    ok = sum(1 for r in rows if r.get("state") in ("ok", "empty"))
    bad = [r for r in rows if r.get("state") in ("fail", "timeout")]
    ts = str(st.session_state.get(f"{key_prefix}{_PROBE_TS_SUFFIX}") or "")
    st.caption(get_text("health_probe_last_summary").format(
        ts=ts, ok=ok, bad=len(bad), total=len(rows)))
    for row in bad[:max_rows]:
        st.markdown(_probe_row_html(row), unsafe_allow_html=True)
    if len(bad) > max_rows:
        st.caption(f"+{len(bad) - max_rows}")


def _run_online_probe(key_prefix: str) -> None:
    """联网检测主体：并发逐源真实探测 + 实时进度 + 落盘 + 失效缓存 + 重绘。

    进度可见性：Streamlit 单次脚本运行内可多次更新同一 placeholder，因此
    每源完成即刷新「进度条 + 逐源状态行」，而不是等全部结束才出结果。
    探测结论由 ``probe_registry`` 逐条落盘，中途切页也不会丢掉已完成的部分。
    """
    from datetime import datetime

    from intelnexus.core.search.probe import probe_registry

    try:
        registry = _probe_registry()
        sources = [s for s in registry.all_sources() if getattr(s, "enabled", True)]
    except Exception as e:
        logger.warning(f"联网检测：构造注册表失败: {e}")
        st.error(get_text("health_probe_registry_failed").format(err=e))
        return
    total = len(sources)
    if total == 0:
        st.warning(get_text("health_probe_no_sources"))
        return

    order = [s.name for s in sources]
    rows = {}
    done = 0

    with st.status(get_text("health_probe_running_title"), expanded=True) as box:
        progress = st.progress(
            0.0, text=get_text("health_probe_running").format(done=0, total=total))
        table = st.empty()

        def _on_result(outcome):
            nonlocal done
            done += 1
            rows[outcome.source_name] = {
                "name": outcome.source_name,
                "state": outcome.state,
                "latency_ms": outcome.latency_ms,
                "error": outcome.error,
                "count": outcome.result_count,
            }
            progress.progress(
                min(done / total, 1.0),
                text=get_text("health_probe_running").format(done=done, total=total))
            table.markdown(
                "<br>".join(_probe_row_html(rows[n]) for n in order if n in rows)
                or "…", unsafe_allow_html=True)

        outcomes = probe_registry(registry, on_result=_on_result)
        n_bad = sum(1 for o in outcomes if o.state in ("fail", "timeout"))
        box.update(
            label=get_text("health_probe_done_title"),
            state="complete" if n_bad == 0 else "error",
            expanded=False,
        )

    # 先存后 rerun：重绘由下方固定渲染点展示本轮结果
    try:
        st.session_state[f"{key_prefix}{_PROBE_RESULTS_SUFFIX}"] = [
            {"name": o.source_name, "state": o.state,
             "latency_ms": o.latency_ms, "error": o.error,
             "count": o.result_count} for o in outcomes
        ]
        st.session_state[f"{key_prefix}{_PROBE_TS_SUFFIX}"] = \
            datetime.now().strftime("%H:%M:%S")
    except Exception:
        pass
    _invalidate_caches()
    st.rerun()


def _rule_caption() -> None:
    """状态规则说明：解释 3/6 次阈值、时间维度与 down 的真实后果。"""
    st.caption(get_text("health_state_rule"))
    st.caption(get_text("health_down_effect"))


def _retry_button(entry, key_prefix: str) -> None:
    """「立即重试」按钮：解除冷却，让该源在下次检索立刻被放行。

    只清 ``last_attempt``，不动计数——重试仍失败就会立刻回到 down。
    """
    if st.button(get_text("health_retry_now"),
                 key=f"{key_prefix}_retry_{entry.source_name}",
                 help=get_text("health_retry_now_help")):
        try:
            from intelnexus.core.search.health import mark_for_retry
            mark_for_retry(entry.source_name)
        except Exception as e:
            logger.warning(f"解除冷却失败 [{entry.source_name}]: {e}")
        _invalidate_caches()
        st.rerun()


def _action_for(entry, key_prefix: str) -> None:
    """按状态给出操作。

    - ``down``（冷却期内被剔除）→ 「立即重试」：解除冷却，下次检索就试；
    - ``degraded``（仍在检索但排后）→ 「清除标记」：历史失败已确认修复时清零；
    - ``stale``（判定过期）→ 不给按钮，下次检索本来就会重试。
    """
    state = status_of(entry)
    if state == "stale":
        st.caption(get_text("health_stale_hint"))
    elif state == "down":
        _retry_button(entry, key_prefix)
    else:
        _clear_button(entry, key_prefix)


# ---------------------------------------------------------------------------
# 侧边栏紧凑版
# ---------------------------------------------------------------------------

def compact_title(snapshot) -> str:
    """侧边栏 expander 标题：折叠时也能看出有没有问题。"""
    base = get_text("source_health")
    if snapshot.is_empty:
        return base
    problems = len(snapshot.problems)
    if problems:
        return get_text("health_title_with_problems").format(
            base=base, n=problems)
    return get_text("health_title_all_ok").format(base=base)


def render_health_compact(snapshot) -> None:
    """侧边栏「数据源状态」主体（调用方负责 expander 与标题）。"""
    summary = snapshot.summary
    st.caption(get_text("health_summary_line").format(
        healthy=summary.get("healthy", 0),
        degraded=summary.get("degraded", 0),
        stale=summary.get("stale", 0),
        down=summary.get("down", 0),
    ))

    _reload_button("sb_health", snapshot)
    st.caption(get_text("health_reload_hint"))

    # 联网检测：真正的连通性刷新（逐源真实检索 + 实时进度）
    if st.button(get_text("health_probe_btn"), key="sb_health_probe",
                 help=get_text("health_probe_btn_help"),
                 use_container_width=True):
        _run_online_probe("sb_health")
    _render_last_probe_results("sb_health")

    if snapshot.is_empty:
        st.caption(get_text("health_empty"))
        return

    problems = snapshot.problems
    healthy = snapshot.healthy

    if problems:
        st.caption(get_text("health_only_problems"))
        for entry in problems:
            col_main, col_action = st.columns([3, 1])
            with col_main:
                st.markdown(
                    f'{_dot(status_of(entry))} **{html.escape(entry.source_name)}**'
                    f' · {get_text(status_key(entry))}',
                    unsafe_allow_html=True,
                )
                st.caption(_metrics_line(entry))
                err = last_error_text(entry, limit=90)
                if err:
                    st.caption(get_text("health_last_error").format(err=err))
            with col_action:
                _action_for(entry, "sb_health")

    # 正常源默认折叠：侧边栏空间有限，正常项不占版面
    if healthy:
        label = get_text("health_show_healthy").format(n=len(healthy))
        if st.checkbox(label, key="sb_health_show_healthy"):
            for entry in healthy:
                st.markdown(
                    f'{_dot("healthy")} {html.escape(entry.source_name)}'
                    f' <span class="hc-inline-metric">{_metrics_line(entry)}</span>',
                    unsafe_allow_html=True,
                )
        elif not problems:
            st.caption(get_text("health_all_ok"))

    st.caption(get_text("health_full_panel_hint"))


# ---------------------------------------------------------------------------
# 简报中心完整版
# ---------------------------------------------------------------------------

def render_health_overview():
    """渲染数据源健康检查概览面板（简报中心设置区）。"""
    snapshot = load_snapshot()
    purge_once(snapshot.active_names)

    st.markdown(f'''
    <div class="bf-panel bf-panel--source">
        <div class="bf-label">
            <span class="bf-label__tag">{get_text("health_panel_tag")}</span>
            <span class="bf-label__title">{get_text("health_panel_title")}</span>
        </div>
    ''', unsafe_allow_html=True)

    _rule_caption()

    # ---- 操作层：重新读取（清僵尸 + 失效缓存 + rerun，绝不发起网络探测）----
    _reload_button("hc", snapshot)
    st.caption(get_text("health_reload_hint"))

    # ---- 操作层：联网检测（真正刷新连通性，逐源真实检索）----
    if st.button(get_text("health_probe_btn"), key="hc_probe",
                 help=get_text("health_probe_btn_help")):
        _run_online_probe("hc")
    st.caption(get_text("health_probe_hint"))
    _render_last_probe_results("hc")

    # ---- 聚合层：4 张指标卡（与明细同源，口径恒一致）----
    summary = snapshot.summary
    cards = [
        ("hc-card--healthy", "health_card_healthy", summary.get("healthy", 0)),
        ("hc-card--degraded", "health_card_degraded", summary.get("degraded", 0)),
        ("hc-card--stale", "health_card_stale", summary.get("stale", 0)),
        ("hc-card--down", "health_card_down", summary.get("down", 0)),
    ]
    cols = st.columns(len(cards))
    for col, (cls, label_key, value) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="hc-card {cls}">', unsafe_allow_html=True)
            st.metric(get_text(label_key), value)
            st.markdown('</div>', unsafe_allow_html=True)

    if snapshot.is_empty:
        st.markdown(
            f"<p class='bf-hint'>{get_text('health_empty')}</p>",
            unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    st.caption(get_text("health_clear_flag_help"))

    # ---- 明细层：列头 + 逐源 ----
    _render_table_header()
    for entry in snapshot.entries:
        _render_table_row(entry)

    st.markdown('</div>', unsafe_allow_html=True)


def _render_table_header() -> None:
    cols = st.columns([2.6, 0.9, 0.9, 0.9, 0.9, 1.5, 1.1])
    labels = [
        "health_col_source",
        "health_col_state",
        "health_col_rate",
        "health_col_latency",
        "health_col_streak",
        "health_col_last_ok",
        "health_col_action",
    ]
    for col, key in zip(cols, labels):
        with col:
            st.caption(f"**{get_text(key)}**")


def _render_table_row(entry) -> None:
    col_name, col_state, col_rate, col_lat, col_streak, col_last, col_action = st.columns(
        [2.6, 0.9, 0.9, 0.9, 0.9, 1.5, 1.1])
    with col_name:
        # source_name 用户可控（自定义源名），拼入 HTML 前必须转义防 XSS
        st.markdown(
            f"{_dot(status_of(entry))} **{html.escape(entry.source_name)}**",
            unsafe_allow_html=True)
        err = last_error_text(entry)
        if err:
            st.caption(get_text("health_last_error").format(err=err))
    with col_state:
        st.caption(get_text(status_key(entry)))
    with col_rate:
        st.caption(format_rate(entry))
    with col_lat:
        st.caption(format_latency(entry))
    with col_streak:
        st.caption(format_streak(entry))
    with col_last:
        st.caption(_ago_text(entry))
    with col_action:
        # stale 不给按钮：它的正确处置是「下次检索自动重试」，
        # 而非手动清零（那只会让过期结论变成假绿灯）。表格列窄，说明留在规则文案里。
        if status_of(entry) == "down":
            _retry_button(entry, "hc")
        elif status_of(entry) == "degraded":
            _clear_button(entry, "hc")


__all__ = [
    "compact_title",
    "load_snapshot",
    "purge_once",
    "render_health_compact",
    "render_health_overview",
]
