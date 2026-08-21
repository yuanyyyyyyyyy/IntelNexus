"""
共享语义编码缓存
================
复用 sentence-transformers 单例，对同一批 scraped 文本只编码一次，
供 SourceScorer / ConsistencyAnalyzer / EvidenceTracer 共享，
消除单次搜索中同一批文本被重复 encode 3 次的问题。
"""

import threading
from typing import Dict, List, Optional

import numpy as np

from intelnexus.analysis import load_sentence_model
from intelnexus.core.logger import get_logger

_logger = get_logger(__name__)

# 按编码文本元组缓存 LRU 样式的结果，避免同一会话内重复编码
_local_lock = threading.Lock()
_text_cache: Dict[tuple, "np.ndarray"] = {}
_cache_order: List[tuple] = []  # 记录访问顺序，用于 LRU 淘汰


def encode_texts(texts: List[str], use_cache: bool = True) -> Optional["np.ndarray"]:
    """
    批量编码文本列表（一次性 encode），返回嵌入矩阵。

    对同一组文本（按内容去重哈希）在进程内做记忆化，
    避免 SourceScorer / ConsistencyAnalyzer / EvidenceTracer
    各自独立 encode 同一批 scraped 内容。

    Args:
        texts: 待编码文本列表
        use_cache: 是否启用进程内记忆化缓存

    Returns:
        shape 为 (len(texts), dim) 的 numpy 矩阵；模型不可用时返回 None
    """
    if not texts:
        return None

    model = load_sentence_model()
    if model is None:
        return None

    safe_texts = [t if t else "" for t in texts]

    if use_cache:
        key = tuple(safe_texts)
        with _local_lock:
            cached = _text_cache.get(key)
            if cached is not None:
                # 更新访问顺序（移到末尾）
                if key in _cache_order:
                    _cache_order.remove(key)
                _cache_order.append(key)
        if cached is not None:
            _logger.debug("语义编码命中进程内缓存，跳过 %d 条重复 encode", len(safe_texts))
            return cached

    try:
        embs = model.encode(safe_texts, show_progress_bar=False)
        embs = np.asarray(embs, dtype=np.float32)
    except Exception:
        _logger.warning("语义编码失败", exc_info=True)
        return None

    if use_cache:
        with _local_lock:
            # LRU 淘汰：超过上限时删除最久未使用的条目
            if len(_text_cache) > 64:
                oldest_key = _cache_order.pop(0) if _cache_order else None
                if oldest_key and oldest_key in _text_cache:
                    del _text_cache[oldest_key]
            _text_cache[key] = embs
            _cache_order.append(key)

    return embs


def encode_single(text: str) -> Optional["np.ndarray"]:
    """编码单条文本（供 EvidenceTracer 对 report 句子编码使用）。"""
    embs = encode_texts([text] if text else [])
    if embs is None or len(embs) == 0:
        return None
    return embs[0]


def clear_cache() -> None:
    """清空进程内编码缓存（测试或显式重置时使用）。"""
    with _local_lock:
        _text_cache.clear()
        _cache_order.clear()
