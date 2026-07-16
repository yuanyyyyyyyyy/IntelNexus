import requests
from urllib.parse import urljoin
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Callable, Optional, List
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks.base import BaseCallbackHandler
from config import OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY, GOOGLE_API_KEY

from src.logger import get_logger

logger = get_logger(__name__)


class BufferedStreamingHandler(BaseCallbackHandler):
    def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            logger.info(self.buffer)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        if self.buffer:
            logger.info(self.buffer)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""


# --- Configuration Data ---
# Instantiate common dependencies once
_common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]

# Define common parameters for most LLMs
_common_llm_params = {
    "temperature": 0,
    "streaming": True,
    "callbacks": _common_callbacks,
    "request_timeout": 120,  # API 请求超时 120 秒
    "max_retries": 3,       # 失败后最多重试 3 次
}

# Map input model choices (lowercased) to their configuration
# Each config includes the class and any model-specific constructor parameters
_llm_config_map = {
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
        'constructor_params': {'model': 'gemini-2.5-flash', 'google_api_key': GOOGLE_API_KEY }
    },
    'gemini-2.5-flash-lite': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-flash-lite', 'google_api_key': GOOGLE_API_KEY}
    },
    'gemini-2.5-pro': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-pro', 'google_api_key': GOOGLE_API_KEY}
    },
    'gpt-5.1-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'openai/gpt-5.1',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    'gpt-5-mini-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'openai/gpt-5-mini',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    'claude-sonnet-4.5-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'anthropic/claude-sonnet-4.5',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    'grok-4.1-fast-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'x-ai/grok-4.1-fast',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    # 'llama3.2': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'llama3.2:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'llama3.1': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'llama3.1:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'gemma3': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'gemma3:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'deepseek-r1': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'deepseek-r1:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    
    # Add more models here easily:
    # 'mistral7b': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'mistral:7b', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'gpt3.5': {
    #      'class': ChatOpenAI,
    #      'constructor_params': {'model_name': 'gpt-3.5-turbo', 'base_url': OLLAMA_BASE_URL}
    # }
}


def _normalize_model_name(name: str) -> str:
    return name.strip().lower()


def _get_ollama_base_url() -> Optional[str]:
    if not OLLAMA_BASE_URL:
        return None
    return OLLAMA_BASE_URL.rstrip("/") + "/"


def fetch_ollama_models() -> List[str]:
    """
    Retrieve the list of locally available Ollama models by querying the Ollama HTTP API.
    Returns an empty list if the API isn't reachable or the base URL is not defined.
    """
    base_url = _get_ollama_base_url()
    if not base_url:
        return []

    try:
        resp = requests.get(urljoin(base_url, "api/tags"), timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        available = []
        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                available.append(name)
        return available
    except (requests.RequestException, ValueError):
        return []


def get_model_choices() -> List[str]:
    """
    Combine the statically configured cloud models with the locally available Ollama models and custom models.
    """
    base_models = list(_llm_config_map.keys())
    dynamic_models = fetch_ollama_models()
    
    # Import custom models
    try:
        from src.llm.models import get_custom_model_names
        custom_models = get_custom_model_names()
    except ImportError:
        custom_models = []

    normalized = {_normalize_model_name(m): m for m in base_models}
    
    # Add Ollama models
    for dm in dynamic_models:
        key = _normalize_model_name(dm)
        if key not in normalized:
            normalized[key] = dm
    
    # Add custom models
    for cm in custom_models:
        key = _normalize_model_name(cm)
        if key not in normalized:
            normalized[key] = cm

    # Preserve the order: original base models first, then custom models, then dynamic ones in alphabetical order
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
    model_choice_lower = _normalize_model_name(model_choice)
    
    # Check predefined models first
    config = _llm_config_map.get(model_choice_lower)
    if config:
        return config

    # Check Ollama models
    for ollama_model in fetch_ollama_models():
        if _normalize_model_name(ollama_model) == model_choice_lower:
            return {
                "class": ChatOllama,
                "constructor_params": {"model": ollama_model, "base_url": OLLAMA_BASE_URL},
            }
    
    # Check custom models
    try:
        from src.llm.models import get_model_config, get_custom_model_names
        for custom_model_name in get_custom_model_names():
            if _normalize_model_name(custom_model_name) == model_choice_lower:
                model_config = get_model_config(custom_model_name)
                if model_config:
                    model_type = model_config.get("type", "").lower()
                    config_params = model_config.get("config", {})
                    
                    # Handle different custom model types
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
                                "base_url": config_params.get("base_url", OLLAMA_BASE_URL),
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
