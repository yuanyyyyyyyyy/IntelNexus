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
    /* Remove dark theme gradient background */
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
</style>
""", unsafe_allow_html=True)
