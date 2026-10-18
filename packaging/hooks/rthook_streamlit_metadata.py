"""
PyInstaller runtime hook: patch importlib.metadata for Streamlit.
Streamlit uses importlib.metadata.version("streamlit") at import time,
which fails in bundled apps because dist-info directories are missing.
This hook provides a fallback that returns the version from streamlit.__version__.
"""
import sys

if getattr(sys, "frozen", False):
    import importlib.metadata
    _original_version = importlib.metadata.version

    def _patched_version(name: str) -> str:
        if name == "streamlit":
            try:
                import streamlit
                return getattr(streamlit, "__version__", "0.0.0")
            except Exception:
                return "0.0.0"
        return _original_version(name)

    importlib.metadata.version = _patched_version
