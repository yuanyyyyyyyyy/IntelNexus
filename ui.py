"""
IntelNexus - Web UI
==================
Multi-source network intelligence search interface.
Apple-inspired minimalist design.
"""

import base64
import streamlit as st
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from scrape import scrape_multiple

from report_export import export_report, get_export_formats
from web_search import get_web_results
from news_search import get_news_results
from social_search import get_social_results
from academic_search import get_academic_results
from darkweb_search import get_darkweb_results, is_available as darkweb_available

from llm_utils import BufferedStreamingHandler, get_model_choices
from llm import get_llm, refine_query, filter_results, generate_summary
from custom_models import add_custom_model, get_custom_model_names, remove_custom_model


LANG = {
    "zh": {
        "title": "IntelNexus",
        "subtitle": "多源网络情报分析平台",
        "search_placeholder": "输入搜索内容...",
        "search_button": "搜索",
        "search_mode": "搜索模式",
        "settings": "设置",
        "language": "语言",
        "llm_model": "AI模型",
        "threads": "线程数",
        "sources": "数据来源",
        "loading": "加载中...",
        "refining": "优化查询中...",
        "searching": "搜索中...",
        "filtering": "筛选中...",
        "scraping": "抓取内容...",
        "generating": "生成报告中...",
        "refined_query": "优化后的查询",
        "search_results": "搜索结果",
        "filtered_results": "筛选结果",
        "report_title": "情报报告",
        "download": "下载报告",
        "download_format": "下载格式",
        "complete": "完成",
        "darkweb_warning": "暗网搜索已启用",
        "mode_all": "全部来源",
        "mode_web": "网页搜索",
        "mode_news": "新闻资讯",
        "mode_social": "社交媒体",
        "mode_academic": "学术论文",
        "mode_darkweb": "暗网搜索",
        "results_count": "条结果",
        "zh": "中文",
        "en": "English",
        "add_custom_model": "添加自定义模型",
        "model_name": "模型名称",
        "model_type": "模型类型",
        "base_url": "Base URL (可选)",
        "api_key": "API密钥",
        "model_id": "模型ID",
        "add_model": "添加模型",
        "model_exists": "模型名称已存在或添加失败",
        "fill_fields": "请填写所有必填字段",
        "ok": "确定",
        "deleted": "已删除",
        "custom_models_list": "已添加的模型",
        "model_add_success": "模型已添加",
        "error": "错误",
        "download_ready": "准备下载",
        "download_failed": "下载失败",
        "pdf_ready": "PDF已准备",
        "word_ready": "Word已准备",
        "md_ready": "Markdown已准备",
        "ollama_base_url": "Ollama Base URL",
        "delete": "删除",
    },
    "en": {
        "title": "IntelNexus",
        "subtitle": "Multi-Source Network Intelligence Platform",
        "search_placeholder": "Enter search query...",
        "search_button": "Search",
        "search_mode": "Search Mode",
        "settings": "Settings",
        "language": "Language",
        "llm_model": "AI Model",
        "threads": "Threads",
        "sources": "Data Sources",
        "loading": "Loading...",
        "refining": "Refining query...",
        "searching": "Searching...",
        "filtering": "Filtering...",
        "scraping": "Scraping content...",
        "generating": "Generating report...",
        "refined_query": "Refined Query",
        "search_results": "Search Results",
        "filtered_results": "Filtered Results",
        "report_title": "Intelligence Report",
        "download": "Download",
        "download_format": "Format",
        "complete": "Complete",
        "darkweb_warning": "Dark web mode enabled",
        "mode_all": "All Sources",
        "mode_web": "Web Search",
        "mode_news": "News",
        "mode_social": "Social Media",
        "mode_academic": "Academic Papers",
        "mode_darkweb": "Dark Web",
        "results_count": "results",
        "zh": "Chinese",
        "en": "English",
        "add_custom_model": "Add Custom Model",
        "model_name": "Model Name",
        "model_type": "Model Type",
        "base_url": "Base URL (optional)",
        "api_key": "API Key",
        "model_id": "Model ID",
        "add_model": "Add Model",
        "model_exists": "Model name already exists or failed to add",
        "fill_fields": "Please fill all required fields",
        "ok": "OK",
        "deleted": "Deleted",
        "custom_models_list": "Custom Models",
        "model_add_success": "Model added",
        "error": "Error",
        "download_ready": "Ready to download",
        "download_failed": "Download failed",
        "pdf_ready": "PDF Ready",
        "word_ready": "Word Ready",
        "md_ready": "Markdown Ready",
        "ollama_base_url": "Ollama Base URL",
        "delete": "Delete",
    }
}

SEARCH_MODES = {
    "all": ["mode_all", "全部来源"],
    "web": ["mode_web", "网页搜索"],
    "news": ["mode_news", "新闻资讯"],
    "social": ["mode_social", "社交媒体"],
    "academic": ["mode_academic", "学术论文"],
    "darkweb": ["mode_darkweb", "暗网搜索"],
}


def get_text(key):
    lang_code = st.session_state.get("lang", "zh")
    return LANG.get(lang_code, LANG["zh"]).get(key, key)


@st.cache_data(ttl=200, show_spinner=False)
def cached_search(mode, refined_query, threads):
    results = []
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        
        if mode in ["web", "all"]:
            futures.append(executor.submit(get_web_results, refined_query, threads, 40))
        
        if mode in ["news", "all"]:
            futures.append(executor.submit(get_news_results, refined_query, 30))
        
        if mode in ["social", "all"]:
            futures.append(executor.submit(get_social_results, refined_query, 30))
        
        if mode in ["academic", "all"]:
            futures.append(executor.submit(get_academic_results, refined_query, 20))
        
        if mode in ["darkweb", "all"] and darkweb_available():
            futures.append(executor.submit(get_darkweb_results, refined_query, threads))
        
        for f in futures:
            try:
                results.extend(f.result())
            except Exception as e:
                print(f"Search error: {e}")
    
    return results


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape(filtered, threads):
    return scrape_multiple(filtered, max_workers=threads)


st.set_page_config(
    page_title="IntelNexus",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# Force Light theme
st.markdown("""
<style>
    /* Force Light Theme */
    .stApp {
        background-color: #FFFFFF !important;
        color: #1E1E1E !important;
    }
    [data-testid="stSidebar"] {
        background-color: #F5F5F5 !important;
    }
    div[data-testid="stMarkdownContainer"] {
        color: #1E1E1E !important;
    }
    .stTextInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #1E1E1E !important;
    }
    /* Remove dark theme gradient background */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
    .stDeployButton {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

if "lang" not in st.session_state:
    st.session_state.lang = "zh"

if "query_cache" not in st.session_state:
    st.session_state.query_cache = ""

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Text:wght@300;400;500;600&display=swap');
    
    :root {
        --morandi-bg: #E8E4DF;
        --morandi-sidebar: #DCD8D3;
        --morandi-card: #F5F2EE;
        --morandi-blue: #7B9CB5;
        --morandi-green: #8FA890;
        --morandi-pink: #C4A4A4;
        --morandi-peach: #D4A5A5;
        --morandi-text: #5C5C5C;
        --morandi-text-light: #8A8A8A;
        --morandi-border: #C9C5C0;
        --morandi-accent: #9CB5B0;
    }
    
    #stDecoration {
        display: none !important;
    }
    
    * {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif !important;
    }
    
    .stApp {
        background: var(--morandi-bg);
    }
    
    div[data-testid="stSidebar"] {
        background: var(--morandi-sidebar);
        border-right: 1px solid var(--morandi-border);
    }
    
    .sidebar-title {
        font-size: 20px;
        font-weight: 600;
        color: var(--morandi-text);
        padding: 20px 16px 10px;
    }
    
    .sidebar-subtitle {
        font-size: 13px;
        color: var(--morandi-text-light);
        padding: 0 16px 20px;
    }
    
    .main-title {
        font-size: 40px;
        font-weight: 600;
        color: var(--morandi-text);
        letter-spacing: -0.02em;
    }
    
    .main-subtitle {
        font-size: 19px;
        font-weight: 400;
        color: var(--morandi-text-light);
        margin-top: 4px;
    }
    
    .search-input input {
        border-radius: 14px !important;
        border: 1px solid var(--morandi-border) !important;
        padding: 14px 18px !important;
        font-size: 17px !important;
        background: #FFFFFF !important;
        color: var(--morandi-text) !important;
        transition: all 0.3s ease !important;
    }
    
    .search-input input:focus {
        border-color: var(--morandi-blue) !important;
        box-shadow: 0 0 0 3px rgba(123, 156, 181, 0.15) !important;
        outline: none !important;
    }
    
    .search-input input::placeholder {
        color: var(--morandi-text-light) !important;
    }
    
    .search-button button {
        border-radius: 14px !important;
        background: var(--morandi-blue) !important;
        border: none !important;
        padding: 14px 28px !important;
        font-size: 17px !important;
        font-weight: 500 !important;
        color: #FFFFFF !important;
        transition: all 0.3s ease !important;
    }
    
    .search-button button:hover {
        background: #6B8BA5 !important;
        transform: translateY(-1px);
    }
    
    .search-button button:active {
        transform: scale(0.98) translateY(0);
    }
    
    div[data-testid="stRadio"] > div {
        gap: 8px;
    }
    
    div[data-testid="stRadio"] label {
        border-radius: 12px !important;
        padding: 12px 16px !important;
        background: var(--morandi-sidebar) !important;
        border: 1px solid transparent !important;
        transition: all 0.2s ease !important;
        color: var(--morandi-text) !important;
    }
    
    div[data-testid="stRadio"] label:hover {
        background: var(--morandi-sidebar) !important;
    }
    
    div[data-testid="stRadio"] input:checked + div {
        background: var(--morandi-sidebar) !important;
        border-color: transparent !important;
        color: var(--morandi-text) !important;
    }
    
    div[data-testid="stSelectbox"] > div {
        background: var(--morandi-sidebar) !important;
        border: 1px solid var(--morandi-border) !important;
        border-radius: 12px !important;
    }
    
    div[data-testid="stSelectbox"] > div:focus-within {
        border-color: var(--morandi-border) !important;
        box-shadow: none !important;
    }
    
    .lang-switch {
        display: flex;
        gap: 8px;
        padding: 12px 16px;
    }
    
    .lang-btn {
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 13px;
        cursor: pointer;
        border: 1px solid var(--morandi-border);
        background: var(--morandi-card);
        color: var(--morandi-text);
        transition: all 0.2s;
    }
    
    .lang-btn:hover {
        background: #E5E1DC;
    }
    
    .lang-btn.active {
        background: var(--morandi-green);
        color: #FFFFFF;
        border-color: var(--morandi-green);
    }
    
    .result-card {
        background: var(--morandi-card);
        border-radius: 18px;
        padding: 24px;
        margin: 16px 0;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        border: 1px solid var(--morandi-border);
    }
    
    .result-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--morandi-text);
        margin-bottom: 8px;
    }
    
    .result-stats {
        display: flex;
        gap: 16px;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--morandi-border);
    }
    
    .stat-item {
        text-align: center;
    }
    
    .stat-value {
        font-size: 24px;
        font-weight: 600;
        color: var(--morandi-text);
    }
    
    .stat-label {
        font-size: 12px;
        color: var(--morandi-text-light);
        margin-top: 4px;
    }
    
    .report-section {
        background: var(--morandi-card);
        border-radius: 18px;
        padding: 24px;
        margin: 16px 0;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        border: 1px solid var(--morandi-border);
    }
    
    .report-title {
        font-size: 22px;
        font-weight: 600;
        color: var(--morandi-text);
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--morandi-border);
    }
    
    .download-btn {
        display: inline-block;
        padding: 12px 24px;
        background: var(--morandi-green);
        border-radius: 12px;
        color: #FFFFFF;
        text-decoration: none;
        font-weight: 500;
        transition: all 0.3s;
    }
    
    .download-btn:hover {
        background: #7F9680;
        transform: translateY(-1px);
    }
    
    .section-header {
        font-size: 13px;
        font-weight: 600;
        color: var(--morandi-text-light);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
    }
    
    div.stButton > button {
        border-radius: 12px;
    }
    
    div[data-testid="stSelectbox"] > div > div {
        border-radius: 12px;
    }
    
    div[data-testid="stSlider"] > div > div {
        border-radius: 12px;
    }
    
    .stSuccess {
        background: var(--morandi-green);
        color: #FFFFFF;
        border-radius: 12px;
    }
    
    .stSpinner > div > div {
        border-top-color: var(--morandi-blue);
    }
    
    div[data-testid="stMarkdownContainer"] p {
        color: var(--morandi-text);
    }
    
    .stTextInput > div > div > input {
        border-radius: 14px !important;
    }
    
    header {
        background: none !important;
    }
    
    [data-testid="stHeaderContainer"] {
        background: var(--morandi-bg) !important;
    }
    
    div[data-testid="stHeaderContainer"]::before {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("search_mode")}</div>', unsafe_allow_html=True)
    
    mode_options = list(SEARCH_MODES.keys())
    search_mode = st.radio(
        "mode",
        mode_options,
        format_func=lambda x: get_text(SEARCH_MODES[x][0]),
        label_visibility="collapsed",
        index=0
    )

    if search_mode == "darkweb" and not darkweb_available():
        st.warning(get_text("darkweb_warning"))

    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("settings")}</div>', unsafe_allow_html=True)

    model_options = get_model_choices()
    default_model = "qwen2.5:7b" if "qwen2.5:7b" in model_options else (model_options[0] if model_options else "gpt-4o")
    model_index = model_options.index(default_model) if default_model in model_options else 0

    model = st.selectbox(get_text("llm_model"), model_options, index=model_index)
    threads = st.slider(get_text("threads"), 1, 16, 5)
    
    # 语言切换 - 在设置中
    lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
    current_lang_display = get_text("zh") if st.session_state.lang == "zh" else get_text("en")
    selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()), 
                                  index=0 if st.session_state.lang == "zh" else 1, 
                                  key="lang_selector")
    if lang_options.get(selected_lang) != st.session_state.lang:
        st.session_state.lang = lang_options[selected_lang]
        st.rerun()
    
    # 自定义模型管理
    st.markdown("---")
    with st.expander(get_text("add_custom_model")):
        col_name, col_type = st.columns(2)
        with col_name:
            custom_model_name = st.text_input(
                get_text("model_name"),
                key="custom_model_name"
            )
        with col_type:
            model_type = st.selectbox(
                get_text("model_type"),
                [
                    "OpenAI", "Azure OpenAI", "Anthropic", "Google", "Cohere", 
                    "Mistral", "DeepSeek", "Ollama", "通义千问", "智谱AI", 
                    "百度文心一言", "讯飞星火", "Moonshot", "01.AI"
                ],
                key="model_type_selector"
            )
        
        if model_type == "OpenAI":
            base_url = st.text_input(get_text("base_url"))
            api_key = st.text_input(get_text("api_key"), type="password", key="openai_api_key")
            model_id = st.text_input(get_text("model_id"))
        elif model_type == "Anthropic":
            api_key = st.text_input(get_text("api_key"), type="password", key="anthropic_api_key")
            model_id = st.text_input(get_text("model_id"))
        elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
            api_key = st.text_input(get_text("api_key"), type="password", key=f"{model_type.lower()}_api_key")
            base_url = st.text_input(get_text("base_url"), key=f"{model_type.lower()}_base_url")
            model_id = st.text_input(get_text("model_id"))
        else:  # Ollama
            base_url = st.text_input(get_text("ollama_base_url"), value="http://127.0.0.1:11434", key="ollama_base_url")
            api_key = None
            model_id = st.text_input(get_text("model_name"))
        
        if st.button(get_text("add_model")):
            if custom_model_name and model_id:
                config = {"model_name": model_id}
                if model_type in ["OpenAI", "Azure OpenAI"]:
                    if base_url:
                        config["base_url"] = base_url
                    if api_key:
                        config["api_key"] = api_key
                elif model_type == "Anthropic":
                    if api_key:
                        config["api_key"] = api_key
                elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
                    if api_key:
                        config["api_key"] = api_key
                    if base_url:
                        config["base_url"] = base_url
                else:  # Ollama
                    config["base_url"] = base_url
                
                if add_custom_model(custom_model_name, model_type.lower(), config):
                    st.success(get_text("model_add_success"))
                    st.rerun()
                else:
                    st.error(get_text("model_exists"))
            else:
                st.error(get_text("fill_fields"))
    
    # 显示已添加的自定义模型
    custom_models = get_custom_model_names()
    if custom_models:
        with st.expander(get_text("custom_models_list")):
            for custom_model in custom_models:
                col_model, col_delete = st.columns([3, 1])
                with col_model:
                    st.write(custom_model)
                with col_delete:
                    if st.button(get_text("delete"), key=f"delete_{custom_model}"):
                        if remove_custom_model(custom_model):
                            st.success(get_text("deleted"))
                            st.rerun()

    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("download_format")}</div>', unsafe_allow_html=True)
    
    # 初始化下载格式
    if "sidebar_download_format" not in st.session_state:
        st.session_state.sidebar_download_format = "md"
    
    # 初始化下载状态（用于解决页面消失问题）
    if "download_ready" not in st.session_state:
        st.session_state.download_ready = False
    if "download_data" not in st.session_state:
        st.session_state.download_data = None
    if "download_filename" not in st.session_state:
        st.session_state.download_filename = None
    if "download_mime" not in st.session_state:
        st.session_state.download_mime = None
    
    format_options = ["md", "pdf", "docx", "xlsx"]
    format_labels = {
        "md": "Markdown",
        "pdf": "PDF",
        "docx": "Word",
        "xlsx": "Excel"
    }
    
    sidebar_format = st.selectbox(
        "选择下载格式",
        format_options,
        format_func=lambda x: format_labels[x],
        label_visibility="collapsed",
        key="sidebar_format_select"
    )
    st.session_state.sidebar_download_format = sidebar_format
    
    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("sources")}</div>', unsafe_allow_html=True)
    st.caption("Semantic Scholar, RSS, Reddit, Bing")


col1, col2 = st.columns([8, 2])
with col1:
    st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

with st.form("search_form", clear_on_submit=False):
    col_input, col_button = st.columns([10, 1])
    with col_input:
        query = st.text_input(
            "query",
            placeholder=get_text("search_placeholder"),
            label_visibility="collapsed",
            key="query_input"
        )
    with col_button:
        run_button = st.form_submit_button(get_text("search_button"))

status_slot = st.empty()

# 搜索逻辑
if run_button and query:
    # 保存搜索词到session_state
    st.session_state.query_cache = query
    st.session_state.search_mode_cache = search_mode
    st.session_state.threads_cache = threads
    st.session_state.model_cache = model
    
    # 清空之前的搜索结果
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
        st.session_state.pop(k, None)
    
    with status_slot.container():
        with st.spinner(get_text("loading")):
            llm = get_llm(model)
    
    with status_slot.container():
        with st.spinner(get_text("refining")):
            st.session_state.refined = refine_query(llm, query)
    
    st.markdown(f"""
    <div class="result-card">
        <div class="section-header">{get_text("refined_query")}</div>
        <div class="result-title">{st.session_state.refined}</div>
    </div>
    """, unsafe_allow_html=True)
    
    with status_slot.container():
        with st.spinner(get_text("searching")):
            st.session_state.results = cached_search(search_mode, st.session_state.refined, threads)
    
    source_counts = {}
    for r in st.session_state.results:
        src = r.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    
    results_count = len(st.session_state.results)
    
    st.markdown(f"""
    <div class="result-card">
        <div class="result-stats">
            <div class="stat-item">
                <div class="stat-value">{results_count}</div>
                <div class="stat-label">{get_text("results_count")}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with status_slot.container():
        with st.spinner(get_text("filtering")):
            st.session_state.filtered = filter_results(llm, st.session_state.refined, st.session_state.results)
    
    with status_slot.container():
        with st.spinner(get_text("scraping")):
            st.session_state.scraped = cached_scrape(st.session_state.filtered, threads)
    
    st.session_state.streamed_summary = ""
    
    def ui_emit(chunk):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)
    
    st.markdown(f"""
    <div class="report-section">
        <div class="report-title">{get_text("report_title")}</div>
    </div>
    """, unsafe_allow_html=True)
    summary_slot = st.empty()
    
    with status_slot.container():
        with st.spinner(get_text("generating")):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, st.session_state.scraped)
    
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    st.session_state.report_timestamp = now
    
    # 标记搜索已完成
    st.session_state.search_completed = True
    st.session_state.status_slot = "complete"
    st.session_state.export_format_choice = "md"
    
    status_slot.success(get_text("complete"))


# 显示搜索结果和下载区域（独立于run_button）
if st.session_state.get("search_completed", False) and st.session_state.get("streamed_summary"):
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 获取sidebar中选择的下载格式
    download_format = st.session_state.get('sidebar_download_format', 'md')
    format_labels_display = {"md": "Markdown", "pdf": "PDF", "docx": "Word", "xlsx": "Excel"}
    
    st.info(f"下载格式: **{format_labels_display.get(download_format)}**")
    
    # 直接生成并下载，不使用rerun
    if st.button(get_text("download"), use_container_width=True, key="download_btn"):
        from pathlib import Path
        
        try:
            filename = f"report_{st.session_state.report_timestamp}"
            if download_format == 'pdf':
                from report_export import export_pdf
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
                except:
                    pass
                
            elif download_format == 'docx':
                from report_export import export_word
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
                except:
                    pass
                
            elif download_format == 'xlsx':
                from report_export import export_excel
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
                except:
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
    
    # 显示搜索结果实际内容
    if st.session_state.get("filtered") and len(st.session_state.get("filtered", [])) > 0:
        st.markdown("---")
        st.markdown(f'<div class="report-title">📋 搜索结果详情 ({len(st.session_state.filtered)}条)</div>', unsafe_allow_html=True)
        
        # 按来源分组显示
        source_groups = {}
        for item in st.session_state.filtered:
            source = item.get("source", "Unknown")
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(item)
        
        for source, items in source_groups.items():
            with st.expander(f"📌 {source} ({len(items)}条)", expanded=False):
                for i, item in enumerate(items):
                    st.markdown(f"**{i+1}. {item.get('title', '无标题')[:100]}**")
                    if item.get('description'):
                        st.markdown(f"📝 {item.get('description', '')[:300]}...")
                    elif item.get('summary'):
                        st.markdown(f"📝 {item.get('summary', '')[:300]}...")
                    if item.get('link') or item.get('url'):
                        link = item.get('link') or item.get('url')
                        st.markdown(f"🔗 [查看原文]({link})")
                    st.markdown("---")
