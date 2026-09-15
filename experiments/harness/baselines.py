"""非 LLM 基线：关键词规则 / TextRank / TF-IDF 簇中心+首句（表3 基线行）。

三条基线都是**确定性**的（无随机性），因此重复运行方差为 0 —— 表3 中的
"均值±标准差"对基线而言标准差为 0，这是真实性而非缺陷。

复用项目已有的 jieba 分词（``intelnexus/core/search/tokenizer.py``），
不重复造轮子；TextRank 的打分用 networkx 的 pagerank（项目已依赖），
缺失时回退幂迭代。
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Sequence

from experiments.logging_utils import get_logger

logger = get_logger("exp.baselines")

# 安全领域关键词（用于关键词规则基线；词典固定在配置里，保证可复现）
SECURITY_KEYWORDS = [
    "漏洞", "补丁", "修复", "受影响", "攻击", "利用", "权限提升", "远程代码执行",
    "拒绝服务", "信息泄露", "缓冲区溢出", "提权", "恶意", "后门", "证书",
    "vulnerability", "exploit", "patch", "affected", "remote code execution",
    "privilege escalation", "denial of service", "CVE-", "advisory", "security",
]

_SENT_SPLIT = re.compile(r"(?<=[。！？!?\.])\s*|\n+")


def split_sentences(text: str) -> List[str]:
    parts = [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]
    return [p for p in parts if len(p) >= 4]


def _tokens(text: str) -> List[str]:
    try:
        from intelnexus.core.search.tokenizer import tokenize

        return [t for t in tokenize(text) if t and t.strip()]
    except Exception:  # noqa: BLE001
        return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z][A-Za-z0-9._-]*|\d+(?:\.\d+)*", text or "")


def keyword_extract(text: str, top_k: int = 3, min_sentence_chars: int = 12) -> str:
    """关键词规则抽取：命中安全关键词最多的若干句，按原文顺序输出。"""
    sents = [s for s in split_sentences(text) if len(s) >= min_sentence_chars]
    scored = []
    for i, s in enumerate(sents):
        low = s.lower()
        hits = sum(1 for k in SECURITY_KEYWORDS if k.lower() in low)
        if hits:
            scored.append((hits, i, s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = sorted(scored[: max(1, int(top_k))], key=lambda x: x[1])
    return " ".join(s for _, _, s in picked)


def _similarity(a: Sequence[str], b: Sequence[str]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    if inter == 0:
        return 0.0
    return inter / (math.log(len(sa) + 1) + math.log(len(sb) + 1))


def textrank(text: str, window: int = 5, max_sentences: int = 5, damping: float = 0.85) -> str:
    """TextRank 抽取式摘要：句子作为节点，token 重叠度作为边权。"""
    sents = split_sentences(text)
    if not sents:
        return ""
    if len(sents) == 1:
        return sents[0]
    toks = [_tokens(s) for s in sents]
    n = len(sents)
    edges = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            w = _similarity(toks[i], toks[j])
            if w > 0:
                edges[i][j] = w
                edges[j][i] = w
    scores = _pagerank(edges, damping)
    ranked = sorted(range(n), key=lambda i: -scores[i])[: max(1, int(max_sentences))]
    return " ".join(sents[i] for i in sorted(ranked))


def _pagerank(matrix: List[List[float]], damping: float = 0.85, iters: int = 50) -> List[float]:
    """优先用 networkx，缺失时用幂迭代（结果在同一实现下确定性）。"""
    n = len(matrix)
    try:
        import networkx as nx  # type: ignore

        g = nx.Graph()
        g.add_nodes_from(range(n))
        for i in range(n):
            for j in range(i + 1, n):
                if matrix[i][j] > 0:
                    g.add_edge(i, j, weight=matrix[i][j])
        return list(nx.pagerank(g, alpha=damping, max_iter=iters).values())
    except Exception:  # noqa: BLE001
        scores = [1.0 / n] * n
        for _ in range(iters):
            new = [0.0] * n
            for i in range(n):
                out = sum(matrix[i])
                if out == 0:
                    new[i] += (1 - damping) / n
                    continue
                for j in range(n):
                    if matrix[i][j] > 0:
                        new[j] += damping * scores[i] * matrix[i][j] / out
                new[i] += (1 - damping) / n
            total = sum(new) or 1.0
            scores = [v / total for v in new]
        return scores


def tfidf_cluster(text: str, clusters: int = 8, first_sentence: bool = True,
                  max_sentences: int = 5, seed: int = 0) -> str:
    """TF-IDF + k-means 聚类后取簇中心首句。

    k-means 用固定初始中心（按 TF-IDF 范数排序取前 k 个），
    保证结果确定、可复现。
    """
    sents = split_sentences(text)
    if not sents:
        return ""
    if len(sents) <= max_sentences:
        return " ".join(sents)
    toks = [_tokens(s) for s in sents]
    df: Dict[str, int] = {}
    for t in toks:
        for w in set(t):
            df[w] = df.get(w, 0) + 1
    n = len(toks)
    vecs: List[Dict[str, float]] = []
    for t in toks:
        tf: Dict[str, int] = {}
        for w in t:
            tf[w] = tf.get(w, 0) + 1
        vecs.append({w: (c / len(t)) * math.log((n + 1) / (df.get(w, 0) + 1)) for w, c in tf.items()})

    k = max(1, min(int(clusters), len(vecs)))
    # 确定性初始中心：按向量范数排序后等距取 k 个
    norms = sorted(range(len(vecs)), key=lambda i: -math.sqrt(sum(v * v for v in vecs[i].values())))
    centers = [vecs[norms[round(i * (len(norms) - 1) / max(1, k - 1))]] for i in range(k)] if k > 1 else [vecs[norms[0]]]

    for _ in range(20):
        assign: List[int] = []
        for v in vecs:
            best, best_sim = 0, -1.0
            for ci, c in enumerate(centers):
                sim = _cosine(v, c)
                if sim > best_sim:
                    best, best_sim = ci, sim
            assign.append(best)
        new_centers = []
        for ci in range(k):
            members = [vecs[i] for i in range(len(vecs)) if assign[i] == ci]
            if not members:
                new_centers.append(centers[ci])
                continue
            merged: Dict[str, float] = {}
            for m in members:
                for w, val in m.items():
                    merged[w] = merged.get(w, 0.0) + val
            new_centers.append({w: v / len(members) for w, v in merged.items()})
        if new_centers == centers:
            break
        centers = new_centers

    # 每簇取最接近中心的句子；按簇内句子数和位置排序后取首句
    picked: List[int] = []
    for ci in range(k):
        members = [i for i in range(len(vecs)) if assign[i] == ci]
        if not members:
            continue
        members.sort(key=lambda i: -_cosine(vecs[i], centers[ci]))
        picked.append(members[0])
    picked = sorted(set(picked))[: max(1, int(max_sentences))]
    if first_sentence:
        return " ".join(sents[i] for i in picked)
    return " ".join(sents[i] for i in sorted(picked))


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[w] * b[w] for w in common)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return num / (da * db) if da and db else 0.0


def run_baseline(kind: str, text: str, params: Dict[str, Any]) -> str:
    """按配置执行一条基线，返回生成的摘要文本。"""
    p = params or {}
    if kind == "keyword":
        return keyword_extract(text, top_k=int(p.get("top_k", 3)),
                               min_sentence_chars=int(p.get("min_sentence_chars", 12)))
    if kind == "textrank":
        return textrank(text, window=int(p.get("window", 5)),
                        max_sentences=int(p.get("max_sentences", 5)),
                        damping=float(p.get("damping", 0.85)))
    if kind == "tfidf":
        return tfidf_cluster(text, clusters=int(p.get("clusters", 8)),
                             first_sentence=bool(p.get("first_sentence", True)),
                             max_sentences=int(p.get("max_sentences", 5)))
    raise ValueError(f"未知基线类型: {kind}")
