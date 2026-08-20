"""
证据角标注入器
==============
将 EvidenceTracer 的 claim → evidence 映射注入到报告正文：
- 在 claim 末尾追加 <sup>[n]</sup> 角标
- 在文末追加 ## 证据参考 参考文献

仅对 confidence >= 0.5 的 claim 做角标，低置信度或不支持的 claim 不注入。
"""
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

_MIN_CONFIDENCE = 0.5
_MAX_ANCHOR_TEXT = 60


def annotate_report(report: str, evidence_data: dict) -> str:
    if not report or not evidence_data:
        return report

    claims = evidence_data.get("claims", [])
    if not claims:
        return report

    # 过滤符合条件的 claims
    annotated_claims = []
    for claim in claims:
        if claim.get("is_unsupported"):
            continue
        conf = claim.get("confidence", 0)
        if conf < _MIN_CONFIDENCE:
            continue
        text = claim.get("text", "")
        if not text:
            continue
        best_evidence = (claim.get("evidence") or [None])[0]
        if not best_evidence:
            continue
        annotated_claims.append({
            "text": text,
            "evidence": best_evidence,
            "section": claim.get("section", ""),
        })

    if not annotated_claims:
        return report

    annotated = report
    references = []
    for idx, ac in enumerate(annotated_claims, start=1):
        anchor = ac["text"][:_MAX_ANCHOR_TEXT]
        ev = ac["evidence"]
        ref_source = _extract_source_name(ev.get("url", ""))
        ref_conf = ev.get("confidence", 0)

        # 在报告中模糊匹配 anchor 文本并追加角标
        annotated = _inject_footnote(annotated, anchor, idx)
        references.append(
            f"[{idx}] **{ref_source}** · 置信度 {ref_conf:.0%} · "
            f"[查看原文]({ev.get('url', '')})"
        )

    # 文末追加参考文献
    if references:
        ref_section = "\n\n---\n## 证据参考\n\n" + "\n".join(references)
        annotated = annotated.rstrip() + ref_section

    return annotated


def _inject_footnote(text: str, anchor: str, index: int) -> str:
    """在 text 中找到 anchor 的首次出现并在其后追加 <sup>[n]</sup>。"""
    if anchor not in text:
        return text
    pos = text.index(anchor)
    end_pos = pos + len(anchor)
    # 避免在已有角标后重复注入
    after = text[end_pos:end_pos + 20]
    if f"[{index}]" in after or f"<sup>[{index}]" in after:
        return text
    footnote = f"<sup>[{index}]</sup>"
    return text[:end_pos] + footnote + text[end_pos:]


def _extract_source_name(url: str) -> str:
    if not url:
        return "未知来源"
    from urllib.parse import urlparse
    try:
        netloc = urlparse(url).netloc
        parts = netloc.replace("www.", "").split(".")
        return parts[0].capitalize() if parts else netloc
    except Exception:
        return url[:30]
