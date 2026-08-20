"""
知识库检索服务
==============
把知识库条目按语义相关性检索出来，供搜索管线（RAG 注入）
与简报分析（关联历史收藏）共用，让知识库从被动存储变为记忆中枢。

复用 analysis.embed_cache 的 sentence-transformers 编码，
模型不可用时返回空结果，不影响调用方主流程。
"""

import threading
from typing import Dict, List, Optional

import numpy as np

from intelnexus.analysis.embed_cache import encode_texts
from intelnexus.config import knowledge_base
from intelnexus.core.logger import get_logger

_logger = get_logger(__name__)

_lock = threading.Lock()
# 知识库指纹 -> 条目文本嵌入矩阵 的进程内缓存
_index_cache: Dict[str, "np.ndarray"] = {}

# 条目参与编码的文本长度上限（标题 + 摘要），控制编码开销
_MAX_TEXT_CHARS = 600


def _item_text(item: dict) -> str:
    title = (item.get("title") or "").strip()
    content = (item.get("content") or "").strip()
    if len(content) > _MAX_TEXT_CHARS:
        content = content[:_MAX_TEXT_CHARS]
    return f"{title}\n{content}".strip()


def _kb_fingerprint(items: List[dict]) -> str:
    """条目 id + updated_at 指纹，知识库无变化时跳过重新编码。"""
    return "|".join(f"{i.get('id')}:{i.get('updated_at', '')}" for i in items)


def _get_index_embeddings(items: List[dict]):
    """编码全部条目文本，命中指纹缓存则直接返回。"""
    if not items:
        return None
    fingerprint = _kb_fingerprint(items)
    with _lock:
        cached = _index_cache.get(fingerprint)
    if cached is not None:
        return cached

    embs = encode_texts([_item_text(i) for i in items])
    if embs is None:
        return None
    with _lock:
        if len(_index_cache) > 8:
            _index_cache.clear()
        _index_cache[fingerprint] = embs
    return embs


def retrieve_relevant(
    query: str,
    top_k: int = 5,
    min_similarity: float = 0.45,
) -> List[Dict]:
    """
    检索与 query 语义相关的知识库条目。

    Args:
        query: 查询文本（搜索问题 / 简报类目关键词聚合）
        top_k: 最多返回条数
        min_similarity: 余弦相似度下限

    Returns:
        按相似度降序的条目列表（附加 kb_similarity 字段）；
        知识库为空或编码模型不可用时返回 []
    """
    if not query or not query.strip():
        return []

    items = knowledge_base.get_items(limit=10**9)
    if not items:
        return []

    index_embs = _get_index_embeddings(items)
    query_emb = encode_texts([query.strip()])
    if index_embs is None or query_emb is None:
        _logger.debug("知识库语义检索降级：编码模型不可用")
        return []

    query_vec = np.asarray(query_emb[0], dtype=np.float32)
    index_mat = np.asarray(index_embs, dtype=np.float32)

    # 余弦相似度
    q_norm = np.linalg.norm(query_vec) or 1.0
    mat_norm = np.linalg.norm(index_mat, axis=1)
    mat_norm[mat_norm == 0] = 1.0
    sims = (index_mat @ query_vec) / (mat_norm * q_norm)

    scored = [
        (float(sims[i]), items[i])
        for i in range(len(items))
        if sims[i] >= min_similarity
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for sim, item in scored[:top_k]:
        entry = dict(item)
        entry["kb_similarity"] = round(sim, 4)
        results.append(entry)
    _logger.debug("知识库检索 '%s' 命中 %d 条", query[:50], len(results))
    return results


def build_kb_context(items: List[Dict], max_chars: int = 2000) -> str:
    """
    把检索到的条目格式化为供 LLM prompt 注入的文本块。

    Args:
        items: retrieve_relevant 的返回值（或任意条目列表）
        max_chars: 上下文总长度上限
    """
    if not items:
        return ""

    blocks = []
    for item in items:
        title = (item.get("title") or "").strip() or "(无标题)"
        date = (item.get("created_at") or "")[:10]
        source = (item.get("source") or "").strip() or (item.get("url") or "").strip()
        content = (item.get("content") or "").strip()
        if len(content) > 200:
            content = content[:200] + "…"
        tags = "、".join(item.get("tags") or [])
        lines = [f"- {title}（{date}）"]
        if source:
            lines.append(f"  来源: {source}")
        if content:
            lines.append(f"  摘要: {content}")
        if tags:
            lines.append(f"  标签: {tags}")
        blocks.append("\n".join(lines))

    context = "\n".join(blocks)
    if len(context) > max_chars:
        context = context[:max_chars] + "…"
    return context
