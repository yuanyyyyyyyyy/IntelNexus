"""
Custom Models Management Module
==============================
Allow users to add and manage custom LLM models.
"""

import base64
import os
from typing import Dict, List, Optional
from pathlib import Path

from intelnexus.core.logger import get_logger
from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json

logger = get_logger(__name__)


CUSTOM_MODELS_FILE = "data/custom_models.json"

_SENSITIVE_KEYS = ("api_key", "password", "secret")


def _ensure_custom_models_file():
    """Ensure the custom models file exists."""
    Path("data").mkdir(exist_ok=True)
    if not os.path.exists(CUSTOM_MODELS_FILE):
        safe_write_json(CUSTOM_MODELS_FILE, {"models": []})


def _encode_sensitive(config: Dict) -> Dict:
    """Base64-encode sensitive fields (api_key, password, secret) before writing."""
    encoded = {}
    for k, v in config.items():
        if k in _SENSITIVE_KEYS and isinstance(v, str) and v:
            encoded[k] = base64.b64encode(v.encode("utf-8")).decode("utf-8")
        else:
            encoded[k] = v
    return encoded


def _decode_sensitive(config: Dict) -> Dict:
    """Base64-decode sensitive fields after reading."""
    decoded = {}
    for k, v in config.items():
        if k in _SENSITIVE_KEYS and isinstance(v, str) and v:
            try:
                decoded[k] = base64.b64decode(v.encode("utf-8")).decode("utf-8")
            except Exception:
                decoded[k] = v
        else:
            decoded[k] = v
    return decoded


def get_custom_models() -> List[Dict[str, str]]:
    """Get all custom models."""
    _ensure_custom_models_file()
    data = safe_read_json(CUSTOM_MODELS_FILE)
    return data.get("models", [])


def add_custom_model(name: str, model_type: str, config: Dict) -> bool:
    """
    Add a new custom model.

    Args:
        name: Model name (e.g., "my-gpt-4")
        model_type: Type of model (e.g., "openai", "ollama", "anthropic")
        config: Model configuration (API key, base URL, etc.)

    Returns:
        True if successful, False otherwise
    """
    if not name or not model_type:
        return False

    _ensure_custom_models_file()

    data = safe_read_json(CUSTOM_MODELS_FILE)
    if not data:
        data = {"models": []}

    existing_names = [m["name"] for m in data.get("models", [])]
    if name in existing_names:
        return False

    new_model = {
        "name": name,
        "type": model_type,
        "config": _encode_sensitive(config)
    }
    data.setdefault("models", []).append(new_model)

    return safe_write_json(CUSTOM_MODELS_FILE, data)


def remove_custom_model(name: str) -> bool:
    """Remove a custom model by name."""
    _ensure_custom_models_file()

    data = safe_read_json(CUSTOM_MODELS_FILE)
    if not data:
        return False

    original_count = len(data.get("models", []))
    data["models"] = [m for m in data.get("models", []) if m["name"] != name]

    if len(data["models"]) < original_count:
        return safe_write_json(CUSTOM_MODELS_FILE, data)
    return False


def get_custom_model_names() -> List[str]:
    """Get a list of custom model names."""
    return [m["name"] for m in get_custom_models()]


def get_model_config(name: str) -> Optional[Dict]:
    """Get the configuration for a custom model (sensitive fields decoded)."""
    for model in get_custom_models():
        if model["name"] == name:
            return {
                "type": model.get("type"),
                "config": _decode_sensitive(model.get("config", {}))
            }
    return None


def update_custom_model(name: str, model_type: str, config: Dict) -> bool:
    """
    Update an existing custom model by name.

    Args:
        name: Model name to update
        model_type: New model type
        config: New model configuration

    Returns:
        True if successful, False otherwise
    """
    if not name or not model_type:
        return False

    _ensure_custom_models_file()

    data = safe_read_json(CUSTOM_MODELS_FILE)
    if not data:
        return False

    for model in data.get("models", []):
        if model["name"] == name:
            model["type"] = model_type
            model["config"] = _encode_sensitive(config)
            return safe_write_json(CUSTOM_MODELS_FILE, data)

    return False


def test_model_connection(model_type: str, config: Dict) -> tuple:
    """
    Test a model connection by sending a simple request.

    Args:
        model_type: Type of model (e.g., "openai", "ollama", "anthropic")
        config: Model configuration (API key, base URL, etc.)

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        from intelnexus.core.llm.core import _common_llm_params

        temp_model = config.get("model_name", "test")
        type_lower = model_type.lower()

        # Build constructor params based on type
        constructor_params = {}
        if type_lower in ("openai", "deepseek", "cohere", "mistral",
                          "通义千问", "智谱ai", "百度文心一言", "讯飞星火",
                          "moonshot", "01.ai"):
            base_url = config.get("base_url", "")
            if "/anthropic" in (base_url or "").lower():
                from langchain_anthropic import ChatAnthropic
                llm_class = ChatAnthropic
                constructor_params = {
                    "model": temp_model,
                    "anthropic_api_key": config.get("api_key"),
                    "anthropic_api_url": base_url,
                }
            else:
                from langchain_openai import ChatOpenAI
                llm_class = ChatOpenAI
                constructor_params = {
                    "model_name": temp_model,
                    "base_url": base_url,
                    "api_key": config.get("api_key"),
                }
        elif type_lower == "azure openai":
            from langchain_openai import ChatOpenAI
            llm_class = ChatOpenAI
            constructor_params = {
                "model_name": temp_model,
                "azure_endpoint": config.get("base_url"),
                "api_key": config.get("api_key"),
                "api_version": "2024-02-01",
            }
        elif type_lower == "ollama":
            from langchain_ollama import ChatOllama
            llm_class = ChatOllama
            constructor_params = {
                "model": temp_model,
                "base_url": config.get("base_url", "http://127.0.0.1:11434"),
            }
        elif type_lower == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm_class = ChatAnthropic
            constructor_params = {
                "model": temp_model,
                "api_key": config.get("api_key"),
            }
        elif type_lower == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm_class = ChatGoogleGenerativeAI
            constructor_params = {
                "model": temp_model,
                "google_api_key": config.get("api_key"),
            }
        else:
            return False, f"不支持的模型类型: {model_type}"

        # Build params: disable streaming for test
        params = {**constructor_params}
        params["temperature"] = 0
        params["max_retries"] = 1
        params["streaming"] = False

        # Timeout: OpenAI uses request_timeout, Anthropic uses default_request_timeout
        if llm_class.__name__ == "ChatAnthropic":
            params["default_request_timeout"] = 30
        else:
            params["request_timeout"] = 30

        llm = llm_class(**params)
        llm.invoke("Hi")
        return True, "连接成功"
    except Exception as e:
        logger.exception("模型连接测试失败 [%s] model=%s", model_type, temp_model)
        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."

        ERROR_TRANSLATIONS = {
            "Connection error": "连接错误",
            "Connection refused": "连接被拒绝",
            "Connection reset": "连接被重置",
            "Read timed out": "读取超时",
            "connect timed out": "连接超时",
            "401 Unauthorized": "认证失败（API密钥无效）",
            "403 Forbidden": "访问被拒绝",
            "404 Not Found": "地址不存在",
            "429 Too Many Requests": "请求过于频繁",
            "500 Internal Server Error": "服务器内部错误",
            "502 Bad Gateway": "网关错误",
            "503 Service Unavailable": "服务不可用",
        }
        translated = error_msg
        for en, zh in ERROR_TRANSLATIONS.items():
            if en.lower() in error_msg.lower():
                translated = zh
                break

        return False, f"连接失败: {translated}\n{error_msg}"
