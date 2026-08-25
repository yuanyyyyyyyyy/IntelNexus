"""
证据角标注入器
==============
将 EvidenceTracer 的 claim -> evidence 映射注入到报告正文：
- 在 claim 所在句子末尾追加 <sup>[n]</sup> 角标（永不插入 URL/链接内部）
- 文末「证据参考」按唯一 URL 聚合去重，标注每源被引用次数

仅对 confidence >= 0.5 且有证据支撑的 claim 注入角标。
"""
import re
from urllib.parse import urlparse

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

_MIN_CONFIDENCE = 0.5
_MAX_ANCHOR_TEXT = 60


def _is_inside_url(text: str, pos: int) -> bool:
    """判断 text[pos] 是否处于 markdown 链接或裸 URL 内部。"""
    # 向前找最近的 ( 和 ) —— 处于未闭合的 (…) 内即视为在链接里
    return text.rfind("(", 0, pos) > text.rfind(")", 0, pos)


def _find_sentence_end(text: str, start: int) -> int:
    """从 start 向后找句末位置（。！？.!?. 或换行），返回插入点（句末标点之后）。"""
    m = re.search(r"[。！？!?.]|\n", text[start:])
    if not m:
        return len(text)
    end = start + m.end()
    # 连续结尾标点（如 ”。 或 ！）一并吞掉
    while end < len(text) and text[end] in "」』\"'.！？。":
        end += 1
    return end


def annotate_report(report: str, evidence_data: dict) -> str:
    if not report or not evidence_data:
        return report

    claims = evidence_data.get("claims", [])
    if not claims:
        return report

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
        _ev = claim.get("evidence")
        if isinstance(_ev, dict):
            best_evidence = _ev  # 兼容单证据对象形态
        elif isinstance(_ev, list) and _ev:
            best_evidence = _ev[0]
        else:
            continue
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
    # url -> {ref_no, source, conf, count}：同 URL 只占一个编号
    ref_by_url = {}
    ordered_refs = []

    for ac in annotated_claims:
        anchor = ac["text"][:_MAX_ANCHOR_TEXT]
        ev = ac["evidence"]
        url = ev.get("url", "")

        entry = ref_by_url.get(url)
        if entry is None:
            idx = len(ordered_refs) + 1
            entry = {
                "no": idx,
                "source": _extract_source_name(url),
                "conf": ev.get("confidence", 0),
                "url": url,
                "count": 0,
            }
            ref_by_url[url] = entry
            ordered_refs.append(entry)
        entry["count"] += 1
        footnote = f"<sup>[{entry['no']}]</sup>"

        # 找 anchor 首次出现；角标插到所在句子的末尾（而非 anchor 尾部），
        # 并拒绝注入 URL/链接内部
        pos = annotated.find(anchor) if anchor in annotated else -1
        # 表格行内不注入角标：句尾插入会把 <sup> 推到下一管道行行首，
        # 撕裂 markdown 表格结构（导出 PDF/Word 时整表错乱）
        if pos >= 0:
            line_start = annotated.rfind("\n", 0, pos) + 1
            if annotated[line_start:pos].lstrip().startswith("|") or "|" in annotated[pos:annotated.find("\n", pos)]:
                logger.debug("anchor inside table row, skipped: %s", anchor[:40])
                continue
        if pos >= 0 and not _is_inside_url(annotated, pos):
            insert_at = _find_sentence_end(annotated, pos + len(anchor))
            annotated = annotated[:insert_at] + footnote + annotated[insert_at:]
        elif pos < 0:
            logger.debug("anchor not found in report: %s", anchor[:40])
        # pos 在 URL 内部时放弃本条角标（宁缺毋滥）

    if ordered_refs:
        lines = []
        for e in ordered_refs:
            count_note = f"（引用 {e['count']} 次）" if e["count"] > 1 else ""
            lines.append(
                f"[{e['no']}] **{e['source']}**{count_note} · "
                f"置信度 {e['conf']:.0%} · [查看原文]({e['url']})"
            )
        ref_section = "\n\n---\n## 证据参考\n\n" + "\n".join(lines)
        annotated = annotated.rstrip() + ref_section

    return annotated


def _extract_source_name(url: str) -> str:
    if not url:
        return "未知来源"
    try:
        netloc = urlparse(url).netloc
        parts = netloc.replace("www.", "").split(".")
        # Yahoo 重定向链还原为真实来源名不可行时至少给出主域名首段
        return parts[0].capitalize() if parts else netloc
    except Exception:
        return url[:30]
