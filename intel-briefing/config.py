"""Re-export config from root project."""
import sys
import os
import importlib.util

_root_dir = os.path.join(os.path.dirname(__file__), "..")
_root_config_path = os.path.join(_root_dir, "config.py")

# Load root config as a unique module to avoid circular import
spec = importlib.util.spec_from_file_location("_root_config", _root_config_path)
_root_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_root_config)

OPENAI_API_KEY = _root_config.OPENAI_API_KEY
ANTHROPIC_API_KEY = _root_config.ANTHROPIC_API_KEY
GOOGLE_API_KEY = _root_config.GOOGLE_API_KEY
OLLAMA_BASE_URL = _root_config.OLLAMA_BASE_URL
OPENROUTER_BASE_URL = _root_config.OPENROUTER_BASE_URL
OPENROUTER_API_KEY = _root_config.OPENROUTER_API_KEY
NEWS_API_KEY = _root_config.NEWS_API_KEY
ENABLE_DARKWEB = _root_config.ENABLE_DARKWEB
TOR_PROXY_PORT = _root_config.TOR_PROXY_PORT
ENABLE_CREDIBILITY = _root_config.ENABLE_CREDIBILITY
