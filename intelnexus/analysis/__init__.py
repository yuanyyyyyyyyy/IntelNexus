import threading
import os

_shared_model = None
_model_load_lock = threading.Lock()
# 模型加载超时（秒）：超过则视为不可用，降级运行，避免首次搜索长时间挂起
_MODEL_LOAD_TIMEOUT = 15

# 禁用 sentence-transformer（HuggingFace在中国无法访问，会导致20+分钟超时）
DISABLE_SENTENCE_TRANSFORMER = os.getenv("DISABLE_SENTENCE_TRANSFORMER", "true").lower() == "true"


def _build_sentence_model():
    """构造 SentenceTransformer 实例，失败抛异常（由调用方捕获处理）。"""
    import os
    # 跳过 hf-mirror.com 等镜像站的 SSL 证书验证（国内网络环境常见问题）
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("CURL_CA_BUNDLE", "")
    os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2')


def load_sentence_model():
    """Load the shared SentenceTransformer model (lazy singleton).

    若模型尚未加载，会在后台线程中加载并最多等待 ``_MODEL_LOAD_TIMEOUT`` 秒。
    超时或加载失败时返回 ``None``，调用方应降级运行（使用默认分数）。

    注意：在中国大陆环境下，HuggingFace被墙会导致加载超时20+分钟，
    因此默认禁用（DISABLE_SENTENCE_TRANSFORMER=true）。
    """
    global _shared_model

    # 禁用检查：直接跳过，不尝试加载
    if DISABLE_SENTENCE_TRANSFORMER:
        return None

    if _shared_model is not None:
        return _shared_model

    with _model_load_lock:
        # 双检锁：避免重复触发加载
        if _shared_model is not None:
            return _shared_model

        result = {}

        def _do_load():
            try:
                result["model"] = _build_sentence_model()
            except Exception as e:
                result["error"] = e

        t = threading.Thread(target=_do_load, daemon=True)
        t.start()
        t.join(_MODEL_LOAD_TIMEOUT)

        if t.is_alive():
            # 加载线程仍未结束：超时，降级
            return None
        if "error" in result:
            return None
        _shared_model = result.get("model")
        return _shared_model


def warm_up_models():
    """
    预热分析所需的重模型（sentence-transformers），非阻塞带超时。
    模型加载慢或失败时不会阻塞主流程，调用方负责降级处理。
    """
    try:
        load_sentence_model()
    except Exception:
        pass
