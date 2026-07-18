"""
Custom Models Management Module
==============================
Allow users to add and manage custom LLM models.
"""

import base64
import os
from typing import Dict, List, Optional
from pathlib import Path

from src.logger import get_logger
from src.config.file_lock import safe_read_json, safe_write_json

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

    # Check if model already exists
    existing_names = [m["name"] for m in data.get("models", [])]
    if name in existing_names:
        return False

    # Add new model
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
