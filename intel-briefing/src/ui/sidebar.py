import streamlit as st
from shared.logger import get_logger
from src.ui.i18n import get_text
from shared.llm.utils import get_model_choices

logger = get_logger(__name__)


def _render_model_settings():
    """模型选择 + 语言"""
    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("settings")}</div>', unsafe_allow_html=True)

    model_options = get_model_choices()
    default_model = "qwen2.5:7b" if "qwen2.5:7b" in model_options else (model_options[0] if model_options else "gpt-4o")
    model_index = model_options.index(default_model) if default_model in model_options else 0

    model = st.selectbox(get_text("llm_model"), model_options, index=model_index)

    lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
    selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()),
                                  index=0 if st.session_state.lang == "zh" else 1,
                                  key="lang_selector")
    if lang_options.get(selected_lang) != st.session_state.lang:
        st.session_state.lang = lang_options[selected_lang]
        st.rerun()

    return model


def render_sidebar():
    """
    侧边栏仅保留全局设置（模型 + 语言）。

    简报业务（数据源/订阅者/生成）已收拢至简报 Tab，
    避免在搜索 Tab 下展示无关的简报管理造成认知混乱。
    """
    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

        st.markdown("---")
        model = _render_model_settings()

    return model
