"""
IntelNexus Unified Streamlit UI
===============================
Combines search and briefing UI from sub-projects.
"""
import os
import sys

# Add sub-projects to path
_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_root, "shared"))
sys.path.insert(0, os.path.join(_root, "intel-search"))
sys.path.insert(0, os.path.join(_root, "intel-briefing"))

import streamlit as st

st.set_page_config(
    page_title="IntelNexus",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# --- Combined i18n ---
from intel_search_src_ui_i18n import get_text as _search_get_text
from intel_briefing_src_ui_i18n import get_text as _briefing_get_text
from shared_ui_styles import render_light_theme_css, render_morandi_theme_css

_search_i18n = None
_briefing_i18n = None

def _load_search_i18n():
    global _search_i18n
    if _search_i18n is None:
        from intel_search_src_ui_i18n import I18N as s
        _search_i18n = s
    return _search_i18n

def _load_briefing_i18n():
    global _briefing_i18n
    if _briefing_i18n is None:
        from intel_briefing_src_ui_i18n import I18N as b
        _briefing_i18n = b
    return _briefing_i18n

def get_text(key):
    """Get translated text, trying search i18n first, then briefing."""
    lang = st.session_state.get("lang", "zh")
    i18n = _load_search_i18n()
    if key in i18n.get(lang, {}):
        return i18n[lang][key]
    i18n = _load_briefing_i18n()
    if key in i18n.get(lang, {}):
        return i18n[lang][key]
    return key
