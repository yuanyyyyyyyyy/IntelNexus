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


def test_provider_connection(base_url: str, api_key: str = "", api_format: str = "openai") -> tuple:
    """
    测试供应商连接速度和可用性。

    Args:
        base_url: 供应商 API 端点
        api_key: API 密钥（可选）
        api_format: API 格式 (openai/anthropic/custom)

    Returns:
        tuple: (success: bool, message: str)
    """
    import time
    import requests

    logger.info("[PROVIDER TEST] ======== 开始测试供应商连接 ========")
    logger.info("[PROVIDER TEST] 原始 URL: %s", base_url)
    logger.info("[PROVIDER TEST] API 格式: %s", api_format)
    logger.info("[PROVIDER TEST] API Key: %s...", api_key[:10] if api_key and len(api_key) > 10 else api_key or "无")

    if not base_url:
        logger.warning("[PROVIDER TEST] URL 为空，终止测试")
        return False, "请填写请求地址"

    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            if api_format == "anthropic":
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {api_key}"

        logger.info("[PROVIDER TEST] 请求头: %s", {k: v[:20] + "..." if len(v) > 20 else v for k, v in headers.items()})

        test_payload = {"model": "test", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
        logger.info("[PROVIDER TEST] 请求体: %s", test_payload)

        url = base_url.rstrip("/")
        
        # 构建候选 URL 列表：先尝试原始 URL，再尝试拼接后的 URL
        candidate_urls = [url]
        
        if api_format == "anthropic":
            if not url.endswith("/messages") and not url.endswith("/v1/messages"):
                if "/v1" in url:
                    candidate_urls.append(url + "/messages")
                else:
                    candidate_urls.append(url + "/v1/messages")
        else:
            if not url.endswith("/chat/completions") and not url.endswith("/completions"):
                if "/v1" in url:
                    candidate_urls.append(url + "/chat/completions")
                else:
                    candidate_urls.append(url + "/v1/chat/completions")
        
        logger.info("[PROVIDER TEST] 候选 URL 列表 (%d 个):", len(candidate_urls))
        for i, u in enumerate(candidate_urls, 1):
            logger.info("[PROVIDER TEST]   %d. %s", i, u)
        
        last_error = None
        for idx, test_url in enumerate(candidate_urls, 1):
            logger.info("[PROVIDER TEST] 尝试 URL %d/%d: %s", idx, len(candidate_urls), test_url)
            try:
                start_time = time.time()
                # 禁用代理，直连目标服务器（避免系统代理导致连接失败）
                proxies = {"http": None, "https": None}
                response = requests.post(test_url, json=test_payload, headers=headers, timeout=10, proxies=proxies)
                latency_ms = int((time.time() - start_time) * 1000)
                
                logger.info("[PROVIDER TEST] 响应状态码: %d", response.status_code)
                logger.info("[PROVIDER TEST] 响应内容: %s", response.text[:500] if response.text else "空")
                
                # 如果得到任何响应（包括错误响应），说明连接成功
                if response.status_code in (200, 201):
                    logger.info("[PROVIDER TEST] 连接成功 (%dms)", latency_ms)
                    return True, f"连接成功 ({latency_ms}ms)"
                elif response.status_code == 401:
                    logger.warning("[PROVIDER TEST] 认证失败 (401)")
                    return False, f"认证失败 (401) - API Key 无效"
                elif response.status_code == 403:
                    logger.warning("[PROVIDER TEST] 访问被拒绝 (403)")
                    return False, f"访问被拒绝 (403)"
                elif response.status_code == 404:
                    last_error = f"地址不存在 (404)"
                    logger.warning("[PROVIDER TEST] URL %d 返回 404，尝试下一个", idx)
                    continue  # 尝试下一个 URL
                elif response.status_code == 429:
                    logger.warning("[PROVIDER TEST] 请求过于频繁 (429)")
                    return False, f"请求过于频繁 (429)"
                elif response.status_code == 405:
                    logger.info("[PROVIDER TEST] 连接成功 (%dms) - 方法不允许但服务器可达", latency_ms)
                    return True, f"连接成功 ({latency_ms}ms) - 方法不允许但服务器可达"
                else:
                    logger.info("[PROVIDER TEST] 连接成功 (%dms) - 状态码: %d", latency_ms, response.status_code)
                    return True, f"连接成功 ({latency_ms}ms) - 状态码: {response.status_code}"
            except requests.exceptions.Timeout:
                last_error = "连接超时 (10s)"
                logger.warning("[PROVIDER TEST] URL %d 超时 (10s)", idx)
                continue
            except requests.exceptions.ConnectionError as e:
                last_error = f"连接错误: {str(e)[:100]}"
                logger.warning("[PROVIDER TEST] URL %d 连接错误: %s", idx, str(e)[:200])
                continue
            except Exception as e:
                error_msg = str(e)
                if len(error_msg) > 200:
                    error_msg = error_msg[:200] + "..."
                last_error = f"连接失败: {error_msg}"
                logger.warning("[PROVIDER TEST] URL %d 异常: %s", idx, error_msg)
                continue
        
        logger.error("[PROVIDER TEST] 所有 URL 均失败，最后错误: %s", last_error)
        return False, last_error or "无法访问目标地址"

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        logger.exception("[PROVIDER TEST] 未预期的异常")
        return False, f"连接失败: {error_msg}"


# ============================================================================
# Custom Providers Management
# ============================================================================

CUSTOM_PROVIDERS_FILE = "data/custom_providers.json"


def _ensure_custom_providers_file():
    """Ensure the custom providers file exists."""
    Path("data").mkdir(exist_ok=True)
    if not os.path.exists(CUSTOM_PROVIDERS_FILE):
        safe_write_json(CUSTOM_PROVIDERS_FILE, {"providers": []})


def get_custom_providers() -> List[Dict[str, str]]:
    """Get all custom providers."""
    _ensure_custom_providers_file()
    data = safe_read_json(CUSTOM_PROVIDERS_FILE)
    return data.get("providers", [])


def add_custom_provider(
    name: str,
    base_url: str,
    remark: str = "",
    website: str = "",
    api_key: str = "",
    api_format: str = "openai",
    auth_field: str = "Authorization",
    model_mapping: Optional[Dict] = None,
) -> bool:
    """
    Add a new custom provider.

    Args:
        name: Provider name (e.g., "Claude", "My Provider")
        base_url: Base URL for the provider's API
        remark: Optional remark/note
        website: Optional official website URL
        api_key: API key for authentication
        api_format: API format (openai, anthropic, custom)
        auth_field: Authentication header field name
        model_mapping: Optional model name mapping dict

    Returns:
        True if successful, False otherwise
    """
    if not name:
        return False

    _ensure_custom_providers_file()

    data = safe_read_json(CUSTOM_PROVIDERS_FILE)
    if not data:
        data = {"providers": []}

    existing_names = [p["name"] for p in data.get("providers", [])]
    if name in existing_names:
        return False

    new_provider = {
        "name": name,
        "base_url": base_url,
        "remark": remark,
        "website": website,
        "api_key": _encode_sensitive({"api_key": api_key}).get("api_key", ""),
        "api_format": api_format,
        "auth_field": auth_field,
        "model_mapping": model_mapping or {},
    }
    data.setdefault("providers", []).append(new_provider)

    return safe_write_json(CUSTOM_PROVIDERS_FILE, data)


def remove_custom_provider(name: str) -> bool:
    """Remove a custom provider by name."""
    _ensure_custom_providers_file()

    data = safe_read_json(CUSTOM_PROVIDERS_FILE)
    if not data:
        return False

    original_count = len(data.get("providers", []))
    data["providers"] = [p for p in data.get("providers", []) if p["name"] != name]

    if len(data["providers"]) < original_count:
        return safe_write_json(CUSTOM_PROVIDERS_FILE, data)
    return False


def get_custom_provider_names() -> List[str]:
    """Get a list of custom provider names."""
    return [p["name"] for p in get_custom_providers()]


def get_provider_config(name: str) -> Optional[Dict]:
    """Get the configuration for a custom provider (sensitive fields decoded)."""
    for provider in get_custom_providers():
        if provider["name"] == name:
            result = provider.copy()
            if "api_key" in result and result["api_key"]:
                result["api_key"] = _decode_sensitive({"api_key": result["api_key"]}).get("api_key", "")
            return result
    return None


def update_custom_provider(
    name: str,
    base_url: str,
    remark: str = "",
    website: str = "",
    api_key: str = "",
    api_format: str = "openai",
    auth_field: str = "Authorization",
    model_mapping: Optional[Dict] = None,
) -> bool:
    """
    Update an existing custom provider by name.

    Args:
        name: Provider name to update
        base_url: New base URL
        remark: Optional remark/note
        website: Optional official website URL
        api_key: API key for authentication
        api_format: API format (openai, anthropic, custom)
        auth_field: Authentication header field name
        model_mapping: Optional model name mapping dict

    Returns:
        True if successful, False otherwise
    """
    if not name:
        return False

    _ensure_custom_providers_file()

    data = safe_read_json(CUSTOM_PROVIDERS_FILE)
    if not data:
        return False

    for provider in data.get("providers", []):
        if provider["name"] == name:
            provider["base_url"] = base_url
            provider["remark"] = remark
            provider["website"] = website
            if api_key:
                provider["api_key"] = _encode_sensitive({"api_key": api_key}).get("api_key", "")
            provider["api_format"] = api_format
            provider["auth_field"] = auth_field
            provider["model_mapping"] = model_mapping or {}
            return safe_write_json(CUSTOM_PROVIDERS_FILE, data)

    return False
