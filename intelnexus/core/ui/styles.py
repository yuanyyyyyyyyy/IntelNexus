import streamlit as st


def render_hermes_theme_css():
    """Hermes Agent '纸白与石墨' 社区浅色主题 CSS。"""
    st.markdown("""
<style>
    /* ============================================================
       Hermes Agent — Paper White & Graphite
       单一浅色主题：纸白画布 + 石墨文字 + 橙色强调
       ============================================================ */

    /* --- CSS Variable System --- */
    :root {
        /* 背景色 */
        --bg-canvas: #F5F5F5;
        --bg-dot: #B8B8B8;
        --bg-nav: #F5F5F5;
        --bg-sidebar: #FFFFFF;
        --bg-sidebar-hover: #EAEAEA;
        --bg-card: #FFFFFF;
        --bg-tab-active: #1A1A1A;
        --bg-tag: #F0F0F0;
        --bg-status-bar: #F5F5F5;
        /* 文字色 */
        --text-primary: #1A1A1A;
        --text-secondary: #666666;
        --text-tertiary: #999999;
        --text-sidebar: #1A1A1A;
        --text-sidebar-muted: #666666;
        --text-placeholder: #AAAAAA;
        /* 强调色 */
        --accent-orange: #0055FF;
        --accent-green: #4ADE80;
        --accent-red: #EF5350;
        /* 边框 */
        --border-light: #E8E8E8;
        --border-medium: #E0E0E0;
        --border-sidebar: #E0E0E0;
        /* 间距 */
        --space-xs: 4px;
        --space-sm: 8px;
        --space-md: 16px;
        --space-lg: 24px;
        --space-xl: 48px;
        /* 圆角 */
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;
        /* 字体（自托管：config.toml [[theme.fontFaces]] 注册 woff2）。
           标题 Playfair Display（衬线体）+ 正文 Inter（无衬线体）
           + 中文 Noto Serif SC（宋体）+ 等宽 JetBrains Mono。
           HarmonyOS Sans SC 作为中文备选。 */
        --font-ui: "Inter", "Noto Serif SC", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
        --font-heading: "Playfair Display", "Noto Serif SC", "Source Han Serif SC", "SimSun", serif;
        --font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, "Courier New", monospace;

        /* --- Legacy-compatible tokens (used by workbench / onboarding) --- */
        --in-surface-white: #FFFFFF;
        --in-chevron-gray: #999999;
        --in-sidebar-bg: #F5F5F5;
        --in-divider-gray: #E8E8E8;
        --in-sidebar-border: #E0E0E0;
        --in-sidebar-title-fg: #1A1A1A;
        --in-btn-secondary-fg: #1A1A1A;
        --in-btn-ghost-fg: #999999;
        --in-btn-secondary-border: #E0E0E0;
        --in-btn-secondary-bg: #F5F5F5;
        --in-action-primary: #0055FF;
        --in-action-primary-hover: #0044DD;
        --in-accent-blue-hover: #0055FF;
        --in-lang-hover-bg: #F0F0F0;
        --in-download-btn-hover: #0044DD;
        --in-status-dot-active: #4ADE80;
        --in-status-dot-error: #EF5350;
        --in-hint-warn-gold: #0055FF;
        --in-panel-hover-border: #CCCCCC;
        --in-bf-panel-hover-border: #CCCCCC;
        --in-step-index-bg: #F0F0F0;
        --in-step-done-bg: #EFF6FF;
        --in-step-current-bg: #F5F5F5;
        --in-history-row-hover: #F5F5F5;
        --in-toggle-btn-hover: #333333;
        --in-output-header-bg: #F5F5F5;
        --in-step-done-alt: #EFF6FF;
        --in-step-current-alt: #F5F5F5;
        --in-sev-high-bg: #FEE2E2;
        --in-sev-high-fg: #DC2626;
        --in-sev-med-bg: #FEF3C7;
        --in-sev-med-fg: #D97706;

        /* Icon system tokens — graphite palette */
        --icon-gray: #999999;
        --icon-blue: #666666;
        --icon-warm: #888888;
        --icon-rose: #999999;
        --icon-sage: #888888;
        --icon-lavender: #999999;
        --icon-terracotta: #888888;
        --icon-success: #4ADE80;
        --icon-warning: #0055FF;
        --icon-error: #EF5350;
        --icon-dark: #1A1A1A;
        --icon-light: #CCCCCC;

        /* Workbench tokens — Hermes paper-white */
        --wb-surface: #FFFFFF;
        --wb-card: #FFFFFF;
        --wb-text-primary: #1A1A1A;
        --wb-text-secondary: #666666;
        --wb-accent: #0055FF;
        --wb-border: #E8E8E8;
        --wb-tag-source: #0055FF;
        --wb-tag-sub: #0055FF;
        --wb-tag-gen: #0055FF;
        --wb-tag-cat: #0055FF;
        --wb-hover: #F5F5F5;
        --wb-bg: #F5F5F5;
        --wb-green: #4ADE80;
        --wb-orange: #0055FF;
        --wb-red: #EF5350;
    }

    /* --- Hide Streamlit decoration --- */
    #stDecoration {
        display: none !important;
    }

    /* --- Font System ---
       旧版通配符选择器 + !important 的全局字体压制已移除：
       它会盖过 Streamlit 主题字体（config.toml fontFaces），
       且连代码块等宽字体一起压掉。改为显式覆盖面选择器 + var(--font-ui)，
       不带 !important，允许更高特异性规则（含 Streamlit 原生主题）正常覆盖；
       个别元素若被内建样式盖过，应针对性补规则而不是恢复通配。 */
    html,
    body,
    [class*="st-"],
    [data-baseweb],
    div, span, p, li, a, label,
    button, input, select, textarea, optgroup {
        font-family: var(--font-ui);
    }
    body {
        line-height: 1.55;
    }
    /* 代码 / 哈希 / 数据展示区统一等宽字体。
       注意：全局 [class*="st-"] { font-family: var(--font-ui) } 特异性 (0,1,0)，
       而 Streamlit 的 code/pre 自身带 st-emotion-cache 类会被其命中，
       裸类型选择器 (0,0,1) 会被盖过；故用祖先/自身类组合抬升特异性。 */
    html code, html pre, html kbd, html samp,
    [class*="st-"] code, [class*="st-"] pre, [class*="st-"] kbd, [class*="st-"] samp,
    code[class*="st-"], pre[class*="st-"], kbd[class*="st-"], samp[class*="st-"],
    [data-testid="stCode"] {
        font-family: var(--font-mono);
    }
    /* 标题衬线体：Playfair Display 优雅人文风格 */
    [data-testid="stHeading"] h1,
    [data-testid="stHeading"] h2,
    [data-testid="stHeading"] h3,
    [data-testid="stHeading"] h4,
    [data-testid="stHeading"] h5,
    [data-testid="stHeading"] h6 {
        font-family: var(--font-heading);
        letter-spacing: -0.02em;
    }

    /* --- Main Canvas Background --- */
    .stApp {
        background-color: #FAFAFA !important;
        background-image: radial-gradient(circle, #D5D5D5 1px, transparent 1px) !important;
        background-size: 32px 32px !important;
        background-position: 0 0 !important;
        padding-bottom: 40px !important;
    }
    /* Force main content area gray (override Streamlit inner containers) */
    .stApp > header,
    .stApp [data-testid="stHeaderContainer"] {
        background-color: #FAFAFA !important;
        background-image: none !important;
    }
    section[data-testid="stMain"] {
        background-color: #FAFAFA !important;
        background-image: radial-gradient(circle, #D5D5D5 1px, transparent 1px) !important;
        background-size: 32px 32px !important;
        background-position: 0 0 !important;
    }
    /* Sidebar white */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
    }

    /* --- Header --- */
    header {
        background: none !important;
    }
    [data-testid="stHeaderContainer"] {
        background: var(--bg-canvas) !important;
    }
    div[data-testid="stHeaderContainer"]::before {
        display: none !important;
    }

    /* ============================================================
       MAIN NAVIGATION（横向 radio 主导航，tab 化外观）
       st.tabs 已移除：导航为 st.radio(key="main_nav_radio")，
       前置隐藏 main-nav-marker 供 :has() 定位（Streamlit 1.62 radio DOM：
       stRadio > stRadioGroup > [stRadioOption]，选中项携带 data-selected）。
       ============================================================ */
    .main-nav-marker,
    .app-main-scope {
        display: none !important;
    }
    /* 选项横排成 tab 栏，底部细线贯穿 */
    .element-container:has(.main-nav-marker) + .element-container div[data-testid="stRadio"] [data-testid="stRadioGroup"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 4px !important;
        border-bottom: 1px solid var(--border-medium) !important;
        min-height: 0 !important;
    }
    /* 未选中：灰字 */
    .element-container:has(.main-nav-marker) + .element-container div[data-testid="stRadio"] [data-testid="stRadioOption"] {
        background-color: transparent !important;
        color: var(--text-secondary) !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
        padding: var(--space-sm) var(--space-md) !important;
        margin: 0 !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    .element-container:has(.main-nav-marker) + .element-container div[data-testid="stRadio"] [data-testid="stRadioOption"]:hover,
    .element-container:has(.main-nav-marker) + .element-container div[data-testid="stRadio"] [data-testid="stRadioOption"][data-hovered] {
        background-color: var(--border-medium) !important;
        color: var(--text-primary) !important;
    }
    /* 选中：黑字 + 强调底线 */
    .element-container:has(.main-nav-marker) + .element-container div[data-testid="stRadio"] [data-testid="stRadioOption"][data-selected],
    .element-container:has(.main-nav-marker) + .element-container div[data-testid="stRadio"] [data-testid="stRadioOption"][aria-checked="true"] {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        border-bottom-color: var(--accent-orange) !important;
    }
    /* 隐藏 radio 圆点，仅保留 tab 文字（选项 > 内容列 > 行 > 首个子元素即圆点） */
    .element-container:has(.main-nav-marker) + .element-container div[data-testid="stRadio"] [data-testid="stRadioOption"] > div > div > div:first-child {
        display: none !important;
    }

    /* ============================================================
       MAIN TITLE / SUBTITLE / GUIDANCE
       ============================================================ */
    .main-title {
        font-size: 42px !important;
        font-weight: 700 !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.02em !important;
        line-height: 1.2 !important;
        margin-bottom: 8px !important;
    }
    .main-subtitle {
        font-size: 15px !important;
        font-weight: 400 !important;
        color: var(--text-secondary) !important;
        margin-bottom: 2px !important;
    }
    .main-guidance {
        font-size: 13px !important;
        color: var(--text-tertiary) !important;
        margin-bottom: 0 !important;
    }

    /* ============================================================
       CARDS / PANELS
       ============================================================ */
    .result-card, .report-section {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: var(--radius-lg) !important;
        padding: var(--space-lg) !important;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .result-card:hover, .report-section:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.10) !important;
        border-color: var(--text-tertiary) !important;
    }
    .result-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 8px;
    }
    .result-stats {
        display: flex;
        gap: 16px;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--border-light);
    }
    .stat-item { text-align: center; }
    .stat-value {
        font-size: 24px;
        font-weight: 600;
        color: var(--text-primary);
    }
    .stat-label {
        font-size: 12px;
        color: var(--text-secondary);
        margin-top: 4px;
    }
    .report-title {
        font-size: 22px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--border-light);
    }
    .section-header {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
    }

    /* ============================================================
       SEARCH HISTORY PANEL
       ============================================================ */
    .sh-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border-light);
    }
    .sh-title-row {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .sh-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
    }
    .sh-count {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 20px;
        height: 20px;
        padding: 0 6px;
        font-size: 11px;
        font-weight: 600;
        color: var(--accent-orange);
        background: rgba(0, 85, 255, 0.08);
        border-radius: 10px;
    }
    .sh-empty {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 24px 16px;
        color: var(--text-tertiary);
        font-size: 14px;
        justify-content: center;
    }
    .sh-entry {
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: var(--radius-md);
        padding: 12px 16px;
        margin-bottom: 8px;
        transition: all 0.2s ease;
    }
    .sh-entry:hover {
        border-color: var(--text-tertiary);
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .sh-entry-query {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 6px;
        word-break: break-all;
    }
    .sh-entry-meta {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }
    .sh-entry-badge {
        display: inline-block;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 500;
        color: var(--accent-orange);
        background: rgba(0, 85, 255, 0.06);
        border-radius: 4px;
        white-space: nowrap;
    }
    .sh-entry-count {
        font-size: 12px;
        color: var(--text-secondary);
    }
    .sh-entry-time {
        font-size: 12px;
        color: var(--text-tertiary);
        margin-left: auto;
    }

    /* ============================================================
       BUTTONS
       ============================================================ */
    .stButton > button {
        background-color: var(--bg-tab-active) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: var(--radius-md) !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    }
    .stButton > button:hover {
        background-color: #333333 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    }
    .stButton > button:active {
        transform: scale(0.98) !important;
    }
    /* Secondary / download buttons（新版 Streamlit 可能把 data-testid
       直接放在 <button> 自身，两种 DOM 形态均兼容，下同） */
    div[data-testid="stBaseButton-secondary"] > button,
    button[data-testid="stBaseButton-secondary"],
    div[data-testid="stDownloadButton"] button,
    button[data-testid="stDownloadButton"] {
        background-color: var(--bg-tag) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-medium) !important;
    }
    .download-btn {
        display: inline-block;
        padding: 12px 24px;
        background: var(--accent-orange);
        border-radius: var(--radius-lg);
        color: #FFFFFF;
        text-decoration: none;
        font-weight: 500;
        transition: all 0.3s;
    }
    .download-btn:hover {
        background: #0044DD;
        transform: translateY(-1px);
    }

    /* ============================================================
       INPUT / SEARCH
       ============================================================ */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-medium) !important;
        border-radius: var(--radius-md) !important;
        color: var(--text-primary) !important;
    }
    .stTextInput > div > div > input::placeholder,
    .stTextArea > div > div > textarea::placeholder {
        color: var(--text-placeholder) !important;
    }
    .stTextInput > div > div > input {
        border-radius: var(--radius-md) !important;
    }
    .search-input input {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-medium) !important;
        padding: 14px 18px !important;
        font-size: 17px !important;
        background: var(--bg-card) !important;
        color: var(--text-primary) !important;
        transition: all 0.3s ease !important;
    }
    .search-input input:focus {
        border-color: var(--accent-orange) !important;
        box-shadow: 0 0 0 3px rgba(0,85,255,0.15) !important;
        outline: none !important;
    }
    .search-input input::placeholder {
        color: var(--text-placeholder) !important;
    }
    .search-button button {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border-radius: 6px !important;
        border: 1px solid #E0E0E0 !important;
        padding: 14px 28px !important;
        font-size: 17px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 12px rgba(0,85,255,0.35) !important;
    }
    .search-button button:hover {
        background-color: #F5F5F5 !important;
        box-shadow: 0 4px 16px rgba(0,85,255,0.25) !important;
    }
    .search-button button:active {
        transform: scale(0.98) !important;
    }
    /* Main area buttons — white bg + blue shadow (exclude sidebar) */
    section[data-testid="stMain"] .stButton > button,
    section[data-testid="stMain"] .search-button button {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        box-shadow: 0 4px 12px rgba(0,85,255,0.35) !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stMain"] .stButton > button:hover,
    section[data-testid="stMain"] .search-button button:hover {
        background: #F5F5F5 !important;
        box-shadow: 0 4px 16px rgba(0,85,255,0.25) !important;
    }

    /* 全局主按钮风格 — 白底深色文字+蓝色阴影（与生成简报一致） */
    section[data-testid="stMain"] div[data-testid="stBaseButton-primary"] > button,
    section[data-testid="stMain"] div[data-testid="stBaseButton-primary"] button,
    section[data-testid="stMain"] button[data-testid="stBaseButton-primary"] {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 5px 16px !important;
        min-height: 30px !important;
        box-shadow: 0 4px 12px rgba(0,85,255,0.45) !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stMain"] div[data-testid="stBaseButton-primary"] > button:hover,
    section[data-testid="stMain"] div[data-testid="stBaseButton-primary"] button:hover,
    section[data-testid="stMain"] button[data-testid="stBaseButton-primary"]:hover {
        background: #F5F5F5 !important;
        box-shadow: 0 4px 16px rgba(0,85,255,0.4) !important;
    }

    /* 表单提交按钮（搜索按钮）— 白底深色文字+蓝色阴影 */
    section[data-testid="stMain"] div[data-testid="stBaseButton-primaryFormSubmit"] button,
    section[data-testid="stMain"] div[data-testid="stBaseButton-secondaryFormSubmit"] button,
    section[data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"],
    section[data-testid="stMain"] button[data-testid="stBaseButton-secondaryFormSubmit"] {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 5px 16px !important;
        min-height: 30px !important;
        box-shadow: 0 4px 12px rgba(0,85,255,0.45) !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stMain"] div[data-testid="stBaseButton-primaryFormSubmit"] button:hover,
    section[data-testid="stMain"] div[data-testid="stBaseButton-secondaryFormSubmit"] button:hover,
    section[data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
    section[data-testid="stMain"] button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
        background: #F5F5F5 !important;
        box-shadow: 0 4px 16px rgba(0,85,255,0.4) !important;
    }

    /* 按钮与下拉框垂直对齐 — 列布局底部对齐 */
    section[data-testid="stMain"] [data-testid="stHorizontalBlock"] {
        align-items: flex-end !important;
    }
    section[data-testid="stMain"]:has(.ov-scope) [data-testid="stHorizontalBlock"] {
        align-items: stretch !important;
    }
    section[data-testid="stMain"] [data-testid="column"] > div > .stButton {
        padding-bottom: 0 !important;
        margin-bottom: 0 !important;
    }
    section[data-testid="stMain"] [data-testid="column"] > div > .stButton > button {
        margin-bottom: 0 !important;
        margin-top: 0 !important;
    }

    /* ============================================================
       STATUS DOTS
       ============================================================ */
    .status-dot {
        width: 8px !important;
        height: 8px !important;
        border-radius: 50% !important;
        display: inline-block !important;
        margin-right: 6px;
        vertical-align: middle;
    }
    .status-dot.active {
        background-color: var(--accent-green) !important;
        box-shadow: 0 0 6px rgba(74,222,128,0.4) !important;
    }
    .status-dot.warning {
        background-color: var(--accent-orange) !important;
        box-shadow: 0 0 6px rgba(0,85,255,0.4) !important;
    }
    .status-dot.error {
        background-color: var(--accent-red) !important;
        box-shadow: 0 0 6px rgba(239,83,80,0.4) !important;
    }

    /* ============================================================
       SIDEBAR SECTION TITLES
       ============================================================ */
    .sb-section {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 20px 0 10px;
        padding: 0 4px;
        border-left: 3px solid #0055FF !important;
        color: #1A1A1A !important;
    }
    .sb-section::before {
        content: '';
        display: block;
        width: 3px;
        height: 14px;
        background: #0055FF;
        border-radius: 2px;
        flex-shrink: 0;
    }
    .sb-section__label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #1A1A1A !important;
    }
    /* Sidebar action buttons */
    .sb-action-primary {
        width: 100% !important;
        padding: 12px 20px !important;
        background: var(--accent-orange) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
    }
    .sb-action-primary:hover {
        background: #0044DD !important;
    }
    .sb-action-secondary {
        width: 100% !important;
        padding: 10px 20px !important;
        background: transparent !important;
        color: var(--text-sidebar-muted) !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: var(--radius-sm) !important;
        font-size: 13px !important;
        font-weight: 500 !important;
    }
    .sb-action-secondary:hover {
        background: #EAEAEA !important;
        color: #1A1A1A !important;
    }

    /* ============================================================
       SEVERITY BADGES
       ============================================================ */
    .bf-sev-badge {
        font-size: 10px !important;
        font-weight: 600 !important;
        border-radius: var(--radius-sm) !important;
        padding: 2px 8px !important;
    }
    .bf-sev-badge.high, .bf-sev-badge--high {
        background-color: #FEE2E2 !important;
        color: #DC2626 !important;
    }
    .bf-sev-badge.medium, .bf-sev-badge--med {
        background-color: #FEF3C7 !important;
        color: #D97706 !important;
    }

    /* ============================================================
       BRIEFING WELCOME / STEP CARDS
       ============================================================ */
    .briefing-step-card {
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: var(--radius-lg);
        padding: 20px 16px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: all 0.25s ease;
    }
    .briefing-step-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }
    .step-num {
        display: inline-block;
        width: 28px;
        height: 28px;
        line-height: 28px;
        background: var(--accent-orange);
        color: #FFFFFF;
        border-radius: 50%;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 12px;
    }
    .step-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 8px 0 6px;
    }
    .step-desc {
        font-size: 13px;
        color: var(--text-secondary);
        line-height: 1.6;
        margin: 0;
    }
    .briefing-tip-box {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        background: rgba(0,85,255,0.06);
        border-radius: var(--radius-md);
        padding: 16px 20px;
        margin-top: 24px;
    }
    .tip-accent {
        width: 3px;
        height: auto;
        min-height: 40px;
        background: var(--accent-orange);
        border-radius: 2px;
        flex-shrink: 0;
    }
    .tip-content {
        color: var(--text-secondary);
        font-size: 14px;
        line-height: 1.65;
        margin: 0;
    }

    /* ============================================================
       BRIEFING CONFIG PANEL
       ============================================================ */
    .briefing-config-panel {
        background: linear-gradient(135deg, rgba(0,85,255,0.03) 0%, rgba(74,222,128,0.03) 100%);
        border: 1px solid var(--border-light);
        border-radius: var(--radius-lg);
        padding: 24px;
        margin: 16px 0 24px 0;
    }
    .briefing-config-header {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0 0 12px 0;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border-light);
        letter-spacing: 0.3px;
    }
    .briefing-config-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--border-light), transparent);
        margin: 20px 0;
    }

    /* ============================================================
       FUNCTION TAG BAR PANEL (.bf-panel)
       ============================================================ */
    .bf-panel {
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-left: 4px solid var(--accent-orange);
        border-radius: var(--radius-sm);
        padding: 20px 24px;
        margin: 12px 0;
        transition: border-color 0.15s ease;
    }
    .bf-panel:hover {
        border-color: var(--text-tertiary);
    }
    .bf-panel.bf-panel--source { border-left-color: var(--accent-orange); }
    .bf-panel.bf-panel--sub { border-left-color: var(--accent-orange); }
    .bf-panel.bf-panel--cat { border-left-color: var(--accent-orange); }
    .bf-panel.bf-panel--gen { border-left-color: var(--accent-orange); }

    /* ============================================================
       ONBOARDING 3-STEP BAR (.bf-step)
       ============================================================ */
    .bf-step {
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-left: 3px solid var(--border-light);
        border-radius: var(--radius-sm);
        padding: 12px 14px;
        height: 100%;
        min-height: 84px;
        transition: border-color 0.15s ease, background 0.15s ease;
    }
    .bf-step__head {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-primary);
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
        background: var(--in-step-index-bg);
        color: var(--text-secondary);
    }
    .bf-step__desc {
        font-size: 12px;
        color: var(--text-secondary);
        margin-top: 8px;
        line-height: 1.5;
    }
    .bf-step--done {
        border-left-color: var(--accent-orange);
        background: var(--in-step-done-alt);
    }
    .bf-step--done .bf-step__index {
        background: var(--accent-orange);
        color: #FFFFFF;
    }
    .bf-step--current {
        border-left-color: var(--accent-orange);
        background: var(--in-step-current-alt);
    }
    .bf-step--current .bf-step__index {
        background: var(--accent-orange);
        color: #FFFFFF;
    }
    .bf-step--pending {
        border-left-color: var(--border-light);
        opacity: 0.85;
    }

    /* ============================================================
       SECTION LABEL (.bf-label)
       ============================================================ */
    .bf-label {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--border-light);
    }
    .bf-label__tag {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-secondary);
        background: var(--bg-tag);
        padding: 3px 8px;
        border-radius: 3px;
    }
    .bf-label__title {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
    }

    /* ============================================================
       OUTPUT AREA ([data-key="bf-output"])
       ============================================================ */
    [data-key="bf-output"] {
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: var(--radius-sm);
        padding: 20px 24px;
        margin: 12px 0;
    }
    .bf-output__header {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border-light);
    }

    /* ============================================================
       HISTORY ITEMS
       ============================================================ */
    .bf-history-item {
        padding: 12px 0;
        border-bottom: 1px solid var(--border-light);
    }
    .bf-history-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }
    .bf-history-item__time {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1.4;
    }
    .bf-history-item__meta {
        margin-top: 4px;
        font-size: 12px;
        color: var(--text-secondary);
        line-height: 1.5;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
    }
    .bf-history-item__org { font-weight: 500; color: var(--text-primary); }
    .bf-history-item__sep { color: var(--border-light); }

    /* History item buttons */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-history-item button {
        width: 100% !important;
        min-height: 28px !important;
        padding: 2px 10px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        border-radius: 5px !important;
        background: transparent !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border-light) !important;
        box-shadow: none !important;
        writing-mode: horizontal-tb !important;
        text-orientation: mixed !important;
        white-space: nowrap !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-history-item button:hover {
        background: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border-color: var(--accent-orange) !important;
    }

    /* ============================================================
       ENTRY ROWS (.bf-entry-row)
       ============================================================ */
    .bf-entry-row {
        display: flex;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid var(--border-light);
    }
    .bf-entry-row:last-child { border-bottom: none; }
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
        color: var(--text-primary);
        flex: 1;
        min-width: 200px;
    }
    .bf-entry-source {
        font-size: 11px;
        color: var(--text-secondary);
        background: var(--bg-tag);
        padding: 2px 6px;
        border-radius: 3px;
    }
    .bf-entry-cred { font-size: 11px; font-weight: 600; }
    .bf-entry-row + div[data-testid="stHorizontalBlock"] {
        margin-top: -4px;
        align-items: center;
    }
    .bf-entry-row + div[data-testid="stHorizontalBlock"] button {
        font-size: 11px !important;
        padding: 2px 8px !important;
        min-height: 0 !important;
        max-height: 28px !important;
        line-height: 1.3 !important;
        border-radius: var(--radius-sm) !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    .bf-entry-url {
        font-size: 10.5px;
        color: var(--text-secondary);
        opacity: 0.75;
        display: inline-block;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        direction: rtl;
        text-align: left;
    }

    /* ============================================================
       EMPTY STATE
       ============================================================ */
    .bf-empty {
        text-align: center;
        padding: 32px 16px;
        color: var(--text-secondary);
        font-size: 14px;
    }
    .bf-empty__action {
        display: inline-block;
        margin-top: 10px;
        color: var(--accent-orange);
        font-weight: 500;
        cursor: pointer;
    }
    .bf-empty__action:hover { text-decoration: underline; }

    /* ============================================================
       MISC WIDGET OVERRIDES
       ============================================================ */
    div[data-testid="stRadio"] > div { gap: 8px; }
    div[data-testid="stRadio"] label {
        border-radius: var(--radius-lg) !important;
        padding: 12px 16px !important;
        background: var(--bg-nav) !important;
        border: 1px solid transparent !important;
        transition: all 0.2s ease !important;
        color: var(--text-primary) !important;
    }
    div[data-testid="stRadio"] label:hover {
        background: var(--bg-tag) !important;
    }
    div[data-testid="stRadio"] input:checked + div {
        background: var(--bg-tag) !important;
        border-color: var(--accent-orange) !important;
        color: var(--text-primary) !important;
    }
    div[data-testid="stSelectbox"] > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-medium) !important;
        border-radius: var(--radius-lg) !important;
    }
    div[data-testid="stSelectbox"] > div:focus-within {
        border-color: var(--accent-orange) !important;
        box-shadow: none !important;
    }
    div[data-testid="stSelectbox"] > div > div { border-radius: var(--radius-lg); }
    div[data-testid="stSlider"] > div > div { border-radius: var(--radius-lg); }
    div.stButton > button { border-radius: var(--radius-lg); }

    .stSuccess {
        background: var(--accent-green);
        color: #FFFFFF;
        border-radius: var(--radius-lg);
    }
    .stSpinner > div > div { border-top-color: var(--accent-orange); }

    div[data-testid="stMarkdownContainer"] p { color: var(--text-primary); }

    /* ============================================================
       MAIN AREA — Streamlit Native Components
       ============================================================ */

    /* Main area Expander */
    [data-testid="stExpander"] {
        border: 1px solid var(--border-light) !important;
        border-radius: var(--radius-md) !important;
        background: var(--bg-card) !important;
    }
    [data-testid="stExpander"] > details,
    [data-testid="stExpander"] > div {
        background: var(--bg-card) !important;
        border: none !important;
    }
    [data-testid="stExpander"] summary {
        background: transparent !important;
        color: var(--text-primary) !important;
        border: none !important;
        font-weight: 500 !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: var(--bg-tag) !important;
    }
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span {
        color: var(--text-primary) !important;
    }
    [data-testid="stExpander"] summary svg {
        color: var(--text-secondary) !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderContent"],
    [data-testid="stExpander"] details > div {
        background: transparent !important;
    }

    /* Main area Checkbox */
    div[data-testid="stCheckbox"] label {
        color: var(--text-primary) !important;
    }
    div[data-testid="stCheckbox"] input[type="checkbox"] {
        accent-color: var(--accent-orange);
    }

    /* Main area Progress Bar — 淡蓝色发光 */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #7EB8FF, #4A9EFF) !important;
        box-shadow: 0 0 8px rgba(74,158,255,0.5), 0 0 16px rgba(74,158,255,0.2) !important;
    }
    .stProgress > div > div {
        background: rgba(74,158,255,0.08) !important;
        border-radius: 4px !important;
    }

    /* Progress phase row: icon + text alignment */
    .progress-phase-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 0;
    }
    .progress-phase-row .in-icon {
        flex-shrink: 0;
    }

    /* Main area Divider / Horizontal Rule */
    hr {
        border-color: var(--border-light) !important;
        opacity: 0.8 !important;
    }

    /* Main area Radio (global, non-sidebar) */
    div[data-testid="stRadio"] label {
        color: var(--text-primary) !important;
    }

    /* Language switch */
    .lang-switch { display: flex; gap: 8px; padding: 12px 16px; }
    .lang-btn {
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 13px;
        cursor: pointer;
        border: 1px solid var(--border-medium);
        background: var(--bg-card);
        color: var(--text-primary);
        transition: all 0.2s;
    }
    .lang-btn:hover { background: var(--bg-tag); }
    .lang-btn.active {
        background: var(--accent-orange);
        color: #FFFFFF;
        border-color: var(--accent-orange);
    }

    /* Selectbox z-index fix (Streamlit 1.62 RAC) */
    div[data-testid="stSelectbox"] {
        pointer-events: auto !important;
    }
    div[data-testid="stSelectbox"] ul,
    div[data-testid="stSelectbox"] [role="listbox"],
    div[data-testid="stSelectboxVirtualDropdown"] {
        z-index: 999999 !important;
        position: relative !important;
        pointer-events: auto !important;
    }

    /* ============================================================
       ICON MATERIAL FALLBACK (CSS-only chevron, no font dependency)
       ============================================================ */
    span[data-testid="stIconMaterial"] {
        font-size: 0 !important;
        width: 16px !important;
        height: 16px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        position: relative !important;
    }
    span[data-testid="stIconMaterial"]::before {
        content: "";
        width: 7px !important;
        height: 7px !important;
        border-right: 2px solid var(--in-chevron-gray) !important;
        border-bottom: 2px solid var(--in-chevron-gray) !important;
        transform: rotate(45deg) !important;
        transition: transform 0.15s ease !important;
        display: block !important;
    }
    [data-testid="stExpander"][open] span[data-testid="stIconMaterial"]::before {
        transform: rotate(225deg) !important;
    }

    /* ============================================================
       HINT / WARN
       ============================================================ */
    .bf-hint {
        margin: 4px 0 !important;
        padding: 6px 0 6px 12px !important;
        border-left: 3px solid var(--border-light);
        color: var(--text-secondary);
        font-size: 13px;
        line-height: 1.5;
    }
    .bf-hint--warn {
        border-left-color: var(--accent-orange);
    }

    /* Download button in output */
    .bf-download-btn {
        display: inline-block;
        padding: 8px 18px;
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-radius: var(--radius-sm);
        color: var(--accent-orange);
        font-size: 13px;
        font-weight: 500;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.15s ease;
        margin-right: 8px;
    }
    .bf-download-btn:hover {
        background: var(--bg-tag);
        border-color: var(--accent-orange);
    }

    /* ============================================================
       SIDEBAR — ALL RULES IN ONE PLACE
       Streamlit 1.62+ (React Aria Components)
       Placed after all global rules so CSS cascade wins.
       ============================================================ */

    /* --- 1. Sidebar base --- */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid #E0E0E0 !important;
        overflow: visible !important;
        --text-sidebar-muted: #999999;
    }
    section[data-testid="stSidebar"] * {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] section {
        overflow: visible !important;
    }

    /* --- 2. Sidebar title / subtitle --- */
    .sidebar-title {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #1A1A1A !important;
        padding: 20px 16px 12px !important;
        letter-spacing: -0.01em !important;
    }
    .sidebar-subtitle {
        display: none !important;
    }

    /* --- 3. Sidebar Radio (RAC) --- */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] {
        background: transparent !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
        background: transparent !important;
        color: #1A1A1A !important;
        border-radius: var(--radius-sm) !important;
        padding: 8px 12px !important;
        border: 1px solid transparent !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
        background: #EAEAEA !important;
    }

    /* --- 4. Sidebar Selectbox (RAC) --- */
    section[data-testid="stSidebar"] .stSelectbox label {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > div {
        background: #FFFFFF !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: var(--radius-sm) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > div:focus-within {
        border-color: #0055FF !important;
    }
    section[data-testid="stSidebar"] .stSelectbox input,
    section[data-testid="stSidebar"] .stSelectbox [role="combobox"] {
        color: #1A1A1A !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] .stSelectbox > div > div > div > div {
        color: #1A1A1A !important;
    }

    /* --- 5. Sidebar Buttons --- */
    section[data-testid="stSidebar"] .stButton > button,
    section[data-testid="stSidebar"] div[data-testid="stBaseButton-secondary"] > button,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
        transition: all 0.15s ease !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover,
    section[data-testid="stSidebar"] div[data-testid="stBaseButton-secondary"] > button:hover,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
        background: #F0F0F0 !important;
        border-color: #CCCCCC !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stBaseButton-primary"] > button,
    section[data-testid="stSidebar"] div[data-testid="stBaseButton-primary"] button,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        box-shadow: 0 4px 12px rgba(0,85,255,0.45) !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stBaseButton-primary"] > button:hover,
    section[data-testid="stSidebar"] div[data-testid="stBaseButton-primary"] button:hover,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {
        background: #F5F5F5 !important;
        box-shadow: 0 4px 16px rgba(0,85,255,0.4) !important;
    }

    /* --- 5b. Sidebar element-container spacing (compact model cards) --- */
    section[data-testid="stSidebar"] .element-container {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    /* --- 5b-1. Sidebar health panel: compact buttons in column rows ---
       健康面板每行用 st.columns 布局，重置按钮所在列很窄，
       默认按钮样式会导致文字换行（竖向显示）。强制紧凑单行。 */
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton > button {
        font-size: 11px !important;
        padding: 2px 6px !important;
        min-height: 0 !important;
        max-height: 24px !important;
        line-height: 1.2 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    /* --- 5b-2. 搜索结果条目下方三按钮紧凑布局 ---
       收藏/有用/知识库三个按钮在 st.columns(3) 中均分全宽导致间距过大。
       通过 .result-btn-row 包装器的列容器缩窄 + 按钮宽度限制，使按钮更靠近。 */
    .result-btn-row [data-testid="column"] {
        padding-left: 4px !important;
        padding-right: 4px !important;
        max-width: 160px !important;
    }
    .result-btn-row [data-testid="column"] .stButton > button {
        width: 100% !important;
        padding: 4px 10px !important;
        font-size: 12px !important;
        white-space: nowrap !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    /* --- 5b-2. 中和框架对 markdown 容器的补偿性负 margin ---
       Streamlit 给 [data-testid="stMarkdownContainer"] 内置 margin-bottom: -1rem，
       用于抵消内部 p 的默认 1rem 下边距；但上面 5b 已把 p 的 margin 清零，
       若不中和该 -1rem，名称行的盒子会向上收缩 16px，叠加条目容器 gap 时
       按钮行将侵蚀/覆盖文字（实测：gap=None 时名称行与按钮行重叠 -16px）。
       仅限定在自定义模型/供应商列表内，不影响侧边栏其他 markdown。 */
    section[data-testid="stSidebar"] .st-key-cm_list [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] .st-key-cp_list [data-testid="stMarkdownContainer"] {
        margin-bottom: 0 !important;
    }
    /* --- 5c. 侧边栏自定义模型/供应商列表（紧凑间距） ---
       锚定框架对 keyed container 生成的包装类（.st-key-cm_list / .st-key-cp_list，
       由前端 Block 组件直接渲染，不经过 markdown 净化器，不会被剥离）；
       仅命中列表条目间的 st.divider()，.sb-divider、st.markdown("---") 等不受影响 */
    section[data-testid="stSidebar"] .st-key-cm_list hr,
    section[data-testid="stSidebar"] .st-key-cp_list hr {
        margin: 4px 0 !important;
    }

    /* --- 6. Sidebar Slider (RAC) --- */
    section[data-testid="stSidebar"] .stSlider label {
        color: #1A1A1A !important;
    }

    /* --- 7. Sidebar Checkbox --- */
    section[data-testid="stSidebar"] .stCheckbox label {
        color: #1A1A1A !important;
    }

    /* --- 8. Sidebar TextInput / NumberInput --- */
    section[data-testid="stSidebar"] .stTextInput > div > div > input,
    section[data-testid="stSidebar"] .stNumberInput > div > div > input {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
        border-color: #E0E0E0 !important;
    }

    /* --- 9. Selectbox dropdown panel (global — rendered at body level) --- */
    div[data-testid="stSelectboxVirtualDropdown"] {
        background-color: #FFFFFF !important;
        border-color: #E0E0E0 !important;
    }
    div[data-testid="stSelectboxVirtualDropdown"] [role="option"] {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
    }
    div[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
    div[data-testid="stSelectboxVirtualDropdown"] [data-focused] {
        background-color: #F0F0F0 !important;
    }
    div[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"] {
        background-color: #F0F0F0 !important;
        color: #1A1A1A !important;
    }

    /* --- 9b. Multiselect dropdown panel (global — rendered at body level) --- */
    div[data-testid="stMultiSelectVirtualDropdown"] {
        background-color: #FFFFFF !important;
        border-color: #E0E0E0 !important;
    }
    div[data-testid="stMultiSelectVirtualDropdown"] [role="option"] {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
    }
    div[data-testid="stMultiSelectVirtualDropdown"] [role="option"]:hover,
    div[data-testid="stMultiSelectVirtualDropdown"] [data-focused] {
        background-color: rgba(74,158,255,0.08) !important;
    }
    div[data-testid="stMultiSelectVirtualDropdown"] [role="option"][aria-selected="true"] {
        background-color: rgba(74,158,255,0.12) !important;
        color: #0055FF !important;
    }
    /* Multiselect 选中标签（pill）*/
    div[data-testid="stMultiSelect"] [data-testid="stMarkdownContainer"] span,
    div[data-testid="stMultiSelect"] .stMultiSelectSelectedOption,
    div[data-testid="stMultiSelect"] div[role="listbox"] > div > div > div > div > div {
        background-color: rgba(74,158,255,0.12) !important;
        color: #0055FF !important;
        border-color: rgba(74,158,255,0.3) !important;
    }

    /* --- 10. Sidebar Expander --- */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        border: 1px solid #E0E0E0 !important;
        border-radius: var(--radius-sm) !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details {
        background: transparent !important;
        border: none !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background: transparent !important;
        color: #1A1A1A !important;
        border: none !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
        background: #EAEAEA !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
        color: #1A1A1A !important;
        fill: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderContent"],
    section[data-testid="stSidebar"] [data-testid="stExpander"] details > div {
        background: transparent !important;
    }

    /* --- 11. Sidebar Caption --- */
    section[data-testid="stSidebar"] .stCaptionContainer,
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    section[data-testid="stSidebar"] .stCaption {
        color: #999999 !important;
    }

    /* --- 12. Sidebar Widget Labels --- */
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] strong,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown strong {
        color: #1A1A1A !important;
    }

    /* --- 12b. Sidebar text color enforcement --- */
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] .stTextInput > div > div > input,
    section[data-testid="stSidebar"] .stTextArea > div > div > textarea {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] .stSelectbox [data-value],
    section[data-testid="stSidebar"] .stSelectbox [role="combobox"] {
        color: #1A1A1A !important;
    }
    section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div {
        color: #1A1A1A !important;
    }

    /* --- 13. Sidebar Divider --- */
    section[data-testid="stSidebar"] hr {
        border-color: #E0E0E0 !important;
        opacity: 0.6 !important;
    }
</style>
<script>
(function() {
    function fixBtnColor() {
        document.querySelectorAll('div[data-testid="stBaseButton-primary"] button, div[data-testid="stBaseButton-primaryFormSubmit"] button, div[data-testid="stBaseButton-secondaryFormSubmit"] button, button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"], button[data-testid="stBaseButton-secondaryFormSubmit"]').forEach(function(btn) {
            btn.style.setProperty('color', '#1A1A1A', 'important');
        });
    }
    function fixAlignment() {
        document.querySelectorAll('[data-testid="stHorizontalBlock"]').forEach(function(block) {
            block.style.setProperty('align-items', 'flex-end', 'important');
        });
    }
    fixBtnColor();
    fixAlignment();
    var obs = new MutationObserver(function() { fixBtnColor(); fixAlignment(); });
    obs.observe(document.body, {childList: true, subtree: true});
})();
</script>
""", unsafe_allow_html=True)


def render_workbench_css():
    """Workbench theme for Briefing Center tab — Hermes paper-white palette."""
    st.markdown("""
<style>
    /* 隐藏定位标记 */
    .bf-workbench-scope {
        display: none !important;
    }

    /* 通过 :has() 将 workbench 样式限定到简报页激活时的主区（st.tabs 已由
       radio 主导航替代，旧 Tab panel 锚点失效）。
       CSS 变量与白纸表面挂在主区（等价旧 Tab panel 的白纸背景）；
       不改写 padding，避免标题/导航条位移。 */
    section[data-testid="stMain"]:has(.bf-workbench-scope) {
        --wb-surface: #FFFFFF;
        --wb-card: #FFFFFF;
        --wb-text-primary: #1A1A1A;
        --wb-text-secondary: #666666;
        --wb-accent: #0055FF;
        --wb-border: #E8E8E8;
        --wb-tag-source: #0055FF;
        --wb-tag-sub: #0055FF;
        --wb-tag-gen: #0055FF;
        --wb-tag-cat: #0055FF;
        --wb-green: #4ADE80;
        --wb-orange: #0055FF;
        --wb-red: #EF5350;
    }

    /* 去掉简报 Tab 内 .stMarkdown 容器自带的背景 / padding / margin */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .stMarkdown {
        background: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Override page title for workbench context */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .main-title {
        font-size: 28px !important;
        font-weight: 700 !important;
        color: var(--wb-text-primary) !important;
        letter-spacing: -0.02em !important;
        margin-bottom: 4px !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .main-subtitle {
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
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .bf-panel:hover {
        border-color: #CCCCCC;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .bf-panel.bf-panel--source { border-top-color: var(--wb-tag-source); }
    .bf-panel.bf-panel--sub { border-top-color: var(--wb-tag-sub); }
    .bf-panel.bf-panel--cat { border-top-color: var(--wb-tag-cat); }
    .bf-panel.bf-panel--gen { border-top-color: var(--wb-tag-source); }

    /* Onboarding 3-step bar */
    .bf-step {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-top: 3px solid var(--wb-border);
        border-radius: 8px;
        padding: 12px 14px;
        height: 100%;
        min-height: 84px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
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
        background: #F0F0F0;
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
        border-top-color: var(--wb-accent);
        background: #EFF6FF;
    }
    .bf-step--done .bf-step__index {
        background: var(--wb-accent);
        color: #FFFFFF;
    }
    .bf-step--current {
        border-top-color: var(--wb-accent);
        background: #FFF7ED;
    }
    .bf-step--current .bf-step__index {
        background: var(--wb-accent);
        color: #FFFFFF;
    }
    .bf-step--pending {
        border-top-color: var(--wb-border);
        opacity: 0.85;
    }

    /* 引导条按钮卡片样式 */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button {
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
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
        font-size: 13px;
        font-weight: 600;
        color: var(--wb-text-primary);
        display: flex;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.10);
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button .bf-step__index {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        font-size: 11px;
        font-weight: 700;
        flex-shrink: 0;
        background: #F0F0F0;
        color: var(--wb-text-secondary);
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker) [data-testid="stButton"] > button .bf-step__title {
        line-height: 1.4;
    }
    /* 三态配色 */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--done) [data-testid="stButton"] > button {
        border-top-color: var(--wb-accent);
        background: #EFF6FF;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--done) [data-testid="stButton"] > button .bf-step__index {
        background: var(--wb-accent);
        color: #FFFFFF;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--current) [data-testid="stButton"] > button {
        border-top-color: var(--wb-accent);
        background: #FFF7ED;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--current) [data-testid="stButton"] > button .bf-step__index {
        background: var(--wb-accent);
        color: #FFFFFF;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container [data-testid="stVerticalBlock"]:has(.bf-step-marker.bf-step--pending) [data-testid="stButton"] > button {
        border-top-color: var(--wb-border);
        opacity: 0.85;
    }

    /* 可折叠配置区 */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .stTabs [data-baseweb="tab-panel"] {
        background: transparent !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .stTabs .bf-panel {
        margin: 8px 0 0 0 !important;
        border-top-width: 3px !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container > div[data-testid="stVerticalBlock"] > div[data-testid="stToggle"] {
        margin-top: 18px !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .stContainer {
        border: 1px solid var(--wb-border);
        border-radius: 8px;
        padding: 14px 16px 4px 16px;
        margin-top: 6px;
        background: var(--wb-surface);
    }

    /* Section label as card header */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-panel > .bf-label {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 20px;
        padding-bottom: 0;
        border-bottom: none;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-panel > .bf-label + [data-testid="stExpander"],
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-panel > .bf-label + div [data-testid="stExpander"],
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-panel > .bf-label + div [data-testid="stAlertContainer"],
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-panel > .bf-label + div .stAlert {
        margin-top: 0 !important;
    }

    .bf-label__tag {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--wb-text-secondary);
        background: #F0F0F0;
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

    /* 生成简报 / 添加笔记 — 按钮对齐（强制底部对齐） */
    [data-key="bf-output"] .stButton,
    .bf-panel .stButton {
        display: flex !important;
        align-items: flex-end !important;
        justify-content: flex-start !important;
        margin: 0 !important;
        height: 100% !important;
    }
    [data-key="bf-output"] .stButton > button,
    .bf-panel .stButton > button {
        padding: 8px 20px !important;
        margin: 0 !important;
        margin-bottom: 0 !important;
        line-height: 1.5 !important;
        width: auto !important;
        white-space: nowrap !important;
    }

    /* 工作台作用域内所有按钮 — 白底深色文字（primary 规则在后面自然覆盖） */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stButton"] > button {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 5px 16px !important;
        min-height: 30px !important;
        transition: all 0.15s ease !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stButton"] > button:hover {
        background: #F5F5F5 !important;
        border-color: #CCCCCC !important;
    }

    /* 生成简报 / 添加笔记主按钮 — 白底深色文字+蓝色阴影（统一风格） */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stBaseButton-primary"] > button,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stBaseButton-primary"] button,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container button[data-testid="stBaseButton-primary"] {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 5px 16px !important;
        min-height: 30px !important;
        box-shadow: 0 4px 12px rgba(0,85,255,0.45) !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stBaseButton-primary"] > button:hover,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stBaseButton-primary"] button:hover,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container button[data-testid="stBaseButton-primary"]:hover {
        background: #F5F5F5 !important;
        box-shadow: 0 4px 16px rgba(0,85,255,0.4) !important;
    }

    /* Generate 概览折叠条 — 去掉边框（expander 在 .bf-panel--gen 内部） */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-panel--gen [data-testid="stExpander"],
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .element-container:has(> div > .bf-panel--gen) div[data-testid="stExpander"],
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .element-container:has(> div > .bf-panel--gen) + .element-container div[data-testid="stExpander"] {
        border: none !important;
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-panel--gen [data-testid="stExpander"] > summary,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .element-container:has(> div > .bf-panel--gen) div[data-testid="stExpander"] > summary,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .element-container:has(> div > .bf-panel--gen) + .element-container div[data-testid="stExpander"] > summary {
        border: none !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        color: var(--wb-text-secondary) !important;
        padding: 6px 12px !important;
    }

    /* 配置区 tab 切换器 */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] > div {
        display: flex;
        gap: 4px;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] label {
        border-radius: 6px 6px 0 0 !important;
        padding: 8px 16px !important;
        background: transparent !important;
        border: 1px solid var(--wb-border) !important;
        border-bottom: 2px solid transparent !important;
        color: var(--wb-text-secondary) !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] label:hover {
        background: var(--wb-surface) !important;
        color: var(--wb-text-primary) !important;
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] input:checked + div {
        background: var(--wb-surface) !important;
        color: var(--wb-text-primary) !important;
        border-color: var(--wb-border) !important;
        border-bottom: 2px solid var(--wb-accent) !important;
    }

    /* 生成结果统计 */
    [data-key^="bf-stats-"] {
        margin-top: 16px;
        padding: 14px 16px;
        border: 1px solid var(--wb-border);
        border-radius: 8px;
        background: var(--wb-surface);
    }

    /* 通用确认/操作按钮 */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stBaseButton-secondary"] > button,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container button[data-testid="stBaseButton-secondary"],
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container div[data-testid="stButton"] > button:not(:has(~ [data-testid="stBaseButton-primary"])):not(:has(~ [data-testid="stBaseButton-secondary"])) {
        padding: 6px 14px !important;
        min-height: 32px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
    }

    /* Output area */
    [data-key="bf-output"],
    [data-key="bf-entries"],
    [data-key="bf-history"] {
        background: var(--wb-card);
        border: 1px solid var(--wb-border);
        border-top: 3px solid var(--wb-accent);
        border-radius: 8px;
        padding: 20px 24px;
        margin: 12px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .bf-output__header {
        font-size: 13px;
        font-weight: 600;
        color: var(--wb-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--wb-border);
    }

    /* 历史列表 */
    .bf-history-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 0;
        border-bottom: 1px solid var(--wb-border);
    }
    .bf-history-item:last-child { border-bottom: none; }

    /* Hint */
    .bf-hint {
        margin: 4px 0 !important;
        padding: 6px 0 6px 12px !important;
        border-left: 3px solid var(--wb-border);
        color: var(--wb-text-secondary);
        font-size: 13px;
        line-height: 1.5;
    }
    .bf-hint--warn { border-left-color: var(--wb-accent); }

    /* Expander inside panel */
    .bf-panel [data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    .bf-panel [data-testid="stExpander"] details,
    .bf-panel [data-testid="stExpander"] > div {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    .bf-panel [data-testid="stExpander"] summary {
        border: none !important;
        background: transparent !important;
        border-radius: 0 !important;
        padding: 8px 4px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: var(--wb-text-primary) !important;
    }
    .bf-panel [data-testid="stExpander"] summary:hover { background: transparent !important; }
    .bf-panel [data-testid="stExpander"] summary p {
        font-weight: 600 !important;
        color: var(--wb-text-primary) !important;
    }
    .bf-panel [data-testid="stExpanderToggle"] {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: var(--wb-text-primary) !important;
    }
    .bf-panel [data-testid="stExpander"] + [data-testid="stExpander"] {
        border-top: 1px solid var(--wb-border) !important;
        margin-top: 4px !important;
        padding-top: 4px !important;
    }
    .bf-panel [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        padding: 4px 4px 8px 4px !important;
    }

    /* Flatten alerts inside card */
    .bf-panel .stAlert,
    .bf-panel [data-testid="stAlertContainer"],
    .bf-panel [data-testid="stAlertContainer"] > div,
    .bf-panel [data-baseweb="notification"] {
        background: transparent !important;
        border: none !important;
        border-left: 3px solid var(--wb-border) !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        padding: 6px 0 6px 12px !important;
        margin: 4px 0 !important;
    }
    .bf-panel .stAlert[data-baseweb="notification"][kind="info"] {
        border-left-color: var(--wb-tag-source) !important;
    }
    .bf-panel .stAlert[data-baseweb="notification"][kind="warning"] {
        border-left-color: var(--wb-accent) !important;
    }
    .bf-panel .stAlert [data-testid="stMarkdownContainer"],
    .bf-panel [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] {
        color: var(--wb-text-secondary) !important;
        font-size: 13px !important;
        line-height: 1.5 !important;
    }
    .bf-panel .stAlert [data-testid="stIcon"],
    .bf-panel [data-testid="stAlertContainer"] [data-testid="stIcon"] {
        color: var(--wb-text-secondary) !important;
        opacity: 0.7 !important;
    }

    /* Clean up old briefing styles */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .briefing-step-card,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .briefing-tip-box,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .briefing-config-panel,
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .briefing-config-divider {
        display: none !important;
    }

    /* Status dots */
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .status-dot {
        width: 6px;
        height: 6px;
    }

    /* Severity badges */
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

    /* ============================================================
       健康检查概览面板指标卡（任务3 · intelnexus/ui/health_dashboard.py）
       浅色底 + 左侧 4px 色条，仿 bf-panel 语言；色取 :root 强调色变量。
       ============================================================ */
    .hc-card {
        background: var(--bg-card);
        border: 1px solid var(--border-light);
        border-left: 3px solid var(--border-light);
        border-radius: var(--radius-sm);
        padding: 14px 18px 8px;
        margin: 12px 0;
        transition: border-color 0.15s ease;
    }
    .hc-card--healthy { border-left-color: rgba(74,222,128,0.35); }
    .hc-card--degraded { border-left-color: rgba(251,146,60,0.35); }
    .hc-card--down { border-left-color: rgba(239,68,68,0.35); }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .hc-card {
        background: var(--wb-surface);
        border-color: var(--wb-border);
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .hc-card--healthy { border-left-color: rgba(74,222,128,0.35); }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .hc-card--degraded { border-left-color: rgba(251,146,60,0.35); }
    section[data-testid="stMain"]:has(.bf-workbench-scope) .element-container:has(.app-main-scope) ~ .element-container .hc-card--down { border-left-color: rgba(239,68,68,0.35); }

    /* ============================================================
       今日概览首页（任务5 · intelnexus/ui/overview.py）
       隐藏 ov-scope marker + :has() 作用域，写法与 bf-workbench-scope 段一致；
       卡片复用 .hc-card 语言，主操作按钮遵「白底 + 蓝色阴影」主区规范。
       ============================================================ */
    .ov-scope {
        display: none !important;
    }

    /* 问候区：情感化副文案 + 日期弱化显示 */
    .ov-tagline {
        font-size: 15px !important;
        font-weight: 400;
        color: var(--text-secondary) !important;
        margin-top: 8px;
        line-height: 1.6;
    }
    .ov-date {
        font-size: 12px !important;
        color: var(--text-tertiary) !important;
        letter-spacing: 0.04em;
        margin-top: 6px;
    }

    /* 指标卡片区：纸白表面 + 等高对齐 + 左侧微弱色条 */
    .ov-card {
        flex: 1 !important;
        background: var(--bg-card);
        border: 1px solid var(--border-light) !important;
        border-left: 3px solid var(--border-light) !important;
        border-radius: var(--radius-sm) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        min-height: 140px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 20px 22px 14px;
        margin: 20px 0;
    }
    .ov-card.hc-card--healthy {
        border-left-color: rgba(74,222,128,0.35) !important;
    }
    .ov-card.hc-card--degraded {
        border-left-color: rgba(251,146,60,0.35) !important;
    }
    .ov-card.hc-card--down {
        border-left-color: rgba(239,68,68,0.35) !important;
    }
    .ov-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .ov-card__tag {
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-tertiary) !important;
    }
    .ov-card__value {
        font-size: 18px !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }
    .ov-card__sub {
        font-size: 12px !important;
        color: var(--text-secondary) !important;
        margin-top: 8px;
    }

    /* 数据源状态点阵：一行彩色圆点 + 短名称，快速定位故障源（视觉降级） */
    .ov-status-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 6px 14px;
        padding: 12px 0;
        margin: 16px 0 20px;
        opacity: 0.75;
    }
    .ov-status-dot {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        cursor: default;
    }
    .ov-status-dot .status-dot {
        width: 6px;
        height: 6px;
        flex-shrink: 0;
    }
    .ov-status-label {
        font-size: 11px !important;
        color: var(--text-secondary) !important;
        white-space: nowrap;
    }

    /* 主操作入口按钮 — 白底 + 柔和蓝色阴影 */
    section[data-testid="stMain"]:has(.ov-scope) div[data-testid="stButton"] > button {
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: var(--radius-md) !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        padding: 14px 24px !important;
        min-height: 48px !important;
        box-shadow: 0 2px 8px rgba(0,85,255,0.15) !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.01em !important;
    }
    section[data-testid="stMain"]:has(.ov-scope) div[data-testid="stButton"] > button:hover {
        background: #F5F5F5 !important;
        border-color: #CCCCCC !important;
        box-shadow: 0 4px 12px rgba(0,85,255,0.2) !important;
        transform: translateY(-1px) !important;
    }
    section[data-testid="stMain"]:has(.ov-scope) div[data-testid="stButton"] > button:active {
        transform: scale(0.98) !important;
    }
</style>
""", unsafe_allow_html=True)


def render_onboarding_css():
    """渲染首次使用向导的CSS样式 — Hermes 纸白与石墨风格。"""
    st.markdown("""
<style>
    /* --- Onboarding Wizard --- */
    .ob-wizard {
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        border-radius: 12px;
        padding: 40px;
        margin: 24px auto;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        max-width: 800px;
    }
    .ob-title {
        font-size: 32px;
        font-weight: 700;
        color: #1A1A1A;
        text-align: center;
        margin-bottom: 8px;
        letter-spacing: -0.02em;
    }
    .ob-subtitle {
        font-size: 16px;
        font-weight: 400;
        color: #666666;
        text-align: center;
        margin-bottom: 32px;
    }
    .ob-step-indicator {
        text-align: center;
        margin-bottom: 24px;
        font-size: 13px;
        color: #999999;
    }
    .ob-prompt {
        font-size: 18px;
        font-weight: 600;
        color: #1A1A1A;
        text-align: center;
        margin-bottom: 24px;
    }

    /* Choice Cards */
    .ob-choice-card {
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        border-top: 3px solid #E8E8E8;
        border-radius: 12px;
        padding: 32px 24px;
        text-align: center;
        min-height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .ob-choice-card:hover {
        border-top-color: #0055FF;
        box-shadow: 0 6px 20px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }
    .ob-choice-icon { font-size: 48px; margin-bottom: 16px; }
    .ob-choice-title {
        font-size: 18px;
        font-weight: 600;
        color: #1A1A1A;
        margin-bottom: 8px;
    }
    .ob-choice-desc {
        font-size: 13px;
        color: #666666;
        line-height: 1.5;
    }

    /* Skip Button */
    .ob-skip { text-align: center; margin-top: 24px; }
    .ob-skip button {
        background: transparent !important;
        border: none !important;
        color: #999999 !important;
        font-size: 13px !important;
        text-decoration: underline !important;
    }
    .ob-skip button:hover { color: #1A1A1A !important; }

    /* Success State */
    .ob-success-icon { font-size: 64px; text-align: center; margin-bottom: 16px; }
    .ob-complete-title {
        font-size: 24px;
        font-weight: 700;
        color: #1A1A1A;
        text-align: center;
        margin-bottom: 8px;
    }
    .ob-complete-desc {
        font-size: 14px;
        color: #666666;
        text-align: center;
        margin-bottom: 32px;
    }

    /* Category Checkboxes */
    .ob-category-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 16px;
        border-radius: 8px;
        transition: all 0.15s ease;
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        margin-bottom: 8px;
    }
    .ob-category-item:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        border-color: #0055FF;
    }

    /* Schedule Section */
    .ob-schedule-row {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 16px;
    }
    .ob-schedule-label {
        font-size: 14px;
        font-weight: 500;
        color: #1A1A1A;
        min-width: 80px;
    }
    /* ---- 状态栏窄屏裁剪（只隐藏低优先级段，健康段始终保留）----
       < 1100px 隐藏「今日」段（.sb-today）；< 900px 再隐藏调度器段（.sb-scheduler）。
       窗口宽度以视口为准；段类名由 render_status_bar 生成。 */
    @media (max-width: 1100px) {
        .sb-metrics .sb-today { display: none !important; }
    }
    @media (max-width: 900px) {
        .sb-metrics .sb-scheduler { display: none !important; }
    }
</style>
""", unsafe_allow_html=True)


def render_status_bar(metrics: "dict | None" = None):
    """Render Hermes-style bottom status bar.

    - metrics 为 None：纯静态渲染（向后兼容旧调用方式）。
    - metrics 传入 {"health": {...}, "scheduler": {...}, "today": {...}}
      （由调用方组装）：右侧追加运行指标段。每段独立 try/except，
      单段失败不影响其余段与整栏。
    本函数只渲染不取数；颜色一律走 :root CSS 变量。
    """
    import datetime
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%Y-%m-%d")

    # 左侧圆点颜色随健康态动态变化：全正常/无数据为绿，有降级橙，有 down 红
    dot_color = "var(--accent-green)"
    if isinstance(metrics, dict):
        try:
            _h = metrics.get("health") or {}
            if int(_h.get("down") or 0) > 0:
                dot_color = "var(--accent-red)"
            elif int(_h.get("degraded") or 0) > 0:
                dot_color = "var(--accent-orange)"
        except Exception:
            dot_color = "var(--accent-green)"

    # --- 右侧运行指标段（仅当传入 metrics 时渲染）---
    metrics_html = ""
    if isinstance(metrics, dict):
        # 延迟导入 i18n：保持 core 层模块加载期不依赖 ui 层（函数内局部导入先例见上方 datetime）
        try:
            from intelnexus.ui.i18n import get_text
        except Exception:
            get_text = None

        if get_text is not None:
            segs = []

            # 数据源健康段：全正常时只显示「● N 正常」（降噪），
            # 有降级/异常时追加对应颜色的「▲ N 降级」「✕ N 异常」
            try:
                h = metrics.get("health") or {}
                total = int(h.get("total") or 0)
                healthy = int(h.get("healthy") or 0)
                degraded = int(h.get("degraded") or 0)
                down = int(h.get("down") or 0)
                if total > 0:
                    parts = []
                    if healthy > 0 or (degraded == 0 and down == 0):
                        parts.append(
                            '<span style="color: var(--accent-green);">● '
                            + get_text("sb_health_ok").format(n=healthy) + "</span>"
                        )
                    if degraded > 0:
                        parts.append(
                            '<span style="color: var(--accent-orange);">▲ '
                            + get_text("sb_health_degraded").format(n=degraded) + "</span>"
                        )
                    if down > 0:
                        parts.append(
                            '<span style="color: var(--accent-red);">✕ '
                            + get_text("sb_health_down").format(n=down) + "</span>"
                        )
                    if parts:
                        segs.append(
                            '<span class="sb-health" style="white-space: nowrap;">' + " ".join(parts) + "</span>"
                        )
            except Exception:
                pass

            # 调度器段：有任务显示下次推送时间；空载显示空闲；未运行灰字手动模式
            try:
                s = metrics.get("scheduler") or {}
                if s.get("running"):
                    if int(s.get("job_count") or 0) > 0 and s.get("next_run_str"):
                        segs.append(
                            '<span class="sb-scheduler" style="white-space: nowrap;">'
                            + get_text("sb_next_push").format(when=s["next_run_str"])
                            + "</span>"
                        )
                    else:
                        segs.append(
                            '<span class="sb-scheduler" style="white-space: nowrap;">'
                            + get_text("sb_scheduler_idle") + "</span>"
                        )
                else:
                    segs.append(
                        '<span class="sb-scheduler" style="white-space: nowrap; color: var(--text-tertiary);">'
                        + get_text("sb_manual_mode") + "</span>"
                    )
            except Exception:
                pass

            # 今日统计段：简报与推送均为 0 时整段隐藏
            try:
                t = metrics.get("today") or {}
                b = int(t.get("briefings_today") or 0)
                p = int(t.get("pushes_today") or 0)
                if b > 0 or p > 0:
                    segs.append(
                        '<span class="sb-today" style="white-space: nowrap;">'
                        + get_text("sb_today").format(b=b, p=p) + "</span>"
                    )
            except Exception:
                pass

            if segs:
                metrics_html = "".join(segs)

    # 无指标段（如测试环境）时追加空容器标记，便于测试与样式定位。
    metrics_cls = "sb-metrics" + ("" if metrics_html else " sb-metrics-empty")

    status_html = """
    <div style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 32px;
        background-color: var(--bg-status-bar);
        border-top: 1px solid var(--border-medium);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 16px;
        font-size: 12px;
        color: var(--text-tertiary);
        white-space: nowrap;
        z-index: 9999;
        font-family: var(--font-ui);
    ">
        <div style="display: flex; align-items: center; gap: 16px;">
            <span style="display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background-color: """ + dot_color + """; display: inline-block; box-shadow: 0 0 6px color-mix(in srgb, """ + dot_color + """ 40%, transparent);"></span>
                IntelNexus
            </span>
            <span>""" + date_str + """</span>
            <span>""" + time_str + """</span>
        </div>
        <div class=""" + '"' + metrics_cls + '"' + """ style="display: flex; align-items: center; gap: 16px; min-width: 0; overflow: hidden;">
            """ + metrics_html + """
            <span>Intel Search Engine</span>
        </div>
    </div>
    """
    st.markdown(status_html, unsafe_allow_html=True)
