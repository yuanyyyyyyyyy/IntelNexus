"""
Delta —— 简报增量感知
========================
对比上一期简报（来自 briefing_history 存档）与本期采集结果，输出
「新增 / 消失」条目，直接击中「信息过载、缺增量感知」的痛点。

无需新增存储：上一期 URL 集合从已存档的 Markdown 中以正则提取。
"""
import re
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

_URL_RE = re.compile(r"https?://[^\s)\]\"'>]+")


def _clean_url(url: str) -> str:
    """清理URL：去除UTM参数等追踪参数，用于增量对比"""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        # 移除常见追踪参数
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
            'ref', 'source', 'fbclid', 'gclid', 'mc_cid', 'mc_eid'
        }
        params = parse_qs(parsed.query)
        cleaned_params = {k: v for k, v in params.items() if k.lower() not in tracking_params}
        new_query = urlencode(cleaned_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url.rstrip(".,;") if url else url


def _extract_urls(markdown: str) -> Set[str]:
    if not markdown:
        return set()
    return {_clean_url(u) for u in _URL_RE.findall(markdown)}


def _prev_briefing_markdown() -> str:
    """取上一期简报 Markdown（最近一期，排除当前正在生成的）。"""
    try:
        from intelnexus.config.briefing_history import get_briefing_history
        history = get_briefing_history().get_briefings(limit=5)
        if not history:
            return ""
        # 最新一条即上一期（当前期尚未写入）
        return history[0].get("content", "") or ""
    except Exception as e:
        logger.warning(f"读取上一期简报失败: {e}")
        return ""


def _collected_urls(collected_data: Dict[str, List[Dict]]) -> Tuple[Dict[str, Set[str]], Dict[str, Dict]]:
    """提取URL并构建URL到标题/摘要的映射"""
    per_cat: Dict[str, Set[str]] = {}
    url_info: Dict[str, Dict] = {}  # url -> {"title": ..., "source": ..., "description": ...}
    for cat, items in collected_data.items():
        urls = set()
        for it in items:
            u = it.get("url") or it.get("link", "")
            if u:
                cleaned = _clean_url(u)
                urls.add(cleaned)
                # 存储条目信息用于增强输出
                if cleaned not in url_info:
                    url_info[cleaned] = {
                        "title": it.get("title", ""),
                        "source": it.get("source", ""),
                        "description": (it.get("description", "") or "")[:80]
                    }
        per_cat[cat] = urls
    return per_cat, url_info


def compute_delta(collected_data: Dict[str, List[Dict]]) -> str:
    """生成增量感知 Markdown（新增/消失条目）。无历史时返回提示。"""
    from intelnexus.briefing.config import BRIEFING_CONFIG

    prev_md = _prev_briefing_markdown()
    if not prev_md:
        return ("## 本期增量速览（对比上期）\n\n"
                "> 暂无上一期存档，本期为基线简报；下期起将自动对比新增与消失条目。")

    prev_urls = _extract_urls(prev_md)
    cur, url_info = _collected_urls(collected_data)
    cur_all = set().union(*cur.values()) if cur else set()

    added = sorted(cur_all - prev_urls)
    removed = sorted(prev_urls - cur_all)

    # 从配置读取显示数量限制
    max_added = BRIEFING_CONFIG.get("diff", {}).get("max_added_display", 8)
    max_removed = BRIEFING_CONFIG.get("diff", {}).get("max_removed_display", 5)

    lines = ["## 本期增量速览（对比上期）", ""]
    if added:
        lines.append(f"- **新增情报（{len(added)} 条）**：本期出现、上期未收录")
        for u in added[:max_added]:
            info = url_info.get(u, {})
            title = info.get("title", "")
            source = info.get("source", "")
            desc = info.get("description", "")
            if title:
                lines.append(f"  - [{title}]({u})")
                if source or desc:
                    lines.append(f"    {source} — {desc}..." if desc else f"    {source}")
            else:
                lines.append(f"  - {u}")
        if len(added) > max_added:
            lines.append(f"  - …（其余 {len(added) - max_added} 条）")
    else:
        lines.append("- **新增情报**：本期无相对上期的新条目")

    lines.append("")
    if removed:
        lines.append(f"- **本期未收录（上期有 {len(removed)} 条）**：可能已降温或本期未检出")
        for u in removed[:max_removed]:
            lines.append(f"  - {u}")
        if len(removed) > max_removed:
            lines.append(f"  - …（其余 {len(removed) - max_removed} 条）")
    else:
        lines.append("- **本期未收录**：无（上期条目本期均续报）")

    lines.append("")
    lines.append("> 本栏由简报历史存档自动对比生成，帮助快速识别「变化」而非重复浏览。")
    return "\n".join(lines)
