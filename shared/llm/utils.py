import requests
from urllib.parse import urljoin
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Callable, Optional, List
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks.base import BaseCallbackHandler
from shared.settings import get as get_config

from shared.logger import get_logger

logger = get_logger(__name__)


class BufferedStreamingHandler(BaseCallbackHandler):
    def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            logger.debug(self.buffer)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        if self.buffer:
            logger.debug(self.buffer)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""


_common_llm_params = {
    "temperature": 0,
    "streaming": True,
    "request_timeout": 120,
    "max_retries": 3,
}


def _get_config_values():
    """Get config values from injected config."""
    return {
        "OLLAMA_BASE_URL": get_config("OLLAMA_BASE_URL", ""),
        "OPENROUTER_BASE_URL": get_config("OPENROUTER_BASE_URL", ""),
        "OPENROUTER_API_KEY": get_config("OPENROUTER_API_KEY", ""),
        "GOOGLE_API_KEY": get_config("GOOGLE_API_KEY", ""),
    }


def _build_llm_config_map():
    """Build the LLM config map with current config values."""
    cfg = _get_config_values()
    return {
        'gpt-4.1': {
            'class': ChatOpenAI,
            'constructor_params': {'model_name': 'gpt-4.1'}
        },
        'gpt-5.1': {
            'class': ChatOpenAI,
            'constructor_params': {'model_name': 'gpt-5.1'}
        },
        'gpt-5-mini': {
            'class': ChatOpenAI,
            'constructor_params': {'model_name': 'gpt-5-mini'}
        },
        'gpt-5-nano': {
            'class': ChatOpenAI,
            'constructor_params': {'model_name': 'gpt-5-nano'}
        },
        'claude-sonnet-4-5': {
            'class': ChatAnthropic,
            'constructor_params': {'model': 'claude-sonnet-4-5'}
        },
        'claude-sonnet-4-0': {
            'class': ChatAnthropic,
            'constructor_params': {'model': 'claude-sonnet-4-0'}
        },
        'gemini-2.5-flash': {
            'class': ChatGoogleGenerativeAI,
            'constructor_params': {'model': 'gemini-2.5-flash', 'google_api_key': cfg["GOOGLE_API_KEY"]}
        },
        'gemini-2.5-flash-lite': {
            'class': ChatGoogleGenerativeAI,
            'constructor_params': {'model': 'gemini-2.5-flash-lite', 'google_api_key': cfg["GOOGLE_API_KEY"]}
        },
        'gemini-2.5-pro': {
            'class': ChatGoogleGenerativeAI,
            'constructor_params': {'model': 'gemini-2.5-pro', 'google_api_key': cfg["GOOGLE_API_KEY"]}
        },
        'gpt-5.1-openrouter': {
            'class': ChatOpenAI,
            'constructor_params': {
                'model_name': 'openai/gpt-5.1',
                'base_url': cfg["OPENROUTER_BASE_URL"],
                'api_key': cfg["OPENROUTER_API_KEY"]
            }
        },
        'gpt-5-mini-openrouter': {
            'class': ChatOpenAI,
            'constructor_params': {
                'model_name': 'openai/gpt-5-mini',
                'base_url': cfg["OPENROUTER_BASE_URL"],
                'api_key': cfg["OPENROUTER_API_KEY"]
            }
        },
        'claude-sonnet-4.5-openrouter': {
            'class': ChatOpenAI,
            'constructor_params': {
                'model_name': 'anthropic/claude-sonnet-4.5',
                'base_url': cfg["OPENROUTER_BASE_URL"],
                'api_key': cfg["OPENROUTER_API_KEY"]
            }
        },
        'grok-4.1-fast-openrouter': {
            'class': ChatOpenAI,
            'constructor_params': {
                'model_name': 'x-ai/grok-4.1-fast',
                'base_url': cfg["OPENROUTER_BASE_URL"],
                'api_key': cfg["OPENROUTER_API_KEY"]
            }
        },
    }


def _normalize_model_name(name: str) -> str:
    return name.strip().lower()


def _get_ollama_base_url() -> Optional[str]:
    base_url = get_config("OLLAMA_BASE_URL", "")
    if not base_url:
        return None
    return base_url.rstrip("/") + "/"


def fetch_ollama_models() -> List[str]:
    """
    Retrieve the list of locally available Ollama models by querying the Ollama HTTP API.
    Returns an empty list if the API isn't reachable or the base URL is not defined.
    Results are cached for 5 minutes to avoid repeated HTTP calls.
    """
    import time
    base_url = _get_ollama_base_url()
    if not base_url:
        return []

    now = time.time()
    if _ollama_models_cache["models"] is not None and now - _ollama_models_cache["time"] < 300:
        return _ollama_models_cache["models"]

    try:
        resp = requests.get(urljoin(base_url, "api/tags"), timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        available = []
        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                available.append(name)
        _ollama_models_cache["models"] = available
        _ollama_models_cache["time"] = now
        return available
    except (requests.RequestException, ValueError):
        _ollama_models_cache["models"] = []
        _ollama_models_cache["time"] = now
        return []


_ollama_models_cache = {"models": None, "time": 0}


def get_model_choices() -> List[str]:
    """
    Combine the statically configured cloud models with the locally available Ollama models and custom models.
    """
    _llm_config_map = _build_llm_config_map()
    base_models = list(_llm_config_map.keys())
    dynamic_models = fetch_ollama_models()

    try:
        from shared.llm.models import get_custom_model_names
        custom_models = get_custom_model_names()
    except ImportError:
        custom_models = []

    normalized = {_normalize_model_name(m): m for m in base_models}

    for dm in dynamic_models:
        key = _normalize_model_name(dm)
        if key not in normalized:
            normalized[key] = dm

    for cm in custom_models:
        key = _normalize_model_name(cm)
        if key not in normalized:
            normalized[key] = cm

    ordered_dynamic = sorted(
        [name for key, name in normalized.items() if name not in base_models and name not in custom_models],
        key=_normalize_model_name,
    )
    return base_models + custom_models + ordered_dynamic


def resolve_model_config(model_choice: str):
    """
    Resolve a model choice (case-insensitive) to the corresponding configuration.
    Supports predefined remote models, locally installed Ollama models, and custom models.
    """
    _llm_config_map = _build_llm_config_map()
    model_choice_lower = _normalize_model_name(model_choice)

    config = _llm_config_map.get(model_choice_lower)
    if config:
        return config

    for ollama_model in fetch_ollama_models():
        if _normalize_model_name(ollama_model) == model_choice_lower:
            return {
                "class": ChatOllama,
                "constructor_params": {"model": ollama_model, "base_url": get_config("OLLAMA_BASE_URL", "")},
            }

    try:
        from shared.llm.models import get_model_config, get_custom_model_names
        for custom_model_name in get_custom_model_names():
            if _normalize_model_name(custom_model_name) == model_choice_lower:
                model_config = get_model_config(custom_model_name)
                if model_config:
                    model_type = model_config.get("type", "").lower()
                    config_params = model_config.get("config", {})

                    if model_type == "openai":
                        return {
                            "class": ChatOpenAI,
                            "constructor_params": {
                                "model_name": config_params.get("model_name", custom_model_name),
                                "base_url": config_params.get("base_url"),
                                "api_key": config_params.get("api_key"),
                            }
                        }
                    elif model_type == "azure openai":
                        return {
                            "class": ChatOpenAI,
                            "constructor_params": {
                                "model_name": config_params.get("model_name", custom_model_name),
                                "azure_endpoint": config_params.get("base_url"),
                                "api_key": config_params.get("api_key"),
                                "api_version": "2024-02-01",
                            }
                        }
                    elif model_type == "ollama":
                        return {
                            "class": ChatOllama,
                            "constructor_params": {
                                "model": config_params.get("model_name", custom_model_name),
                                "base_url": config_params.get("base_url", get_config("OLLAMA_BASE_URL", "")),
                            }
                        }
                    elif model_type == "anthropic":
                        return {
                            "class": ChatAnthropic,
                            "constructor_params": {
                                "model": config_params.get("model_name", custom_model_name),
                                "api_key": config_params.get("api_key"),
                            }
                        }
                    elif model_type == "google":
                        return {
                            "class": ChatGoogleGenerativeAI,
                            "constructor_params": {
                                "model": config_params.get("model_name", custom_model_name),
                                "google_api_key": config_params.get("api_key"),
                            }
                        }
                    elif model_type in ["cohere", "mistral", "deepseek", "通义千问", "智谱ai", "百度文心一言", "讯飞星火", "moonshot", "01.ai"]:
                        return {
                            "class": ChatOpenAI,
                            "constructor_params": {
                                "model_name": config_params.get("model_name", custom_model_name),
                                "base_url": config_params.get("base_url"),
                                "api_key": config_params.get("api_key"),
                            }
                        }
    except ImportError:
        pass

    return None
