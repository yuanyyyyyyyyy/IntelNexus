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
    /* 图标兜底（修复：Material Icons 连字字体被墙时，折叠面板图标
       显示为原始英文文本 keyboard_arrow_right 叠在中文标题上）。
       隐藏连字文本，用纯 CSS 画一个旋转箭头，零字体依赖。 */
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
        border-right: 2px solid #8A8A8A !important;
        border-bottom: 2px solid #8A8A8A !important;
        transform: rotate(45deg) !important;
        transition: transform 0.15s ease !important;
        display: block !important;
    }
    [data-testid="stExpander"][open] span[data-testid="stIconMaterial"]::before {
        transform: rotate(225deg) !important;
    }

    /* 字体栈去掉被墙的 Google Fonts @import（曾拖慢 CSS 应用且加载失败） */
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

    /* 历史列表条目：清晰分隔、信息分层 */
    .bf-history-item {
        padding: 12px 0;
        border-bottom: 1px solid var(--wb-border);
    }
    .bf-history-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }
    .bf-history-item__time {
        font-size: 14px;
        font-weight: 600;
        color: var(--wb-text-primary);
        line-height: 1.4;
    }
    .bf-history-item__meta {
        margin-top: 4px;
        font-size: 12px;
        color: var(--wb-text-secondary);
        line-height: 1.5;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
    }
    .bf-history-item__org {
        font-weight: 500;
        color: var(--wb-text-primary);
    }
    .bf-history-item__sep {
        color: var(--wb-border);
    }
    /* 历史条目内的查看/删除按钮：轻量文字按钮风格，与左侧信息协调 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-history-item button {
        width: 100% !important;
        min-height: 28px !important;
        padding: 2px 10px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        border-radius: 5px !important;
        background: transparent !important;
        color: var(--wb-text-secondary) !important;
        border: 1px solid var(--wb-border) !important;
        box-shadow: none !important;
        writing-mode: horizontal-tb !important;
        text-orientation: mixed !important;
        white-space: nowrap !important;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-history-item button:hover {
        background: var(--wb-surface) !important;
        color: var(--wb-text-primary) !important;
        border-color: var(--wb-accent) !important;
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
        /* 语义辅助色（修复：briefing_viewer 可信度三档着色引用了从未定义的
           --wb-green/orange/red，浏览器忽略非法值导致着色整体失效）。
           取 Morandi 同族但加深一档，白底上对比度 ≥ 4.5:1（WCAG AA 正文级）。 */
        --wb-green: #5F7358;
        --wb-orange: #9A6B3F;
        --wb-red: #9C4848;
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
    .bf-panel.bf-panel--cat { border-top-color: var(--wb-tag-cat); }
    .bf-panel.bf-panel--gen { border-top-color: var(--wb-tag-gen); }

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
    /* 标题头与首个内部分区之间保留自然间距，避免内容紧贴标题 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label {
        margin-bottom: 20px;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label + [data-testid="stExpander"],
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label + div [data-testid="stExpander"],
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label + div [data-testid="stAlertContainer"],
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-panel > .bf-label + div .stAlert {
        margin-top: 0 !important;
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

    /* Generate 主按钮：紧凑、自适应宽度，彻底覆盖 Streamlit 默认大按钮
       通过隐藏 marker(.bf-gen-btn-marker) 稳定命中，不依赖 DOM 兄弟顺序 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-gen-btn-marker + .element-container div[data-testid="stButton"] > button,
    div[role="tabpanel"]:has(.bf-workbench-scope) .element-container:has(.bf-gen-btn-marker) + .element-container div[data-testid="stButton"] > button {
        width: auto !important;
        height: auto !important;
        min-height: 30px !important;
        padding: 5px 16px !important;
        background: var(--wb-accent) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        line-height: 1.2 !important;
        transition: background 0.15s ease !important;
    }

    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-gen-btn-marker + .element-container div[data-testid="stButton"] > button:hover,
    div[role="tabpanel"]:has(.bf-workbench-scope) .element-container:has(.bf-gen-btn-marker) + .element-container div[data-testid="stButton"] > button:hover {
        background: #8E938A !important;
        transform: none !important;
    }

    /* Generate 概览折叠条：轻量、收敛，不喧宾夺主
       基于 .bf-panel--gen 卡片头后面的 columns 命中，不再依赖 .bf-gen-header */
    div[role="tabpanel"]:has(.bf-workbench-scope) .element-container:has(> div > .bf-panel--gen) + .element-container div[data-testid="stExpander"] {
        border: 1px solid var(--wb-border) !important;
        border-radius: 6px !important;
        background: transparent !important;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .element-container:has(> div > .bf-panel--gen) + .element-container div[data-testid="stExpander"] > summary {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: var(--wb-text-secondary) !important;
        padding: 6px 12px !important;
    }

    /* 配置区 tab 切换器：把横向 radio 渲染成 tab 标签 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] > div {
        display: flex;
        gap: 4px;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] label {
        border-radius: 6px 6px 0 0 !important;
        padding: 8px 16px !important;
        background: transparent !important;
        border: 1px solid var(--wb-border) !important;
        border-bottom: 2px solid transparent !important;
        color: var(--wb-text-secondary) !important;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] label:hover {
        background: var(--wb-surface) !important;
        color: var(--wb-text-primary) !important;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-settings-tabs-marker + .element-container div[data-testid="stRadio"] input:checked + div {
        background: var(--wb-surface) !important;
        color: var(--wb-text-primary) !important;
        border-color: var(--wb-border) !important;
        border-bottom: 2px solid var(--wb-accent) !important;
    }

    /* 生成结果统计：轻量卡片，与主操作区视觉分离 */
    .bf-generate-stats {
        margin-top: 16px;
        padding: 14px 16px;
        border: 1px solid var(--wb-border);
        border-radius: 8px;
        background: var(--wb-surface);
    }

    /* 通用确认/操作按钮：收紧尺寸，避免「添加数据源」「保存」「删除」等过大 */
    div[role="tabpanel"]:has(.bf-workbench-scope) div[data-testid="stButton"] > button[kind="secondary"],
    div[role="tabpanel"]:has(.bf-workbench-scope) div[data-testid="stButton"] > button:not([kind="primary"]):not([kind="secondary"]) {
        padding: 6px 14px !important;
        min-height: 32px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
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

    /* 历史列表条目：清晰分隔、信息分层 */
    .bf-history-item {
        padding: 12px 0;
        border-bottom: 1px solid var(--wb-border);
    }
    .bf-history-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }
    .bf-history-item__time {
        font-size: 14px;
        font-weight: 600;
        color: var(--wb-text-primary);
        line-height: 1.4;
    }
    .bf-history-item__meta {
        margin-top: 4px;
        font-size: 12px;
        color: var(--wb-text-secondary);
        line-height: 1.5;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
    }
    .bf-history-item__org {
        font-weight: 500;
        color: var(--wb-text-primary);
    }
    .bf-history-item__sep {
        color: var(--wb-border);
    }
    /* 历史条目内的查看/删除按钮：轻量文字按钮风格，与左侧信息协调 */
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-history-item button {
        width: 100% !important;
        min-height: 28px !important;
        padding: 2px 10px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        border-radius: 5px !important;
        background: transparent !important;
        color: var(--wb-text-secondary) !important;
        border: 1px solid var(--wb-border) !important;
        box-shadow: none !important;
        writing-mode: horizontal-tb !important;
        text-orientation: mixed !important;
        white-space: nowrap !important;
    }
    div[role="tabpanel"]:has(.bf-workbench-scope) .bf-history-item button:hover {
        background: var(--wb-surface) !important;
        color: var(--wb-text-primary) !important;
        border-color: var(--wb-accent) !important;
    }

    /* Light inline hint used for empty-state / module-unavailable messages
       inside cards — reads as part of the card, not a separate alert block */
    .bf-hint {
        margin: 4px 0 !important;
        padding: 6px 0 6px 12px !important;
        border-left: 3px solid var(--wb-border);
        color: var(--wb-text-secondary);
        font-size: 13px;
        line-height: 1.5;
    }
    .bf-hint--warn {
        border-left-color: #C99A2E;
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

    /* Flatten st.info / st.warning inside the card: keep them as inline
       light hints (left color bar only) instead of standalone alert blocks */
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
        border-left-color: #C99A2E !important;
    }
    .bf-panel .stAlert [data-testid="stMarkdownContainer"],
    .bf-panel [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] {
        color: var(--wb-text-secondary) !important;
        font-size: 13px !important;
        line-height: 1.5 !important;
    }
    /* mute the icon so it doesn't read as a separate colored chip */
    .bf-panel .stAlert [data-testid="stIcon"],
    .bf-panel [data-testid="stAlertContainer"] [data-testid="stIcon"] {
        color: var(--wb-text-secondary) !important;
        opacity: 0.7 !important;
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

    /* 条目操作行：紧凑小按钮 + 右对齐 URL */
    .bf-entry-row + div[data-testid="stHorizontalBlock"] {
        margin-top: -4px;
        align-items: center;
    }
    .bf-entry-row + div[data-testid="stHorizontalBlock"] button {
        font-size: 11px !important;
        padding: 2px 8px !important;
        min-height: 0 !important;
        border-radius: 6px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    .bf-entry-url {
        font-size: 10.5px;
        color: var(--wb-text-secondary);
        opacity: 0.75;
        display: inline-block;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        direction: rtl;
        text-align: left;
    }
</style>
""", unsafe_allow_html=True)


def render_onboarding_css():
    """渲染首次使用向导的CSS样式"""
    st.markdown("""
<style>
    /* --- Onboarding Wizard --- */
    .ob-wizard {
        background: var(--morandi-card);
        border: 1px solid var(--morandi-border);
        border-radius: 18px;
        padding: 40px;
        margin: 24px 0;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }

    .ob-title {
        font-size: 32px;
        font-weight: 700;
        color: var(--morandi-text);
        text-align: center;
        margin-bottom: 8px;
        letter-spacing: -0.02em;
    }

    .ob-subtitle {
        font-size: 16px;
        font-weight: 400;
        color: var(--morandi-text-light);
        text-align: center;
        margin-bottom: 32px;
    }

    .ob-step-indicator {
        text-align: center;
        margin-bottom: 24px;
        font-size: 13px;
        color: var(--morandi-text-light);
    }

    .ob-prompt {
        font-size: 18px;
        font-weight: 600;
        color: var(--morandi-text);
        text-align: center;
        margin-bottom: 24px;
    }

    /* Choice Cards */
    .ob-choice-card {
        background: #FFFFFF;
        border: 1px solid var(--morandi-border);
        border-top: 3px solid var(--morandi-border);
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
        border-top-color: var(--morandi-accent);
        box-shadow: 0 4px 16px rgba(123,156,181,0.12);
        transform: translateY(-2px);
    }

    .ob-choice-icon {
        font-size: 48px;
        margin-bottom: 16px;
    }

    .ob-choice-title {
        font-size: 18px;
        font-weight: 600;
        color: var(--morandi-text);
        margin-bottom: 8px;
    }

    .ob-choice-desc {
        font-size: 13px;
        color: var(--morandi-text-light);
        line-height: 1.5;
    }

    /* Skip Button */
    .ob-skip {
        text-align: center;
        margin-top: 24px;
    }

    .ob-skip button {
        background: transparent !important;
        border: none !important;
        color: var(--morandi-text-light) !important;
        font-size: 13px !important;
        text-decoration: underline !important;
    }

    .ob-skip button:hover {
        color: var(--morandi-text) !important;
    }

    /* Success State */
    .ob-success-icon {
        font-size: 64px;
        text-align: center;
        margin-bottom: 16px;
    }

    .ob-complete-title {
        font-size: 24px;
        font-weight: 700;
        color: var(--morandi-text);
        text-align: center;
        margin-bottom: 8px;
    }

    .ob-complete-desc {
        font-size: 14px;
        color: var(--morandi-text-light);
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
        transition: background 0.15s ease;
        background: #FFFFFF;
        border: 1px solid var(--morandi-border);
        margin-bottom: 8px;
    }

    .ob-category-item:hover {
        background: var(--morandi-card);
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
        color: var(--morandi-text);
        min-width: 80px;
    }
</style>
""", unsafe_allow_html=True)
