"""
情报搜索报告构建器
===================
将搜索结果、分析数据与 LLM 输出组装为结构化 10 板块情报报告。

架构：混合生成模式
- 程序化生成：板块 1/3/5/6/7/10（确定性高、零 LLM 成本）
- LLM 生成：板块 2/8/9（需要语义理解）
- 混合生成：板块 4（程序化筛选 + LLM 摘要一句判断）
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# 正则提取 LLM 生成的三个分析板块
# ============================================================================

_SECTION_PATTERNS = {
    "executive_summary": re.compile(
        r'##\s*(?:一[、.]?\s*)?执行摘要\s*\n(.*?)(?=\n##\s)', re.DOTALL | re.IGNORECASE),
    "sentiment_analysis": re.compile(
        r'##\s*(?:八[、.]?\s*)?舆情趋势(?:分析)?\s*\n(.*?)(?=\n##\s|\Z)', re.DOTALL | re.IGNORECASE),
    "risk_assessment": re.compile(
        r'##\s*(?:九[、.]?\s*)?风险评估\s*\n(.*?)(?=\n##\s|\Z)', re.DOTALL | re.IGNORECASE),
}


def _extract_llm_section(llm_output: str, key: str) -> str:
    """从 LLM 输出中提取指定板块内容。"""
    pattern = _SECTION_PATTERNS.get(key)
    if not pattern or not llm_output:
        return ""
    m = pattern.search(llm_output)
    return m.group(1).strip() if m else ""


def extract_analytical_sections(llm_output: str) -> Dict[str, str]:
    """提取 LLM 生成的三个分析板块。

    Returns:
        {"executive_summary": ..., "sentiment_analysis": ..., "risk_assessment": ...}
    """
    return {
        "executive_summary": _extract_llm_section(llm_output, "executive_summary"),
        "sentiment_analysis": _extract_llm_section(llm_output, "sentiment_analysis"),
        "risk_assessment": _extract_llm_section(llm_output, "risk_assessment"),
    }


# ============================================================================
# 各板块生成函数
# ============================================================================

def build_report_overview(query: str, search_mode: str, model: str,
                          report_id: str = None) -> str:
    """板块 1：报告概览（程序化生成）。"""
    now = datetime.now()
    mode_labels = {
        "all": "全源搜索", "web": "网页搜索", "news": "新闻",
        "darkweb": "暗网", "threat": "威胁情报", "smart": "智能路由",
    }
    mode_label = mode_labels.get(search_mode, search_mode)

    lines = [
        "=" * 48,
        "          IntelNexus 情报搜索分析报告",
        "=" * 48,
        "",
        f"报告编号：{report_id or _gen_report_id(now)}",
        "",
        f"分析主题：{query}",
        "",
        f"搜索时间：{now.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"分析模式：{mode_label}",
        "",
        f"分析模型：{model}",
        "",
        f"报告生成时间：{now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "=" * 48,
    ]
    return "\n".join(lines)


def _gen_report_id(now: datetime) -> str:
    """生成报告编号 INTEL-YYYYMMDD-NNN。"""
    date_part = now.strftime("%Y%m%d")
    # 简单递增：用秒数作为序号（同一秒内可能重复，可接受）
    seq = now.second % 1000
    return f"INTEL-{date_part}-{seq:03d}"


def build_executive_summary(llm_sections: Dict[str, str]) -> str:
    """板块 2：核心摘要（LLM 生成）。"""
    content = llm_sections.get("executive_summary", "")
    if not content:
        return "> （执行摘要未生成，请检查 LLM 输出）"
    return content


def build_source_analysis(source_counts: Dict[str, int],
                          source_stats: Dict[str, dict],
                          credibility_data: Optional[dict] = None) -> str:
    """板块 3：来源分析（程序化生成）。"""
    total = sum(source_counts.values()) if source_counts else 0

    lines = ["## 三、来源分析", ""]

    # 来源分布表
    lines.append("### 3.1 来源分布")
    lines.append("")
    if source_counts:
        lines.append("| 来源 | 数量 | 占比 |")
        lines.append("|------|------|------|")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            pct = f"{count / total * 100:.0f}%" if total > 0 else "0%"
            lines.append(f"| {src} | {count} | {pct} |")
    else:
        lines.append("> 无有效来源数据")
    lines.append("")

    # 来源质量评分
    lines.append("### 3.2 来源质量评分")
    lines.append("")
    if credibility_data and credibility_data.get("scores"):
        scores = credibility_data["scores"]
        # 按来源类型分组
        domain_scores = {}
        for s in scores:
            name = s.get("name", "Unknown")
            score = s.get("score", 0.5)
            # 简化：取每个来源的最高分
            if name not in domain_scores or score > domain_scores[name]:
                domain_scores[name] = score

        # 按分数排序展示 Top 10
        sorted_sources = sorted(domain_scores.items(), key=lambda x: -x[1])[:10]
        for name, score in sorted_sources:
            stars = _score_to_stars(score)
            lines.append(f"- **{name}**：{stars} ({score:.0%})")
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


def build_key_intelligence(results: List[dict],
                           kg_entities: List[dict] = None,
                           top_n: int = 10) -> str:
    """板块 4：关键情报（程序化筛选 + 可选 LLM 判断）。"""
    lines = ["## 四、关键情报", ""]

    if not results:
        lines.append("> 无有效情报条目")
        return "\n".join(lines)

    # 按可信度排序，取 Top N
    sorted_results = sorted(
        results,
        key=lambda r: r.get("credibility_score", 0.5),
        reverse=True,
    )[:top_n]

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

        # 关联实体（如果有）
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


def build_credibility_assessment(credibility_data: Optional[dict]) -> str:
    """板块 5：可信度评估（程序化生成）。"""
    lines = ["## 五、可信度评估", ""]

    if not credibility_data:
        lines.append("> 无可信度评估数据")
        return "\n".join(lines)

    avg_score = credibility_data.get("avg_score", 0.5)
    high_count = credibility_data.get("high_count", 0)
    low_count = credibility_data.get("low_count", 0)
    consistency = credibility_data.get("overall_consistency", 1.0)

    lines.append(f"**综合评分**：{avg_score:.0%} / 100")
    lines.append("")

    # 评分因素分解（基于 M-SCORE 权重）
    lines.append("### 5.1 评分因素")
    lines.append("")
    lines.append("| 因素 | 权重 | 说明 |")
    lines.append("|------|------|------|")
    lines.append("| 来源可靠性 | 30% | 域名权威性、历史信誉 |")
    lines.append("| 多源验证 | 25% | 跨源一致性程度 |")
    lines.append("| 发布时间 | 20% | 信息新鲜度 |")
    lines.append("| 内容深度 | 25% | 内容完整性与分析深度 |")
    lines.append("")

    # 统计概览
    lines.append("### 5.2 统计概览")
    lines.append("")
    lines.append(f"- **高可信度条目**（≥70%）：{high_count} 条")
    lines.append(f"- **低可信度条目**（<40%）：{low_count} 条")
    lines.append(f"- **跨源一致性**：{consistency:.0%}")
    lines.append("")

    # 风险提示
    if low_count > 0:
        lines.append("**风险提示**：部分匿名或低权威来源无法充分验证，相关信息建议进一步人工确认。")
        lines.append("")

    return "\n".join(lines)


def build_timeline(results: List[dict]) -> str:
    """板块 6：时间线分析（程序化生成）。"""
    lines = ["## 六、事件时间线", ""]

    if not results:
        lines.append("> 无有效时间数据")
        return "\n".join(lines)

    # 提取有日期的条目并排序
    dated_items = []
    for r in results:
        pub = r.get("published_at", "")
        if pub:
            dated_items.append((pub, r.get("title", "无标题"), r.get("source", "")))

    if not dated_items:
        lines.append("> 搜索结果中未检测到有效日期信息")
        return "\n".join(lines)

    # 按日期排序
    dated_items.sort(key=lambda x: x[0])

    # 去重（同一天多条合并）
    from collections import OrderedDict
    by_date = OrderedDict()
    for date, title, source in dated_items:
        # 标准化日期格式（取前10字符 YYYY-MM-DD）
        date_key = date[:10] if len(date) >= 10 else date
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append((title, source))

    dates = list(by_date.keys())
    for i, date in enumerate(dates):
        items = by_date[date]
        lines.append(f"**{date}**")
        for title, source in items[:3]:  # 每天最多显示 3 条
            lines.append(f"- {title}（{source}）")
        if len(items) > 3:
            lines.append(f"- …（其余 {len(items) - 3} 条）")

        # 添加箭头（非最后一条）
        if i < len(dates) - 1:
            lines.append("")
            lines.append("↓")

        lines.append("")

    return "\n".join(lines)


def build_entity_graph(kg_entities: List[dict],
                       kg_relations: List[dict] = None) -> str:
    """板块 7：实体关系图谱（程序化生成）。"""
    lines = ["## 七、实体关系图谱", ""]

    if not kg_entities:
        lines.append("> 未提取到有效实体")
        return "\n".join(lines)

    # 按重要性排序，取 Top 15
    sorted_entities = sorted(
        kg_entities,
        key=lambda e: e.get("importance", 0),
        reverse=True,
    )[:15]

    # 分类展示
    by_type = {}
    for e in sorted_entities:
        etype = e.get("type", "OTHER")
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append(e)

    type_labels = {
        "ORG": "组织", "PERSON": "人物", "PRODUCT": "产品",
        "TECHNOLOGY": "技术", "LOCATION": "地点", "EVENT": "事件",
        "OTHER": "其他",
    }

    for etype, entities in sorted(by_type.items(), key=lambda x: -len(x[1])):
        label = type_labels.get(etype, etype)
        lines.append(f"### {label}（{len(entities)}）")
        lines.append("")
        for e in entities[:8]:  # 每类最多显示 8 个
            importance = e.get("importance", 0)
            lines.append(f"- **{e['name']}**（重要性：{importance:.0%}）")
        lines.append("")

    # 关系列表（如果有）
    if kg_relations:
        lines.append("### 主要关系")
        lines.append("")
        for rel in kg_relations[:10]:
            src = rel.get("source", "?")
            tgt = rel.get("target", "?")
            rel_type = rel.get("type", "关联")
            lines.append(f"- {src} → {rel_type} → {tgt}")
        lines.append("")

    return "\n".join(lines)


def build_sentiment_analysis(llm_sections: Dict[str, str]) -> str:
    """板块 8：舆情趋势（LLM 生成）。"""
    content = llm_sections.get("sentiment_analysis", "")
    if not content:
        return "> （舆情趋势分析未生成，请检查 LLM 输出）"
    return content


def build_risk_assessment(llm_sections: Dict[str, str],
                          conflicts: List[dict] = None,
                          action_items: List[dict] = None) -> str:
    """板块 9：风险评估（LLM + 程序化补充）。"""
    content = llm_sections.get("risk_assessment", "")

    lines = ["## 九、风险评估", ""]

    if content:
        lines.append(content)
        lines.append("")

    # 补充冲突信息
    if conflicts:
        lines.append("### 9.1 跨源冲突")
        lines.append("")
        for c in conflicts[:5]:
            severity = c.get("severity", 0)
            desc = c.get("description", "")
            ctype = c.get("type", "未知")
            lines.append(f"- [{ctype}] {desc}（严重度：{severity:.0%}）")
        lines.append("")

    # 补充行动项
    if action_items:
        lines.append("### 9.2 建议行动")
        lines.append("")
        priority_icons = {"high": "🔴", "medium": "🟡", "low": ""}
        for a in action_items[:5]:
            icon = priority_icons.get(a.get("priority", "low"), "⚪")
            lines.append(f"- {icon} {a.get('action', '')}")
        lines.append("")

    return "\n".join(lines)


def build_evidence_appendix(scraped: Dict[str, str],
                            results: List[dict] = None) -> str:
    """板块 10：证据附件（程序化生成）。"""
    lines = ["## 十、证据附件", ""]

    if not scraped and not results:
        lines.append("> 无可用证据材料")
        return "\n".join(lines)

    # 优先使用 scraped URL（有实际内容）
    sources = []
    if scraped:
        for url in list(scraped.keys())[:30]:
            sources.append({"url": url, "title": "", "has_content": True})

    # 补充 results 中的链接（如果 scraped 不足）
    if results and len(sources) < 30:
        for r in results:
            link = r.get("link", "")
            if link and link not in [s["url"] for s in sources]:
                sources.append({
                    "url": link,
                    "title": r.get("title", ""),
                    "has_content": False,
                })
                if len(sources) >= 30:
                    break

    if not sources:
        lines.append("> 无可用证据材料")
        return "\n".join(lines)

    for idx, src in enumerate(sources, 1):
        lines.append(f"[{idx}] **{src['title'] or src['url']}**")
        lines.append(f"- URL：{src['url']}")
        if src.get("has_content"):
            lines.append("- 状态：已抓取全文")
        else:
            lines.append("- 状态：仅元数据")
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
) -> str:
    """组装完整的 10 板块情报搜索报告。

    Args:
        query: 用户查询
        search_mode: 搜索模式
        model: LLM 模型名
        llm_output: LLM 生成的原始报告（含 TL;DR + 执行摘要 + 舆情 + 风险等）
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

    Returns:
        完整的 Markdown 报告字符串
    """
    # 1. 提取 LLM 生成的三个分析板块
    llm_sections = extract_analytical_sections(llm_output)

    # 2. 组装各板块
    sections = [
        build_report_overview(query, search_mode, model, report_id),
        "",
        "# 二、核心摘要",
        "",
        build_executive_summary(llm_sections),
        "",
        build_source_analysis(source_counts, source_stats, credibility_data),
        build_key_intelligence(results, kg_entities),
        build_credibility_assessment(credibility_data),
        build_timeline(results),
        build_entity_graph(kg_entities, kg_relations),
        build_sentiment_analysis(llm_sections),
        build_risk_assessment(llm_sections, conflicts, action_items),
        build_evidence_appendix(scraped or {}, results),
    ]

    return "\n".join(sections)
