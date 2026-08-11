"""
查询语义相关性工具
====================
计算每条检索结果与用户查询的语义相似度，按相似度排序并对弱相关结果做标注。

复用 ``embed_cache.encode_texts``（all-MiniLM-L6-v2 单例 + 进程内缓存），
不重复加载模型。模型不可用时（超时/未下载）返回 ``None``，由调用方降级到
原有 ``results[:N]`` 行为，不阻断搜索主流程。

设计要点：
- 相似度用余弦相似度（向量已 L2 归一化，等价于点积）。
- 弱相关阈值默认 0.30，常量可配，避免误伤边缘相关结果。
- 弱相关结果不进 ``filtered`` 主干，但保留在原列表尾部并打 ``weak_related`` 标记，
  供 UI 折叠展示，兼顾可追溯性与结果聚焦。
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from intelnexus.analysis.embed_cache import encode_texts
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 低于该相似度的结果视为弱相关（被降权到列表尾部，不进报告/KG 主干）
WEAK_RELATED_THRESHOLD = 0.30


def _build_text(item: Dict) -> str:
    """从结果条目拼出用于编码的代表性文本（标题权重更高）。"""
    title = item.get("title", "") or ""
    desc = item.get("description", "") or item.get("summary", "") or ""
    return f"{title}. {desc}".strip()


def compute_query_relevance(query: str,
                            items: List[Dict],
                            threshold: float = WEAK_RELATED_THRESHOLD
                            ) -> Optional[List[Dict]]:
    """计算查询与每条结果的语义相似度，返回带 ``relevance_score`` / ``weak_related`` 的列表。

    Args:
        query: 用户原始查询（如 "九江"）
        items: 检索结果列表（已跨源去重）
        threshold: 弱相关阈值

    Returns:
        排序后可迭代的列表，每个元素为原 item 增加 ``relevance_score``（float）与
        ``weak_related``（bool）字段。模型不可用 / 输入为空时返回 ``None``（调用方降级）。
    """
    if not query or not items:
        return None

    texts = [_build_text(it) for it in items]
    # query 与所有结果文本一起批量编码，减少模型调用次数
    all_emb = encode_texts([query] + texts)
    if all_emb is None or len(all_emb) != len(texts) + 1:
        logger.warning("嵌入模型不可用，跳过相关性排序/过滤（降级到原有行为）")
        return None

    # L2 归一化，使余弦相似度等价于点积
    q_emb = _normalize(all_emb[0:1])[0]
    t_emb = _normalize(all_emb[1:])

    try:
        scores = (t_emb @ q_emb).astype(float)
    except Exception:
        logger.warning("相似度计算失败，跳过相关性排序/过滤", exc_info=True)
        return None

    scored = []
    for item, score in zip(items, scores):
        new_item = dict(item)
        new_item["relevance_score"] = float(score)
        new_item["weak_related"] = bool(score < threshold)
        scored.append(new_item)

    # 高相关在前（分数降序），弱相关沉底（仍保留可追溯）
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored


def _normalize(mat: "np.ndarray") -> "np.ndarray":
    """对矩阵按行 L2 归一化；零向量保持不变以避免除零。"""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms
