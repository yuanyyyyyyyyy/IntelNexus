"""ROUGE-L（最长公共子序列），中文先分词。

实现细节与论文口径一致：
- 计算前用 jieba 对中英文混合文本分词（复用项目 tokenizer）；
- 中文场景下"词"即分词结果，英文按空白与常见标点切分后统一处理；
- 报告 F1（论文表3 的 ROUGE-L 列），同时保留 P/R 便于复核。

数值范围 [0, 1]；参考摘要为空时返回 None（由上层保留占位，不得记 0）。
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence

_WS = re.compile(r"\s+")


def tokenize(text: str) -> List[str]:
    """中英混合分词：优先项目 tokenizer（jieba），失败时按字符/空白切分。"""
    if not text:
        return []
    try:
        from intelnexus.core.search.tokenizer import tokenize as _tk

        toks = [t for t in _tk(text) if t and t.strip()]
        if toks:
            return toks
    except Exception:  # noqa: BLE001
        pass
    # 回退：中文按字切，英文/数字按词切
    return re.findall(r"[\u4e00-\u9fff]|[A-Za-z][A-Za-z0-9._-]*|\d+(?:\.\d+)*", text)


def _lcs_length(a: Sequence[str], b: Sequence[str]) -> int:
    """LCS 长度（O(n*m) DP，摘要长度量级无性能压力）。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            cur[j] = prev[j - 1] + 1 if x == y else (prev[j] if prev[j] >= cur[j - 1] else cur[j - 1])
        prev = cur
    return prev[-1]


def rouge_l(candidate: str, reference: str) -> Optional[float]:
    """ROUGE-L 的 F1；任一为空返回 None。"""
    c = tokenize(candidate)
    r = tokenize(reference)
    if not c or not r:
        return None
    l = _lcs_length(c, r)
    if l == 0:
        return 0.0
    p = l / len(c)
    rec = l / len(r)
    return (2 * p * rec / (p + rec)) if (p + rec) else 0.0


def rouge_l_prf(candidate: str, reference: str) -> Optional[dict]:
    c = tokenize(candidate)
    r = tokenize(reference)
    if not c or not r:
        return None
    l = _lcs_length(c, r)
    p = l / len(c)
    rec = l / len(r)
    f1 = (2 * p * rec / (p + rec)) if (p + rec) else 0.0
    return {"precision": p, "recall": rec, "f1": f1}


def batch(candidates: Sequence[str], references: Sequence[str]) -> List[Optional[float]]:
    return [rouge_l(c, r) for c, r in zip(candidates, references)]
