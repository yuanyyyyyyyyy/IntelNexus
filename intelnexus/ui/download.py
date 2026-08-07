import streamlit as st
from intelnexus.ui.i18n import get_text


def render_download_section():
    """渲染报告下载区域"""
    if not (st.session_state.get("search_completed", False) and st.session_state.get("streamed_summary")):
        return

    st.markdown("---")
    format_options = ["md", "pdf", "docx", "xlsx"]
    format_labels = {"md": "Markdown", "pdf": "PDF", "docx": "Word", "xlsx": "Excel"}

    download_format = st.selectbox(
        get_text("select_download_format"),
        format_options,
        format_func=lambda x: format_labels[x],
        key="download_format_select"
    )
    st.session_state.sidebar_download_format = download_format

    if st.button(get_text("download"), use_container_width=True, key="download_btn"):
        from pathlib import Path

        try:
            filename = f"report_{st.session_state.report_timestamp}"
            if download_format == 'pdf':
                from intelnexus.export.report import export_pdf
                pdf_path = export_pdf(st.session_state.streamed_summary, st.session_state.refined, filename)
                with open(pdf_path, 'rb') as f:
                    pdf_data = f.read()
                st.download_button(
                    label=get_text("pdf_ready"),
                    data=pdf_data,
                    file_name=f"{filename}.pdf",
                    mime="application/pdf",
                    key="pdf_download_now"
                )
                try:
                    Path(pdf_path).unlink()
                except Exception:
                    pass

            elif download_format == 'docx':
                from intelnexus.export.report import export_word
                docx_path = export_word(st.session_state.streamed_summary, st.session_state.refined, filename)
                with open(docx_path, 'rb') as f:
                    docx_data = f.read()
                st.download_button(
                    label=get_text("word_ready"),
                    data=docx_data,
                    file_name=f"{filename}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="docx_download_now"
                )
                try:
                    Path(docx_path).unlink()
                except Exception:
                    pass

            elif download_format == 'xlsx':
                from intelnexus.export.report import export_excel
                xlsx_path = export_excel(st.session_state.streamed_summary, st.session_state.refined, filename)
                with open(xlsx_path, 'rb') as f:
                    xlsx_data = f.read()
                st.download_button(
                    label="Excel已准备",
                    data=xlsx_data,
                    file_name=f"{filename}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="xlsx_download_now"
                )
                try:
                    Path(xlsx_path).unlink()
                except Exception:
                    pass

            else:  # markdown
                st.download_button(
                    label=get_text("md_ready"),
                    data=st.session_state.streamed_summary,
                    file_name=f"{filename}.md",
                    mime="text/markdown",
                    key="md_download_now"
                )
        except Exception as e:
            st.error(f"{get_text('error')}: {str(e)}")
