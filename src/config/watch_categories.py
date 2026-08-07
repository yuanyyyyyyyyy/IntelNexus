"""Thin wrapper: re-export from intel-briefing sub-project."""
import importlib.util as _ilu, os as _os, sys as _sys

_spec = _ilu.spec_from_file_location(
    __name__,
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                  "..", "..", "intel-briefing", "src", "config", "watch_categories.py"))
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_sys.modules[__name__] = _mod
