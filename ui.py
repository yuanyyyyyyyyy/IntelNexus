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


from report_export import export_report, get_export_formats
from web_search import get_web_results
from academic_search import get_academic_results
from news_search import get_news_results
from social_search import get_social_results
from darkweb_search import get_darkweb_results, is_available as darkweb_available

from llm_utils import BufferedStreamingHandler, get_model_choices
from llm import get_llm, refine_query, filter_results, generate_summary


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
        "darkweb_warning": "暗网模式已禁用，可在.env中启用",
        "mode_all": "全部来源",
        "mode_web": "网页搜索",
        "mode_academic": "学术论文",
        "mode_news": "新闻资讯",
        "mode_social": "社交媒体",
        "mode_darkweb": "暗网搜索",
        "results_count": "条结果",
        "zh": "中文",
        "en": "English",
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
        "darkweb_warning": "Dark web mode disabled. Enable in .env",
        "mode_all": "All Sources",
        "mode_web": "Web Search",
        "mode_academic": "Academic Papers",
        "mode_news": "News",
        "mode_social": "Social Media",
        "mode_darkweb": "Dark Web",
        "results_count": "results",
        "zh": "中文",
        "en": "English",
    }
}

SEARCH_MODES = {
    "all": ["mode_all", "All Sources"],
    "web": ["mode_web", "Web Search"],
    "academic": ["mode_academic", "Academic Papers"],
    "news": ["mode_news", "News"],
    "social": ["mode_social", "Social Media"],
    "darkweb": ["mode_darkweb", "Dark Web"],
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
            futures.append(executor.submit(get_web_results, refined_query, threads, 20))
        
        if mode in ["academic", "all"]:
            futures.append(executor.submit(get_academic_results, refined_query, 15))
        
        if mode in ["news", "all"]:
            futures.append(executor.submit(get_news_results, refined_query, 15))
        
        if mode in ["social", "all"]:
            futures.append(executor.submit(get_social_results, refined_query, 15))
        
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

if "lang" not in st.session_state:
    st.session_state.lang = "zh"

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
        background: var(--morandi-card) !important;
        border: 1px solid transparent !important;
        transition: all 0.2s ease !important;
        color: var(--morandi-text) !important;
    }
    
    div[data-testid="stRadio"] label:hover {
        background: #EAE7E2 !important;
    }
    
    div[data-testid="stRadio"] input:checked + div {
        background: var(--morandi-blue) !important;
        border-color: var(--morandi-blue) !important;
        color: #FFFFFF !important;
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
    current_lang_display = "中文" if st.session_state.lang == "zh" else "English"
    selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()), 
                                  index=0 if st.session_state.lang == "zh" else 1, 
                                  key="lang_selector")
    if lang_options.get(selected_lang) != st.session_state.lang:
        st.session_state.lang = lang_options[selected_lang]
        st.rerun()

    st.markdown("---")
    st.markdown(f'<div class="section-header">{get_text("sources")}</div>', unsafe_allow_html=True)
    st.caption("ArXiv, Semantic Scholar, RSS, Reddit, Bing")


col1, col2 = st.columns([8, 2])
with col1:
    st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)

with st.form("search_form", clear_on_submit=True):
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

if run_button and query:
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
    
    # 创建两列：格式选择和下载按钮
    col_format, col_download = st.columns([2, 3])
    
    with col_format:
        available_formats = get_export_formats()
        download_format = st.selectbox(
            get_text("download_format"), 
            available_formats,
            index=0,
            key="export_format"
        )
    
    with col_download:
        if st.button("📥 " + get_text("download"), use_container_width=True, key="download_btn"):
            # 生成文件内容
            import io
            from pathlib import Path
            
            try:
                filename = f"report_{now}"
                if download_format == 'pdf':
                    from report_export import export_pdf
                    buffer = io.BytesIO()
                    pdf_path = export_pdf(st.session_state.streamed_summary, st.session_state.refined, filename)
                    with open(pdf_path, 'rb') as f:
                        buffer = io.BytesIO(f.read())
                    st.download_button(
                        label="✓ PDF已准备",
                        data=buffer,
                        file_name=f"{filename}.pdf",
                        mime="application/pdf",
                        disabled=True
                    )
                    Path(pdf_path).unlink()  # 删除临时文件
                    st.success("PDF已下载！")
                    
                elif download_format == 'docx':
                    from report_export import export_word
                    buffer = io.BytesIO()
                    docx_path = export_word(st.session_state.streamed_summary, st.session_state.refined, filename)
                    with open(docx_path, 'rb') as f:
                        buffer = io.BytesIO(f.read())
                    st.download_button(
                        label="✓ Word已准备",
                        data=buffer,
                        file_name=f"{filename}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        disabled=True
                    )
                    Path(docx_path).unlink()  # 删除临时文件
                    st.success("Word已下载！")
                    
                else:  # markdown
                    b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
                    href = f'<a href="data:file/markdown;base64,{b64}" download="{filename}.md">✓ Markdown已准备</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("Markdown已下载！")
            except Exception as e:
                st.error(f"下载失败: {str(e)}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    status_slot.success(get_text("complete"))
