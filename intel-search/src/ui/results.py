import os
import streamlit as st
from src.ui.i18n import get_text


def render_results_panels():
    """渲染所有结果可视化面板 — Intel Report Document 风格"""
    if not (st.session_state.get("search_completed", False) and st.session_state.get("streamed_summary")):
        return

    # Close summary box opened in pipeline
    st.markdown("</div><!-- /ir-summary-box -->", unsafe_allow_html=True)

    cred = st.session_state.get("credibility_data")
    if cred:
        avg = cred['avg_score']
        high = cred['high_count']
        low = cred['low_count']
        cons = cred['overall_consistency']

        # Metric bar color helpers
        def metric_bar(val, threshold_high=0.7, threshold_low=0.4):
            if val >= threshold_high:
                return "ok"
            elif val >= threshold_low:
                return "warn"
            return "bad"

        pct = f"{avg * 100:.0f}"
        st.markdown(f"""
            <div class="ir-metrics">
                <div class="ir-metric">
                    <div class="ir-metric__val">{avg:.2f}</div>
                    <div class="ir-metric__lbl">Avg Cred</div>
                    <div class="ir-metric__bar"><span style="width:{pct}%" class="ir-metric__bar--{metric_bar(avg)}"></span></div>
                </div>
                <div class="ir-metric">
                    <div class="ir-metric__val">{high}</div>
                    <div class="ir-metric__lbl">High</div>
                    <div class="ir-metric__bar"><span style="width:100%" class="ir-metric__bar--ok"></span></div>
                </div>
                <div class="ir-metric">
                    <div class="ir-metric__val">{low}</div>
                    <div class="ir-metric__lbl">Low</div>
                    <div class="ir-metric__bar"><span style="width:100%" class="ir-metric__bar--{'warn' if low > 0 else 'ok'}"></span></div>
                </div>
                <div class="ir-metric">
                    <div class="ir-metric__val">{cons:.2f}</div>
                    <div class="ir-metric__lbl">Consistency</div>
                    <div class="ir-metric__bar"><span style="width:{cons * 100:.0f}%" class="ir-metric__bar--{metric_bar(cons)}"></span></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Credibility table
        st.markdown('<div class="ir-section-title ir-section-title--cred">Source Credibility</div>', unsafe_allow_html=True)
        rows = []
        for s in cred['scores'][:20]:
            sc = s['score']
            badge_class = "high" if sc >= 0.7 else ("mid" if sc >= 0.4 else "low")
            badge_label = "High" if sc >= 0.7 else ("Mid" if sc >= 0.4 else "Low")
            rows.append(
                f'<tr><td>{s["name"]}</td>'
                f'<td>{sc:.2f}</td>'
                f'<td><span class="ir-badge ir-badge--{badge_class}">{badge_label}</span></td>'
                f'<td>{s["reason"][:50]}</td></tr>')
        if rows:
            table_html = (
                '<table class="ir-table">'
                '<thead><tr><th>Source</th><th>Score</th><th>Level</th><th>Reason</th></tr></thead>'
                '<tbody>' + "\n".join(rows) + '</tbody></table>'
            )
            st.markdown(table_html, unsafe_allow_html=True)

    # Conflicts
    conflicts = st.session_state.get("conflicts", [])
    if conflicts:
        st.markdown('<div class="ir-section-title ir-section-title--conflict">Cross-Source Conflicts</div>', unsafe_allow_html=True)
        for c in conflicts[:5]:
            sev = c.get("severity", 0.5)
            sev_class = "high" if sev >= 0.7 else ("mid" if sev >= 0.4 else "low")
            with st.expander(f"[{c['type'].upper()}] {c.get('description', '')[:80]}", expanded=sev >= 0.7):
                st.markdown(f"<div class='ir-conflict-item'>"
                            f"<span class='ir-conflict-item__type'>{c.get('type')}</span>"
                            f"<span class='ir-badge ir-badge--{sev_class} ir-conflict-item__sev'>Sev: {sev:.2f}</span>"
                            f"<br/><br/>{c.get('description', '')}"
                            f"</div>", unsafe_allow_html=True)
                st.markdown("**Sources:**")
                for src in c.get("sources", []):
                    val = src.get('value', '')
                    st.markdown(f"- {src.get('name', '?')}: _{val}_")

    # Knowledge Graph
    kg_path = st.session_state.get("kg_html_path", "")
    if kg_path and os.path.exists(kg_path):
        st.markdown('<div class="ir-section-title ir-section-title--graph">Knowledge Graph</div>', unsafe_allow_html=True)
        entities = st.session_state.get("kg_entities", [])
        if entities:
            entity_tags = ", ".join(
                [f"<span class='ir-badge ir-badge--mid'>{e['name']}</span>" for e in entities[:8]])
            st.markdown(f"<p style='font-size:13px;color:#6B7280;margin-bottom:12px;'>Key entities: {entity_tags}</p>",
                        unsafe_allow_html=True)
        with open(kg_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        st.components.v1.html(html_content, height=600, scrolling=True)

    # Evidence Chain
    ev = st.session_state.get("evidence_data")
    if ev and ev.get("claims"):
        st.markdown('<div class="ir-section-title ir-section-title--evidence">Evidence Chain</div>', unsafe_allow_html=True)
        cov = ev.get('coverage', 0)
        st.markdown(
            f"<div class='ir-metrics' style='grid-template-columns:1fr;'>"
            f"<div class='ir-metric'>"
            f"<div class='ir-metric__val'>{cov:.0%}</div>"
            f"<div class='ir-metric__lbl'>Coverage</div>"
            f"</div></div>", unsafe_allow_html=True)
        for claim in ev["claims"][:10]:
            if claim["is_unsupported"]:
                st.markdown(
                    f"<div class='ir-evidence-item ir-evidence-item--unsup'>"
                    f"{claim['text'][:100]}... "
                    f"<span class='ir-badge ir-badge--low'>Unsupported</span>"
                    f"</div>", unsafe_allow_html=True)
            else:
                best = claim["evidence"][0]
                url = best.get('url', '#')
                st.markdown(
                    f"<div class='ir-evidence-item'>"
                    f"{claim['text'][:100]}..."
                    f"<br/><small>Conf: {best['confidence']:.2f} | "
                    f"<a href='{url}' target='_blank'>Source</a></small>"
                    f"</div>", unsafe_allow_html=True)
