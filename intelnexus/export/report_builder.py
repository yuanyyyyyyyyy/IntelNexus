"""
情报搜索报告构建器 v2
======================
将搜索结果、分析数据与 LLM 输出组装为结构化情报报告。

架构：混合生成模式
- 程序化生成：板块 01/03/04/05/06/07/14/15（确定性高、零 LLM 成本）
- LLM 生成：板块 02/08/09/10/11/12/13（需要语义理解）

15 板块结构：
 01. 报告概览          02. 核心摘要(LLM)       03. 事件画像
 04. 来源分析          05. 关键情报            06. 证据链分析(LLM)
 07. 实体关系图谱      08. 事件演化时间线      09. 舆情趋势(LLM)
 10. 影响评估(LLM)     11. 风险评估(LLM)       12. 攻击面分析(LLM)
 13. 情报判断(LLM)     14. 历史关联            15. 原始证据
"""

import re
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from intelnexus.core.logger import get_logger
from intelnexus.core.search.source_meta import summarize_empty_channels
from intelnexus.ui.icons import icon

logger = get_logger(__name__)


# ============================================================================
# 正则提取 LLM 生成的五个分析板块
# ============================================================================

_SECTION_PATTERNS = {
    "executive_summary": re.compile(
        r'##\s*(?:二[、.]\s*)?核心摘要\s*\n+(.*?)(?=\n+##\s|$)', re.DOTALL | re.IGNORECASE),
    "evidence_chain": re.compile(
        # LLM 按模板会写出「证据链分析」标题，后缀必须可选，否则板块永远提取不到
        r'##\s*(?:六[、.]\s*)?证据链(?:\s*分析)?\s*\n+(.*?)(?=\n+##\s|$)', re.DOTALL | re.IGNORECASE),
    "sentiment_analysis": re.compile(
        r'##\s*(?:八[、.]\s*)?舆情趋势(?: 分析)?\s*\n+(.*?)(?=\n+##\s|$)', re.DOTALL | re.IGNORECASE),
    "impact_assessment": re.compile(
        r'##\s*(?:九[、.]\s*)?影响评估\s*\n+(.*?)(?=\n+##\s|$)', re.DOTALL | re.IGNORECASE),
    "risk_assessment": re.compile(
        r'##\s*(?:十[、.]\s*)?风险评估\s*\n+(.*?)(?=\n+##\s|$)', re.DOTALL | re.IGNORECASE),
    "attack_surface": re.compile(
        r'##\s*(?:十二[、.]\s*)?攻击面分析\s*\n+(.*?)(?=\n+##\s|$)', re.DOTALL | re.IGNORECASE),
    "intelligence_judgment": re.compile(
        # 「情报判断与后续关注」中间无空格，此处不能用字面空格匹配
        r'##\s*(?:十三[、.]\s*)?情报判断\s*(?:与后续关注)?\s*\n+(.*?)(?=\n+##\s|$)', re.DOTALL | re.IGNORECASE),
}


def _extract_llm_section(llm_output: str, key: str) -> str:
    """从 LLM 输出中提取指定板块内容。"""
    pattern = _SECTION_PATTERNS.get(key)
    if not pattern or not llm_output:
        return ""
    m = pattern.search(llm_output)
    if m:
        logger.debug(f"[_extract_llm_section] 成功提取 '{key}': {len(m.group(1))} chars")
    else:
        logger.debug(f"[_extract_llm_section] 未匹配 '{key}'（板块不存在或 LLM 未输出）")
    return m.group(1).strip() if m else ""


def extract_analytical_sections(llm_output: str) -> Dict[str, str]:
    """提取 LLM 生成的七个分析板块。

    Returns:
        {"executive_summary", "evidence_chain", "sentiment_analysis",
         "impact_assessment", "risk_assessment", "attack_surface",
         "intelligence_judgment"}
    """
    return {
        "executive_summary": _extract_llm_section(llm_output, "executive_summary"),
        "evidence_chain": _extract_llm_section(llm_output, "evidence_chain"),
        "sentiment_analysis": _extract_llm_section(llm_output, "sentiment_analysis"),
        "impact_assessment": _extract_llm_section(llm_output, "impact_assessment"),
        "risk_assessment": _extract_llm_section(llm_output, "risk_assessment"),
        "attack_surface": _extract_llm_section(llm_output, "attack_surface"),
        "intelligence_judgment": _extract_llm_section(llm_output, "intelligence_judgment"),
    }


# ============================================================================
# 各板块生成函数
# ============================================================================

def compute_heat_level(results: List[dict], source_count: int = 0,
                       relevance_ratio: Optional[float] = None) -> int:
    """热度估算（0-100）：去重后的独立文章数 ×4 + 跨源广度加成。

    多个搜索引擎会收录同一篇文章（旧实现按原始条数 ×2 计），同一篇文章
    最多被重复计 5 次，导致热度虚高；此处按归一化 URL 去重后再计。

    Args:
        relevance_ratio: 相关结果占比（0-1）。传入时按其折算文章基数 ——
            热度原本是纯音量指标，一批全部弱相关的噪声同样能刷出高分，
            与「首次发现：未知 / 状态：信息不足」并排显示自相矛盾。
            不传（None）表示相关率未知，保持原有口径。
    """
    unique_urls = set()
    for r in results or []:
        # 归一化后字段是 url，link/resolved_url 仅为兼容旧结构：回填完成后
        # url 已是真实地址，取错键会让热度按空集兜底为原始条数（虚高）
        u = r.get("url") or r.get("resolved_url") or r.get("link") or ""
        if not u:
            continue
        try:
            p = urlparse(u)
            key = f"{(p.netloc or '').lower()}{p.path.rstrip('/')}"
        except Exception:
            key = u
        unique_urls.add(key)
    base = len(unique_urls) or len(results or [])
    if relevance_ratio is not None:
        ratio = max(0.0, min(1.0, float(relevance_ratio)))
        base = int(round(base * ratio))
    if source_count:
        breadth = max(0, source_count - 1)
    else:
        breadth = max(0, len({r.get("source", "") for r in results or [] if r.get("source")}) - 1)
    return min(100, base * 4 + breadth * 5)


def compute_snapshot_heat(results: List[dict], source_count: int = 0) -> int:
    """事件快照用热度 —— 与 :func:`build_event_profile` 完全同口径。

    事件历史里的「热度变化」要与报告里展示的热度可对表，两边必须用
    同一函数、同一输入（相关结果子集 + 相关率折算）。抽出来是因为
    ``search_worker`` 在保存快照时也要用，避免口径分叉后注释声称
    「一致」而实现早已漂移。
    """
    if not results:
        return 0
    relevant, _ = _select_relevant(results)
    try:
        from intelnexus.analysis.relevance import relevant_ratio as _relevant_ratio
        ratio = _relevant_ratio(list(results))
    except Exception:  # pragma: no cover
        ratio = None
    return compute_heat_level(relevant or results, source_count,
                              relevance_ratio=ratio)


def _select_relevant(results: List[dict]) -> tuple:
    """按 ``weak_related`` 标记挑出相关结果。

    报告侧统一走这里，不再各自按空白切词匹配查询关键词 —— 中文查询整句
    会塌成 1 个关键词而零命中，随后「无匹配就用全量」的兜底会把噪声全量
    放进统计（热度/可信度/时间线无一幸免）。

    Returns:
        ``(items, note)``：``note`` 为空串表示正常按相关性过滤；否则是一句
        面向读者的降级说明，必须渲染到报告中，不允许静默回退。
    """
    if not results:
        return [], ""
    try:
        from intelnexus.analysis.relevance import split_relevant
    except Exception as e:  # pragma: no cover - 相关性模块缺失不应阻断报告
        logger.warning(f"相关性模块不可用，本板块未做相关性过滤: {e}")
        return list(results), (
            "> ⚠️ 相关性模块不可用，本板块未做相关性过滤，"
            "统计口径包含全部检索结果。"
        )

    relevant, available = split_relevant(results)
    if not available:
        return list(results), (
            "> ⚠️ 相关性评估不可用（嵌入模型未就绪），本板块未做相关性过滤，"
            "统计口径包含全部检索结果。"
        )
    if not relevant:
        return [], (
            "> ⚠️ 本次检索结果全部被判定为弱相关，本板块无有效样本；"
            "结论不应基于该查询的现有语料得出。"
        )
    return relevant, ""


def build_report_overview(query: str, search_mode: str, model: str,
                          source_counts: Dict[str, int] = None,
                          result_count: int = 0,
                          report_id: str = None,
                          authorization: Optional[dict] = None) -> str:
    """板块 01：报告概览（程序化生成）。"""
    now = datetime.now()
    # 模式中文名的唯一事实来源是 SEARCH_MODES —— 旧实现local 维护了一份副本，
    # 漏登记 resolve_mode 实际返回的 "smart_general"，导致报告头部直接打印内部模式名。
    mode_label = search_mode
    try:
        from intelnexus.core.search.modes import SEARCH_MODES
        entry = SEARCH_MODES.get(search_mode)
        if entry and len(entry) > 1 and entry[1]:
            mode_label = entry[1]
    except Exception:  # pragma: no cover - 取不到就原样展示
        pass
    total_sources = len(source_counts) if source_counts else 0

    lines = [
        "# IntelNexus 情报搜索分析报告",
        "",
        # 旧版缺失该标题，导致正文从「二、核心摘要」起编，章节号断档
        "## 一、报告概览",
        "",
        f"**报告编号**：{report_id or _gen_report_id(now)}",
        "",
        f"**分析主题**：{query}",
        "",
        f"**搜索时间**：{now.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"**分析模式**：{mode_label}",
        "",
        f"**分析模型**：{model}",
        "",
        f"**数据来源**：{total_sources} 个来源",
        "",
        f"**采集信息**：{result_count} 条",
        "",
        f"**报告生成时间**：{now.strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # 授权状态：针对具名实体的侦察请求必须显式声明，否则读者无法判断
    # 报告中的安全内容是否可以据以开展主动测试。
    if authorization:
        if authorization.get("requires_authorization"):
            state = "已声明授权" if authorization.get("authorized") else "未声明授权"
            lines.append(f"**授权状态**：{state}")
            lines.append("")
            note = authorization.get("scope_note") or ""
            if note:
                lines.append(f"> {note}")
                lines.append("")

    lines.append("---")
    return "\n".join(lines)


def _gen_report_id(now: datetime) -> str:
    """生成报告编号 INTEL-YYYYMMDD-NNN。"""
    date_part = now.strftime("%Y%m%d")
    seq = now.second % 1000
    return f"INTEL-{date_part}-{seq:03d}"


def build_executive_summary(llm_sections: Dict[str, str]) -> str:
    """板块 02：核心摘要（LLM 生成）。"""
    content = llm_sections.get("executive_summary", "")
    if not content:
        return "> （执行摘要未生成，请检查 LLM 输出）"
    # 清理 LLM 输出中可能包含的原始标题（避免重复）
    content = re.sub(r'^##\s*(?:二[、.]?\s*)?核心摘要\s*\n', '', content, flags=re.MULTILINE)
    return content.strip()


def build_event_profile(results: List[dict], llm_sections: Dict[str, str], query: str = "") -> str:
    """板块 03：事件画像（程序化 + LLM 辅助）。

    从搜索结果中提取事件基本信息，形成事件卡片。
    只统计与查询主题相关的结果（消费检索阶段产出的 weak_related 标记）。
    """
    lines = ["## 三、事件画像", ""]

    if not results:
        lines.append("> 无有效数据生成事件画像")
        return "\n".join(lines)

    # 过滤相关结果：统一消费 weak_related，禁止「零命中就回退全量」
    all_results = list(results)
    results, relevance_note = _select_relevant(results)
    if relevance_note:
        lines.append(relevance_note)
        lines.append("")
    if not results:
        lines.append("> 无有效数据生成事件画像")
        return "\n".join(lines)

    # 提取时间范围（只取标准日期格式 YYYY-MM-DD）
    dates = []
    for r in results:
        pub = r.get("published_at", "")
        if pub:
            # 只接受 YYYY-MM-DD 格式（长度 >= 10 且以数字开头）
            if len(pub) >= 10 and pub[0:4].isdigit():
                dates.append(pub[:10])

    if dates:
        dates.sort()
        first_seen = dates[0]
        last_seen = dates[-1]
        try:
            d1 = datetime.strptime(first_seen, "%Y-%m-%d")
            d2 = datetime.strptime(last_seen, "%Y-%m-%d")
            duration = (d2 - d1).days + 1
        except (ValueError, TypeError):
            duration = len(set(dates))
    else:
        first_seen = "未知"
        last_seen = "未知"
        duration = "未知"

    # 统计来源数
    sources = set(r.get("source", "") for r in results if r.get("source"))

    # 计算热度（去重独立文章数 + 跨源广度，详见 compute_heat_level）
    # 相关率按「过滤前的全量」计，避免过滤后恒为 100% 而失去惩罚意义
    try:
        from intelnexus.analysis.relevance import relevant_ratio as _relevant_ratio
        _ratio = _relevant_ratio(all_results)
    except Exception:  # pragma: no cover
        _ratio = None
    heat_level = compute_heat_level(results, relevance_ratio=_ratio)
    heat_bar = "█" * (heat_level // 10) + "░" * (10 - heat_level // 10)

    # 计算可信度
    scores = [r.get("credibility_score", 0.5) for r in results if r.get("credibility_score")]
    avg_cred = sum(scores) / len(scores) if scores else 0.5
    cred_bar = "█" * int(avg_cred * 10) + "░" * (10 - int(avg_cred * 10))

    lines.append(f"**首次发现**：{first_seen}")
    lines.append("")
    lines.append(f"**最新变化**：{last_seen}")
    lines.append("")
    # duration 为「未知」时不能拼单位，否则渲染成「未知 天」
    duration_text = duration if duration == "未知" else f"{duration} 天"
    lines.append(f"**持续时间**：{duration_text}")
    lines.append("")
    lines.append(f"**信息来源**：{len(sources)} 个独立来源")
    lines.append("")
    lines.append(f"**热度**：{heat_bar} {heat_level}")
    lines.append("")
    lines.append(f"**可信度**：{cred_bar} {avg_cred:.0%}")
    lines.append("")

    # 事件状态判断（基于时间跨度）
    if duration == "未知":
        status = "信息不足"
    elif duration <= 1:
        status = "刚出现"
    elif duration <= 3:
        status = "发展中"
    elif duration <= 7:
        status = "持续关注"
    else:
        status = "长期事件"

    lines.append(f"**当前状态**：{status}")
    lines.append("")

    return "\n".join(lines)


def _empty_channel_notes(source_stats: Dict[str, dict]) -> List[str]:
    """依据 source_stats 列出「已检索但未产出相关结果」的渠道（count==0）。

    委托 ``intelnexus.core.search.source_meta.summarize_empty_channels`` 计算
    渠道标签（单一事实来源，报告与 UI 共用，避免漂移）。仅用于报告透明度展示：
    帮助读者区分「只配了单渠道」与「多渠道检索后仅部分命中」，不改变
    ``source_counts`` 口径（热度计算的跨源广度加成依赖其规模，不可因补充空渠道而虚高）。
    返回可直接 extend 进报告行的 Markdown 片段列表；无空渠道时返回空列表。
    """
    notes = summarize_empty_channels(source_stats)
    if not notes:
        return []
    return [
        "",
        f"> 另有 {len(notes)} 个渠道已检索但未产出相关结果：{', '.join(notes)}。",
    ]


def build_source_analysis(source_counts: Dict[str, int],
                          source_stats: Dict[str, dict],
                          credibility_data: Optional[dict] = None) -> str:
    """板块 04：来源分析（程序化生成）。

    分两个维度呈现：**检索渠道**（Bing/Baidu/RSS 等，回答「从哪找到的」）与
    **出版方**（ctrip.com/zhihu.com 等，回答「谁说的」）。旧实现把引擎名当
    出版方，导致可信度评分打在 www.baidu.com 上，真实出版方被完全遮蔽。
    """
    total = sum(source_counts.values()) if source_counts else 0

    scores = (credibility_data or {}).get("scores") or []
    # 只有评分条目携带出版方字段时才切换为双维度口径；
    # 旧缓存 / 旧调用方未提供该字段时保持原样，避免破坏既有导出。
    has_publisher_data = any("publisher" in s for s in scores)

    lines = ["## 四、来源分析", ""]

    # 4.1 检索渠道分布
    lines.append("### 4.1 检索渠道分布" if has_publisher_data else "### 4.1 来源分布")
    lines.append("")
    if source_counts:
        head = "检索渠道" if has_publisher_data else "来源"
        lines.append(f"| {head} | 数量 | 占比 | 角色 |")
        lines.append("|------|------|------|------|")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            pct = f"{count / total * 100:.0f}%" if total > 0 else "0%"
            role = _get_source_role(src)
            lines.append(f"| {src} | {count} | {pct} | {role} |")
        if has_publisher_data:
            lines.append("")
            lines.append("> 检索渠道只表示「从哪个引擎/订阅源找到」，不代表内容出版方；"
                         "可信度按下方出版方计分。")
    else:
        lines.append("> 无有效来源数据")
    lines.append("")

    # 透明度补充：揭示「已检索但未产出相关结果」的渠道，避免读者误判为单渠道配置。
    # 不改动 source_counts，热度跨源广度加成口径保持不变。
    lines.extend(_empty_channel_notes(source_stats))

    # 4.2 质量评分（出版方维度 / 兼容旧的来源维度）
    lines.append("### 4.2 出版方质量评分" if has_publisher_data
                 else "### 4.2 来源质量评分")
    lines.append("")

    if scores:
        grouped: Dict[str, float] = {}
        for s in scores:
            score = s.get("score", 0.5)
            if has_publisher_data:
                publisher = (s.get("publisher") or "").strip()
                # 出版方未解析时显式标注，禁止用引擎名冒充出版方
                label = publisher or f"出版方未解析（{s.get('engine') or s.get('name', 'Unknown')}）"
            else:
                label = s.get("name", "Unknown")
            if label not in grouped or score > grouped[label]:
                grouped[label] = score

        sorted_sources = sorted(grouped.items(), key=lambda x: -x[1])[:10]
        for name, score in sorted_sources:
            stars = _score_to_stars(score)
            if name.startswith("出版方未解析"):
                lines.append(f"- **{name}**：{stars} ({score:.0%}) "
                             f"[跳转未解析，按检索渠道回退计分]")
            else:
                lines.append(f"- **{name}**：{stars} ({score:.0%}) "
                             f"[{_get_source_role(name)}]")
    else:
        lines.append("> 无可信度评分数据")
    lines.append("")

    return "\n".join(lines)


def _score_to_stars(score: float) -> str:
    """将 0-1 分数转换为星级字符串。"""
    full = int(score * 5)
    half = 1 if (score * 5 - full) >= 0.5 else 0
    empty = 5 - full - half
    return "★" * full + ("☆" if half else "") + "☆" * empty


# 来源角色分类映射
# Primary: 官方/权威数据源（漏洞库、公告）
# Secondary: 媒体/新闻源
# Community: 社区/论坛/开源平台
# Research: 技术分析/学术研究
_SOURCE_ROLE_MAP = {
    # Primary - 官方权威
    "NVD": "Primary",
    "CISA_KEV": "Primary",
    "CNVD": "Primary",
    "ExploitDB": "Primary",
    "AlienVault_OTX": "Primary",
    # Secondary - 媒体报道
    "Google News": "Secondary",
    "SecRSS": "Secondary",
    "Qianxin": "Secondary",
    "scheduled": "Secondary",
    # Community - 社区
    "HackerNews": "Community",
    "HuggingFace": "Community",
    "arXiv": "Community",
    "GitHub": "Community",
    "Reddit": "Community",
    "Twitter": "Community",
    # Darkweb - 暗网
    "Ahmia": "Community",
    "OnionLink": "Community",
    "TorDex": "Community",
}


def _get_source_role(source_name: str) -> str:
    """根据来源名称返回角色分类标签。"""
    # 精确匹配
    if source_name in _SOURCE_ROLE_MAP:
        return _SOURCE_ROLE_MAP[source_name]
    # 模糊匹配（包含关键词）
    name_lower = source_name.lower()
    if any(kw in name_lower for kw in ('news', 'rss', 'media', 'blog')):
        return "Secondary"
    if any(kw in name_lower for kw in ('forum', 'community', 'reddit', 'hn', 'hacker')):
        return "Community"
    if any(kw in name_lower for kw in ('research', 'lab', 'arxiv', 'paper')):
        return "Research"
    if any(kw in name_lower for kw in ('nvd', 'cve', 'kev', 'cnvd', 'exploit', 'otx')):
        return "Primary"
    return "Secondary"  # 默认归类为媒体


def build_key_intelligence(results: List[dict],
                           kg_entities: List[dict] = None,
                           top_n: int = 10) -> str:
    """板块 05：关键情报（程序化筛选 + 实体关联）。"""
    lines = ["## 五、关键情报", ""]

    if not results:
        lines.append("> 无有效情报条目")
        return "\n".join(lines)

    # 先剔除弱相关条目，再按「相关度优先、可信度次之」排序。
    # 旧实现只按 credibility_score 排序 —— 与主题无关的条目只要来源权威就会
    # 顶到榜首（如订阅源最新条目），是噪声登上关键情报的直接原因。
    pool, relevance_note = _select_relevant(results)
    if relevance_note:
        lines.append(relevance_note)
        lines.append("")

    if not pool:
        lines.append("> 无有效情报条目（全部结果被判定为弱相关）")
        return "\n".join(lines)

    sorted_results = sorted(
        pool,
        key=lambda r: (r.get("relevance_score", 0.0), r.get("credibility_score", 0.5)),
        reverse=True,
    )[:top_n]

    if len(pool) > len(sorted_results):
        lines.append(
            f"> 按相关度与可信度展示前 {len(sorted_results)} 条"
            f"（相关结果共 {len(pool)} 条，采集总量 {len(results)} 条）"
        )
        lines.append("")

    for idx, item in enumerate(sorted_results, 1):
        title = item.get("title", "无标题")
        source = item.get("source", "未知来源")
        score = item.get("credibility_score", 0.5)
        link = item.get("link", "")
        published = item.get("published_at", "")

        lines.append(f"### {idx:03d}. {title}")
        lines.append("")
        lines.append(f"- **来源**：{source}")
        if published:
            lines.append(f"- **时间**：{published}")
        lines.append(f"- **可信度**：{score:.0%}")
        if link:
            lines.append(f"- **链接**：[{link}]({link})")

        if kg_entities:
            related = _find_related_entities(title, kg_entities)
            if related:
                entity_tags = " ".join(f"[{e['name']}]" for e in related[:5])
                lines.append(f"- **关联实体**：{entity_tags}")

        lines.append("")

    return "\n".join(lines)


def _find_related_entities(text: str, entities: List[dict],
                           max_return: int = 5) -> List[dict]:
    """从文本中查找匹配的实体（简单子串匹配）。"""
    text_lower = text.lower()
    matched = []
    for e in entities:
        name = e.get("name", "")
        if name and name.lower() in text_lower:
            matched.append(e)
            if len(matched) >= max_return:
                break
    return matched


def _postprocess_llm_text(text: str) -> str:
    """对 LLM 输出进行后处理：置信度数字转等级 + 风险命名修正。"""
    if not text:
        return text
    
    # 1. 置信度精确数字转等级（向后兼容旧模型输出）
    def _conf_to_level(match):
        val = float(match.group(1))
        if val >= 0.8:
            return "高"
        elif val >= 0.5:
            return "中"
        else:
            return "低"
    
    # 匹配 "综合置信度：0.82" 或 "**综合置信度**：0.82\n" 格式
    text = re.sub(
        r'\*?\*?综合置信度\*?\*?[：:]\s*(0\.\d+)\s*\n',
        lambda m: f"**综合置信度**：{_conf_to_level(m)}\n",
        text
    )
    # 匹配 "支持度：0.85" 格式
    text = re.sub(
        r'支持度[：:]\s*(0\.\d+)',
        lambda m: f"支持度：{_conf_to_level(m)}",
        text
    )
    
    # 2. "供应链风险" → "供应链透明风险"（更精确的情报术语）
    text = text.replace("供应链风险", "供应链透明风险")
    
    return text


#: 证据链中「（来源：XXX，来源等级：…）」形式的引用
_CITED_SOURCE_RE = re.compile(r'来源[：:]\s*([^，,、；;（()）\[\]|\n]{2,40})')


def _known_source_names(results: List[dict]) -> set:
    """本次检索中可核验的来源名集合（渠道名 + 出版方 + 域名，全部小写）。"""
    names = set()
    for r in results or []:
        for key in ("source", "publisher"):
            val = (r.get(key) or "").strip().lower()
            if val:
                names.add(val)
        host = _evidence_domain(r.get("url") or r.get("link") or "")
        if host:
            names.add(host.lower())
    return names


def _unverifiable_citations(text: str, known: set) -> List[str]:
    """找出无法在原始证据清单中定位的引用来源。

    仅对纯 ASCII 引用名做判定：中文品牌名与域名之间无法自动比对
    （「携程酒店」 vs ``hotels.ctrip.com``），宁可漏报也不误报 ——
    误报会训练读者忽略告警。
    """
    if not text or not known:
        return []
    unknown: List[str] = []
    for m in _CITED_SOURCE_RE.finditer(text):
        cited = m.group(1).strip().strip('*` 　')
        if not cited or not cited.isascii():
            continue
        low = cited.lower()
        if any(low in k or k in low for k in known):
            continue
        if low not in [u.lower() for u in unknown]:
            unknown.append(cited)
    return unknown


def build_evidence_chain(results: List[dict],
                         credibility_data: Optional[dict] = None,
                         conflicts: List[dict] = None,
                         llm_sections: Dict[str, str] = None) -> str:
    """板块 06：证据链分析（LLM 生成结论→证据节点 + 程序化补充跨源冲突）。

    展示关键结论的证据支撑情况，每个结论有独立的证据节点和置信度。
    """
    lines = ["## 六、证据链分析", ""]

    llm_sections = llm_sections or {}
    llm_evidence = llm_sections.get("evidence_chain", "")

    if llm_evidence:
        # 清理 LLM 输出中可能包含的原始标题
        llm_evidence = re.sub(
            r'^##\s*(?:六[、.]?\s*)?证据链\s*\n', '', llm_evidence, flags=re.MULTILINE)
        # 后处理：置信度转等级 + 风险命名修正
        llm_evidence = _postprocess_llm_text(llm_evidence)
        lines.append(llm_evidence.strip())
        lines.append("")

        # 引用存在性校验：LLM 可能引用本次检索中根本不存在的外部来源
        # （审计实锤：E2 引用 Expedia，但原始证据清单里没有任何 Expedia URL），
        # 这类引用必须显式标注，不能无声地当成已证实证据。
        unverified = _unverifiable_citations(llm_evidence, _known_source_names(results))
        if unverified:
            lines.append("### 引用来源可核验性")
            lines.append("")
            for name in unverified[:10]:
                lines.append(f"- ⚠️ **{name}**：未核验 —— 该来源未出现在本次原始证据清单中")
            lines.append("")
            lines.append("> 「未核验」表示无法从本次检索结果回溯该引用，"
                         "其支持度不应作为已证实证据采信。")
            lines.append("")
    else:
        # 降级：无可信度数据时提示
        if not credibility_data:
            lines.append("> 无可信度评估数据，证据链未生成")
            return "\n".join(lines)

        avg_score = credibility_data.get("avg_score", 0.5)
        high_count = credibility_data.get("high_count", 0)
        low_count = credibility_data.get("low_count", 0)
        consistency = credibility_data.get("overall_consistency", 1.0)

        lines.append(f"**总体证据强度**：{avg_score:.0%}")
        lines.append("")
        lines.append(f"- **高可信度来源**（≥70%）：{high_count} 个")
        lines.append(f"- **低可信度来源**（<40%）：{low_count} 个")
        lines.append(f"- **跨源一致性**：{consistency:.0%}")
        lines.append("")

        if credibility_data.get("scores"):
            lines.append("### 来源证据详情")
            lines.append("")
            # 按来源聚合评分（同一来源取最高分）
            source_scores = {}
            for s in credibility_data["scores"]:
                name = s.get("name", "Unknown")
                score = s.get("score", 0.5)
                reason = s.get("reason", "")
                if name not in source_scores or score > source_scores[name]["score"]:
                    source_scores[name] = {"score": score, "reason": reason}
            
            sorted_sources = sorted(source_scores.items(), key=lambda x: -x[1]["score"])[:10]
            for name, data in sorted_sources:
                score = data["score"]
                reason = data["reason"]
                strength = "★" * int(score * 5) + "☆" * (5 - int(score * 5))
                lines.append(f"- **{name}**：{strength} ({score:.0%}) — {reason}")
            lines.append("")

    # 跨源冲突（始终展示，无论 LLM 是否生成了证据链）
    if conflicts:
        lines.append("### 跨源冲突")
        lines.append("")
        for c in conflicts[:5]:
            severity = c.get("severity", 0)
            desc = c.get("description", "")
            ctype = c.get("type", "未知")
            # Markdown 不支持 HTML SVG，改用 Unicode 警告符号
            lines.append(f"- ⚠️ [{ctype}] {desc}（严重度：{severity:.0%}）")
        lines.append("")

    return "\n".join(lines)


def build_entity_graph(kg_entities: List[dict],
                       kg_relations: List[dict] = None) -> str:
    """板块 07：实体关系图谱（程序化生成）。"""
    lines = ["## 七、实体关系图谱", ""]

    if not kg_entities:
        lines.append("> 未提取到有效实体")
        lines.append("")
        lines.append("**可能原因**：")
        lines.append("- 网页内容抓取不足，实体抽取器缺少分析素材")
        lines.append("- spaCy 语言模型未安装（需要 zh_core_web_sm 或 en_core_web_sm）")
        lines.append("- 搜索结果以短文本为主，难以提取有效实体")
        return "\n".join(lines)

    # 噪声实体在渲染层再拦一次：KG 可能来自历史快照或缓存产物，
    # 抽取层的过滤未必覆盖到，这里是读者看到的最后一道防线。
    try:
        from intelnexus.analysis.intelligence_graph import EntityExtractor
        kg_entities = [
            e for e in kg_entities
            if not EntityExtractor._is_noise_entity(e.get("name", ""))
        ]
    except Exception:  # pragma: no cover - 过滤失败不应阻断报告
        pass

    if not kg_entities:
        lines.append("> 未提取到有效实体（候选实体均在降噪阶段被过滤）")
        return "\n".join(lines)

    sorted_entities = sorted(
        kg_entities,
        key=lambda e: e.get("importance", 0),
        reverse=True,
    )[:15]

    by_type = {}
    for e in sorted_entities:
        etype = e.get("type", "OTHER")
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append(e)

    type_labels = {
        "ORG": "组织", "PERSON": "人物", "PRODUCT": "产品",
        "TECHNOLOGY": "技术", "LOCATION": "地点", "EVENT": "事件",
        "GPE": "地缘政治实体", "NORP": "群体/民族", "LAW": "法律",
        "DATE": "时间", "MONEY": "金额", "OTHER": "其他",
        "UNKNOWN": "未分类（类型未识别）",
    }

    for etype, entities in sorted(by_type.items(), key=lambda x: -len(x[1])):
        label = type_labels.get(etype, etype)
        lines.append(f"### {label}（{len(entities)}）")
        lines.append("")
        for e in entities[:8]:
            importance = e.get("importance", 0)
            lines.append(f"- **{e['name']}**（重要性：{importance:.0%}）")
        lines.append("")

    if kg_relations:
        # 关系两端渲染为实体名，且只保留两侧都出现在本板块的实体 ——
        # 旧实现直接打印实体 id，也不检查实体是否已被 TopN 截断，
        # 于是出现「关系里的实体在实体清单中不存在」的悬空引用。
        name_by_id = {e.get("id"): e.get("name") for e in kg_entities if e.get("id")}
        displayed_ids = {e.get("id") for e in sorted_entities if e.get("id")}

        rendered = []
        for rel in kg_relations:
            src_id = rel.get("subject_id")
            tgt_id = rel.get("object_id")
            src = name_by_id.get(src_id, rel.get("source"))
            tgt = name_by_id.get(tgt_id, rel.get("target"))
            if not src or not tgt:
                continue
            if src_id is not None and tgt_id is not None:
                if src_id not in displayed_ids or tgt_id not in displayed_ids:
                    continue
            rel_type = rel.get("type", rel.get("predicate", "关联"))
            rendered.append(f"- {src} → {rel_type} → {tgt}")
            if len(rendered) >= 10:
                break

        if rendered:
            lines.append("### 主要关系")
            lines.append("")
            lines.extend(rendered)
            lines.append("")

    return "\n".join(lines)


def _normalize_date(date_str: str) -> str:
    """将各种日期格式标准化为 YYYY-MM-DD。
    
    支持的格式：
    - 2026-08-20T00:17:57Z (ISO)
    - 2026-08-20 (标准)
    - Fri, 28 Aug 2026 (RFC 2822)
    - Fri, 28 Au (截断格式，尝试解析)
    
    返回标准化日期字符串，无法解析则返回空字符串。
    """
    if not date_str:
        return ""
    
    # 已经是标准格式
    if len(date_str) >= 10 and date_str[0:4].isdigit() and date_str[4] == '-':
        return date_str[:10]
    
    # 尝试解析常见格式
    from datetime import datetime
    date_formats = [
        "%Y-%m-%dT%H:%M:%SZ",      # ISO 8601
        "%Y-%m-%d",                   # 标准
        "%a, %d %b %Y",              # RFC 2822
        "%a, %d %b",                  # 截断格式（无年份）
    ]
    
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_str.strip(), fmt)
            # 如果是截断格式（无年份），假设是当前年份
            if parsed.year == 1900:
                parsed = parsed.replace(year=2026)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # 尝试处理截断的月份名（如 "Au" → "Aug"）
    import re
    m = re.match(r'\w+,\s*(\d+)\s+(\w+)', date_str.strip())
    if m:
        day = m.group(1)
        month_abbr = m.group(2)
        # 尝试补全月份名（至少 3 字符）
        month_map = {
            'ja': 'Jan', 'fe': 'Feb', 'ma': 'Mar', 'ap': 'Apr',
            'au': 'Aug', 'se': 'Sep', 'oc': 'Oct', 'no': 'Nov', 'de': 'Dec',
        }
        if len(month_abbr) < 3:
            prefix = month_abbr.lower()[:2]
            if prefix in month_map:
                month_abbr = month_map[prefix]
        # 尝试解析
        try:
            parsed = datetime.strptime(f"{day} {month_abbr} 2026", "%d %b %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    # 无法解析，返回空字符串（而非原字符串，避免污染时间线）
    return ""


def build_event_evolution(results: List[dict],
                          llm_sections: Dict[str, str] = None,
                          query: str = "") -> str:
    """板块 08：事件演化时间线（程序化 + 可选 AI 总结）。"""
    lines = ["## 八、事件演化", ""]

    if not results:
        lines.append("> 无有效时间数据")
        return "\n".join(lines)

    # 过滤相关结果：与事件画像同一口径（消费 weak_related）
    results, relevance_note = _select_relevant(results)
    if relevance_note:
        lines.append(relevance_note)
        lines.append("")
    if not results:
        lines.append("> 无有效时间数据")
        return "\n".join(lines)

    # 标准化日期后收集（只保留可解析的日期）
    dated_items = []
    for r in results:
        title = r.get("title", "无标题")
        source = r.get("source", "")
        
        # 过滤 SEO 垃圾站点（Mshale 等带有随机标签的条目）
        if re.search(r'\([A-Za-z0-9]{8,}\)', title):
            continue
        # 过滤已知垃圾源
        if source.lower() in ('mshale', ):
            continue
        
        pub = r.get("published_at", "")
        if pub:
            normalized = _normalize_date(pub)
            # 只保留成功解析的日期（YYYY-MM-DD 格式）
            if normalized and len(normalized) == 10 and normalized[0:4].isdigit():
                dated_items.append((normalized, title, source))

    if not dated_items:
        lines.append("> 搜索结果中未检测到有效日期信息")
        return "\n".join(lines)

    # 按标准化日期排序
    dated_items.sort(key=lambda x: x[0])

    by_date = OrderedDict()
    for date, title, source in dated_items:
        date_key = date[:10] if len(date) >= 10 else date
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append((title, source))

    dates = list(by_date.keys())

    # 检测事件阶段变化（使用情报术语）
    total_dates = len(dates)
    if total_dates >= 3:
        third = total_dates // 3
        phases = {
            "early": dates[:third],
            "mid": dates[third:third * 2],
            "late": dates[third * 2:],
        }
        phase_labels = {
            "early": "Discovery（发现期）",
            "mid": "Attribution（归因期）",
            "late": "Expansion（扩散期）",
        }
    else:
        phases = {"early": dates, "mid": [], "late": []}
        phase_labels = {
            "early": "Discovery（发现期）",
            "mid": "Attribution（归因期）",
            "late": "Expansion（扩散期）",
        }

    for i, date in enumerate(dates):
        items = by_date[date]
        lines.append(f"**{date}**")
        for title, source in items[:3]:
            lines.append(f"- {title}（{source}）")
        if len(items) > 3:
            lines.append(f"- …（其余 {len(items) - 3} 条）")

        # 阶段标记
        if total_dates >= 3:
            if date == phases["early"][-1] and phases["mid"]:
                lines.append("")
                lines.append(f"*--- {phase_labels['early']} 结束 ---*")
            elif date == phases["mid"][-1] and phases["late"]:
                lines.append("")
                lines.append(f"*--- {phase_labels['mid']} 结束 ---*")

        if i < len(dates) - 1:
            lines.append("")
            lines.append("↓")
        lines.append("")

    # AI 生成的演化总结（如果有）
    llm_sections = llm_sections or {}
    judgment = llm_sections.get("intelligence_judgment", "")
    if judgment:
        # 尝试从情报判断中提取演化相关总结
        evolution_hint = ""
        for line in judgment.split("\n"):
            if "态势" in line or "演变" in line or "发展" in line:
                evolution_hint = line.strip()
                break
        if evolution_hint:
            lines.append("---")
            lines.append("")
            lines.append(f"**演化总结**：{evolution_hint}")
            lines.append("")

    return "\n".join(lines)


def build_sentiment_analysis(llm_sections: Dict[str, str]) -> str:
    """板块 09：舆情趋势（LLM 生成）。"""
    content = llm_sections.get("sentiment_analysis", "")
    if not content:
        return "> （舆情趋势分析未生成，请检查 LLM 输出）"
    # 清理标题
    content = re.sub(r'^##\s*(?:八[、.]?\s*)?舆情趋势(?:分析)?\s*\n', '', content, flags=re.MULTILINE)
    return content.strip()


def build_impact_assessment(llm_sections: Dict[str, str]) -> str:
    """板块 10：影响评估（LLM 生成）。"""
    content = llm_sections.get("impact_assessment", "")
    if not content:
        return "> （影响评估未生成，请检查 LLM 输出）"
    # 清理标题
    content = re.sub(r'^##\s*(?:九[、.]?\s*)?影响评估\s*\n', '', content, flags=re.MULTILINE)
    return content.strip()


def build_risk_assessment(llm_sections: Dict[str, str],
                          risk_level: Optional[str] = None,
                          risk_reason: str = "") -> str:
    """板块 11：风险评估（程序化定级 + LLM 论述）。

    风险等级由 :mod:`intelnexus.analysis.risk_level` 依据客观威胁证据给出，
    不接受 LLM 或来源可信度的影响；LLM 只负责论述，不负责定级。
    """
    from intelnexus.analysis.risk_level import LEVEL_INSUFFICIENT
    lines = []
    if risk_level:
        lines.append(f"**程序化风险定级**：{risk_level}")
        lines.append("")
        if risk_reason:
            lines.append(f"> 定级依据：{risk_reason}")
            lines.append("")
        if risk_level == LEVEL_INSUFFICIENT:
            lines.append(
                "> 未采集到漏洞、威胁情报或跨源冲突等客观证据。"
                "「证据不足」表示本次检索无法支撑风险判断，不等于目标安全。"
            )
            lines.append("")

    content = llm_sections.get("risk_assessment", "")
    if not content:
        if not lines:
            return "> （本次分析未生成风险评估内容）"
        return "\n".join(lines).strip()
    # 清理标题
    content = re.sub(r'^##\s*(?:十[、.]?\s*)?风险评估\s*\n', '', content, flags=re.MULTILINE)
    # 后处理：供应链风险→供应链透明风险
    content = _postprocess_llm_text(content)
    lines.append(content.strip())
    return "\n".join(lines).strip()


def build_attack_surface(llm_sections: Dict[str, str],
                         authorized: bool = True) -> str:
    """板块 11.5：攻击面分析（LLM 可选生成，受授权闸门约束）。

    针对具名实体的侦察请求在未声明授权时，本板块替换为合规说明 ——
    攻击面分层/利用路径可直接用于主动测试，不得在未授权场景下输出。
    """
    if not authorized:
        try:
            from intelnexus.core.search.authorization import UNAUTHORIZED_NOTICE
            return UNAUTHORIZED_NOTICE
        except Exception:  # pragma: no cover - 模块缺失时仍需合规兜底
            return (
                "> ⚠️ 本次查询未声明授权，已降级为纯公开信息（OSINT）分析，"
                "不生成攻击面内容。对目标开展主动测试需事先取得书面授权。"
            )

    content = llm_sections.get("attack_surface", "")
    if not content:
        return "> （本次分析未生成攻击面分析内容）"
    # 清理标题
    content = re.sub(r'^##\s*(?:十[、.]?\s*)?攻击面分析\s*\n', '', content, flags=re.MULTILINE)
    return content.strip()


def build_intelligence_judgment(llm_sections: Dict[str, str]) -> str:
    """板块 12：情报判断与后续关注（LLM 可选生成）。"""
    content = llm_sections.get("intelligence_judgment", "")
    if not content:
        return "> （本次分析未生成情报判断内容）"
    # 清理标题
    content = re.sub(r'^##\s*(?:十一[、.]?\s*)?情报判断(?:与后续关注)?\s*\n', '', content, flags=re.MULTILINE)
    return content.strip()


def build_event_history(event_changes: Optional[dict] = None,
                        query: str = "") -> str:
    """板块 13：历史关联与变化检测（程序化生成）。

    展示与历史搜索的对比变化，体现系统的"记忆"能力。
    """
    lines = ["## 十四、历史关联与变化检测", ""]

    if not event_changes:
        lines.append("*首次搜索该主题，暂无历史对比数据。后续搜索将自动检测变化。*")
        lines.append("")
        return "\n".join(lines)

    if not event_changes.get("has_history"):
        lines.append("*首次搜索该主题，暂无历史对比数据。后续搜索将自动检测变化。*")
        lines.append("")
        return "\n".join(lines)

    # 搜索统计
    search_count = event_changes.get("search_count", 0)
    days = event_changes.get("days_since_last", 0)
    lines.append(f"**历史搜索次数**：{search_count} 次")
    lines.append("")
    if days > 0:
        lines.append(f"**距上次搜索**：{days} 天")
        lines.append("")

    # 变化检测
    has_changes = False

    identity_change = event_changes.get("identity_change")
    if identity_change:
        has_changes = True
        lines.append(f"**身份状态变化**：{identity_change}")
        lines.append("")

    heat_change = event_changes.get("heat_change")
    if heat_change:
        has_changes = True
        # Markdown 不支持 HTML SVG，改用 Unicode 箭头
        arrow = "↑" if heat_change.startswith('+') else "↓"
        lines.append(f"**热度变化**：{arrow} {heat_change}")
        lines.append("")

    risk_change = event_changes.get("risk_change")
    if risk_change:
        has_changes = True
        lines.append(f"**风险等级变化**：{risk_change}")
        lines.append("")

    # 「证据不足 ↔ 低/中/高」不同量纲，单独呈现，避免被读成风险升降
    risk_evidence_change = event_changes.get("risk_evidence_change")
    if risk_evidence_change:
        has_changes = True
        lines.append(f"**风险证据状态变化**：{risk_evidence_change}")
        lines.append("")
        lines.append("> 该变化表示威胁证据的完整度改变（此前无法定级 / 现已可定级），"
                     "不等同于风险等级升高或降低。")
        lines.append("")

    new_findings = event_changes.get("new_findings", [])
    if new_findings:
        has_changes = True
        lines.append("**新增发现**：")
        lines.append("")
        for f in new_findings[:5]:
            lines.append(f"- {f}")
        lines.append("")

    if not has_changes:
        lines.append("*与上次搜索相比，未检测到显著变化。*")
        lines.append("")

    return "\n".join(lines)


_MAX_EVIDENCE_ITEMS = 30


def _evidence_url_key(url: str) -> str:
    """证据去重键：域名 + 路径（忽略 scheme、查询串与末尾斜杠）。

    同一篇文章可能以 http/https、带 utm 参数、带尾斜杠等多种形态出现，
    按域名+路径归一后只保留一条证据。
    """
    try:
        parsed = urlparse(url or "")
        return f"{parsed.netloc.lower()}{parsed.path}".rstrip("/")
    except Exception:
        return url or ""


def _evidence_domain(url: str) -> str:
    """展示用来源域名（去掉 www 前缀）。"""
    try:
        host = (urlparse(url or "").netloc or "").lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _is_unresolved_wrapper(url: str) -> bool:
    """URL 是否仍是搜索引擎跳转包装壳（真实地址未解析出来）。"""
    try:
        from intelnexus.core.search.web import is_wrapper_url
        return is_wrapper_url(url)
    except Exception:
        return False


def _evidence_fallback_title(text: str, max_len: int = 40) -> str:
    """降级标题：抓取正文常为「标题 - 正文」形态，取首段作为标题。"""
    flat = " ".join((text or "").split())
    if not flat:
        return ""
    head = flat.split(" - ", 1)[0].strip(" -") or flat
    if len(head) > max_len:
        return head[:max_len].rstrip() + "…"
    return head


def build_evidence_appendix(scraped: Dict[str, str],
                            results: List[dict] = None) -> str:
    """板块 14：原始证据（程序化生成）。

    条目以「标题」为主行（来源域名次之，URL 单列可复制）：URL 只是溯源
    地址，顶到标题位会让人看不出这条证据是什么。
    """
    lines = ["## 十五、原始证据", ""]

    if not scraped and not results:
        lines.append("> 无可用证据材料")
        return "\n".join(lines)

    # URL → 标题/来源 索引。结果归一化后字段是 url，link 仅为兼容旧结构。
    meta_by_key: Dict[str, dict] = {}
    for r in results or []:
        u = r.get("url") or r.get("link") or ""
        key = _evidence_url_key(u)
        if not key:
            continue
        if key not in meta_by_key or not meta_by_key[key].get("title"):
            meta_by_key[key] = {
                "title": r.get("title", ""),
                "source": r.get("source", ""),
                "snippet": r.get("description", ""),
                # 弱相关条目保留在本板块供溯源，但必须标明「未纳入分析」——
                # 否则读者看到噪声标题会以为它参与了结论推导
                "weak": bool(r.get("weak_related", False)),
            }

    sources: List[dict] = []
    seen: set = set()

    for url, content in (scraped or {}).items():
        key = _evidence_url_key(url)
        if not key or key in seen:
            continue
        seen.add(key)
        meta = meta_by_key.get(key, {})
        sources.append({
            "url": url,
            "title": meta.get("title", ""),
            "source": meta.get("source", ""),
            "fallback": _evidence_fallback_title(content) or _evidence_fallback_title(meta.get("snippet", "")),
            "has_content": True,
            "weak": meta.get("weak", False),
        })
        if len(sources) >= _MAX_EVIDENCE_ITEMS:
            break

    if results and len(sources) < _MAX_EVIDENCE_ITEMS:
        for r in results:
            u = r.get("url") or r.get("link") or ""
            key = _evidence_url_key(u)
            if not u or key in seen:
                continue
            seen.add(key)
            sources.append({
                "url": u,
                "title": r.get("title", ""),
                "source": r.get("source", ""),
                "fallback": _evidence_fallback_title(r.get("description", "")),
                "has_content": False,
                "weak": bool(r.get("weak_related", False)),
            })
            if len(sources) >= _MAX_EVIDENCE_ITEMS:
                break

    if not sources:
        lines.append("> 无可用证据材料")
        return "\n".join(lines)

    for idx, src in enumerate(sources, 1):
        url = src["url"]
        domain = _evidence_domain(url)
        title = src["title"] or src["fallback"] or domain or "未命名来源"
        lines.append(f"[{idx}] **{title}**")
        if domain:
            suffix = f"（{src['source']}）" if src["source"] else ""
            lines.append(f"- 来源：{domain}{suffix}")
        # 完整链接优先保留在 URL 行（可复制），解析不出真实地址的包装壳显式标注
        flag = "（跳转包装，未解析）" if _is_unresolved_wrapper(url) else ""
        lines.append(f"- URL：`{url}`{flag}")
        status = "已抓取全文" if src["has_content"] else "仅元数据"
        if src.get("weak"):
            status += " · 弱相关（未纳入结论推导）"
        lines.append(f"- 状态：{status}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# 主入口：组装完整报告
# ============================================================================

def build_intelligence_report(
    query: str,
    search_mode: str,
    model: str,
    llm_output: str,
    results: List[dict],
    source_counts: Dict[str, int],
    source_stats: Dict[str, dict],
    credibility_data: Optional[dict] = None,
    kg_entities: List[dict] = None,
    kg_relations: List[dict] = None,
    conflicts: List[dict] = None,
    action_items: List[dict] = None,
    scraped: Dict[str, str] = None,
    report_id: str = None,
    event_changes: Optional[dict] = None,
    risk_level: Optional[str] = None,
    risk_reason: str = "",
    authorization: Optional[dict] = None,
) -> str:
    """组装完整的情报搜索报告。

    Args:
        query: 用户查询
        search_mode: 搜索模式
        model: LLM 模型名
        llm_output: LLM 生成的原始报告（含 6 个分析板块）
        results: 搜索结果列表
        source_counts: 来源计数
        source_stats: 来源状态
        credibility_data: 可信度评估数据
        kg_entities: 知识图谱实体
        kg_relations: 知识图谱关系
        conflicts: 跨源冲突
        action_items: 行动项
        scraped: 抓取的网页内容
        report_id: 自定义报告编号
        event_changes: 历史事件变化检测数据

    Returns:
        完整的 Markdown 报告字符串
    """
    # 1. 提取 LLM 生成的六个分析板块
    llm_sections = extract_analytical_sections(llm_output)

    result_count = len(results) if results else 0
    # 未声明授权时降级为纯 OSINT：不输出攻击面内容
    authorized = True if not authorization else bool(authorization.get("authorized", True))

    # 2. 组装 14 板块
    sections = [
        # 程序化板块
        build_report_overview(query, search_mode, model, source_counts, result_count,
                              report_id, authorization),
        "",
        # LLM 板块
        "## 二、核心摘要",
        "",
        build_executive_summary(llm_sections),
        "",
        "---",
        "",
        # 程序化板块
        build_event_profile(results, llm_sections, query),
        "",
        "---",
        "",
        build_source_analysis(source_counts, source_stats, credibility_data),
        "",
        "---",
        "",
        build_key_intelligence(results, kg_entities),
        "",
        "---",
        "",
        build_evidence_chain(results, credibility_data, conflicts, llm_sections),
        "",
        "---",
        "",
        build_entity_graph(kg_entities, kg_relations),
        "",
        "---",
        "",
        build_event_evolution(results, llm_sections, query),
        "",
        "---",
        "",
        # LLM 板块
        "## 九、舆情趋势",
        "",
        build_sentiment_analysis(llm_sections),
        "",
        "---",
        "",
        "## 十、影响评估",
        "",
        build_impact_assessment(llm_sections),
        "",
        "---",
        "",
        "## 十一、风险评估",
        "",
        build_risk_assessment(llm_sections, risk_level, risk_reason),
        "",
        "---",
        "",
        "## 十二、攻击面分析",
        "",
        build_attack_surface(llm_sections, authorized=authorized),
        "",
        "---",
        "",
        "## 十三、情报判断与后续关注",
        "",
        build_intelligence_judgment(llm_sections),
        "",
        "---",
        "",
        # 程序化板块：历史关联
        build_event_history(event_changes, query),
        "",
        "---",
        "",
        # 程序化板块
        build_evidence_appendix(scraped or {}, results),
    ]

    return "\n".join(sections)
