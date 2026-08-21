"""
AI简报分析生成器
===============
使用LLM分析搜索结果并生成《AI 与网络安全每日情报简报》内容（Markdown）。
"""

import os
from typing import Dict, List
from datetime import datetime, timedelta

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


def format_briefing_date(date_format: str = None) -> str:
    """生成格式化日期字符串，支持从配置读取date_format"""
    from .config import BRIEFING_CONFIG
    now = datetime.now()
    if date_format is None:
        date_format = BRIEFING_CONFIG["format"]["date_format"]
    weekday_cn = f"（星期{WEEKDAY_CN[now.weekday()]}）"
    return now.strftime(date_format) + weekday_cn

# 各板块对应的采集类目
AI_DYNAMIC_CATS = ["ai_gov_usage", "ai_china_narrative", "ai_legislation", "ai_data_leak"]
CYBER_DYNAMIC_CATS = ["cyber_vuln", "cyber_attack"]
CVE_CATS = ["cyber_vuln", "cyber_attack", "ai_data_leak"]
POLICY_CATS = ["ai_legislation", "cyber_attack"]
ATTACK_CATS = ["cyber_attack", "ai_data_leak"]
PROTECTION_CATS = ["cyber_vuln", "cyber_attack", "ai_data_leak"]

# 生成顺序与展示名称（供进度文案与警告使用）
GENERATION_SECTIONS = [
    ("top3", "_generate_top3"),
    ("delta", "_generate_delta"),
    ("ai_dynamic", "_generate_ai_dynamic"),
    ("cyber_dynamic", "_generate_cyber_dynamic"),
    ("cve_table", "_generate_cve_table"),
    ("policy", "_generate_policy"),
    ("attack_analysis", "_generate_attack_analysis"),
    ("protection", "_generate_protection"),
    ("insights", "_generate_insights"),
    ("links", "_generate_links"),
]
SECTION_LABELS = {
    "top3": "近日要闻 TOP3",
    "delta": "本期增量速览（对比上期）",
    "ai_dynamic": "AI 领域动态",
    "cyber_dynamic": "网络安全动态",
    "cve_table": "近日新增安全漏洞预警",
    "policy": "政策法规动态",
    "attack_analysis": "攻击事件深度分析",
    "protection": "防护建议与厂商方案",
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
        self._kb_context: str = ""

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
    def _clean_url(url: str) -> str:
        """清洗 URL：去除 Yahoo 跟踪参数等垃圾参数"""
        if not url:
            return url
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        # 移除常见跟踪/转发参数
        garbage_keys = {"src", "utm_source", "utm_medium", "utm_campaign",
                        "utm_content", "utm_term", "tcid", "ncid",
                        "feature", "ref", "share"}
        cleaned = {k: v for k, v in params.items()
                   if k.lower() not in garbage_keys}
        if len(cleaned) == len(params):
            return url  # 无变化，直接返回
        new_query = urlencode(cleaned, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    @staticmethod
    def _collect(cats: List[str], collected_data: Dict[str, List[Dict]],
                 max_days: int = None) -> List[Dict]:
        """合并若干类目的采集结果，丢弃超过 max_days 天的旧内容"""
        from .config import BRIEFING_CONFIG
        if max_days is None:
            max_days = BRIEFING_CONFIG["search"]["time_window_days"]
        results = []
        cutoff = datetime.now() - timedelta(days=max_days)
        for cat in cats:
            for item in collected_data.get(cat, []):
                pub_str = item.get("published_at", "")
                if pub_str:
                    try:
                        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00").replace("+00:00", ""))
                        if pub_dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass  # 日期解析失败时保留条目
                results.append(item)
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

        # 关联历史收藏：检索知识库中与本期内容相关的条目，注入各板块 prompt
        on_progress("kb_recall", "正在关联历史收藏...", 0.39)
        self._kb_context = self._build_kb_recall_context(collected_data)

        # 逐板块生成，并在每个板块前后上报进度
        contents: Dict[str, str] = {}
        total = len(GENERATION_SECTIONS)
        top3_cve_ids = set()  # TOP3 中已覆盖的 CVE 编号
        for idx, (key, method_name) in enumerate(GENERATION_SECTIONS):
            label = SECTION_LABELS[key]
            pct = 0.4 + 0.55 * (idx / total)
            on_progress("generate_progress", f"正在生成：{label}（{idx + 1}/{total}）", pct)
            if key == "cve_table":
                contents[key] = getattr(self, method_name)(collected_data, llm,
                                                          skip_cve_ids=top3_cve_ids)
            else:
                contents[key] = getattr(self, method_name)(collected_data, llm)
            # TOP3 生成后提取其中的 CVE 编号，供后续 CVE 表格去重
            if key == "top3":
                import re
                top3_cve_ids = set(re.findall(r'CVE-\d{4}-\d+', contents["top3"]))

        # 知识图谱链接追加到「重要链接」板块
        if kg_path:
            contents["links"] = (contents.get("links", "") or "") + \
                f"\n\n• [图谱] 本期实体关系图谱：{kg_path}"

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
            policy_content=contents.get("policy", ""),
            attack_analysis_content=contents.get("attack_analysis", ""),
            protection_content=contents.get("protection", ""),
            insights_content=contents["insights"],
            links_content=contents["links"]
        )

        if with_warnings:
            return briefing, self._warnings
        return briefing

    def _build_kb_recall_context(self, collected_data: Dict[str, List[Dict]]) -> str:
        """检索知识库中与本期采集内容相关的历史收藏，生成注入 prompt 的上下文。

        以本期条目标题聚合作为检索 query；知识库为空、编码模型
        不可用或检索异常时返回空串，简报生成行为与原来一致。
        """
        try:
            from intelnexus.knowledge.retrieval import retrieve_relevant, build_kb_context

            titles = []
            for items in collected_data.values():
                for it in items:
                    t = (it.get("title") or "").strip()
                    if t:
                        titles.append(t)
            if not titles:
                return ""

            query = " ".join(titles[:30])[:1000]
            hits = retrieve_relevant(query, top_k=8)
            if hits:
                logger.info("简报关联历史收藏：命中 %d 条知识库条目", len(hits))
            return build_kb_context(hits)
        except Exception as e:
            logger.warning(f"知识库历史收藏关联失败，降级跳过: {e}")
            return ""

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
            prompt = get_prompt("top3", search_results=search_summary,
                                kb_context=self._kb_context)

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

    def _generate_cve_table(self, collected_data: Dict[str, List[Dict]], llm,
                            skip_cve_ids: set = None) -> str:
        """生成近日新增安全漏洞预警（CVE 表格），直接使用结构化数据。
        skip_cve_ids: TOP3 中已覆盖的 CVE 编号，跳过不重复展示。"""
        if skip_cve_ids is None:
            skip_cve_ids = set()
        results = self._collect(CVE_CATS, collected_data)
        header = "| CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施 |\n| --- | --- | --- | --- | --- | --- |"

        # 从 NVD / CISA KEV 获取结构化数据
        nvd_data = []
        kev_data = []
        try:
            from intelnexus.core.search.sources.nvd_source import NVDSearchSource
            from intelnexus.core.search.sources.cisa_kev_source import CISAKEVSource
            nvd = NVDSearchSource()
            kev = CISAKEVSource()
            nvd_results = nvd.search_recent_critical(days=7, max_results=10)
            kev_results = kev.search("vulnerability", max_results=10)

            # 提取 NVD 结构化数据
            for r in nvd_results:
                metadata = r.get("metadata", {})
                if metadata.get("cve_id"):
                    nvd_data.append({
                        "cve_id": metadata.get("cve_id", ""),
                        "cvss_score": metadata.get("cvss_score", ""),
                        "affected_products": metadata.get("affected_products", []),
                        "vuln_types": metadata.get("vuln_types", []),
                        "description": r.get("description", "")[:200],
                        "url": r.get("url", ""),
                    })

            # 提取 CISA KEV 结构化数据
            for r in kev_results:
                metadata = r.get("metadata", {})
                if metadata.get("cve_id"):
                    kev_data.append({
                        "cve_id": metadata.get("cve_id", ""),
                        "vendor": metadata.get("vendor", ""),
                        "product": metadata.get("product", ""),
                        "due_date": metadata.get("due_date", ""),
                        "required_action": metadata.get("required_action", ""),
                        "description": r.get("description", "")[:200],
                        "url": r.get("url", ""),
                    })
        except Exception as e:
            logger.warning(f"NVD/KEV API 数据拉取失败: {e}")

        # 合并数据，优先使用 KEV 数据（在野利用更紧急）
        all_cves = {}
        for item in nvd_data:
            cve_id = item["cve_id"]
            all_cves[cve_id] = item

        for item in kev_data:
            cve_id = item["cve_id"]
            if cve_id in all_cves:
                # 合并 KEV 信息
                all_cves[cve_id]["in_kev"] = True
                all_cves[cve_id]["due_date"] = item.get("due_date", "")
                all_cves[cve_id]["required_action"] = item.get("required_action", "")
                all_cves[cve_id]["vendor"] = item.get("vendor", "")
                all_cves[cve_id]["product"] = item.get("product", "")
            else:
                all_cves[cve_id] = item
                all_cves[cve_id]["in_kev"] = True

        if not all_cves:
            self._add_warning("近日新增安全漏洞预警", "未采集到漏洞相关情报，表格为空")
            return f"{header}\n| （暂无） | - | - | - | - | - |"

        # 生成表格行（跳过 TOP3 中已覆盖的 CVE）
        rows = []
        for cve_id, data in list(all_cves.items()):
            if cve_id in skip_cve_ids:
                continue  # TOP3 已详细分析，跳过避免重复
            if len(rows) >= 10:
                break
            # 影响产品
            products = data.get("affected_products", [])
            if not products and data.get("product"):
                products = [data["product"]]
            product_str = ", ".join(products[:3]) if products else "未知"

            # 漏洞类型
            vuln_types = data.get("vuln_types", [])
            vuln_type_str = ", ".join(vuln_types[:2]) if vuln_types else "未知"

            # CVSS 评分
            cvss = data.get("cvss_score", "")
            if not cvss:
                cvss = "未知"

            # 利用状态
            in_kev = data.get("in_kev", False)
            exploit_status = "在野利用" if in_kev else "暂无在野利用"

            # 建议措施
            if in_kev:
                action = data.get("required_action", "")
                if action:
                    suggestion = action if len(action) <= 50 else action[:47] + "…"
                else:
                    suggestion = "立即升级至安全版本"
            else:
                suggestion = "升级至安全版本"

            rows.append(f"| {cve_id} | {product_str} | {vuln_type_str} | {cvss} | {exploit_status} | {suggestion} |")

        if not rows:
            return f"{header}\n| （暂无） | - | - | - | - | - |"

        return header + "\n" + "\n".join(rows)

    def _generate_policy(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成政策法规动态（国内政策 / 国际法规 / 行业标准）"""
        results = self._collect(POLICY_CATS, collected_data)
        if not results:
            self._add_warning("政策法规动态", "未采集到相关情报数据，使用降级内容")
            return "本日暂无相关动态。"

        if llm is None:
            self._add_warning("政策法规动态", "未加载 LLM，使用降级内容")
            return self._fallback_subsections(
                ["国内政策", "国际法规", "行业标准"], results, llm)

        return self._run_prompt("policy", results, llm,
                                 "你是一位政策法规分析师，请生成'政策法规动态'部分。",
                                 label="政策法规动态")

    def _generate_attack_analysis(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成攻击事件深度分析"""
        results = self._collect(ATTACK_CATS, collected_data)
        if not results:
            self._add_warning("攻击事件深度分析", "未采集到相关情报数据")
            return "本日暂无重大安全事件需要深度分析。"

        if llm is None:
            self._add_warning("攻击事件深度分析", "未加载 LLM，使用降级内容")
            return "本日暂无重大安全事件需要深度分析。"

        return self._run_prompt("attack_analysis", results, llm,
                                 "你是一位网络安全事件分析师，请生成'攻击事件深度分析'部分。",
                                 label="攻击事件深度分析")

    def _generate_protection(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成防护建议与厂商方案"""
        results = self._collect(PROTECTION_CATS, collected_data)
        if not results:
            self._add_warning("防护建议与厂商方案", "未采集到相关情报数据")
            return "本日暂无相关动态。"

        if llm is None:
            self._add_warning("防护建议与厂商方案", "未加载 LLM，使用降级内容")
            return self._fallback_subsections(
                ["通用防护建议", "厂商解决方案"], results, llm)

        return self._run_prompt("protection", results, llm,
                                 "你是一位网络安全防护专家，请生成'防护建议与厂商方案'部分。",
                                 label="防护建议与厂商方案")

    def _validate_llm_output(self, result: str, prompt_name: str) -> bool:
        """校验LLM输出是否有效，避免模板占位符或垃圾内容"""
        if not result or not result.strip():
            return False

        result = result.strip()

        # 检测模板占位符（提示词中的示例格式）
        template_patterns = [
            "事件概述（2-3句话说明发生了什么）",
            "影响分析或技术细节（1-2句话阐述意义或影响范围）",
            "新闻标题",
            "影响范围：",
            "紧急程度：",
            "用2-3句话概括事件背景",
            "具体描述攻击入口",
            "具体描述执行的恶意操作",
            "具体描述如何维持权限",
            "具体描述内网扩散方式",
            "具体描述最终造成的影响",
            "具体区域/规模",
            "具体行业",
            "具体损失类型和规模",
            "具体可执行的操作",
            "具体改进方案",
            "具体加固建议",
            "用搜索结果中的真实事件名称替换",
            "真实日期",
            "真实事件节点",
        ]
        for pattern in template_patterns:
            if pattern in result:
                logger.warning(f"LLM输出包含模板占位符，判定无效: {pattern}")
                return False

        # 检测英文标签泄漏（搜索结果格式被LLM复制）
        english_label_patterns = [
            r"(?m)^\s*URL:\s*http",
            r"(?m)^\s*Source:\s*\w",
            r"(?m)^\s*Date:\s*\d",
            r"(?m)^\s*Description:\s*\w",
            r"(?m)^No title",
            r"(?m)^No URL",
        ]
        for pattern in english_label_patterns:
            if re.search(pattern, result):
                logger.warning(f"LLM输出包含英文标签泄漏，判定无效: {pattern}")
                return False

        # 检测Markdown代码块
        if re.search(r"```[\s\S]*?```", result):
            logger.warning("LLM输出包含Markdown代码块，判定无效")
            return False

        # 检测JSON/代码结构（大括号包裹的类JSON内容）
        if re.search(r"^\s*\{[\s\S]{20,}\}\s*$", result, re.MULTILINE):
            logger.warning("LLM输出包含JSON结构，判定无效")
            return False

        # 检测连续纯英文段落（超过3行，排除CVE编号等必要英文）
        lines_for_english = result.split("\n")
        english_streak = 0
        for line in lines_for_english:
            stripped = line.strip()
            if not stripped or re.search(r"CVE-\d{4}-\d+", stripped):
                english_streak = 0
                continue
            # 判断是否为纯英文（排除中文字符、数字、标点）
            if re.match(r"^[a-zA-Z0-9\s\.\,\;\:\-\(\)\[\]\/\\\@\#\$\%\^\&\*\+\=\_\~\`\|\{\}\<\>\?\!]+$", stripped):
                english_streak += 1
                if english_streak >= 3:
                    logger.warning("LLM输出包含连续纯英文段落，判定无效")
                    return False
            else:
                english_streak = 0

        # 检测占位符CVE
        import re
        if re.search(r"CVE-\d{4}-XXXX", result):
            logger.warning("LLM输出包含占位符CVE，判定无效")
            return False

        # 检测重复内容（防止LLM输出循环）
        lines = [l.strip() for l in result.split("\n") if l.strip() and len(l.strip()) > 20]
        if len(lines) > 10:
            from collections import Counter
            line_counter = Counter(lines)
            most_common_count = line_counter.most_common(1)[0][1]
            if most_common_count > 3:
                logger.warning(f"LLM输出包含重复行出现{most_common_count}次，截断处理")
                # 截断到首次重复位置
                seen = set()
                truncated = []
                for line in lines:
                    if line in seen:
                        break
                    seen.add(line)
                    truncated.append(line)
                result = "\n".join(truncated)

        # 根据板块类型做特定校验
        if prompt_name == "top3":
            # TOP3 应至少包含3个加粗标题
            bold_matches = re.findall(r"\*\*(.+?)\*\*", result)
            if len(bold_matches) < 3:
                logger.warning(f"TOP3输出加粗标题不足3个: {len(bold_matches)}")
                return False

        elif prompt_name == "cve_table":
            # CVE表格应至少包含1行CVE数据
            cve_matches = re.findall(r"CVE-\d{4}-\d+", result)
            if len(cve_matches) < 1:
                logger.warning(f"CVE表格输出无有效CVE数据")
                return False

        elif prompt_name in ["ai_dynamic", "cyber_dynamic"]:
            # AI/网络安全动态应包含子标题
            if "###" not in result:
                logger.warning(f"{prompt_name}输出无子标题结构")
                return False

        # 检查输出是否过短
        if len(result) < 80:
            logger.warning(f"LLM输出过短({len(result)}字符)，判定无效")
            return False

        return True

    def _clean_llm_output(self, result: str) -> str:
        """后处理清洗LLM输出，移除英文标签、代码块等残留痕迹"""
        import re
        lines = result.split("\n")
        cleaned = []
        skip_code_block = False

        for line in lines:
            stripped = line.strip()

            # 跳过Markdown代码块
            if stripped.startswith("```"):
                skip_code_block = not skip_code_block
                continue
            if skip_code_block:
                continue

            # 移除英文标签行
            if re.match(r"^(URL|Source|Date|Description|Link):\s*", stripped, re.IGNORECASE):
                continue
            if re.match(r"^(链接|来源|日期|摘要)：", stripped):
                # 保留中文标签行（正常内容）
                pass

            # 移除模板占位符行
            if re.search(r"\[.*(?:具体|真实|替换|描述).*\]", stripped):
                continue

            # 移除纯数字行（可能是序号错误）
            if stripped and re.match(r"^\d+$", stripped):
                continue

            cleaned.append(line)

        # 移除连续空行（保留最多1个）
        final = []
        prev_empty = False
        for line in cleaned:
            if not line.strip():
                if not prev_empty:
                    final.append(line)
                prev_empty = True
            else:
                final.append(line)
                prev_empty = False

        return "\n".join(final).strip()

    def _run_prompt(self, prompt_name: str, results: List[Dict], llm, system_desc: str, label: str = None) -> str:
        """通用：调用提示词生成板块内容"""
        label = label or prompt_name
        try:
            search_summary = self._format_results_for_prompt(results[:12])
            prompt = get_prompt(prompt_name, search_results=search_summary,
                                kb_context=self._kb_context)

            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            prompt_template = ChatPromptTemplate(
                [("system", system_desc), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()

            result = chain.invoke({"prompt": prompt})

            # 校验LLM输出
            if not self._validate_llm_output(result, prompt_name):
                logger.warning(f"{label}: LLM输出校验失败，回退到降级模式")
                self._add_warning(label, "LLM输出校验失败，使用降级内容")
                # 根据板块类型回退到降级模式
                if prompt_name == "top3":
                    return "本日暂无重大要闻。"
                elif prompt_name == "cve_table":
                    return "| CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施 |\n| --- | --- | --- | --- | --- | --- |\n| （暂无） | - | - | - | - | - |"
                elif prompt_name == "ai_dynamic":
                    return self._fallback_subsections(
                        ["模型与技术", "应用与落地", "产业与市场"], results, llm)
                elif prompt_name == "cyber_dynamic":
                    return self._fallback_subsections(
                        ["漏洞与威胁", "攻击事件"], results, llm)
                elif prompt_name == "policy":
                    return self._fallback_subsections(
                        ["国内政策", "国际法规", "行业标准"], results, llm)
                elif prompt_name == "attack_analysis":
                    return "本日暂无重大安全事件需要深度分析。"
                elif prompt_name == "protection":
                    return self._fallback_subsections(
                        ["通用防护建议", "厂商解决方案"], results, llm)
                else:
                    return "本日暂无相关动态。"

            # 后处理清洗
            result = self._clean_llm_output(result)
            return result
        except Exception as e:
            logger.error(f"Error generating {prompt_name}: {e}")
            self._add_warning(label, f"生成异常：{e}")
            return "简报生成过程中出现错误。"

    def _fallback_subsections(self, subsections: List[str], results: List[Dict], llm) -> str:
        """无 LLM 时的降级：输出子板块结构并填入原始条目（增强版）"""
        if not results:
            return "\n".join(f"### {s}\n本日暂无相关动态。" for s in subsections)

        chunks = [results[i::len(subsections)] for i in range(len(subsections))]
        blocks = []
        today = datetime.now().strftime("%Y-%m-%d")
        for sub, items in zip(subsections, chunks):
            lines = [f"### {sub}"]
            for item in items[:4]:
                metadata = item.get("metadata", {})
                title = item.get("title", "未知标题")
                description = item.get("description", "")[:120]
                source = item.get("source", "未知来源")
                date = item.get("published_at", today)

                # 增强降级展示：提取结构化字段
                extra_info = []
                if metadata.get("cve_id"):
                    extra_info.append(f"**CVE**: {metadata['cve_id']}")
                if metadata.get("cvss_score"):
                    extra_info.append(f"**CVSS**: {metadata['cvss_score']}")
                if metadata.get("threat_type"):
                    extra_info.append(f"**类型**: {metadata['threat_type']}")
                if metadata.get("author"):
                    extra_info.append(f"**作者**: {metadata['author']}")
                if metadata.get("tags"):
                    tags = metadata["tags"][:3]
                    extra_info.append(f"**标签**: {', '.join(tags)}")

                # 构建条目
                entry = f"• **{title}**"
                if description:
                    entry += f"\n  {description}"
                if extra_info:
                    entry += "\n  " + " | ".join(extra_info)
                entry += f"\n  （来源：{source} / {date}）"
                lines.append(entry)
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
            prompt = get_prompt("insight", today_highlights=today_highlights,
                                kb_context=self._kb_context)

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
                url = self._clean_url(item.get("url", ""))
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
            delta_content = compute_delta(collected_data)
            # 移除板块标题（由模板负责渲染）
            if delta_content.startswith("## 本期增量速览"):
                lines = delta_content.split("\n")
                # 跳过标题行和空行
                start_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith("##"):
                        start_idx = i + 1
                        # 跳过标题后的空行
                        while start_idx < len(lines) and not lines[start_idx].strip():
                            start_idx += 1
                        break
                return "\n".join(lines[start_idx:]) if start_idx < len(lines) else ""
            return delta_content
        except Exception as e:
            logger.warning(f"增量感知生成失败，降级跳过: {e}")
            return ""

    def _build_knowledge_graph(self, collected_data: Dict[str, List[Dict]]) -> str:
        """生成本期实体关系图谱 HTML（复用搜索的 IntelligenceGraph）。

        以各条目的 content/description 作为近似全文输入；无可用数据或无
        spaCy/pyvis 环境时降级返回空串。
        """
        try:
            from intelnexus.analysis.intelligence_graph import (
                EntityExtractor, IntelligenceGraph
            )
            from datetime import datetime, timedelta

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
            title = r.get("title", "无标题")
            url = r.get("url", "")
            source = r.get("source", "未知来源")
            date = r.get("published_at", "未知日期")
            desc = r.get("description", r.get("content", ""))[:200]

            formatted.append(f"{i}. {title}")
            if url:
                formatted.append(f"   链接：{url}")
            formatted.append(f"   来源：{source}")
            formatted.append(f"   日期：{date}")
            formatted.append(f"   摘要：{desc}")
            formatted.append("")

        return "\n".join(formatted)
