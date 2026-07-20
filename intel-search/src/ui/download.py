import streamlit as st
from src.ui.i18n import get_text


def render_download_section():
    """渲染报告导出工具栏 — Intel Report Document 风格"""
    if not (st.session_state.get("search_completed", False) and st.session_state.get("streamed_summary")):
        return

    # Toolbar label row
    st.markdown('<div class="ir-toolbar"><span class="ir-toolbar__lbl">Export Format</span></div>',
                unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        _do_export("md", "MD")

    with col2:
        _do_export("pdf", "PDF")

    with col3:
        _do_export("docx", "DOCX")

    with col4:
        _do_export("xlsx", "XLSX")

    # Close intel-report container after all panels
    st.markdown("</div><!-- /ir-body --></div><!-- /intel-report -->", unsafe_allow_html=True)


def _do_export(fmt: str, label: str):
    """生成单个格式按钮并处理导出逻辑"""
    from pathlib import Path

    filename = f"report_{st.session_state.report_timestamp}"

    if fmt == "md":
        st.download_button(
            label=label,
            data=st.session_state.streamed_summary,
            file_name=f"{filename}.md",
            mime="text/markdown",
            key=f"toolbar_{fmt}",
            use_container_width=True,
        )
        return

    btn_key = f"toolbar_{fmt}"
    if st.button(label, key=btn_key, use_container_width=True):
        try:
            if fmt == "pdf":
                from src.export.report import export_pdf
                path = export_pdf(st.session_state.streamed_summary, st.session_state.refined, filename)
                mime = "application/pdf"

            elif fmt == "docx":
                from src.export.report import export_word
                path = export_word(st.session_state.streamed_summary, st.session_state.refined, filename)
                mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

            elif fmt == "xlsx":
                from src.export.report import export_excel
                path = export_excel(st.session_state.streamed_summary, st.session_state.refined, filename)
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

            with open(path, 'rb') as f:
                data = f.read()

            st.download_button(
                label=f"{label} Ready",
                data=data,
                file_name=f"{filename}.{fmt}",
                mime=mime,
                key=f"{btn_key}_dl",
                use_container_width=True,
            )
            try:
                Path(path).unlink()
            except Exception:
                pass

        except Exception as e:
            st.error(f"{get_text('error')}: {str(e)}")
