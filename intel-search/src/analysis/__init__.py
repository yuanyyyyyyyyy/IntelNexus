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
