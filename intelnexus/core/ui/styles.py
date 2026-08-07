import streamlit as st


def render_light_theme_css():
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
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
    .stDeployButton {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)


def render_morandi_theme_css():
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
        background: #F0F2F5 !important;
        border-right: 1px solid #E5E7EB !important;
    }

    .sidebar-title {
        font-size: 18px !important;
        font-weight: 700 !important;
        color: #1F2937 !important;
        padding: 20px 16px 12px !important;
        letter-spacing: -0.01em !important;
    }

    .sidebar-subtitle {
        display: none !important;
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

    .main-guidance {
        font-size: 13px;
        font-weight: 400;
        color: var(--morandi-text-light);
        margin-top: 6px;
        opacity: 0.85;
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

    /* Fix selectbox dropdown z-index */
    div[data-testid="stSidebar"] {
        overflow: visible !important;
    }

    div[data-testid="stSidebar"] section {
        overflow: visible !important;
    }

    div[data-testid="stSelectbox"] {
        pointer-events: auto !important;
    }

    div[data-testid="stSelectbox"] ul,
    div[data-testid="stSelectbox"] [role="listbox"],
    div[data-testid="stSelectbox"] [data-baseweb="popover"],
    div[data-testid="stSelectbox"] [data-baseweb="menu"] {
        z-index: 999999 !important;
        position: relative !important;
        pointer-events: auto !important;
    }

    /* === Briefing Welcome Page Styles === */
    .briefing-step-card {
        background: #FFFFFF;
        border: 1px solid var(--morandi-border);
        border-radius: 14px;
        padding: 20px 16px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: all 0.25s ease;
    }

    .briefing-step-card:hover {
        box-shadow: 0 4px 16px rgba(123,156,181,0.12);
        transform: translateY(-2px);
    }

    .step-num {
        display: inline-block;
        width: 28px;
        height: 28px;
        line-height: 28px;
        background: var(--morandi-blue);
        color: #FFFFFF;
        border-radius: 50%;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 12px;
    }

    .step-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--morandi-text);
        margin: 8px 0 6px;
    }

    .step-desc {
        font-size: 13px;
        color: var(--morandi-text-light);
        line-height: 1.6;
        margin: 0;
    }

    .briefing-tip-box {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        background: rgba(123,156,181,0.08);
        border-radius: 10px;
        padding: 16px 20px;
        margin-top: 24px;
    }

    .tip-accent {
        width: 3px;
        height: auto;
        min-height: 40px;
        background: var(--morandi-blue);
        border-radius: 2px;
        flex-shrink: 0;
    }

    .tip-content {
        color: var(--morandi-text-light);
        font-size: 14px;
        line-height: 1.65;
        margin: 0;
    }

    /* === Briefing Config Panel (inside Tab) === */
    .briefing-config-panel {
        background: linear-gradient(135deg, rgba(123,156,181,0.04) 0%, rgba(143,168,144,0.04) 100%);
        border: 1px solid var(--morandi-border);
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0 24px 0;
    }

    .briefing-config-header {
        font-size: 16px;
        font-weight: 600;
        color: var(--morandi-text);
        margin: 0 0 12px 0;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(201,197,192,0.5);
        letter-spacing: 0.3px;
    }

    .briefing-config-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--morandi-border), transparent);
        margin: 20px 0;
    }

    /* === Status Dot (replaces emoji) === */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        vertical-align: middle;
    }

    .status-dot.active {
        background: #4a9d5f;
        box-shadow: 0 0 0 3px rgba(74,157,95,0.15);
    }

    .status-dot.error {
        background: #c94a4a;
        box-shadow: 0 0 0 3px rgba(201,74,74,0.15);
    }

    /* === Sidebar Workbench Theme (cold-gray, compact) === */
    .sb-section {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 20px 0 10px;
        padding: 0 4px;
    }

    .sb-section::before {
        content: '';
        display: block;
        width: 3px;
        height: 14px;
        background: #0366D6;
        border-radius: 2px;
        flex-shrink: 0;
    }

    .sb-section__label {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6B7280;
    }

    /* Sidebar divider — subtle */
    .sb-divider {
        height: 1px;
        background: #E5E7EB;
        margin: 16px 0;
        border: none;
    }

    /* Sidebar buttons: clean, no rounded pills */
    [data-testid="stSidebar"] button[kind="secondary"] {
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        border: 1px solid #D1D5DB !important;
        background: #FFFFFF !important;
        color: #374151 !important;
        padding: 8px 16px !important;
        transition: all 0.15s ease !important;
    }

    [data-testid="stSidebar"] button[kind="secondary"]:hover {
        border-color: #0366D6 !important;
        color: #0366D6 !important;
        background: #F6F8FA !important;
    }

    /* Primary action buttons in sidebar */
    .sb-action-primary {
        width: 100% !important;
        padding: 12px 20px !important;
        background: #0366D6 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
    }

    .sb-action-primary:hover {
        background: #0550AE !important;
    }

    .sb-action-secondary {
        width: 100% !important;
        padding: 10px 20px !important;
        background: transparent !important;
        color: #6B7280 !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
    }

    .sb-action-secondary:hover {
        background: #F6F8FA !important;
        color: #374151 !important;
    }

    /* Expander in sidebar: clean */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
    }

    /* Function Tag Bar Panel — the signature element */
    .bf-panel {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-left: 4px solid var(--wb-tag-source);
        border-radius: 6px;
        padding: 20px 24px;
        margin: 12px 0;
        transition: border-color 0.15s ease;
    }

    .bf-panel:hover {
        border-color: #B0B7C3;
    }

    .bf-panel.bf-panel--source {
        border-left-color: var(--wb-tag-source);
    }

    .bf-panel.bf-panel--sub {
        border-left-color: var(--wb-tag-sub);
    }

    .bf-panel.bf-panel--gen {
        border-left-color: var(--wb-tag-gen);
    }

    .bf-panel.bf-panel--cat {
        border-left-color: var(--wb-tag-cat);
    }

    /* Onboarding 3-step bar */
    .bf-step {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-left: 3px solid var(--wb-border);
        border-radius: 6px;
        padding: 12px 14px;
        height: 100%;
        min-height: 84px;
        transition: border-color 0.15s ease, background 0.15s ease;
    }
    .bf-step__head {
        font-size: 13px;
        font-weight: 600;
        color: var(--wb-text-primary);
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .bf-step__index {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        font-size: 11px;
        font-weight: 700;
        flex-shrink: 0;
        background: #EAECEF;
        color: var(--wb-text-secondary);
    }
    .bf-step__desc {
        font-size: 12px;
        color: var(--wb-text-secondary);
        margin-top: 8px;
        line-height: 1.5;
    }
    /* State variants */
    .bf-step--done {
        border-left-color: var(--wb-tag-sub);
        background: #F4FBF5;
    }
    .bf-step--done .bf-step__index {
        background: var(--wb-tag-sub);
        color: #FFFFFF;
    }
    .bf-step--current {
        border-left-color: var(--wb-accent);
        background: #F0F6FF;
    }
    .bf-step--current .bf-step__index {
        background: var(--wb-accent);
        color: #FFFFFF;
    }
    .bf-step--pending {
        border-left-color: var(--wb-border);
        opacity: 0.85;
    }

    /* Section Label: uppercase + color-coded */
    .bf-label {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #EBEEF2;
    }

    .bf-label__tag {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--wb-text-secondary);
        background: #F0F2F5;
        padding: 3px 8px;
        border-radius: 3px;
    }

    .bf-label__title {
        font-size: 15px;
        font-weight: 600;
        color: var(--wb-text-primary);
        margin: 0;
    }

    /* Generate button: full-width, high visual weight */
    .bf-generate-btn {
        width: 100%;
        padding: 14px 24px;
        background: var(--wb-accent) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        cursor: pointer;
        transition: background 0.15s ease !important;
    }

    .bf-generate-btn:hover {
        background: #0550AE !important;
    }

    /* Output area: clean, no tag bar */
    .bf-output {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-radius: 6px;
        padding: 20px 24px;
        margin: 12px 0;
    }

    .bf-output__header {
        font-size: 13px;
        font-weight: 600;
        color: var(--wb-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 1px solid #EBEEF2;
    }

    /* Empty state: action-oriented */
    .bf-empty {
        text-align: center;
        padding: 32px 16px;
        color: var(--wb-text-secondary);
        font-size: 14px;
    }

    .bf-empty__action {
        display: inline-block;
        margin-top: 10px;
        color: var(--wb-accent);
        font-weight: 500;
        cursor: pointer;
    }

    .bf-empty__action:hover {
        text-decoration: underline;
    }

    /* History list item */
    .bf-history-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 0;
        border-bottom: 1px solid #F0F2F5;
    }

    .bf-history-item:last-child {
        border-bottom: none;
    }

    /* Download buttons in output area */
    .bf-download-btn {
        display: inline-block;
        padding: 8px 18px;
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-radius: 6px;
        color: var(--wb-accent);
        font-size: 13px;
        font-weight: 500;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.15s ease;
        margin-right: 8px;
    }

    .bf-download-btn:hover {
        background: var(--wb-hover);
        border-color: var(--wb-accent);
    }
</style>
""", unsafe_allow_html=True)


def render_workbench_css():
    """Workbench theme for Briefing Center tab (Morandi soft palette)."""
    st.markdown("""
<style>
    /* 隐藏定位标记 */
    .bf-workbench-scope {
        display: none !important;
    }

    /* 通过 :has() 将 workbench 样式限定到包含标记的简报 Tab panel */
    div[role="tabpanel"]:has(.bf-workbench-scope) {
        --wb-surface: #FFFFFF;
        --wb-card: #FFFFFF;
        --wb-text-primary: #4A4540;
        --wb-text-secondary: #8C857D;
        --wb-accent: #A3A89B;
        --wb-border: #E2DDD5;
        --wb-tag-source: #A7B0AE;
        --wb-tag-sub: #A9B59A;
        --wb-tag-gen: #A6B2BC;
        --wb-tag-cat: #B7A6B0;
        --wb-hover: #ECE7DF;
        background: var(--wb-surface) !important;
        padding: 0 20px 16px 20px !important;
    }

    /* 去掉简报 Tab 内 .stMarkdown 容器自带的背景 / padding / margin */
    div[role="tabpanel"]:has(.bf-workbench-scope) .stMarkdown {
        background: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Override page title for workbench context */
    div[role="tabpanel"]:has(.bf-workbench-scope) .main-title {
        font-size: 28px !important;
        font-weight: 700 !important;
        color: var(--wb-text-primary) !important;
        letter-spacing: -0.02em !important;
        margin-bottom: 4px !important;
    }

    div[role="tabpanel"]:has(.bf-workbench-scope) .main-subtitle {
        display: none !important;
    }

    /* Function Tag Bar Panel */
    .bf-panel {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-top: 3px solid var(--wb-tag-source);
        border-radius: 8px;
        padding: 20px 24px;
        margin: 12px 0;
        box-shadow: 0 1px 3px rgba(90,80,70,0.05);
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }

    .bf-panel:hover {
        border-color: #D2CABC;
        box-shadow: 0 2px 8px rgba(90,80,70,0.10);
    }

    .bf-panel.bf-panel--source { border-top-color: var(--wb-tag-source); }
    .bf-panel.bf-panel--sub { border-top-color: var(--wb-tag-sub); }
    .bf-panel.bf-panel--gen { border-top-color: var(--wb-tag-gen); }
    .bf-panel.bf-panel--cat { border-top-color: var(--wb-tag-cat); }

    /* Onboarding 3-step bar */
    .bf-step {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-top: 3px solid var(--wb-border);
        border-radius: 8px;
        padding: 12px 14px;
        height: 100%;
        min-height: 84px;
        box-shadow: 0 1px 2px rgba(90,80,70,0.04);
        transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
    }
    .bf-step__head {
        font-size: 13px;
        font-weight: 600;
        color: var(--wb-text-primary);
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .bf-step__index {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        font-size: 11px;
        font-weight: 700;
        flex-shrink: 0;
        background: #DED8CE;
        color: var(--wb-text-secondary);
    }
    .bf-step__desc {
        font-size: 12px;
        color: var(--wb-text-secondary);
        margin-top: 8px;
        line-height: 1.5;
    }
    /* State variants */
    .bf-step--done {
        border-top-color: var(--wb-tag-sub);
        background: #EBF0E4;
    }
    .bf-step--done .bf-step__index {
        background: var(--wb-tag-sub);
        color: #FFFFFF;
    }
    .bf-step--current {
        border-top-color: var(--wb-accent);
        background: #E8ECEE;
    }
    .bf-step--current .bf-step__index {
        background: var(--wb-accent);
        color: #FFFFFF;
    }
    .bf-step--pending {
        border-top-color: var(--wb-border);
        opacity: 0.85;
    }

    /* 引导条：st.button 即卡片（去掉透明叠加层，help 作唯一悬停提示）
       本列含隐藏 marker(.bf-step-marker.状态)，经 :has() 给同列 button 上卡片样式 */
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button {
        width: 100%;
        text-align: left;
        justify-content: flex-start;
        align-items: center;
        gap: 8px;
        border: 1px solid var(--wb-border);
        border-top: 3px solid var(--wb-border);
        border-radius: 8px;
        padding: 12px 14px;
        min-height: 84px;
        background: var(--wb-card);
        box-shadow: 0 1px 2px rgba(90,80,70,0.04);
        transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
        font-size: 13px;
        font-weight: 600;
        color: var(--wb-text-primary);
        display: flex;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button:hover {
        box-shadow: 0 2px 8px rgba(90,80,70,0.12);
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button .bf-step__index {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        font-size: 11px;
        font-weight: 700;
        flex-shrink: 0;
        background: #DED8CE;
        color: var(--wb-text-secondary);
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button .bf-step__title {
        line-height: 1.4;
    }
    /* 三态配色（边框顶部色条 + 背景） */
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--done) [data-testid="stButton"] > button {
        border-top-color: var(--wb-tag-sub);
        background: #EBF0E4;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--done) [data-testid="stButton"] > button .bf-step__index {
        background: var(--wb-tag-sub);
        color: #FFFFFF;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--current) [data-testid="stButton"] > button {
        border-top-color: var(--wb-accent);
        background: #E8ECEE;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--current) [data-testid="stButton"] > button .bf-step__index {
        background: var(--wb-accent);
        color: #FFFFFF;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--pending) [data-testid="stButton"] > button {
        border-top-color: var(--wb-border);
        opacity: 0.85;
    }

    /* 可折叠配置区：tab 面板透明，避免双层卡片背景 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .stTabs [data-baseweb="tab-panel"] {
        background: transparent !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    /* tab 内 .bf-panel 收敛外边距与顶部彩色条，避免与 tab 重复 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .stTabs .bf-panel {
        margin: 8px 0 0 0 !important;
        border-top-width: 3px !important;
    }

    /* 配置区外层由 expander 改为 toggle + container，补区块间距与轻量边界 */
    div[role="tabpanel"]:has(.bf-workbench-scope) > div[data-testid="stVerticalBlock"] > div[data-testid="stToggle"] {
        margin-top: 18px !important;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .stContainer {
        border: 1px solid var(--wb-border);
        border-radius: 8px;
        padding: 14px 16px 4px 16px;
        margin-top: 6px;
        background: var(--wb-surface);
    }

    /* Section label as card header (merged into .bf-panel, no separate divider) */
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 0;
        padding-bottom: 0;
        border-bottom: none;
    }
    /* 标题头与首个 expander 之间拉开间距，整块视觉为「一张卡片」 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label + [data-testid="stExpander"],
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label + div [data-testid="stExpander"] {
        margin-top: 14px;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label {
        margin-bottom: 4px;
    }

    .bf-label__tag {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--wb-text-secondary);
        background: #E6E0D8;
        padding: 3px 8px;
        border-radius: 3px;
        flex-shrink: 0;
    }

    .bf-label__title {
        font-size: 15px;
        font-weight: 600;
        color: var(--wb-text-primary);
        margin: 0;
    }

    /* Primary generate button: full-width, prominent */
    div[role="tabpanel"]:has(.bf-workbench-scope) div[data-testid="stButton"] > button[kind="primary"],
    .bf-generate-btn-wrapper div[data-testid="stButton"] > button {
        width: 100% !important;
        padding: 14px 24px !important;
        background: var(--wb-accent) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        transition: background 0.15s ease !important;
    }

    .bf-generate-btn-wrapper div[data-testid="stButton"] > button:hover {
        background: #8E938A !important;
        transform: none !important;
    }

    /* Output area */
    .bf-output {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-top: 3px solid var(--wb-accent);
        border-radius: 8px;
        padding: 20px 24px;
        margin: 12px 0;
        box-shadow: 0 1px 3px rgba(90,80,70,0.05);
    }

    .bf-output__header {
        font-size: 13px;
        font-weight: 600;
        color: var(--wb-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 1px solid #E2DDD5;
    }

    /* Override expander styling in workbench:
       make expanders look like inner sections of ONE card, not separate cards */
    .bf-panel [data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }

    /* the inner <details> still draws its own border/background — kill it */
    .bf-panel [data-testid="stExpander"] details,
    .bf-panel [data-testid="stExpander"] > div {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }

    /* summary row: a plain inner heading, no hover card */
    .bf-panel [data-testid="stExpander"] summary {
        border: none !important;
        background: transparent !important;
        border-radius: 0 !important;
        padding: 8px 4px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: var(--wb-text-primary) !important;
    }
    .bf-panel [data-testid="stExpander"] summary:hover {
        background: transparent !important;
    }
    .bf-panel [data-testid="stExpander"] summary p {
        font-weight: 600 !important;
        color: var(--wb-text-primary) !important;
    }

    .bf-panel [data-testid="stExpanderToggle"] {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: var(--wb-text-primary) !important;
    }

    /* thin divider between consecutive expander sections inside the card */
    .bf-panel [data-testid="stExpander"] + [data-testid="stExpander"] {
        border-top: 1px solid var(--wb-border) !important;
        margin-top: 4px !important;
        padding-top: 4px !important;
    }

    /* give the expander body a little breathing room */
    .bf-panel [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        padding: 4px 4px 8px 4px !important;
    }

    /* Clean up old briefing styles inside workbench */
    div[role="tabpanel"]:has(.bf-workbench-scope) .briefing-step-card,
    div[role="tabpanel"]:has(.bf-workbench-scope) .briefing-tip-box,
    div[role="tabpanel"]:has(.bf-workbench-scope) .briefing-config-panel,
    div[role="tabpanel"]:has(.bf-workbench-scope) .briefing-config-divider {
        display: none !important;
    }

    /* Status dots keep working but smaller */
    div[role="tabpanel"]:has(.bf-workbench-scope) .status-dot {
        width: 6px;
        height: 6px;
    }

    /* ---- Reverse Flywheel: briefing entry list ---- */
    .bf-entry-row {
        display: flex;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid var(--wb-border);
    }
    .bf-entry-row:last-child {
        border-bottom: none;
    }
    .bf-entry-info {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        width: 100%;
    }
    .bf-entry-title {
        font-size: 13px;
        font-weight: 500;
        color: var(--wb-text-primary);
        flex: 1;
        min-width: 200px;
    }
    .bf-entry-source {
        font-size: 11px;
        color: var(--wb-text-secondary);
        background: var(--wb-bg);
        padding: 2px 6px;
        border-radius: 3px;
    }
    .bf-entry-cred {
        font-size: 11px;
        font-weight: 600;
    }
    .bf-sev-badge {
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 3px;
        letter-spacing: 0.5px;
    }
    .bf-sev-badge--high {
        background: #FEE2E2;
        color: #DC2626;
    }
    .bf-sev-badge--med {
        background: #FEF3C7;
        color: #D97706;
    }
</style>
""", unsafe_allow_html=True)


def render_intel_report_css():
    """Intel Briefing Document 风格 — 情报报告专用样式"""
    st.markdown("""
<style>
    /* ================================================================
       INTEL REPORT DOCUMENT THEME
       Cold-industrial intelligence product styling with classification
       banner header, mono labels, compact metrics, and clean panels.
       ================================================================ */

    :root {
        --ir-header-bg: #1F2937;
        --ir-header-text: #F9FAFB;
        --ir-classification: #DC2626;
        --ir-surface: #FFFFFF;
        --ir-text-primary: #111827;
        --ir-text-secondary: #6B7280;
        --ir-accent: #0366D6;
        --ir-border: #E5E7EB;
        --ir-hover-bg: #F9FAFB;
    }

    /* --- Document Header Banner --- */
    .ir-header {
        background: var(--ir-header-bg);
        color: var(--ir-header-text);
        padding: 14px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        border-bottom: 2px solid var(--ir-classification);
    }

    .ir-header__title {
        font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #F9FAFB;
    }

    .ir-header__timestamp {
        font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 11px;
        color: #9CA3AF;
        letter-spacing: 0.03em;
    }

    .ir-header__class {
        background: var(--ir-classification);
        color: #FFFFFF;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        padding: 4px 14px;
        border-radius: 2px;
    }

    /* --- Report Surface Container --- */
    .intel-report {
        border: 1px solid var(--ir-border);
        border-radius: 0;
        background: var(--ir-surface);
        overflow: hidden;
    }

    .ir-body {
        padding: 24px;
    }

    /* --- Executive Summary --- */
    .ir-summary-label {
        font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--ir-text-secondary);
        margin: 0 0 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--ir-border);
    }

    .ir-summary-box {
        background: #FAFBFC;
        border: 1px solid var(--ir-border);
        border-radius: 4px;
        padding: 20px 24px;
        line-height: 1.75;
        font-size: 14px;
        color: var(--ir-text-primary);
    }

    .ir-summary-box p { margin: 0 0 12px; }
    .ir-summary-box p:last-child { margin-bottom: 0; }

    /* --- Assessment Metrics Strip --- */
    .ir-metrics {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        border: 1px solid var(--ir-border);
        margin: 20px 0;
        border-radius: 4px;
        overflow: hidden;
    }

    .ir-metric {
        background: var(--ir-surface);
        padding: 16px 12px;
        text-align: center;
        border-right: 1px solid var(--ir-border);
    }

    .ir-metric:last-child {
        border-right: none;
    }

    .ir-metric__val {
        font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 26px;
        font-weight: 700;
        color: var(--ir-text-primary);
        font-variant-numeric: tabular-nums;
        line-height: 1;
    }

    .ir-metric__lbl {
        font-size: 11px;
        font-weight: 500;
        color: var(--ir-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-top: 6px;
    }

    .ir-metric__bar {
        height: 3px;
        background: #E5E7EB;
        margin-top: 10px;
        border-radius: 2px;
        overflow: hidden;
    }

    .ir-metric__bar > span {
        display: block;
        height: 100%;
        border-radius: 2px;
        transition: width 0.3s ease;
    }

    .ir-metric__bar--ok { background: #059669; }
    .ir-metric__bar--warn { background: #D97706; }
    .ir-metric__bar--bad { background: #DC2626; }

    /* --- Analysis Panel Sections --- */
    .ir-section-title {
        font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--ir-text-secondary);
        margin: 24px 0 12px;
        padding-left: 12px;
        border-left: 3px solid var(--ir-accent);
    }

    .ir-section-title--cred { border-left-color: #0366D6; }
    .ir-section-title--conflict { border-left-color: #D97706; }
    .ir-section-title--graph { border-left-color: #7C3AED; }
    .ir-section-title--evidence { border-left-color: #059669; }

    /* Expander overrides scoped to report */
    .intel-report [data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
    }

    .intel-report [data-testid="stExpanderToggle"] {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: var(--ir-text-primary) !important;
    }

    .intel-report [data-testid="stExpanderToggle"]::before {
        content: '' !important;
    }

    /* --- Severity / Credibility Badges --- */
    .ir-badge {
        display: inline-block;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.05em;
        padding: 2px 8px;
        border-radius: 3px;
        vertical-align: middle;
    }

    .ir-badge--high {
        background: #DEF7EC;
        color: #03543F;
    }

    .ir-badge--mid {
        background: #FEF3C7;
        color: #92400E;
    }

    .ir-badge--low {
        background: #FEE2E2;
        color: #991B1B;
    }

    /* --- Export Toolbar --- */
    .ir-toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 16px 0 0;
        border-top: 1px solid var(--ir-border);
        margin-top: 24px;
    }

    .ir-toolbar__lbl {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--ir-text-secondary);
        margin-right: 4px;
    }

    .intel-report .ir-toolbar button,
    .ir-toolbar button {
        padding: 8px 18px !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        border: 1px solid var(--ir-border) !important;
        background: var(--ir-surface) !important;
        color: var(--ir-text-secondary) !important;
        border-radius: 4px !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        transition: all 0.15s ease !important;
    }

    .intel-report .ir-toolbar button:hover,
    .ir-toolbar button:hover {
        background: var(--ir-accent) !important;
        color: #FFFFFF !important;
        border-color: var(--ir-accent) !important;
    }

    .intel-report .ir-toolbar button[kind="primary"],
    .ir-toolbar button[data-testid*="primary"] {
        background: var(--ir-accent) !important;
        color: #FFFFFF !important;
        border-color: var(--ir-accent) !important;
    }

    /* --- Meta Info Cards (replacing old result-card) --- */
    .ir-meta {
        background: var(--ir-surface);
        border: 1px solid var(--ir-border);
        border-radius: 4px;
        padding: 14px 20px;
        margin: 12px 0;
    }

    .ir-meta__hdr {
        font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--ir-text-secondary);
        margin-bottom: 8px;
    }

    .ir-meta__line {
        font-size: 13px;
        color: var(--ir-text-primary);
        margin: 4px 0;
    }

    .ir-meta__line--accent {
        color: var(--ir-accent);
    }

    /* --- Credibility Table --- */
    .ir-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    .ir-table th {
        font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        text-align: left;
        padding: 8px 12px;
        background: #F9FAFB;
        border-bottom: 2px solid var(--ir-border);
        color: var(--ir-text-secondary);
    }

    .ir-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #F3F4F6;
        color: var(--ir-text-primary);
    }

    .ir-table tr:last-child td {
        border-bottom: none;
    }

    /* --- Conflict Items --- */
    .ir-conflict-item {
        padding: 10px 14px;
        border-left: 2px solid #D97706;
        background: #FFFBEB;
        border-radius: 0 4px 4px 0;
        margin: 8px 0;
        font-size: 13px;
    }

    .ir-conflict-item__type {
        font-weight: 600;
        color: #92400E;
    }

    .ir-conflict-item__sev {
        float: right;
    }

    /* --- Evidence Chain --- */
    .ir-evidence-item {
        padding: 10px 14px;
        border-left: 2px solid #059669;
        background: #ECFDF5;
        border-radius: 0 4px 4px 0;
        margin: 8px 0;
        font-size: 13px;
    }

    .ir-evidence-item--unsup {
        border-left-color: #DC2626;
        background: #FEF2F2;
    }

    .ir-evidence-item a {
        color: var(--ir-accent);
        text-decoration: none;
    }

    .ir-evidence-item a:hover {
        text-decoration: underline;
    }

    /* --- Divider --- */
    .ir-divider {
        border: none;
        border-top: 1px solid var(--ir-border);
        margin: 20px 0;
    }

    /* --- Kill old morandi styles inside report area --- */
    .intel-report .result-card,
    .intel-report .report-section,
    .intel-report .report-title,
    .intel-report .section-header,
    .intel-report .stat-card {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)
