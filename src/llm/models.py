"""
Custom Models Management Module
==============================
Allow users to add and manage custom LLM models.
"""

import json
import os
from typing import Dict, List, Optional
from pathlib import Path


CUSTOM_MODELS_FILE = "data/custom_models.json"


def _ensure_custom_models_file():
    """Ensure the custom models file exists."""
    Path("data").mkdir(exist_ok=True)
    if not os.path.exists(CUSTOM_MODELS_FILE):
        with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"models": []}, f, ensure_ascii=False, indent=2)


def get_custom_models() -> List[Dict[str, str]]:
    """Get all custom models."""
    _ensure_custom_models_file()
    try:
        with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("models", [])
    except Exception as e:
        print(f"Error reading custom models: {e}")
        return []


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
    
    try:
        with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if model already exists
        existing_names = [m["name"] for m in data.get("models", [])]
        if name in existing_names:
            return False
        
        # Add new model
        new_model = {
            "name": name,
            "type": model_type,
            "config": config
        }
        data.get("models", []).append(new_model)
        
        with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Error adding custom model: {e}")
        return False


def remove_custom_model(name: str) -> bool:
    """Remove a custom model by name."""
    _ensure_custom_models_file()
    
    try:
        with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        original_count = len(data.get("models", []))
        data["models"] = [m for m in data.get("models", []) if m["name"] != name]
        
        if len(data["models"]) < original_count:
            with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        return False
    except Exception as e:
        print(f"Error removing custom model: {e}")
        return False


def get_custom_model_names() -> List[str]:
    """Get a list of custom model names."""
    return [m["name"] for m in get_custom_models()]


def get_model_config(name: str) -> Optional[Dict]:
    """Get the configuration for a custom model."""
    for model in get_custom_models():
        if model["name"] == name:
            return {
                "type": model.get("type"),
                "config": model.get("config", {})
            }
    return None
