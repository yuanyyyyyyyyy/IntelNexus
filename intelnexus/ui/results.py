import os
import streamlit as st
from intelnexus.ui.i18n import get_text
from intelnexus.ui.icons import icon, status_icon


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

        rows = []
        for s in cred['scores'][:20]:
            rows.append(
                f"| {s['name']} | {s['score']:.2f} | {_cred_label(s['score'])} | {s['reason']} |")
        if rows:
            header = (f"| {get_text('col_source')} | {get_text('col_credibility')} | "
                      f"{get_text('col_level')} | {get_text('col_reason')} |\n"
                      "|------|--------|------|------|")
            st.markdown(header + "\n" + "\n".join(rows))

    conflicts = st.session_state.get("conflicts", [])
    if conflicts:
        st.markdown("---")
        st.markdown(f"## {icon('warning', 'lg', 'warning')} {get_text('results_conflict_title')}", unsafe_allow_html=True)
        for c in conflicts[:5]:
            sev = c.get("severity", 0.5)
            sev_label = _cred_label(sev)
            with st.expander(f"[{sev_label}] {c.get('description', '')[:80]}", expanded=sev >= 0.7):
                st.markdown(f"**{get_text('label_type')}**: {c.get('type')} | "
                            f"**{get_text('label_severity')}**: {sev:.2f}")
                st.markdown(f"**{get_text('label_involved_sources')}**:")
                for src in c.get("sources", []):
                    val = src.get('value', '')
                    st.markdown(f"- {src.get('name', '?')}: _{val}_")

    kg_path = st.session_state.get("kg_html_path", "")
    if kg_path and os.path.exists(kg_path):
        st.markdown("---")
        st.markdown(f"## {icon('knowledge', 'lg', 'lavender')} {get_text('results_kg_title')}", unsafe_allow_html=True)
        entities = st.session_state.get("kg_entities", [])
        if entities:
            st.markdown(f"**{get_text('label_key_entities')}**: " +
                        ", ".join([f"{e['name']}({e['type']})" for e in entities[:8]]))
        # 重内容折叠：600px iframe 默认收起，需要时再展开
        with st.expander(get_text("kg_details_expander")):
            with open(kg_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=600, scrolling=True)

    ev = st.session_state.get("evidence_data")
    if ev and ev.get("claims"):
        st.markdown("---")
        st.markdown(f"## {icon('link', 'lg', 'terracotta')} {get_text('results_evidence_title')}", unsafe_allow_html=True)
        st.metric(get_text("label_evidence_coverage"), f"{ev['coverage']:.0%}")
        with st.expander(get_text("evidence_details_expander")):
            for claim in ev["claims"][:10]:
                if claim["is_unsupported"]:
                    st.markdown(f"{icon('error', 'sm', 'error')} _{claim['text'][:80]}..._ "
                                f"— **{get_text('label_no_direct_evidence')}**",
                                unsafe_allow_html=True)
                else:
                    best = claim["evidence"][0]
                    st.markdown(f"{icon('success', 'sm', 'sage')} _{claim['text'][:80]}..._",
                                unsafe_allow_html=True)
                    st.markdown(f" → {get_text('label_confidence')} {best['confidence']:.2f} | "
                                f"[{get_text('link_view_original')}]({best['url']})")

    # 行动项清单面板
    actions = st.session_state.get("action_items", [])
    if actions:
        st.markdown("---")
        st.markdown(f"## {icon('checklist', 'lg', 'blue')} {get_text('results_actions_title')}", unsafe_allow_html=True)
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
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
            pi = priority_icons.get(a.get("priority", "low"), "⚪")
            pl = priority_labels.get(a.get("priority", "low"),
                                     get_text("priority_suggested"))
            dl = deadline_labels.get(a.get("deadline", "this_month"),
                                     get_text("deadline_this_month"))
            st.markdown(f"- {pi} **[{pl}]** {a.get('action', '')} "
                        f"*({get_text('label_deadline')}: {dl})*")
