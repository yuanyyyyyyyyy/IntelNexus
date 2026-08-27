"""
首次运行模型接入向导
====================
解决「直接给别人用」的最大断点：新机器上 get_model_choices() 为空，
主界面模型下拉是死胡同，而添加 API 模型的入口埋在侧边栏深处。

触发条件：本地无任何可用模型（Ollama 无模型且无自定义模型）时，
在主界面顶部显示一条可折叠的接入引导卡片。完成或跳过后本次会话不再打扰。
纯 UI 组件，复用 models.py 既有的 add_custom_model / test_model_connection API。
"""
import streamlit as st

from intelnexus.ui.i18n import get_text, localize_llm_test_error
from intelnexus.core.llm.utils import get_model_choices


def _has_any_model() -> bool:
    """是否已有任何可用模型（Ollama 本地模型或自定义模型）。"""
    try:
        return len(get_model_choices()) > 0
    except Exception:
        return False


def render_model_setup_hint() -> None:
    """无模型时在页面顶部渲染可折叠的「3 步接入」引导卡片。

    - 已有模型、或用户点过「暂不设置」→ 不渲染
    - 提供商预设覆盖国内常用 OpenAI 兼容服务，用户只需粘贴 Key
    """
    if _has_any_model():
        return
    if st.session_state.get("model_setup_dismissed"):
        return

    with st.container(border=True):
        st.markdown(f"### {get_text('ms_title')}")
        st.caption(get_text("ms_subtitle"))

        provider = st.selectbox(
            get_text("ms_provider"),
            options=["deepseek", "moonshot", "通义千问", "智谱ai", "openai", "ollama"],
            format_func=lambda p: get_text(f"ms_provider_{p}"),
            key="ms_provider_sel",
        )

        if provider == "ollama":
            st.info(get_text("ms_ollama_hint"))
        else:
            col_name, col_key = st.columns([1, 2])
            with col_name:
                model_name = st.text_input(
                    get_text("ms_model_name"),
                    value=get_text(f"ms_default_model_{provider}"),
                    key="ms_model_name_input",
                )
            with col_key:
                api_key = st.text_input(get_text("ms_api_key"), type="password",
                                        key="ms_api_key_input")

            base_url = get_text(f"ms_base_url_{provider}")

            b_col1, b_col2, b_col3 = st.columns([1, 1, 2])
            with b_col1:
                do_test = st.button(get_text("ms_test_btn"), key="ms_test_btn")
            with b_col2:
                do_save = st.button(get_text("ms_save_btn"), type="primary", key="ms_save_btn")

            if do_test:
                if not (model_name.strip() and api_key.strip()):
                    st.warning(get_text("fill_fields"))
                else:
                    from intelnexus.core.llm.models import test_model_connection
                    ok, msg = test_model_connection(provider, {
                        "model_name": model_name.strip(),
                        "base_url": base_url,
                        "api_key": api_key.strip(),
                    })
                    if ok:
                        st.success(get_text("ms_test_ok"))
                    else:
                        st.error(f"{get_text('ms_test_fail')}: {localize_llm_test_error(msg)}")

            if do_save:
                if not (model_name.strip() and api_key.strip()):
                    st.warning(get_text("fill_fields"))
                else:
                    from intelnexus.core.llm.models import add_custom_model
                    if add_custom_model(model_name.strip(), provider, {
                        "model_name": model_name.strip(),
                        "base_url": base_url,
                        "api_key": api_key.strip(),
                    }):
                        st.session_state["model_setup_done"] = True
                        st.success(get_text("ms_saved"))
                        st.rerun()
                    else:
                        st.error(get_text("ms_save_fail"))

        if st.button(get_text("ms_dismiss"), key="ms_dismiss_btn"):
            st.session_state["model_setup_dismissed"] = True
            st.rerun()
