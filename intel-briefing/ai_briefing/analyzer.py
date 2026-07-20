"""
AI简报分析生成器
===============
使用LLM分析搜索结果并生成《AI 与网络安全每日情报简报》内容（Markdown）。
"""

from typing import Dict, List
from datetime import datetime

from ai_briefing.config import WATCH_CATEGORIES, BRIEFING_CONFIG
from ai_briefing.prompts import get_prompt
from ai_briefing.templates import (
    render_markdown_briefing,
    format_news_item
)
from shared.logger import get_logger

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


class AIBriefingAnalyzer:
    """AI简报分析生成器"""

    def __init__(self, llm=None):
        """
        初始化分析器

        Args:
            llm: LLM模型实例（可选，如果不提供则尝试自动加载）
        """
        self._llm = llm

    def _get_llm(self):
        """获取LLM实例"""
        if self._llm is not None:
            return self._llm

        try:
            from shared.llm.core import get_llm
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

    def generate_briefing(
        self,
        collected_data: Dict[str, List[Dict]],
        organization_name: str = None
    ) -> str:
        """
        生成完整的简报

        Args:
            collected_data: 采集的数据，格式为 {category_id: [results]}
            organization_name: 组织名称（覆盖配置中的 name）

        Returns:
            str: Markdown格式的完整简报
        """
        org = dict(BRIEFING_CONFIG["organization"])
        if organization_name is not None:
            org["name"] = organization_name

        generated_date = self._format_date()
        llm = self._get_llm()

        # 生成各部分内容
        top3_content = self._generate_top3(collected_data, llm)
        ai_dynamic_content = self._generate_ai_dynamic(collected_data, llm)
        cyber_dynamic_content = self._generate_cyber_dynamic(collected_data, llm)
        cve_table_content = self._generate_cve_table(collected_data, llm)
        insights_content = self._generate_insights(collected_data, llm)
        links_content = self._generate_links(collected_data)

        # 渲染完整简报
        briefing = render_markdown_briefing(
            generated_date=generated_date,
            organization=org,
            top3_content=top3_content,
            ai_dynamic_content=ai_dynamic_content,
            cyber_dynamic_content=cyber_dynamic_content,
            cve_table_content=cve_table_content,
            insights_content=insights_content,
            links_content=links_content
        )

        return briefing

    def _generate_top3(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成近日要闻TOP3"""
        all_results = self._collect(list(collected_data.keys()), collected_data)

        if not all_results:
            return "本日暂无重要新闻。"

        if llm is None:
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
            return "简报生成过程中出现错误，请检查LLM配置。"

    def _generate_ai_dynamic(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成 AI 领域动态（模型与技术 / 应用与落地 / 产业与市场）"""
        results = self._collect(AI_DYNAMIC_CATS, collected_data)
        if not results:
            return self._fallback_subsections(
                ["模型与技术", "应用与落地", "产业与市场"], results, llm)

        if llm is None:
            return self._fallback_subsections(
                ["模型与技术", "应用与落地", "产业与市场"], results, llm)

        return self._run_prompt("ai_dynamic", results, llm,
                                 "你是一位AI领域情报分析师，请生成'AI 领域动态'部分。")

    def _generate_cyber_dynamic(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成 网络安全动态（漏洞与威胁 / 攻击事件 / 政策与合规）"""
        results = self._collect(CYBER_DYNAMIC_CATS, collected_data)
        if not results:
            return self._fallback_subsections(
                ["漏洞与威胁", "攻击事件", "政策与合规"], results, llm)

        if llm is None:
            return self._fallback_subsections(
                ["漏洞与威胁", "攻击事件", "政策与合规"], results, llm)

        return self._run_prompt("cyber_dynamic", results, llm,
                                 "你是一位网络安全情报分析师，请生成'网络安全动态'部分。")

    def _generate_cve_table(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成近日新增安全漏洞预警（CVE 表格）"""
        results = self._collect(CVE_CATS, collected_data)
        header = "| CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施 |\n| --- | --- | --- | --- | --- | --- |"

        if not results or llm is None:
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
            return f"{header}\n| （暂无） | - | - | - | - | - |"

    def _run_prompt(self, prompt_name: str, results: List[Dict], llm, system_desc: str) -> str:
        """通用：调用提示词生成板块内容"""
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
            return "本日暂无足够数据生成趋势分析。"

        today_highlights = "\n".join(highlights)

        if llm is None:
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
            return "趋势分析生成过程中出现错误。"

    def _generate_links(self, collected_data: Dict[str, List[Dict]]) -> str:
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
