import os

import requests
from urllib.parse import urljoin
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Callable, Dict, Optional, List
from langchain_core.callbacks.base import BaseCallbackHandler
from intelnexus.core.settings import get as get_config

from intelnexus.core.logger import get_logger

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

# 本地 Ollama 探测使用的「无代理」配置：本地服务必须直连，
# 否则 requests 会继承 HTTP(S)_PROXY 环境变量，把 127.0.0.1 的请求也路由给代理。
_NO_PROXY = {"http": None, "https": None}

# ---------------------------------------------------------------------------
# LLM 直连（代理隔离）
# ---------------------------------------------------------------------------
# .env 中的 HTTP(S)_PROXY 是为搜索/采集管线设计的（见 core.search.get_http_proxies
# 与 .env 注释「LLM API 直连，不走代理」）。但 httpx（含 openai SDK 3.x 引入的
# 重命名包 httpx2）默认 trust_env=True，构造客户端时会自动继承代理环境变量：
# 当 LLM 端点域名不在 NO_PROXY 白名单内（如阿里云百炼 MaaS 专属域名
# llm-*.maas.aliyuncs.com），请求会被路由到可能未运行的本地代理（如 127.0.0.1:2080）
# 并被积极拒绝（[WinError 10061] / ProxyError）。统一对策：为 LLM 客户端注入显式
# 直连传输（trust_env=False），不再读取代理环境变量。

_PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")


def _llm_proxy_env_active() -> bool:
    """当前环境是否存在 HTTP(S)_PROXY 代理环境变量（无代理时不做任何注入）。"""
    return any(os.getenv(k) for k in _PROXY_ENV_KEYS)


def _build_direct_http_clients():
    """构造一对（同步/异步）不读取代理环境变量的直连 HTTP 客户端。

    优先 httpx2（openai SDK 3.x 使用重命名包），缺失时回退 httpx；
    依赖缺失或构造失败返回 (None, None)，调用方保持既有行为，不因隔离失败阻塞主流程。
    """
    try:
        try:
            import httpx2 as _httpx
        except ImportError:
            import httpx as _httpx
        return _httpx.Client(trust_env=False), _httpx.AsyncClient(trust_env=False)
    except Exception as e:
        logger.debug("构造直连 HTTP 客户端失败，保持默认行为: %s", e)
        return None, None


def _apply_direct_connection_params(llm_class, constructor_params: Dict) -> Dict:
    """为 LLM 类构造参数注入「绕过环境代理」的直连传输。

    仅当存在代理环境变量且目标类实际声明了对应字段时才注入（pydantic
    model_fields 探测，兼容无 http_client 字段的旧版 langchain）；
    ChatOllama 经 client_kwargs 透传 trust_env=False 到底层 httpx.Client。
    """
    if not _llm_proxy_env_active():
        return constructor_params
    fields = getattr(llm_class, "model_fields", None) or {}
    sync_client, async_client = _build_direct_http_clients()
    if sync_client is not None and "http_client" in fields:
        constructor_params.setdefault("http_client", sync_client)
    if async_client is not None and "http_async_client" in fields:
        constructor_params.setdefault("http_async_client", async_client)
    if "client_kwargs" in fields:
        merged = dict(constructor_params.get("client_kwargs") or {})
        merged.setdefault("trust_env", False)
        constructor_params["client_kwargs"] = merged
    return constructor_params


def _get_config_values():
    """Get config values from injected config."""
    return {
        "OLLAMA_BASE_URL": get_config("OLLAMA_BASE_URL", ""),
        "OPENROUTER_BASE_URL": get_config("OPENROUTER_BASE_URL", ""),
        "OPENROUTER_API_KEY": get_config("OPENROUTER_API_KEY", ""),
        "GOOGLE_API_KEY": get_config("GOOGLE_API_KEY", ""),
    }


def _normalize_model_name(name: str) -> str:
    return name.strip().lower()


def _lazy_chat_class(class_name: str, install_hint: str):
    """按名懒加载可选的 LangChain 聊天模型类。

    anthropic/google-genai SDK 属可选扩展（requirements-extras.txt），
    未安装时返回一个实例化即报错的占位类，错误信息含安装指引，
    避免「装了核心包但选了 Anthropic/Google 类型就 ImportError 崩溃」。
    """
    import importlib

    module_map = {
        "ChatAnthropic": ("langchain_anthropic", "anthropic"),
        "ChatGoogleGenerativeAI": ("langchain_google_genai", "google-genai"),
    }
    try:
        module_name, _ = module_map[class_name]
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ImportError, KeyError):
        class _MissingOptionalSDK:
            def __init__(self, *args, **kwargs):
                raise RuntimeError(
                    f"模型类型需要可选依赖 {module_map.get(class_name, ('?','?'))[0]}，请先安装：{install_hint}"
                )
        return _MissingOptionalSDK


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
        # 本地 Ollama 必须直连：显式禁用代理，避免环境代理把本机请求转给不可用的代理
        resp = requests.get(urljoin(base_url, "api/tags"), timeout=3, proxies=_NO_PROXY)
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


# 视觉模型关键字：仅适合图像任务，不适合长文本情报分析 / 摘要生成
VISION_MODEL_HINTS = ("llava", "bakllava", "moondream", "vision", "llama3.2-vision", "minicpm-v")


def is_vision_model(model: str) -> bool:
    """判断模型名是否疑似视觉模型（仅做关键字匹配，不保证精确）。"""
    name = (model or "").lower()
    return any(hint in name for hint in VISION_MODEL_HINTS)


def check_ollama_model_available(model: str, timeout: float = 3.0) -> tuple[bool, str]:
    """检查 Ollama 服务可达且指定模型已存在。

    Returns:
        (available, message): available 为 True 时 message 为空；
        否则 message 为中文错误说明，可直接展示给用户。
    """
    base_url = _get_ollama_base_url()
    if not base_url:
        return False, "未配置 OLLAMA_BASE_URL，无法连接本地模型服务。"

    try:
        resp = requests.get(urljoin(base_url, "api/tags"), timeout=timeout, proxies=_NO_PROXY)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        return False, "无法连接 Ollama 服务，请确认 Ollama 已启动。"
    except requests.exceptions.Timeout:
        return False, "Ollama 服务响应超时，请检查服务状态。"
    except requests.RequestException as e:
        return False, f"无法连接 Ollama 服务：{e}"

    try:
        data = resp.json()
    except (ValueError, Exception) as e:
        return False, f"Ollama 返回异常响应：{type(e).__name__}: {e}"

    models = [m.get("name") or m.get("model") for m in data.get("models", [])]
    models = [m for m in models if m]
    if not any(_normalize_model_name(m) == _normalize_model_name(model) for m in models):
        return False, f"本地未找到模型「{model}」，请先在 Ollama 中拉取该模型。"
    return True, ""


def is_ollama_local_model(model: str) -> bool:
    """判断模型是否为本地 Ollama 直连模型。

    只有这类模型才应做 Ollama 服务预检；云端自定义模型（openai/deepseek/
    anthropic/google 等）连接问题应在实际调用阶段报错，而非误报「Ollama 未启动」。
    匹配两类：① fetch_ollama_models() 发现的本机模型；② 自定义模型中 type=ollama。
    """
    name = _normalize_model_name(model)
    for m in fetch_ollama_models():
        if _normalize_model_name(m) == name:
            return True
    try:
        from intelnexus.core.llm.models import get_custom_models
        for cm in get_custom_models():
            if _normalize_model_name(cm.get("name", "")) == name:
                return str(cm.get("type", "")).lower() == "ollama"
    except Exception:
        pass
    return False


def get_model_choices() -> List[str]:
    """
    只返回本地 Ollama 模型与用户添加的自定义模型，不暴露任何云端预设。
    自定义模型持久化在 data/custom_models.json，重新运行项目不会丢失。
    """
    dynamic_models = fetch_ollama_models()

    try:
        from intelnexus.core.llm.models import get_custom_model_names
        custom_models = get_custom_model_names()
    except ImportError:
        custom_models = []

    normalized = {}

    # 用户添加的自定义模型优先
    for cm in custom_models:
        normalized[_normalize_model_name(cm)] = cm

    # 本地 Ollama 自动探测到的模型
    for dm in dynamic_models:
        key = _normalize_model_name(dm)
        if key not in normalized:
            normalized[key] = dm

    ordered_custom = sorted(custom_models, key=_normalize_model_name)
    ordered_ollama = sorted(
        [name for key, name in normalized.items() if name not in custom_models],
        key=_normalize_model_name,
    )
    return ordered_custom + ordered_ollama


def resolve_model_config(model_choice: str):
    """
    Resolve a model choice (case-insensitive) to the corresponding configuration.
    Supports locally installed Ollama models and user-added custom models.
    """
    model_choice_lower = _normalize_model_name(model_choice)

    for ollama_model in fetch_ollama_models():
        if _normalize_model_name(ollama_model) == model_choice_lower:
            return {
                "class": ChatOllama,
                "constructor_params": _apply_direct_connection_params(ChatOllama, {
                    "model": ollama_model, "base_url": get_config("OLLAMA_BASE_URL", ""),
                }),
            }

    try:
        from intelnexus.core.llm.models import get_model_config, get_custom_model_names
        for custom_model_name in get_custom_model_names():
            if _normalize_model_name(custom_model_name) == model_choice_lower:
                model_config = get_model_config(custom_model_name)
                if model_config:
                    model_type = model_config.get("type", "").lower()
                    config_params = model_config.get("config", {})

                    if model_type == "openai":
                        return {
                            "class": ChatOpenAI,
                            "constructor_params": _apply_direct_connection_params(ChatOpenAI, {
                                "model_name": config_params.get("model_name", custom_model_name),
                                "base_url": config_params.get("base_url"),
                                "api_key": config_params.get("api_key"),
                            }),
                        }
                    elif model_type == "azure openai":
                        return {
                            "class": ChatOpenAI,
                            "constructor_params": _apply_direct_connection_params(ChatOpenAI, {
                                "model_name": config_params.get("model_name", custom_model_name),
                                "azure_endpoint": config_params.get("base_url"),
                                "api_key": config_params.get("api_key"),
                                "api_version": "2024-02-01",
                            }),
                        }
                    elif model_type == "ollama":
                        return {
                            "class": ChatOllama,
                            "constructor_params": _apply_direct_connection_params(ChatOllama, {
                                "model": config_params.get("model_name", custom_model_name),
                                "base_url": config_params.get("base_url", get_config("OLLAMA_BASE_URL", "")),
                            }),
                        }
                    elif model_type == "anthropic":
                        return {
                            # 懒加载：langchain-anthropic 属可选扩展依赖，缺失时给出可操作提示
                            "class": _lazy_chat_class("ChatAnthropic",
                                "pip install langchain-anthropic (或 requirements-extras.txt)"),
                            "constructor_params": {
                                "model": config_params.get("model_name", custom_model_name),
                                "api_key": config_params.get("api_key"),
                            }
                        }
                    elif model_type == "google":
                        return {
                            "class": _lazy_chat_class("ChatGoogleGenerativeAI",
                                "pip install langchain-google-genai (或 requirements-extras.txt)"),
                            "constructor_params": {
                                "model": config_params.get("model_name", custom_model_name),
                                "google_api_key": config_params.get("api_key"),
                            }
                        }
                    elif model_type in [
                        "cohere", "mistral", "deepseek",
                        "通义千问", "qwen",
                        "智谱ai", "zhipu ai",
                        "百度文心一言", "baidu ernie",
                        "讯飞星火", "iflytek spark",
                        "moonshot", "01.ai",
                    ]:
                        base_url = config_params.get("base_url", "")
                        if "/anthropic" in (base_url or "").lower():
                            return {
                                "class": _lazy_chat_class("ChatAnthropic",
                                    "pip install langchain-anthropic (或 requirements-extras.txt)"),
                                "constructor_params": {
                                    "model": config_params.get("model_name", custom_model_name),
                                    "anthropic_api_key": config_params.get("api_key"),
                                    "anthropic_api_url": base_url,
                                }
                            }
                        return {
                            "class": ChatOpenAI,
                            "constructor_params": _apply_direct_connection_params(ChatOpenAI, {
                                "model_name": config_params.get("model_name", custom_model_name),
                                "base_url": base_url,
                                "api_key": config_params.get("api_key"),
                            }),
                        }
                    else:
                        # 未知类型兜底：当作 OpenAI 兼容接口处理
                        base_url = config_params.get("base_url", "")
                        if base_url:
                            return {
                                "class": ChatOpenAI,
                                "constructor_params": _apply_direct_connection_params(ChatOpenAI, {
                                    "model_name": config_params.get("model_name", custom_model_name),
                                    "base_url": base_url,
                                    "api_key": config_params.get("api_key"),
                                }),
                            }
    except ImportError:
        pass

    return None
