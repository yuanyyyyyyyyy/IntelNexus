"""信源响应解析：把不同信源的原始响应归一化为统一条目结构。

统一条目结构（写入 items.jsonl）::

    {
      "id": "<source_id>:<native_id>",
      "source_id": str, "source_name": str, "category": str,
      "title": str, "url": str, "published_at": str|None,
      "official_summary": str,        # 参考摘要（R3 评测依赖）
      "content": str,                 # 送给模型生成摘要的正文
      "content_from": "detail"|"inline",
      "quality_eligible": bool,       # 正文与参考摘要是否来自不同来源
      "content_sha256": str, "collected_at": iso
    }

设计要点：**参考摘要与输入正文必须来源不同**，否则模型输入即参考答案，
ROUGE-L/BERTScore 会虚高。``quality_eligible`` 为 false 的条目只用于
数据集构成、时延、吞吐、成本与隐私测量，不进入表3 质量评测。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from experiments.common import sha256_text, utc_now_iso

# 参考摘要过短则视为无有效金标
MIN_SUMMARY_CHARS = 30
MIN_CONTENT_CHARS = 80


def get_by_path(obj: Any, path: str) -> Optional[Any]:
    """按点号路径取值，支持列表下标（如 ``cve.descriptions.0.value``）。

    ``$`` 表示根对象。路径不存在返回 None（调用方负责跳过该条）。
    """
    if obj is None or not path:
        return None
    cur = obj
    for part in path.split("."):
        if part == "$":
            continue
        if cur is None:
            return None
        if isinstance(cur, list):
            if not part.isdigit():
                return None
            idx = int(part)
            cur = cur[idx] if 0 <= idx < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _pick_lang_value(value: Any, prefer: str = "en") -> Optional[str]:
    """处理 [{lang, value}, ...] 形式的多语言字段。"""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        items = [v for v in value if isinstance(v, dict)]
        if not items:
            return None
        for it in items:
            if str(it.get("lang", "")).lower().startswith(prefer):
                return str(it.get("value") or "")
        return str(items[0].get("value") or "") or None
    return None


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    t = re.sub(r"<[^>]+>", " ", str(text))
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _rss_text(node: Optional[ET.Element], *names: str) -> str:
    if node is None:
        return ""
    for n in names:
        child = node.find(n)
        if child is not None and (child.text or child.get("href")):
            return _clean(child.text or child.get("href"))
    return ""


def parse_rss(text: str) -> List[Dict[str, Any]]:
    """解析 RSS/Atom 的条目列表。"""
    out: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return out
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for n in nodes:
        out.append(
            {
                "title": _rss_text(n, "title", "{http://www.w3.org/2005/Atom}title"),
                "link": _rss_text(n, "link", "{http://www.w3.org/2005/Atom}link"),
                "summary": _rss_text(
                    n, "description", "summary", "{http://www.w3.org/2005/Atom}summary"
                ),
                "published": _rss_text(
                    n, "pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}updated"
                ),
                "raw": None,
            }
        )
    return out


def parse_api_json(data: Any, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按 items_path 与字段路径从 JSON 中提取条目。"""
    items = get_by_path(data, str(spec.get("items_path") or "$"))
    if items is None:
        return []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []

    url_template = spec.get("url_template")
    out: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        summary = _pick_lang_value(get_by_path(raw, str(spec.get("summary_field") or "")))
        content_raw = get_by_path(raw, str(spec.get("content_field") or "")) if spec.get("content_field") else None
        native_id = str(get_by_path(raw, str(spec.get("id_field") or "")) or "")
        link = str(get_by_path(raw, str(spec.get("url_field") or "")) or "")
        if not link and url_template and native_id:
            # 逐条详情页 URL：无独立 URL 字段时按模板构造，
            # 不可回退成信源 URL——否则同信源所有条目会被误判为重复
            link = str(url_template).format(id=native_id)
        out.append(
            {
                "title": _clean(str(get_by_path(raw, str(spec.get("title_field") or "")) or "")) or native_id,
                "link": link,
                "summary": _clean(summary or ""),
                "published": str(get_by_path(raw, str(spec.get("published_field") or "")) or "") or None,
                "content_inline": _clean(_pick_lang_value(content_raw) or "") if content_raw else "",
                "native_id": native_id,
                "raw": raw,
            }
        )
    return out


def extract_main_text(html: str, max_chars: int = 20000) -> str:
    """从公告详情页 HTML 中抽取正文。

    优先 trafilatura（与项目 ``ENABLE_MAIN_CONTENT_EXTRACTION`` 同一依赖），
    缺失时降级为"去标签 + 去脚本样式"的朴素抽取。截断到 max_chars。
    """
    text = ""
    try:
        import trafilatura  # type: ignore

        text = trafilatura.extract(html) or ""
    except Exception:  # noqa: BLE001 - 降级路径
        text = ""
    if not text:
        body = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html or "")
        body = re.sub(r"(?s)<[^>]+>", " ", body)
        text = body
    text = _clean(text)
    return text[:max_chars]


def normalize(spec: Dict[str, Any], entry: Dict[str, Any], content: str, content_from: str) -> Optional[Dict[str, Any]]:
    """归一化为统一条目；任一项不合格返回 None（由调用方记录跳过原因）。"""
    native_id = entry.get("native_id") or entry.get("link") or ""
    summary = _clean(entry.get("summary") or "")
    content = _clean(content)
    if not native_id:
        return None
    if len(summary) < MIN_SUMMARY_CHARS:
        return None
    if len(content) < MIN_CONTENT_CHARS:
        return None
    item = {
        "id": f"{spec.get('id')}:{native_id}",
        "source_id": spec.get("id"),
        "source_name": spec.get("name"),
        "category": spec.get("category"),
        "title": entry.get("title") or native_id,
        # 无逐条 URL 时不回退成信源 URL：否则同信源所有条目 URL 相同，
        # 会在去重时被整体误判为重复
        "url": entry.get("link") or "",
        "published_at": entry.get("published") or None,
        "official_summary": summary,
        "content": content,
        "content_from": content_from,
        "quality_eligible": bool(spec.get("quality_eligible", False)),
        "content_sha256": sha256_text(content),
        "collected_at": utc_now_iso(),
    }
    return item
