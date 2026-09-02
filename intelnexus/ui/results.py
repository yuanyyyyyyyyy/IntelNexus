import os
import html
from pathlib import Path
from urllib.parse import quote, urlparse
import streamlit as st
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon, status_icon


def _esc(value) -> str:
    """外部/模型产出的字符串渲染前统一 HTML 转义（防 XSS/markdown 注入）。"""
    return html.escape(str(value if value is not None else ""), quote=True)


def _safe_md_url(url) -> str:
    """外部 URL 拼入 markdown 链接前的安全处理。

    方案说明（简单稳妥）：
    - 先剔除不可打印字符/换行，防止链接被截断或注入多行内容；
    - 仅 http/https 且主机名非空时才允许作为链接，否则返回空串，
      由调用方降级为转义纯文本（阻断 javascript:/data: 等伪协议）；
    - quote 时不把 ``)``、反引号、尖括号等会破坏 markdown 链接语法/结构的字符
      列入 safe，使其被百分号编码，防止裸 ``)`` 造成链接逃逸注入。
    """
    u = "".join(ch for ch in (url or "") if ch.isprintable()).strip()
    if not u:
        return ""
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    return quote(u, safe=":/?#[]@!$&'*+,;=%-_.~")


def _cred_label(score: float) -> str:
    """可信度分数 → 三档文案（统一供表格与冲突严重度复用）。"""
    if score >= 0.7:
        return get_text("level_high")
    if score >= 0.4:
        return get_text("level_mid")
    return get_text("level_low")


def render_results_panels():
    """渲染所有结果可视化面板。

    只要有搜索产物（search_completed）即可渲染；各子面板（可信度 / 冲突 /
    知识图谱 / 证据链）独立判断自身数据是否存在，报告生成失败时仍展示其他分析。
    排版（F5）：重内容（KG iframe、逐条证据）折叠进 expander，指标摘要保持可见，
    避免长报告滚动地狱。
    """
    if not st.session_state.get("search_completed", False):
        return

    st.markdown("<br>", unsafe_allow_html=True)

    cred = st.session_state.get("credibility_data")
    if cred:
        st.markdown("---")
        st.markdown(f"## {icon('chart', 'lg', 'blue')} {get_text('results_credibility_title')}", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(get_text("metric_avg_credibility"), f"{cred['avg_score']:.2f}")
        col2.metric(get_text("metric_high_cred"), cred['high_count'])
        col3.metric(get_text("metric_low_cred"), cred['low_count'])
        col4.metric(get_text("metric_consistency"), f"{cred['overall_consistency']:.2f}")

        # 可信度雷达图
        radar_chart = st.session_state.get("credibility_radar_chart")
        if radar_chart:
            st.markdown(
                f'<img src="data:image/png;base64,{radar_chart}" '
                f'alt="情报可信度雷达" style="max-width:400px;margin:16px auto;display:block;">',
                unsafe_allow_html=True,
            )

        rows = []
        for s in cred['scores'][:20]:
            rows.append(
                f"| {_esc(s['name'])} | {s['score']:.2f} | {_cred_label(s['score'])} | {_esc(s['reason'])} |")
        if rows:
            header = (f"| {get_text('col_source')} | {get_text('col_credibility')} | "
                      f"{get_text('col_level')} | {get_text('col_reason')} |\n"
                      "|------|--------|------|------|")
            st.markdown(header + "\n" + "\n".join(rows))

    # 结构化摘要（事实/分析/推测）
    structured = st.session_state.get("structured_summary")
    if structured:
        st.markdown("---")
        st.markdown(f"## {icon('summary', 'lg', 'blue')} {get_text('results_structured_summary_title')}", unsafe_allow_html=True)
        from intelnexus.analysis.structured_summary import format_structured_summary_for_display
        md = format_structured_summary_for_display(structured)
        if md:
            st.markdown(md)

    conflicts = st.session_state.get("conflicts", [])
    if conflicts:
        st.markdown("---")
        st.markdown(f"## {icon('warning', 'lg', 'warning')} {get_text('results_conflict_title')}", unsafe_allow_html=True)
        for c in conflicts[:5]:
            sev = c.get("severity", 0.5)
            sev_label = _cred_label(sev)
            with st.expander(f"[{sev_label}] {c.get('description', '')[:80]}", expanded=sev >= 0.7):
                st.markdown(f"**{get_text('label_type')}**: {_esc(c.get('type'))} | "
                            f"**{get_text('label_severity')}**: {sev:.2f}")
                st.markdown(f"**{get_text('label_involved_sources')}**:")
                for src in c.get("sources", []):
                    val = src.get('value', '')
                    st.markdown(f"- {_esc(src.get('name', '?'))}: _{_esc(val)}_")

    kg_path = st.session_state.get("kg_html_path", "")
    if kg_path and os.path.exists(kg_path):
        st.markdown("---")
        st.markdown(f"## {icon('knowledge', 'lg', 'lavender')} {get_text('results_kg_title')}", unsafe_allow_html=True)
        entities = st.session_state.get("kg_entities", [])
        if entities:
            st.markdown(f"**{get_text('label_key_entities')}**: " +
                        ", ".join([f"{_esc(e['name'])}({_esc(e['type'])})" for e in entities[:8]]))
        # 重内容折叠：600px iframe 默认收起，需要时再展开。
        # st.iframe(Path) 对 HTML 文件内部走 srcdoc 嵌入且强制允许滚动，
        # 与旧版 components.html(html, height=600, scrolling=True) 行为等价
        with st.expander(get_text("kg_details_expander")):
            st.iframe(Path(kg_path), height=600)

    ev = st.session_state.get("evidence_data")
    if ev and ev.get("claims"):
        st.markdown("---")
        st.markdown(f"## {icon('link', 'lg', 'terracotta')} {get_text('results_evidence_title')}", unsafe_allow_html=True)
        st.metric(get_text("label_evidence_coverage"), f"{ev['coverage']:.0%}")
        with st.expander(get_text("evidence_details_expander")):
            for claim in ev["claims"][:10]:
                if claim["is_unsupported"]:
                    st.markdown(f"{icon('error', 'sm', 'error')} _{_esc(claim['text'][:80])}..._ "
                                f"— **{get_text('label_no_direct_evidence')}**",
                                unsafe_allow_html=True)
                else:
                    best = claim["evidence"][0]
                    st.markdown(f"{icon('success', 'sm', 'sage')} _{_esc(claim['text'][:80])}..._",
                                unsafe_allow_html=True)
                    # 外部 url 先过安全处理；不合法/伪协议时降级为转义纯文本，不渲染链接
                    safe_url = _safe_md_url(best.get('url', ''))
                    if safe_url:
                        link_part = f"[{get_text('link_view_original')}]({safe_url})"
                    else:
                        link_part = f"{_esc(best.get('url', ''))} ({get_text('link_view_original')})"
                    st.markdown(f" → {get_text('label_confidence')} {best['confidence']:.2f} | "
                                f"{link_part}")

    # 行动项清单面板
    actions = st.session_state.get("action_items", [])
    if actions:
        st.markdown("---")
        st.markdown(f"## {icon('checklist', 'lg', 'blue')} {get_text('results_actions_title')}", unsafe_allow_html=True)
        priority_labels = {
            "high": get_text("priority_urgent"),
            "medium": get_text("priority_important"),
            "low": get_text("priority_suggested"),
        }
        deadline_labels = {
            "immediate": get_text("deadline_immediate"),
            "this_week": get_text("deadline_this_week"),
            "this_month": get_text("deadline_this_month"),
        }
        for a in actions:
            # 优先级标记用项目自有 SVG 状态图标体系（emoji 违反界面无 emoji 约定）
            pi = status_icon(a.get("priority", "low"), "sm")
            pl = priority_labels.get(a.get("priority", "low"),
                                     get_text("priority_suggested"))
            dl = deadline_labels.get(a.get("deadline", "this_month"),
                                     get_text("deadline_this_month"))
            st.markdown(f"- {pi} **[{pl}]** {_esc(a.get('action', ''))} "
                        f"*({get_text('label_deadline')}: {dl})*", unsafe_allow_html=True)
