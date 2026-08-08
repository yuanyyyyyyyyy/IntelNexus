_shared_model = None


def load_sentence_model():
    """Load the shared SentenceTransformer model (lazy singleton)."""
    global _shared_model
    if _shared_model is not None:
        return _shared_model
    try:
        from sentence_transformers import SentenceTransformer
        _shared_model = SentenceTransformer('all-MiniLM-L6-v2')
        return _shared_model
    except Exception:
        return None


def warm_up_models():
    """
    预热分析所需的重模型（sentence-transformers）。
    在流水线启动早期调用一次，把冷启动代价从首次搜索转移到应用加载阶段。
    """
    try:
        load_sentence_model()
    except Exception:
        pass
