import os
import streamlit as st
from intelnexus.ui.icons import icon, status_icon


def render_results_panels():
    """渲染所有结果可视化面板。

    只要有搜索产物（search_completed）即可渲染；各子面板（可信度 / 冲突 /
    知识图谱 / 证据链）独立判断自身数据是否存在，报告生成失败时仍展示其他分析。
    """
    if not st.session_state.get("search_completed", False):
        return

    st.markdown("<br>", unsafe_allow_html=True)

    cred = st.session_state.get("credibility_data")
    if cred:
        st.markdown("---")
        st.markdown(f"## {icon('chart', 'lg', 'blue')} 来源可信度评估", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("平均可信度", f"{cred['avg_score']:.2f}")
        col2.metric("高可信来源", cred['high_count'])
        col3.metric("低可信来源", cred['low_count'])
        col4.metric("一致性", f"{cred['overall_consistency']:.2f}")

        rows = []
        for s in cred['scores'][:20]:
            if s['score'] >= 0.7:
                label = "高"
            elif s['score'] >= 0.4:
                label = "中"
            else:
                label = "低"
            rows.append(f"| {s['name']} | {s['score']:.2f} | {label} | {s['reason'][:40]} |")
        if rows:
            header = "| 来源 | 可信度 | 等级 | 原因 |\n|------|--------|------|------|"
            st.markdown(header + "\n" + "\n".join(rows))

    conflicts = st.session_state.get("conflicts", [])
    if conflicts:
        st.markdown("---")
        st.markdown(f"## {icon('warning', 'lg', 'warning')} 跨源信息冲突", unsafe_allow_html=True)
        for c in conflicts[:5]:
            sev = c.get("severity", 0.5)
            if sev >= 0.7:
                sev_label = "高"
            elif sev >= 0.4:
                sev_label = "中"
            else:
                sev_label = "低"
            with st.expander(f"[{sev_label}] {c.get('description', '')[:80]}", expanded=sev >= 0.7):
                st.markdown(f"**类型**: {c.get('type')} | **严重度**: {sev:.2f}")
                st.markdown(f"**涉及来源**:")
                for src in c.get("sources", []):
                    val = src.get('value', '')
                    st.markdown(f"- {src.get('name', '?')}: _{val}_")

    kg_path = st.session_state.get("kg_html_path", "")
    if kg_path and os.path.exists(kg_path):
        st.markdown("---")
        st.markdown(f"## {icon('knowledge', 'lg', 'lavender')} 情报知识图谱", unsafe_allow_html=True)
        entities = st.session_state.get("kg_entities", [])
        if entities:
            st.markdown("**关键实体**: " +
                        ", ".join([f"{e['name']}({e['type']})" for e in entities[:8]]))
        with open(kg_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        st.components.v1.html(html_content, height=600, scrolling=True)

    ev = st.session_state.get("evidence_data")
    if ev and ev.get("claims"):
        st.markdown("---")
        st.markdown(f"## {icon('link', 'lg', 'terracotta')} 证据链追踪", unsafe_allow_html=True)
        st.metric("证据覆盖率", f"{ev['coverage']:.0%}")
        for claim in ev["claims"][:10]:
            if claim["is_unsupported"]:
                st.markdown(f"{icon('error', 'sm', 'error')} _{claim['text'][:80]}..._ — **无直接证据**", unsafe_allow_html=True)
            else:
                best = claim["evidence"][0]
                st.markdown(f"{icon('success', 'sm', 'sage')} _{claim['text'][:80]}..._", unsafe_allow_html=True)
                st.markdown(f" → 置信度 {best['confidence']:.2f} | "
                            f"[查看原文]({best['url']})")
