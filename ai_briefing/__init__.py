"""Thin wrapper: re-export ai_briefing from intel-briefing sub-project."""
import importlib.util as _ilu, os as _os, sys as _sys

_pkg = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                     "..", "intel-briefing", "ai_briefing")
_sub = _os.path.join(_pkg, "__init__.py")
if _os.path.exists(_sub):
    _spec = _ilu.spec_from_file_location("ai_briefing._init", _sub)
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    # Re-export all public names
    for _k in dir(_mod):
        if not _k.startswith("_"):
            globals()[_k] = getattr(_mod, _k)
