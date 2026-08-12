"""
AI简报分析生成器
===============
使用LLM分析搜索结果并生成《AI 与网络安全每日情报简报》内容（Markdown）。
"""

import os
from typing import Dict, List
from datetime import datetime

from intelnexus.briefing.config import WATCH_CATEGORIES, BRIEFING_CONFIG
from intelnexus.briefing.prompts import get_prompt
from intelnexus.briefing.templates import (
    render_markdown_briefing,
    format_news_item
)
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 中文星期（datetime.weekday(): 0=周一）
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def format_briefing_date() -> str:
    """生成中文星期日期，如「2026年7月7日（星期二）」"""
    now = datetime.now()
    return now.strftime("%Y年%m月%d日") + f"（星期{WEEKDAY_CN[now.weekday()]}）"

# 各板块对应的采集类目
AI_DYNAMIC_CATS = ["ai_gov_usage", "ai_china_narrative", "ai_legislation", "ai_data_leak"]
CYBER_DYNAMIC_CATS = ["cyber_vuln", "cyber_attack"]
CVE_CATS = ["cyber_vuln", "cyber_attack", "ai_data_leak"]

# 生成顺序与展示名称（供进度文案与警告使用）
GENERATION_SECTIONS = [
    ("top3", "_generate_top3"),
    ("delta", "_generate_delta"),
    ("ai_dynamic", "_generate_ai_dynamic"),
    ("cyber_dynamic", "_generate_cyber_dynamic"),
    ("cve_table", "_generate_cve_table"),
    ("insights", "_generate_insights"),
    ("links", "_generate_links"),
]
SECTION_LABELS = {
    "top3": "近日要闻 TOP3",
    "delta": "本期增量速览（对比上期）",
    "ai_dynamic": "AI 领域动态",
    "cyber_dynamic": "网络安全动态",
    "cve_table": "近日新增安全漏洞预警",
    "insights": "趋势研判与防护建议",
    "links": "重要链接",
}


class AIBriefingAnalyzer:
    """AI简报分析生成器"""

    def __init__(self, llm=None):
        """
        初始化分析器

        Args:
            llm: LLM模型实例（可选，如果不提供则尝试自动加载）
        """
        self._llm = llm
        self._warnings: List[str] = []

    def _get_llm(self):
        """获取LLM实例"""
        if self._llm is not None:
            return self._llm

        try:
            from intelnexus.core.llm.core import get_llm
            # 尝试使用默认模型
            self._llm = get_llm("qwen2.5:7b")
            return self._llm
        except Exception as e:
            logger.warning(f"Could not load LLM: {e}")
            return None

    def _format_date(self) -> str:
        """生成中文星期日期（实例方法，委托模块函数）"""
        return format_briefing_date()

    @staticmethod
    def _collect(cats: List[str], collected_data: Dict[str, List[Dict]]) -> List[Dict]:
        """合并若干类目的采集结果"""
        results = []
        for cat in cats:
            results.extend(collected_data.get(cat, []))
        return results

    def _add_warning(self, section: str, message: str) -> None:
        """记录一个板块级警告（用于结果统计面板）"""
        self._warnings.append(f"「{section}」{message}")

    def generate_briefing(
        self,
        collected_data: Dict[str, List[Dict]],
        organization_name: str = None,
        with_warnings: bool = False,
        on_progress=None
    ):
        """
        生成完整的简报

        Args:
            collected_data: 采集的数据，格式为 {category_id: [results]}
            organization_name: 组织名称（覆盖配置中的 name）
            with_warnings: 为 True 时返回 (markdown, warnings)，否则仅返回 markdown
            on_progress: 进度回调 (stage, message, percent)，由流水线驱动 UI

        Returns:
            str 或 (str, List[str])
        """
        on_progress = on_progress or (lambda *a, **k: None)
        self._warnings = []

        org = dict(BRIEFING_CONFIG["organization"])
        if organization_name is not None:
            org["name"] = organization_name

        generated_date = self._format_date()
        llm = self._get_llm()

        # 可信度概览（复用搜索的 SourceScorer / ConflictDetector，降级无 LLM 也能展示）
        on_progress("credibility_overview", "正在评估来源可信度...", 0.35)
        credibility_overview = self._build_credibility_overview(collected_data)

        # 本期实体关系图谱（复用搜索的 IntelligenceGraph，降级无数据则跳过）
        on_progress("knowledge_graph", "正在构建实体关系图谱...", 0.38)
        kg_path = self._build_knowledge_graph(collected_data)

        # 逐板块生成，并在每个板块前后上报进度
        contents: Dict[str, str] = {}
        total = len(GENERATION_SECTIONS)
        for idx, (key, method_name) in enumerate(GENERATION_SECTIONS):
            label = SECTION_LABELS[key]
            pct = 0.4 + 0.55 * (idx / total)
            on_progress("generate_progress", f"正在生成：{label}（{idx + 1}/{total}）", pct)
            contents[key] = getattr(self, method_name)(collected_data, llm)

        # 知识图谱链接追加到「重要链接」板块
        if kg_path:
            from intelnexus.ui.icons import icon
            contents["links"] = (contents.get("links", "") or "") + \
                f"\n\n• {icon('knowledge', 'sm', 'lavender')} 本期实体关系图谱：{kg_path}"

        # 可信度概览作为简报首个板块（拼接到 top3 之前，复用现有模板签名）
        top3_with_overview = credibility_overview + "\n\n---\n\n" + contents["top3"] \
            if credibility_overview else contents["top3"]

        # 渲染完整简报
        briefing = render_markdown_briefing(
            generated_date=generated_date,
            organization=org,
            top3_content=top3_with_overview,
            delta_content=contents.get("delta", ""),
            ai_dynamic_content=contents["ai_dynamic"],
            cyber_dynamic_content=contents["cyber_dynamic"],
            cve_table_content=contents["cve_table"],
            insights_content=contents["insights"],
            links_content=contents["links"]
        )

        if with_warnings:
            return briefing, self._warnings
        return briefing

    def _build_credibility_overview(self, collected_data: Dict[str, List[Dict]]) -> str:
        """基于采集结果生成「可信度概览」栏（复用 SourceScorer / ConflictDetector）。

        无抓取全文时，以 content/description 字段作为 scraped 近似输入。
        返回 Markdown 字符串；若无可评估数据返回空串。
        """
        # 汇总全部结果，构造 url->text 近似 scraped
        all_items = []
        for items in collected_data.values():
            all_items.extend(items)
        if not all_items:
            return ""

        scraped = {}
        for it in all_items:
            url = it.get("url") or it.get("link", "")
            text = it.get("content") or it.get("description", "")
            if url and text:
                scraped[url] = text

        try:
            from intelnexus.analysis.credibility import SourceScorer, ConflictDetector
            scorer = SourceScorer()
            scored = scorer.evaluate(
                [dict(r, **{"url": r.get("url") or r.get("link", "")}) for r in all_items],
                scraped
            )
            detector = ConflictDetector()
            conflicts = detector.detect(scored, scraped)
        except Exception as e:
            logger.warning(f"可信度概览评估失败，降级跳过: {e}")
            return ""

        scores = [r.get("credibility_score", 0.5) for r in scored]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.5
        high = sum(1 for s in scores if s >= 0.7)
        low = sum(1 for s in scores if s < 0.4)
        conflict_count = len(conflicts)

        level = "高" if avg >= 0.7 else ("中" if avg >= 0.4 else "低")
        lines = [
            "## 来源可信度概览",
            "",
            f"- **平均可信度**：{avg:.2f}（{level}）",
            f"- **高可信来源**：{high} 条 · **低可信来源**：{low} 条",
            f"- **跨源冲突提示**：{conflict_count} 处"
            if conflict_count else "- **跨源冲突提示**：未检测到明显冲突",
        ]
        if conflicts:
            lines.append("")
            lines.append("**冲突要点：**")
            for c in conflicts[:3]:
                lines.append(f"- {c.get('description', '')}（严重度 {c.get('severity', 0):.2f}）")
        lines.append("")
        lines.append("> 本栏由来源可信度评分自动生成，供研判参考。")
        return "\n".join(lines)

    def _generate_top3(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成近日要闻TOP3"""
        all_results = self._collect(list(collected_data.keys()), collected_data)

        if not all_results:
            self._add_warning("近日要闻 TOP3", "未采集到任何情报数据，该板块为空")
            return "本日暂无重要新闻。"

        if llm is None:
            self._add_warning("近日要闻 TOP3", "未加载 LLM，使用原始条目降级展示")
            top_items = all_results[:3]
            result = []
            for i, item in enumerate(top_items, 1):
                result.append(format_news_item(
                    title=item.get("title", "未知标题"),
                    content=item.get("description", item.get("content", ""))[:200],
                    source=item.get("source", "未知来源"),
                    date=item.get("published_at", datetime.now().strftime("%Y-%m-%d"))
                ).replace("\n", " "))
            return "\n".join(f"{i}. {r}" for i, r in enumerate(result, 1))

        try:
            search_summary = self._format_results_for_prompt(all_results[:20])
            prompt = get_prompt("top3", search_results=search_summary)

            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            system_prompt = "你是一位高级AI与网络安全情报分析师。请根据搜索结果提取最重要的3条新闻。"
            prompt_template = ChatPromptTemplate(
                [("system", system_prompt), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()

            result = chain.invoke({"prompt": prompt})
            return result if result.strip() else "本日暂无重要新闻。"
        except Exception as e:
            logger.error(f"Error generating TOP3: {e}")
            self._add_warning("近日要闻 TOP3", f"生成异常：{e}")
            return "简报生成过程中出现错误，请检查LLM配置。"

    def _generate_ai_dynamic(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成 AI 领域动态（模型与技术 / 应用与落地 / 产业与市场）"""
        results = self._collect(AI_DYNAMIC_CATS, collected_data)
        if not results:
            self._add_warning("AI 领域动态", "未采集到相关情报数据，使用降级内容")
            return self._fallback_subsections(
                ["模型与技术", "应用与落地", "产业与市场"], results, llm)

        if llm is None:
            self._add_warning("AI 领域动态", "未加载 LLM，使用降级内容")
            return self._fallback_subsections(
                ["模型与技术", "应用与落地", "产业与市场"], results, llm)

        return self._run_prompt("ai_dynamic", results, llm,
                                 "你是一位AI领域情报分析师，请生成'AI 领域动态'部分。",
                                 label="AI 领域动态")

    def _generate_cyber_dynamic(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成 网络安全动态（漏洞与威胁 / 攻击事件 / 政策与合规）"""
        results = self._collect(CYBER_DYNAMIC_CATS, collected_data)
        if not results:
            self._add_warning("网络安全动态", "未采集到相关情报数据，使用降级内容")
            return self._fallback_subsections(
                ["漏洞与威胁", "攻击事件", "政策与合规"], results, llm)

        if llm is None:
            self._add_warning("网络安全动态", "未加载 LLM，使用降级内容")
            return self._fallback_subsections(
                ["漏洞与威胁", "攻击事件", "政策与合规"], results, llm)

        return self._run_prompt("cyber_dynamic", results, llm,
                                 "你是一位网络安全情报分析师，请生成'网络安全动态'部分。",
                                 label="网络安全动态")

    def _generate_cve_table(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成近日新增安全漏洞预警（CVE 表格）"""
        results = self._collect(CVE_CATS, collected_data)
        header = "| CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施 |\n| --- | --- | --- | --- | --- | --- |"

        if not results:
            self._add_warning("近日新增安全漏洞预警", "未采集到漏洞相关情报，表格为空")
            return f"{header}\n| （暂无） | - | - | - | - | - |"

        if llm is None:
            self._add_warning("近日新增安全漏洞预警", "未加载 LLM，表格为空")
            return f"{header}\n| （暂无） | - | - | - | - | - |"

        try:
            search_summary = self._format_results_for_prompt(results[:15])
            prompt = get_prompt("cve_table", search_results=search_summary)

            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            system_prompt = "你是一位漏洞情报分析师，请提取近日新增高危漏洞并输出Markdown表格。"
            prompt_template = ChatPromptTemplate(
                [("system", system_prompt), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()

            result = chain.invoke({"prompt": prompt})
            result = result.strip()
            if not result:
                return f"{header}\n| （暂无） | - | - | - | - | - |"
            return result
        except Exception as e:
            logger.error(f"Error generating CVE table: {e}")
            self._add_warning("近日新增安全漏洞预警", f"生成异常：{e}")
            return f"{header}\n| （暂无） | - | - | - | - | - |"

    def _run_prompt(self, prompt_name: str, results: List[Dict], llm, system_desc: str, label: str = None) -> str:
        """通用：调用提示词生成板块内容"""
        label = label or prompt_name
        try:
            search_summary = self._format_results_for_prompt(results[:12])
            prompt = get_prompt(prompt_name, search_results=search_summary)

            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            prompt_template = ChatPromptTemplate(
                [("system", system_desc), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()

            result = chain.invoke({"prompt": prompt})
            return result if result.strip() else "本日暂无相关动态。"
        except Exception as e:
            logger.error(f"Error generating {prompt_name}: {e}")
            self._add_warning(label, f"生成异常：{e}")
            return "简报生成过程中出现错误。"

    def _fallback_subsections(self, subsections: List[str], results: List[Dict], llm) -> str:
        """无 LLM 时的降级：输出子板块结构并填入原始条目"""
        if not results:
            return "\n".join(f"### {s}\n本日暂无相关动态。" for s in subsections)

        chunks = [results[i::len(subsections)] for i in range(len(subsections))]
        blocks = []
        today = datetime.now().strftime("%Y-%m-%d")
        for sub, items in zip(subsections, chunks):
            lines = [f"### {sub}"]
            for item in items[:4]:
                lines.append(format_news_item(
                    title=item.get("title", "未知标题"),
                    content=item.get("description", item.get("content", ""))[:120],
                    source=item.get("source", "未知来源"),
                    date=item.get("published_at", today)
                ).replace("\n", " "))
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def _generate_insights(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成趋势研判与防护建议"""
        highlights = []
        for category, results in collected_data.items():
            cat_name = WATCH_CATEGORIES.get(category, {}).get("name", category)
            if results:
                highlights.append(f"{cat_name}: {len(results)}条信息")

        if not highlights:
            self._add_warning("趋势研判与防护建议", "数据不足，未能生成趋势研判")
            return "本日暂无足够数据生成趋势分析。"

        today_highlights = "\n".join(highlights)

        if llm is None:
            self._add_warning("趋势研判与防护建议", "未加载 LLM，使用默认趋势研判")
            return """1. **关注AI与网络安全动态**
   本日采集到若干公开信息，建议持续跟踪AI技术进展与网络安全威胁。

   **建议：** 保持对AI新技术的关注，及时评估潜在安全影响。

2. **加强安全防护**
   AI相关安全事件与漏洞披露频繁，需加强安全防护。

   **建议：** 定期检查系统安全性，及时更新防护措施。

3. **跟踪合规要求**
   各国AI与网络安全法规陆续出台，企业需关注合规。

   **建议：** 跟踪相关政策动态，确保业务合规。"""

        try:
            prompt = get_prompt("insight", today_highlights=today_highlights)

            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            system_prompt = "你是一位AI与网络安全风险分析师。请根据今日动态生成3条趋势研判与防护建议。"
            prompt_template = ChatPromptTemplate(
                [("system", system_prompt), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()

            result = chain.invoke({"prompt": prompt})
            return result if result.strip() else "趋势分析生成过程中出现错误。"
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            self._add_warning("趋势研判与防护建议", f"生成异常：{e}")
            return "趋势分析生成过程中出现错误。"

    def _generate_links(self, collected_data: Dict[str, List[Dict]], llm=None) -> str:
        """生成重要链接部分"""
        links = []
        seen_urls = set()

        for results in collected_data.values():
            for item in results[:3]:  # 每个类别最多3个链接
                url = item.get("url", "")
                title = item.get("title", "")[:50]
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    links.append(f"• {title}: {url}")

        if not links:
            return "暂无重要链接。"

        return "\n".join(links[:10])  # 最多10个链接

    def _generate_delta(self, collected_data: Dict[str, List[Dict]], llm=None) -> str:
        """生成增量感知：对比上一期简报，输出新增/消失条目。"""
        try:
            from intelnexus.topics.diff import compute_delta
            return compute_delta(collected_data)
        except Exception as e:
            logger.warning(f"增量感知生成失败，降级跳过: {e}")
            return "## 本期增量速览（对比上期）\n\n> 本期增量对比暂不可用。"

    def _build_knowledge_graph(self, collected_data: Dict[str, List[Dict]]) -> str:
        """生成本期实体关系图谱 HTML（复用搜索的 IntelligenceGraph）。

        以各条目的 content/description 作为近似全文输入；无可用数据或无
        spaCy/pyvis 环境时降级返回空串。
        """
        try:
            from intelnexus.analysis.intelligence_graph import (
                EntityExtractor, IntelligenceGraph
            )
            from datetime import datetime

            scraped = {}
            for items in collected_data.values():
                for it in items:
                    url = it.get("url") or it.get("link", "")
                    text = it.get("content") or it.get("description", "")
                    if url and text and len(text) >= 50:
                        scraped[url] = text
            if not scraped:
                return ""

            extractor = EntityExtractor()
            kg_raw = extractor.extract(scraped)
            if not kg_raw.get("entities"):
                return ""

            kg = IntelligenceGraph()
            kg.build(kg_raw["entities"], kg_raw["relations"])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join("data", "briefings", f"kg_{timestamp}.html")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            saved = kg.export_html(out_path)
            return saved or ""
        except Exception as e:
            logger.warning(f"知识图谱生成失败，降级跳过: {e}")
            return ""

    def _format_results_for_prompt(self, results: List[Dict]) -> str:
        """将搜索结果格式化为提示词可用的格式"""
        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("url", "No URL")
            source = r.get("source", "Unknown")
            date = r.get("published_at", "Unknown date")
            desc = r.get("description", r.get("content", ""))[:200]

            formatted.append(f"{i}. {title}")
            formatted.append(f"   URL: {url}")
            formatted.append(f"   Source: {source}")
            formatted.append(f"   Date: {date}")
            formatted.append(f"   Description: {desc}")
            formatted.append("")

        return "\n".join(formatted)
