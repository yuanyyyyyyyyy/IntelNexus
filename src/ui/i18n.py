"""
Combined i18n — merges keys from intel-search and intel-briefing sub-projects.
"""
import os
import importlib.util
import streamlit as st

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _load_lang(subproject):
    path = os.path.join(_root, subproject, "src", "ui", "i18n.py")
    spec = importlib.util.spec_from_file_location(f"{subproject}_i18n", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "LANG", {})

_search_lang = None
_briefing_lang = None

def _get_search_lang():
    global _search_lang
    if _search_lang is None:
        _search_lang = _load_lang("intel-search")
    return _search_lang

def _get_briefing_lang():
    global _briefing_lang
    if _briefing_lang is None:
        _briefing_lang = _load_lang("intel-briefing")
    return _briefing_lang


def get_text(key):
    lang_code = st.session_state.get("lang", "zh")
    search = _get_search_lang().get(lang_code, {})
    if key in search:
        return search[key]
    briefing = _get_briefing_lang().get(lang_code, {})
    if key in briefing:
        return briefing[key]
    return _get_search_lang().get("zh", {}).get(key, key)
