"""
AI简报分析生成器
===============
使用LLM分析搜索结果并生成《AI 与网络安全每日情报简报》内容（Markdown）。
"""

import os
import re
from typing import Dict, List, Optional
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

# TOP3 主题相关性关键词（AI 与网络安全）
_AI_SECURITY_KEYWORDS = frozenset([
    'ai', 'artificial intelligence', 'machine learning', 'llm', 'gpt', 'deepseek',
    'chatgpt', 'openai', 'anthropic', 'gemini', 'copilot', 'claude',
    'cyber', 'security', 'breach', 'vulnerability', 'cve', 'ransomware', 'malware',
    'hack', 'attack', 'exploit', 'zero-day', '0day', 'phishing', 'data leak',
    'backdoor', 'apt', 'botnet', 'ddos', 'encryption', 'firewall',
    '人工智能', '安全', '漏洞', '泄露', '勒索', '攻击', '入侵', '后门',
    '补丁', '防火墙', '加密', '钓鱼', '挖矿', '木马', '病毒',
    '数据泄露', '网络安全', '信息安全', '隐私', '合规', '监管',
    '模型', '训练', '推理', '算力', '芯片', 'gpu', 'nvidia',
    'patch', 'credential', 'oauth', 'token', 'auth', 'permission',
])


def _topic_relevance(title: str, description: str = "") -> float:
    """计算条目与 AI/安全主题的相关性 (0-1)"""
    text = f"{title} {description}".lower()
    matches = sum(1 for kw in _AI_SECURITY_KEYWORDS if kw in text)
    return min(matches / 5, 1.0)


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
        """获取LLM实例；未显式注入时返回 None（走可感知的降级路径）。

        模型解析不属于本类：定时链路由 scheduler._resolve_llm 显式解析并
        注入（状态上报注册表供横幅展示）；手动链路由 UI/CLI 显式传模型。
        这里不再做任何自动探测——那会引入隐藏的网络探测与静默的质量
        切换，且让无 LLM 的降级行为不可预期。
        """
        if self._llm is None:
            logger.info("AIBriefingAnalyzer running without LLM (degraded template mode)")
        return self._llm

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
    def _parse_published_at(pub_str: str) -> Optional[datetime]:
        """尽力解析条目发布时间；失败返回 None。

        旧实现只走 datetime.fromisoformat——RFC822（Mon, 17 Jun 2026 …）、
        「Aug 13, 2026」等搜索引擎常见格式全部解析失败后被无条件放行，
        数月前的旧闻得以「本日动态」身份混入简报。
        """
        if not pub_str:
            return None
        d = pub_str.strip()
        # ISO（容忍 Z / +00:00 后缀）
        try:
            return datetime.fromisoformat(d.replace("Z", "").replace("+00:00", ""))
        except (ValueError, TypeError):
            pass
        # Mon, 17 Jun 2026 02:21:00 GMT
        m = re.match(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+(\d{1,2})\s+(\w{3})\s+(\d{4})', d)
        if m:
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
            except ValueError:
                pass
        # Aug 13,2026 / Aug 13, 2026
        m = re.match(r'(\w{3})\s+(\d{1,2}),?\s*(\d{4})', d)
        if m:
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y")
            except ValueError:
                pass
        # 2026年8月13日
        m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', d)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        # 前缀式 YYYY-MM-DD（后跟杂讯）
        m = re.match(r'(\d{4}-\d{1,2}-\d{1,2})', d)
        if m:
            try:
                return datetime.fromisoformat(m.group(1))
            except ValueError:
                pass
        return None

    def _collect(self, cats: List[str], collected_data: Dict[str, List[Dict]],
                 max_days: int = None) -> List[Dict]:
        """合并若干类目的采集结果，丢弃超过 max_days 天的旧内容。

        时间窗策略：发布时间可解析且早于窗口 → 丢弃；无日期或无法解析
        （收藏草稿、自定义抓取等合法场景）→ 保留。
        """
        from .config import BRIEFING_CONFIG
        if max_days is None:
            max_days = BRIEFING_CONFIG["search"]["time_window_days"]
        results = []
        cutoff = datetime.now() - timedelta(days=max_days)
        for cat in cats:
            for item in collected_data.get(cat, []):
                pub_dt = self._parse_published_at(item.get("published_at", ""))
                if pub_dt is not None and pub_dt < cutoff:
                    continue
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
                top3_cve_ids = set(re.findall(r'CVE-\d{4}-\d+', contents["top3"]))

        # 知识图谱链接追加到「重要链接」板块（绝对路径：外发/邮件场景下
        # 相对路径 data\briefings\… 无法打开）
        if kg_path:
            kg_display = os.path.abspath(kg_path)
            contents["links"] = (contents.get("links", "") or "") + \
                f"\n\n• [图谱] 本期实体关系图谱：{kg_display}"

        # 生成执行摘要（今日要点）
        on_progress("summary", "正在生成执行摘要...", 0.92)
        summary_content = self._generate_summary(contents, collected_data)

        # 可信度概览作为简报首个板块（拼接到 top3 之前，复用现有模板签名）
        top3_with_overview = credibility_overview + "\n\n---\n\n" + contents["top3"] \
            if credibility_overview else contents["top3"]

        # 渲染完整简报
        briefing = render_markdown_briefing(
            generated_date=generated_date,
            organization=org,
            summary_content=summary_content,
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

        # 按来源聚合分数（同一来源取最高分）
        source_scores = {}
        for r in scored:
            source = r.get("source", "Unknown")
            score = r.get("credibility_score", 0.5)
            if source not in source_scores or score > source_scores[source]:
                source_scores[source] = score

        scores = list(source_scores.values())
        avg = round(sum(scores) / len(scores), 2) if scores else 0.5
        high = sum(1 for s in scores if s >= 0.7)
        low = sum(1 for s in scores if s < 0.4)
        conflict_count = len(conflicts)

        level = "高" if avg >= 0.7 else ("中" if avg >= 0.4 else "低")
        lines = [
            "## 来源可信度概览",
            "",
            f"- **平均可信度**：{avg:.2f}（{level}）",
            f"- **高可信来源**：{high} 个 · **低可信来源**：{low} 个（共 {len(source_scores)} 个独立来源）",
            f"- **跨源冲突提示**：{conflict_count} 处"
            if conflict_count else "- **跨源冲突提示**：未检测到明显冲突",
        ]
        if conflicts:
            # 去重后最多展示 2 条：ConflictDetector 对同类数值差异会产出
            # 多条一字不差的模板描述（实锤：同一句「million级别」重复 3 次、
            # 严重度全是 0.99），原样罗列只是噪声。
            seen_descs = set()
            unique_conflicts = []
            for c in conflicts:
                desc = (c.get("description") or "").strip()
                if desc and desc not in seen_descs:
                    seen_descs.add(desc)
                    unique_conflicts.append(c)
            if unique_conflicts:
                lines.append("")
                lines.append("**冲突要点：**")
                for c in unique_conflicts[:2]:
                    lines.append(f"- {c.get('description', '')}（严重度 {c.get('severity', 0):.1f}）")
        lines.append("")
        lines.append("> 本栏基于采集来源的域名权威性、时效性与内容深度自动评分，供研判参考。")
        return "\n".join(lines)

    def _generate_top3(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成近日要闻TOP3"""
        all_results = self._collect(list(collected_data.keys()), collected_data)

        if not all_results:
            self._add_warning("近日要闻 TOP3", "未采集到任何情报数据，该板块为空")
            return "本日暂无重要新闻。"

        if llm is None:
            self._add_warning("近日要闻 TOP3", "未加载 LLM，使用原始条目降级展示")
            return self._generate_top3_fallback(all_results)

        try:
            # 生成可信度摘要，注入提示词
            credibility_summary = self._build_credibility_summary(all_results)
            search_summary = self._format_results_for_prompt(
                all_results[:BRIEFING_CONFIG["search"].get("max_results_for_top3", 20)]
            )
            prompt = get_prompt(
                "top3",
                search_results=search_summary,
                credibility_summary=credibility_summary,
                kb_context=self._kb_context
            )

            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            system_prompt = "你是一位高级AI与网络安全情报分析师。请根据搜索结果提取最重要的3条新闻。"
            prompt_template = ChatPromptTemplate(
                [("system", system_prompt), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()

            result = chain.invoke({"prompt": prompt})
            if result.strip():
                return result

            # LLM返回空结果，使用降级方案
            self._add_warning("近日要闻 TOP3", "LLM返回空结果，使用降级方案")
            return self._generate_top3_fallback(all_results)

        except Exception as e:
            logger.error(f"Error generating TOP3: {e}")
            self._add_warning("近日要闻 TOP3", f"生成异常，使用降级方案：{e}")
            return self._generate_top3_fallback(all_results)

    def _build_credibility_summary(self, results: List[Dict]) -> str:
        """构建可信度摘要，供TOP3提示词使用"""
        high_trust = []
        medium_trust = []
        low_trust = []

        for r in results:
            score = r.get("credibility_score", 0.5)
            source = r.get("source", "Unknown")
            if score >= 0.7:
                high_trust.append(f"{source}({score:.2f})")
            elif score >= 0.4:
                medium_trust.append(f"{source}({score:.2f})")
            else:
                low_trust.append(f"{source}({score:.2f})")

        lines = ["来源可信度概览："]
        if high_trust:
            lines.append(f"- 高可信来源（≥0.7）：{', '.join(list(set(high_trust))[:5])}")
        if medium_trust:
            lines.append(f"- 中可信来源（0.4-0.7）：{', '.join(list(set(medium_trust))[:5])}")
        if low_trust:
            lines.append(f"- 低可信来源（<0.4）：{', '.join(list(set(low_trust))[:5])}")

        return "\n".join(lines)

    def _generate_top3_fallback(self, all_results: List[Dict]) -> str:
        """TOP3降级方案：按可信度和主题相关性加权排序，取Top3"""
        # 过滤掉暗网链接和极低可信来源
        filtered = [
            r for r in all_results
            if not r.get("url", "").endswith(".onion")
            and r.get("credibility_score", 0) >= 0.2
        ]
        if not filtered:
            filtered = all_results

        # 按可信度(60%) + 主题相关性(40%) 加权排序
        def _sort_key(x):
            cred = x.get("credibility_score", 0.5)
            rel = _topic_relevance(x.get("title", ""), x.get("description", ""))
            return cred * 0.6 + rel * 0.4

        sorted_results = sorted(filtered, key=_sort_key, reverse=True)

        top_items = sorted_results[:BRIEFING_CONFIG["format"].get("max_top3_items", 3)]
        if not top_items:
            return "本日暂无符合标准的重要新闻。"

        result = []
        for i, item in enumerate(top_items, 1):
            title = item.get("title", "未知标题")
            desc = item.get("description", item.get("content", ""))[:200]
            source = item.get("source", "未知来源")
            date = item.get("published_at", datetime.now().strftime("%Y-%m-%d"))
            score = item.get("credibility_score", 0)

            result.append(
                f"{i}. **{title}**\n"
                f"   {desc}...\n"
                f"   （来源：{source} / {date} | 可信度：{score:.2f}）"
            )
        return "\n".join(result)

    def _generate_ai_dynamic(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成 AI 领域动态（模型与技术 / 应用与落地 / 产业与市场）"""
        results = self._collect(AI_DYNAMIC_CATS, collected_data)
        return self._run_prompt("ai_dynamic", results, llm,
                                 "你是一位AI领域情报分析师，请生成'AI 领域动态'部分。",
                                 label="AI 领域动态")

    def _generate_cyber_dynamic(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成 网络安全动态（漏洞与威胁 / 攻击事件 / 政策与合规）"""
        results = self._collect(CYBER_DYNAMIC_CATS, collected_data)
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
            # 从搜索结果中补充 CVE 信息
            for item in results:
                metadata = item.get("metadata", {})
                cve_id = metadata.get("cve_id", "")
                if cve_id and cve_id not in all_cves:
                    all_cves[cve_id] = {
                        "cve_id": cve_id,
                        "cvss_score": metadata.get("cvss_score", ""),
                        "affected_products": metadata.get("affected_products", []),
                        "vuln_types": metadata.get("vuln_types", []),
                        "description": item.get("description", "")[:200],
                        "url": item.get("url", ""),
                    }
            # 从标题中正则提取 CVE 编号
            if not all_cves:
                for item in results:
                    title = item.get("title", "") + " " + item.get("description", "")
                    for m in re.finditer(r'CVE-\d{4}-\d{4,}', title):
                        cve_id = m.group(0)
                        if cve_id not in all_cves:
                            all_cves[cve_id] = {
                                "cve_id": cve_id,
                                "cvss_score": "",
                                "affected_products": [],
                                "vuln_types": [],
                                "description": item.get("description", "")[:200],
                                "url": item.get("url", ""),
                            }
                    if len(all_cves) >= 10:
                        break

        if not all_cves:
            self._add_warning("近日新增安全漏洞预警", "未采集到漏洞相关情报，表格为空")
            return f"{header}\n| （暂无） | - | - | - | - | - |"

        # 排序：在野利用优先，然后按 CVSS 降序
        def _cve_sort_key(item):
            cve_id, data = item
            in_kev = data.get("in_kev", False)
            try:
                cvss = float(data.get("cvss_score", 0) or 0)
            except (ValueError, TypeError):
                cvss = 0
            return (0 if in_kev else 1, -cvss)

        sorted_cves = sorted(all_cves.items(), key=_cve_sort_key)

        # 生成表格行（跳过 TOP3 中已覆盖的 CVE）
        rows = []
        for cve_id, data in sorted_cves:
            if cve_id in skip_cve_ids:
                continue
            if len(rows) >= 10:
                break
            # 影响产品
            products = data.get("affected_products", [])
            if not products and data.get("product"):
                products = [data["product"]]
            product_str = ", ".join(products[:3]) if products else "待确认"

            # 漏洞类型
            vuln_types = data.get("vuln_types", [])
            vuln_type_str = ", ".join(vuln_types[:2]) if vuln_types else "待确认"

            # CVSS 评分
            cvss = data.get("cvss_score", "")
            if not cvss:
                cvss = "待评估"

            # 利用状态
            in_kev = data.get("in_kev", False)
            exploit_status = "🔴 在野利用" if in_kev else "暂无在野利用"

            # 建议措施（根据漏洞类型和利用状态差异化）
            if in_kev:
                action = data.get("required_action", "")
                if action:
                    suggestion = action if len(action) <= 50 else action[:47] + "…"
                else:
                    suggestion = "立即升级至安全版本"
            else:
                # 根据漏洞类型给出差异化建议
                desc_lower = (data.get("description", "") + vuln_type_str).lower()
                if any(kw in desc_lower for kw in ['rce', 'remote code', '代码执行']):
                    suggestion = "立即升级，前置WAF/IPS规则"
                elif any(kw in desc_lower for kw in ['xss', 'cross-site', '跨站']):
                    suggestion = "部署WAF，输入验证过滤"
                elif any(kw in desc_lower for kw in ['sql', '注入', 'injection']):
                    suggestion = "参数化查询，部署WAF"
                elif any(kw in desc_lower for kw in ['info', 'information', '信息泄露']):
                    suggestion = "限制访问控制，升级版本"
                else:
                    suggestion = "升级至安全版本"
                suggestion = "升级至安全版本"

            rows.append(f"| {cve_id} | {product_str} | {vuln_type_str} | {cvss} | {exploit_status} | {suggestion} |")

        if not rows:
            return f"{header}\n| （暂无） | - | - | - | - | - |"

        return header + "\n" + "\n".join(rows)

    def _generate_policy(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成政策法规动态（国内政策 / 国际法规 / 行业标准）"""
        results = self._collect(POLICY_CATS, collected_data)

        # 降级模式（无LLM）：按语言分离国内外内容
        if llm is None or not results:
            if not results:
                self._add_warning("政策法规动态", "未采集到相关情报数据")
                return self._get_fallback_content("policy", results)

            zh_pattern = re.compile(r'[\u4e00-\u9fff]')
            domestic = []
            international = []
            for r in results:
                title = r.get("title", "") + " " + r.get("description", "")
                if zh_pattern.search(title):
                    domestic.append(r)
                else:
                    international.append(r)

            lines = ["### 国内政策"]
            if domestic:
                for item in domestic[:3]:
                    title = self._clean_search_title(item.get("title", ""))
                    if not title:
                        continue
                    source = self._clean_source_name(item.get("source", ""), item.get("url", ""))
                    date = self._clean_date(item.get("published_at", ""))
                    lines.append(f"• [政策] {title}（来源：{source} / {date}）")
            else:
                lines.append("本日暂无相关动态。")

            lines.append("")
            lines.append("### 国际法规")
            if international:
                for item in international[:3]:
                    title = self._clean_search_title(item.get("title", ""))
                    if not title:
                        continue
                    source = self._clean_source_name(item.get("source", ""), item.get("url", ""))
                    date = self._clean_date(item.get("published_at", ""))
                    lines.append(f"• [法规] {title}（来源：{source} / {date}）")
            else:
                lines.append("本日暂无相关动态。")

            lines.append("")
            lines.append("### 行业标准")
            lines.append("本日暂无相关动态。")
            return "\n".join(lines)

        return self._run_prompt("policy", results, llm,
                                 "你是一位政策法规分析师，请生成'政策法规动态'部分。",
                                 label="政策法规动态")

    def _generate_attack_analysis(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成攻击事件深度分析"""
        results = self._collect(ATTACK_CATS, collected_data)
        return self._run_prompt("attack_analysis", results, llm,
                                 "你是一位网络安全事件分析师，请生成'攻击事件深度分析'部分。",
                                 label="攻击事件深度分析")

    def _generate_protection(self, collected_data: Dict[str, List[Dict]], llm) -> str:
        """生成防护建议与厂商方案"""
        results = self._collect(PROTECTION_CATS, collected_data)
        return self._run_prompt("protection", results, llm,
                                 "你是一位网络安全防护专家，请生成'防护建议与厂商方案'部分。",
                                 label="防护建议与厂商方案")

    def _find_unsourced_figures(self, result: str, source_text: str) -> list:
        """找出输出中来源文本不支持、且未标注【推断】的金额/百分比数据。

        反编造抽查：模型常把脑补的黑市估值/股价涨跌写成事实（实锤案例：
        「每条记录50-200美元→潜在价值1.875亿至7.5亿美元」「股价下跌逾12%」）。
        返回疑似编造的数据列表；空列表表示抽查通过。

        规则：
        - 提取百分比、货币金额（$xx / xx美元 / xx万元|亿）、大数值
        - 数字在来源文本中出现 → 放行
        - 所在行含【推断】标注 → 放行
        - 其余视为无来源数据
        """
        if not result or not source_text:
            return []

        # 归一化来源：去空白，便于「1.875亿」「375万」这类跨格式匹配
        src = re.sub(r"\s+", "", source_text)

        suspects = []
        for line in result.split("\n"):
            stripped = line.strip()
            if not stripped or "【推断】" in stripped:
                continue
            figures = re.findall(
                r"\d+(?:\.\d+)?(?:%|％|[美欧人民币]元|万元|亿元|亿美元)"
                r"|\$\s?\d+(?:\.\d+)?(?:\s?(?:million|billion))?",
                stripped,
            )
            for fig in figures:
                num_part = re.sub(r"[\s$%％]|million|billion", "", fig)
                num_core = re.sub(r"^(?:[美欧人民币])?|(?:万元|亿元|亿美元|元)$", "", num_part)
                if num_core and num_core not in src:
                    suspects.append(fig)
        return suspects

    def _validate_llm_output(self, result: str, prompt_name: str, source_text: str = "") -> bool:
        """校验LLM输出是否有效，避免模板占位符或垃圾内容"""
        if not result or not result.strip():
            return False

        result = result.strip()

        # 检测模板占位符（提示词中的示例格式，带方括号的占位文字）
        template_patterns = [
            "事件概述（2-3句话说明发生了什么）",
            "影响分析或技术细节（1-2句话阐述意义或影响范围）",
            "新闻标题",
            "[具体区域/规模]",
            "[具体行业]",
            "[具体损失类型和规模]",
            "[具体可执行的操作]",
            "[具体改进方案]",
            "[具体加固建议]",
            "[用搜索结果中的真实事件名称替换]",
            "[真实日期]",
            "[真实事件节点]",
            "[具体描述攻击入口]",
            "[具体描述执行的恶意操作]",
            "[具体描述如何维持权限]",
            "[具体描述内网扩散方式]",
            "[具体描述最终造成的影响]",
            "[用2-3句话概括事件背景]",
            "用2-3句话概括事件背景",
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
        # protection 板块豁免：该板块天然引用大量英文厂商产品名/英文源，
        # 此规则误杀率过高——且失败后已有优雅降级兜底，不再倒原始转储。
        if prompt_name != "protection":
            english_streak = 0
            for line in result.split("\n"):
                stripped = line.strip()
                if not stripped or re.search(r"CVE-\d{4}-\d+", stripped):
                    english_streak = 0
                    continue
                # 判断是否为纯英文（排除中文字符、数字、标点）
                if re.match(r"^[a-zA-Z0-9\s\.\,\;\:\-\(\)\[\]\\\/\@\#\$\%\^\&\*\+\=\_\~\`\|\{\}\<\>\?\!]+$", stripped):
                    english_streak += 1
                    if english_streak >= 3:
                        logger.warning("LLM输出包含连续纯英文段落，判定无效")
                        return False
                else:
                    english_streak = 0

        # 检测占位符CVE
        if re.search(r"CVE-\d{4}-XXXX", result):
            logger.warning("LLM输出包含占位符CVE，判定无效")
            return False

        # 反编造抽查：深度分析中的金额/百分比必须来自来源文本，
        # 或所在行显式标注【推断】。防止模型把脑补的估值当事实分发。
        if prompt_name == "attack_analysis" and source_text:
            fabricated = self._find_unsourced_figures(result, source_text)
            if fabricated:
                logger.warning(
                    f"攻击事件深度分析包含来源中不存在的数据，判定疑似编造: {fabricated[:3]}"
                )
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

    def _get_fallback_content(self, prompt_name: str, results: List[Dict] = None) -> str:
        """统一降级输出：根据板块类型返回结构化降级内容（无需 LLM）"""
        if results is None:
            results = []
        fallback_map = {
            "top3": "本日暂无重大要闻。",
            "cve_table": (
                "| CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施 |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| （暂无） | - | - | - | - | - |"
            ),
            "ai_dynamic": self._fallback_subsections(
                ["模型与技术", "应用与落地", "产业与市场"], results, None),
            "cyber_dynamic": self._fallback_subsections(
                ["漏洞与威胁", "攻击事件"], results, None),
            "policy": self._fallback_subsections(
                ["国内政策", "国际法规", "行业标准"], results, None),
            "attack_analysis": "本日暂无重大安全事件需要深度分析。",
            # protection 不倒原始条目：抓取器原文是英文粘连转储，直接展示
            # 等于把垃圾发给订阅者。宁可明确告知「本日无可整理内容」。
            "protection": (
                "### 通用防护建议\n本日暂无可整理的防护建议；建议参考上方"
                "漏洞预警表格中的处置措施。\n\n### 厂商解决方案\n本日暂无相关厂商方案。"
            ),
            "insight": (
                "1. **关注AI与网络安全动态**\n"
                "   本日采集到若干公开信息，建议持续跟踪AI技术进展与网络安全威胁。\n\n"
                "   **建议：** 保持对AI新技术的关注，及时评估潜在安全影响。\n\n"
                "2. **加强安全防护**\n"
                "   AI相关安全事件与漏洞披露频繁，需加强安全防护。\n\n"
                "   **建议：** 定期检查系统安全性，及时更新防护措施。\n\n"
                "3. **跟踪合规要求**\n"
                "   各国AI与网络安全法规陆续出台，企业需关注合规。\n\n"
                "   **建议：** 跟踪相关政策动态，确保业务合规。"
            ),
            "links": "暂无重要链接。",
        }
        return fallback_map.get(prompt_name, "本日暂无相关动态。")

    def _run_prompt(self, prompt_name: str, results: List[Dict], llm, system_desc: str, label: str = None) -> str:
        """通用：调用提示词生成板块内容"""
        label = label or prompt_name

        # ---- 前置校验：数据为空或 LLM 不可用时直接降级 ----
        if not results:
            self._add_warning(label, "无可用数据，使用降级内容")
            return self._get_fallback_content(prompt_name, results)
        if llm is None:
            self._add_warning(label, "LLM 不可用，使用降级内容")
            return self._get_fallback_content(prompt_name, results)

        try:
            # 使用配置中的max_results_for_sections参数
            max_results = BRIEFING_CONFIG["search"].get("max_results_for_sections", 15)
            used_results = results[:max_results]
            search_summary = self._format_results_for_prompt(used_results)
            prompt = get_prompt(prompt_name, search_results=search_summary,
                                kb_context=self._kb_context)

            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            prompt_template = ChatPromptTemplate(
                [("system", system_desc), ("user", "{prompt}")]
            )
            chain = prompt_template | llm | StrOutputParser()

            result = chain.invoke({"prompt": prompt})

            # 校验LLM输出（attack_analysis 附带来源文本做反编造抽查）
            source_text = search_summary if prompt_name == "attack_analysis" else ""
            if not self._validate_llm_output(result, prompt_name, source_text=source_text):
                logger.warning(f"{label}: LLM输出校验失败，回退到降级模式")
                self._add_warning(label, "LLM输出校验失败，使用降级内容")
                return self._get_fallback_content(prompt_name, results)

            # 后处理清洗
            result = self._clean_llm_output(result)
            return result
        except Exception as e:
            logger.error(f"Error generating {prompt_name}: {e}")
            self._add_warning(label, f"生成异常：{type(e).__name__}: {str(e)[:200]}")
            return self._get_fallback_content(prompt_name, results)

    @staticmethod
    def _clean_search_title(title: str) -> str:
        """清洗搜索结果标题：移除URL、日期片段、搜索引擎残留文本"""
        if not title:
            return "未知标题"
        t = title.strip()
        # 移除 .onion URL
        if ".onion" in t:
            return ""
        # 移除完整URL（含路径）
        t = re.sub(r'https?://\S+', '', t)
        t = re.sub(r'\S+\.com\S*', '', t)
        t = re.sub(r'\S+\.org\S*', '', t)
        t = re.sub(r'\S+\.gov\S*', '', t)
        t = re.sub(r'\S+\.edu\S*', '', t)
        # 移除日期时间片段
        t = re.sub(r'\b\d{1,2}\s+(hours?|days?|minutes?|months?)\s+ago\b', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\d{1,2}\s+\w+\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+\w+\b', '', t)
        t = re.sub(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s*\d{4}\b', '', t)
        t = re.sub(r'\b\d{4}年\d{1,2}月\d{1,2}日\b', '', t)
        # 移除搜索引擎UI文案残留
        t = re.sub(r'Add\s+\w+\s+as\s+a\s+preferred\s+source.*', '', t, flags=re.IGNORECASE)
        t = re.sub(r'Show\s+HN:\s*', '', t)
        # 移除多余的 > 符号和路径分隔符
        t = re.sub(r'›', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        # 移除首尾标点
        t = t.strip(' .·|:-')
        return t if t else ""

    @staticmethod
    def _clean_source_name(source: str, url: str = "") -> str:
        """清洗来源名称：从URL提取域名或规范化来源名"""
        # 如果来源是搜索引擎，尝试从URL提取实际来源。
        # 用包含匹配而非精确匹配：实际数据里是「Bing News」「DuckDuckGo」
        # 等变体，旧实现只认「Bing」导致搜索引擎名直接漏到署名位。
        search_engine_hints = ('bing', 'google', 'yahoo', 'duckduckgo', 'baidu', 'yandex')
        if url and any(h in (source or "").lower() for h in search_engine_hints):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                if domain.startswith('www.'):
                    domain = domain[4:]
                # 取主域名
                parts = domain.split('.')
                if len(parts) >= 2:
                    return parts[-2].capitalize()
            except Exception:
                pass
        # 清洗来源名称中的URL残留
        if source:
            cleaned = re.sub(r'https?://\S+', '', source).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .·|:-')
            if cleaned:
                return cleaned
        return source or "未知来源"

    @staticmethod
    def _clean_date(date_str: str) -> str:
        """清洗日期：标准化为 YYYY-MM-DD 格式"""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")
        # 移除时间部分
        d = date_str.strip()
        # 处理 ISO 格式
        if 'T' in d:
            d = d.split('T')[0]
        # 处理 "Mon, 17 Jun 2026 02:21:00 GMT" 格式
        m = re.match(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+(\d{1,2})\s+(\w{3})\s+(\d{4})', d)
        if m:
            from datetime import datetime as dt
            try:
                parsed = dt.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                pass
        # 处理 "Aug 13,2026" 或 "Aug 13, 2026" 格式
        m = re.match(r'(\w{3})\s+(\d{1,2}),?\s*(\d{4})', d)
        if m:
            from datetime import datetime as dt
            try:
                parsed = dt.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y")
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                pass
        # 已经是 YYYY-MM-DD 格式
        if re.match(r'\d{4}-\d{2}-\d{2}', d):
            return d[:10]
        # 无法解析，返回原值截断
        return d[:10] if len(d) >= 10 else d

    def _fallback_subsections(self, subsections: List[str], results: List[Dict], llm) -> str:
        """无 LLM 时的降级：输出子板块结构并填入清洗后的条目"""
        if not results:
            return "\n".join(f"### {s}\n本日暂无相关动态。" for s in subsections)

        # 过滤 .onion 链接
        filtered = [r for r in results if not (r.get("url", "") or r.get("link", "")).endswith(".onion")]
        if not filtered:
            filtered = results

        chunks = [filtered[i::len(subsections)] for i in range(len(subsections))]
        blocks = []
        for sub, items in zip(subsections, chunks):
            lines = [f"### {sub}"]
            for item in items[:4]:
                metadata = item.get("metadata", {})
                # 清洗标题
                title = self._clean_search_title(item.get("title", ""))
                if not title:
                    continue  # 跳过.onion或无效条目
                # 清洗来源和日期
                raw_url = item.get("url", "") or item.get("link", "")
                source = self._clean_source_name(item.get("source", "未知来源"), raw_url)
                date = self._clean_date(item.get("published_at", ""))
                description = item.get("description", "")[:150]
                # 清洗描述中的URL和搜索引擎残留
                if description:
                    description = re.sub(r'https?://\S+', '', description)
                    description = re.sub(r'\s+', ' ', description).strip()

                # 增强降级展示：提取结构化字段
                extra_info = []
                if metadata.get("cve_id"):
                    extra_info.append(f"**CVE**: {metadata['cve_id']}")
                if metadata.get("cvss_score"):
                    extra_info.append(f"**CVSS**: {metadata['cvss_score']}")
                if metadata.get("threat_type"):
                    extra_info.append(f"**类型**: {metadata['threat_type']}")
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
            # 如果该子板块无有效条目
            if len(lines) == 1:
                lines.append("本日暂无相关动态。")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def _generate_summary(self, contents: Dict[str, str], collected_data: Dict[str, List[Dict]]) -> str:
        """生成执行摘要（今日要点），从各板块提取关键信息"""
        bullets = []

        # 从 TOP3 提取关键事件
        top3 = contents.get("top3", "")
        if top3:
            titles = re.findall(r'\*\*(.+?)\*\*', top3)
            for t in titles[:3]:
                if t and len(t) > 5:
                    bullets.append(f"- 🔴 {t}")

        # 从漏洞表格提取高危CVE
        cve = contents.get("cve_table", "")
        if cve:
            kev_cves = re.findall(r'(CVE-\d{4}-\d+).*?在野利用', cve)
            for c in kev_cves[:2]:
                bullets.append(f"- ⚠️ {c}：已发现在野利用，需立即处置")

        # 从趋势研判提取核心观点
        insights = contents.get("insights", "")
        if insights:
            insight_titles = re.findall(r'\*\*(.+?)\*\*', insights)
            for t in insight_titles[:2]:
                if t and len(t) > 5:
                    bullets.append(f"- 📊 {t}")

        # 从政策动态提取重要法规——检测「### 国内政策」子板块下是否有实际
        # 条目行（旧实现 `"国内政策" in policy` 恒真：子板块标题本身包含
        # 该子串，导致「今日有国内政策动态」与正文的「本日暂无」自相矛盾）。
        policy = contents.get("policy", "")
        if policy:
            domestic_items = 0
            in_domestic = False
            for line in policy.split("\n"):
                stripped = line.strip()
                if stripped.startswith("### "):
                    in_domestic = "国内" in stripped
                    continue
                if in_domestic and stripped.startswith("•"):
                    domestic_items += 1
            if domestic_items > 0:
                bullets.append("- 📋 今日有国内AI/网络安全政策动态（详见政策法规板块）")

        if not bullets:
            return "本日暂无特别需要关注的要点。"

        return "\n".join(bullets[:8])  # 最多8条要点

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
            self._add_warning("趋势研判与防护建议", "LLM 不可用，使用默认趋势研判")
            return self._get_fallback_content("insight")

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
            if not result or not result.strip():
                self._add_warning("趋势研判与防护建议", "LLM 返回空结果，使用降级内容")
                return self._get_fallback_content("insight")
            return result
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            self._add_warning("趋势研判与防护建议", f"生成异常：{type(e).__name__}: {str(e)[:200]}")
            return self._get_fallback_content("insight")

    def _generate_links(self, collected_data: Dict[str, List[Dict]], llm=None) -> str:
        """生成重要链接部分"""
        links = []
        seen_urls = set()

        for results in collected_data.values():
            for item in results[:3]:
                url = self._clean_url(item.get("url", ""))
                # 过滤 .onion 和重定向URL
                if not url or ".onion" in url:
                    continue
                if "r.search.yahoo.com" in url:
                    # 尝试从Yahoo重定向URL中提取实际目标URL
                    ru_match = re.search(r'RU=([^/]+)', url)
                    if ru_match:
                        from urllib.parse import unquote
                        actual_url = unquote(ru_match.group(1))
                        if actual_url.startswith("http"):
                            url = actual_url
                if url in seen_urls:
                    continue
                # 清洗标题
                title = self._clean_search_title(item.get("title", ""))
                if not title:
                    # 从URL提取域名作为标题
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        title = parsed.netloc.replace("www.", "")
                    except Exception:
                        title = url[:50]
                if len(title) > 60:
                    title = title[:57] + "..."
                seen_urls.add(url)
                links.append(f"• {title}: {url}")

        if not links:
            return "暂无重要链接。"

        return "\n".join(links[:10])

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
