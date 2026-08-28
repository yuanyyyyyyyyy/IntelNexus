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

from intelnexus.core.logger import get_logger
from intelnexus.ui.icons import icon

logger = get_logger(__name__)


# ============================================================================
# 正则提取 LLM 生成的五个分析板块
# ============================================================================

_SECTION_PATTERNS = {
    "executive_summary": re.compile(
        r'##\s*(?:二 [、.]?\s*)?核心摘要\s*\n(.*?)(?=\n##\s)', re.DOTALL | re.IGNORECASE),
    "evidence_chain": re.compile(
        r'##\s*(?:六 [、.]?\s*)?证据链\s*\n(.*?)(?=\n##\s)', re.DOTALL | re.IGNORECASE),
    "sentiment_analysis": re.compile(
        r'##\s*(?:八 [、.]?\s*)?舆情趋势 (?:分析)?\s*\n(.*?)(?=\n##\s|\Z)', re.DOTALL | re.IGNORECASE),
    "impact_assessment": re.compile(
        r'##\s*(?:九 [、.]?\s*)?影响评估\s*\n(.*?)(?=\n##\s)', re.DOTALL | re.IGNORECASE),
    "risk_assessment": re.compile(
        r'##\s*(?:十 [、.]?\s*)?风险评估\s*\n(.*?)(?=\n##\s)', re.DOTALL | re.IGNORECASE),
    "attack_surface": re.compile(
        r'##\s*(?:十二 [、.]?\s*)?攻击面分析\s*\n(.*?)(?=\n##\s)', re.DOTALL | re.IGNORECASE),
    "intelligence_judgment": re.compile(
        r'##\s*(?:十三 [、.]?\s*)?情报判断 (?:与后续关注)?\s*\n(.*?)(?=\n##\s|\Z)', re.DOTALL | re.IGNORECASE),
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
        # 调试：输出前 200 chars 查看实际格式
        preview = llm_output[:200].replace('\n', '\\n')
        logger.warning(f"[_extract_llm_section] 未匹配 '{key}'，LLM 输出预览: {preview}")
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

def build_report_overview(query: str, search_mode: str, model: str,
                          source_counts: Dict[str, int] = None,
                          result_count: int = 0,
                          report_id: str = None) -> str:
    """板块 01：报告概览（程序化生成）。"""
    now = datetime.now()
    mode_labels = {
        "all": "全源搜索", "web": "网页搜索", "news": "新闻",
        "darkweb": "暗网", "threat": "威胁情报", "smart": "智能路由",
    }
    mode_label = mode_labels.get(search_mode, search_mode)
    total_sources = len(source_counts) if source_counts else 0

    lines = [
        "# IntelNexus 情报搜索分析报告",
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
        "---",
    ]
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
    只统计与查询主题相关的结果（标题或摘要包含查询关键词）。
    """
    lines = ["## 三、事件画像", ""]

    if not results:
        lines.append("> 无有效数据生成事件画像")
        return "\n".join(lines)

    # 过滤相关结果（标题或摘要包含查询关键词）
    if query:
        query_lower = query.lower()
        query_keywords = set(query_lower.split())
        relevant_results = []
        for r in results:
            title = r.get("title", "").lower()
            snippet = r.get("snippet", "").lower()
            # 至少有一个关键词匹配
            if any(kw in title or kw in snippet for kw in query_keywords if len(kw) >= 2):
                relevant_results.append(r)
        # 如果没有匹配结果，使用全部结果（避免空数据）
        if relevant_results:
            results = relevant_results

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

    # 计算热度（基于结果数量）
    result_count = len(results)
    heat_level = min(100, result_count * 2)
    heat_bar = "█" * (heat_level // 10) + "░" * (10 - heat_level // 10)

    # 计算可信度
    scores = [r.get("credibility_score", 0.5) for r in results if r.get("credibility_score")]
    avg_cred = sum(scores) / len(scores) if scores else 0.5
    cred_bar = "█" * int(avg_cred * 10) + "░" * (10 - int(avg_cred * 10))

    lines.append(f"**首次发现**：{first_seen}")
    lines.append("")
    lines.append(f"**最新变化**：{last_seen}")
    lines.append("")
    lines.append(f"**持续时间**：{duration} 天")
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


def build_source_analysis(source_counts: Dict[str, int],
                          source_stats: Dict[str, dict],
                          credibility_data: Optional[dict] = None) -> str:
    """板块 04：来源分析（程序化生成）。"""
    total = sum(source_counts.values()) if source_counts else 0

    lines = ["## 四、来源分析", ""]

    # 来源分布表
    lines.append("### 4.1 来源分布")
    lines.append("")
    if source_counts:
        lines.append("| 来源 | 数量 | 占比 | 角色 |")
        lines.append("|------|------|------|------|")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            pct = f"{count / total * 100:.0f}%" if total > 0 else "0%"
            role = _get_source_role(src)
            lines.append(f"| {src} | {count} | {pct} | {role} |")
    else:
        lines.append("> 无有效来源数据")
    lines.append("")

    # 来源质量评分
    lines.append("### 4.2 来源质量评分")
    lines.append("")
    if credibility_data and credibility_data.get("scores"):
        scores = credibility_data["scores"]
        domain_scores = {}
        for s in scores:
            name = s.get("name", "Unknown")
            score = s.get("score", 0.5)
            if name not in domain_scores or score > domain_scores[name]:
                domain_scores[name] = score

        sorted_sources = sorted(domain_scores.items(), key=lambda x: -x[1])[:10]
        for name, score in sorted_sources:
            stars = _score_to_stars(score)
            role = _get_source_role(name)
            lines.append(f"- **{name}**：{stars} ({score:.0%}) [{role}]")
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
        lines.append("### 主要关系")
        lines.append("")
        for rel in kg_relations[:10]:
            src = rel.get("source", rel.get("subject_id", "?"))
            tgt = rel.get("target", rel.get("object_id", "?"))
            rel_type = rel.get("type", rel.get("predicate", "关联"))
            lines.append(f"- {src} → {rel_type} → {tgt}")
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

    # 过滤相关结果（标题或摘要包含查询关键词）
    if query:
        query_lower = query.lower()
        query_keywords = set(query_lower.split())
        filtered = []
        for r in results:
            title = r.get("title", "").lower()
            snippet = r.get("snippet", "").lower()
            if any(kw in title or kw in snippet for kw in query_keywords if len(kw) >= 2):
                filtered.append(r)
        if filtered:
            results = filtered

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


def build_risk_assessment(llm_sections: Dict[str, str]) -> str:
    """板块 11：风险评估（LLM 生成）。"""
    content = llm_sections.get("risk_assessment", "")
    if not content:
        return "> （风险评估未生成，请检查 LLM 输出）"
    # 清理标题
    content = re.sub(r'^##\s*(?:十 [、.]?\s*)?风险评估\s*\n', '', content, flags=re.MULTILINE)
    # 后处理：供应链风险→供应链透明风险
    content = _postprocess_llm_text(content)
    return content.strip()


def build_attack_surface(llm_sections: Dict[str, str]) -> str:
    """板块 11.5：攻击面分析（LLM 生成）。"""
    content = llm_sections.get("attack_surface", "")
    if not content:
        return "> （攻击面分析未生成，请检查 LLM 输出）"
    # 清理标题
    content = re.sub(r'^##\s*(?:十 [、.]?\s*)?攻击面分析\s*\n', '', content, flags=re.MULTILINE)
    return content.strip()


def build_intelligence_judgment(llm_sections: Dict[str, str]) -> str:
    """板块 12：情报判断与后续关注（LLM 生成）。"""
    content = llm_sections.get("intelligence_judgment", "")
    if not content:
        return "> （情报判断未生成，请检查 LLM 输出）"
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


def build_evidence_appendix(scraped: Dict[str, str],
                            results: List[dict] = None) -> str:
    """板块 14：原始证据（程序化生成）。"""
    lines = ["## 十五、原始证据", ""]

    if not scraped and not results:
        lines.append("> 无可用证据材料")
        return "\n".join(lines)

    sources = []
    if scraped:
        for url in list(scraped.keys())[:30]:
            sources.append({"url": url, "title": "", "has_content": True})

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
    event_changes: Optional[dict] = None,
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

    # 2. 组装 14 板块
    sections = [
        # 程序化板块
        build_report_overview(query, search_mode, model, source_counts, result_count, report_id),
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
        build_risk_assessment(llm_sections),
        "",
        "---",
        "",
        "## 十二、攻击面分析",
        "",
        build_attack_surface(llm_sections),
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
