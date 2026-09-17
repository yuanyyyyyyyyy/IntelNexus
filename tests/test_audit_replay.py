"""以 INTEL-20260916-001 的真实语料做端到端重跑回归。

审计结论：该报告「结论碰巧对、过程全错」，六类缺陷同时出现。本文件把
那份报告的真实语料（19 条、4 个渠道、5 条无关 RSS 条目）固化为 fixture，
一次性断言六类缺陷都不再复现 —— 单点测试防局部回归，本文件防「修好一处、
另一处又串回来」。

审计发现的六类缺陷与对应断言：
1. 语料污染 26%      → 无关 RSS 条目不得进入关键情报/事件演化
2. 风险语义错标      → 风险定级必须是「证据不足」，不得因语料质量差给「中」
3. 未授权侦察        → 攻击面章节替换为合规说明（该查询针对具名在营实体）
4. 来源口径错配      → 渠道与出版方分离，禁止用引擎名冒充出版方
5. 实体图谱全噪声    → 「曼哈顿市中心」类片段不得成为实体
6. 渲染不一致        → 章节编号连续、模式汉化、热度受相关率惩罚
"""

import pytest

from intelnexus.analysis.risk_level import LEVEL_INSUFFICIENT, collect_risk_evidence, compute_risk_level
from intelnexus.core.search.authorization import assess_authorization
from intelnexus.export.report_builder import build_intelligence_report

QUERY = "华盛顿华尔道夫酒店位置华盛顿特区宾夕法尼亚大道西北1100号:对酒店所有设施开展调研加漏洞"

# 审计报告中的 5 条无关 RSS 条目（Solidot / AI科技评论 的最新条目）
RSS_NOISE = [
    "AI 时代隐晦式安全已死",
    "微信蠕虫事件敲响 AI 安全警钟",
    "横扫四榜，DM0.5 凭什么面面俱到？",
    "英伟达开源 IMO 金牌配方：不仅是「人海战术」",
    "全球AI大厂集体呼吁“限速” 360：AI安全不能靠企业自审",
]

# 同批语料中的异址同名主体（纽约的 Washington Hotel、马里兰州的 Courtyard Waldorf）
OFF_TARGET = [
    "纽约华盛顿酒店预订价格,联系电话位置地址",
    "万怡华尔道夫酒店点评：泳池与热水浴缸不可用",
]


def _result(title, source, url, publisher, weak, published="2026-09-10"):
    return {
        "title": title, "source": source, "url": url, "publisher": publisher,
        "weak_related": weak, "relevance_score": 0.2 if weak else 0.8,
        "credibility_score": 0.45 if weak else 0.62,
        "published_at": published,
    }


@pytest.fixture
def audit_corpus():
    """审计报告的真实语料（19 条）。"""
    items = []
    # Baidu ×5 —— 3 条跳转未解析（出版方未知），2 条解析出真实出版方
    for i in range(5):
        items.append(_result(f"华盛顿华尔道夫酒店:必住理由 {i}", "Baidu",
                             f"http://www.baidu.com/link?url=opaque{i}",
                             "" if i < 3 else "hotels.ctrip.com", weak=False))
    # Bing ×5
    for i in range(5):
        items.append(_result(f"华盛顿特区奢华住宿体验 {i}", "Bing",
                             f"https://zh-cn.washington.org/page{i}",
                             "zh-cn.washington.org", weak=False))
    # RSS 噪声 ×5
    for i, title in enumerate(RSS_NOISE):
        items.append(_result(title, "Solidot" if i < 2 else "AI科技评论",
                             f"https://news.example.com/n{i}", "solidot.org",
                             weak=True, published="2026-09-15"))
    # 异址同名主体 ×2
    for i, title in enumerate(OFF_TARGET):
        items.append(_result(title, "Bing", f"https://www.ctrip.com/h{i}",
                             "ctrip.com", weak=True))
    # 两条有效目标线索（含同址前身品牌的 Agoda 页面）
    items.append(_result("华尔道夫酒店-华盛顿特区（Waldorf Astoria Washington DC）预订",
                         "Baidu",
                         "https://www.agoda.com/zh-cn/trump-international-washington-d-c_2/hotel/washington-d-c-us.html",
                         "agoda.com", weak=False, published="2026-08-12"))
    items.append(_result("华盛顿酒店（Hotel Washington）设施与政策", "Baidu",
                         "https://hotels.ctrip.com/hotels/2198955.html",
                         "hotels.ctrip.com", weak=False, published="2026-08-20"))
    return items


@pytest.fixture
def report(audit_corpus):
    cred = {
        "scores": [
            {"name": r["source"], "engine": r["source"], "publisher": r["publisher"],
             "score": r["credibility_score"], "reason": "", "domain": 0.5}
            for r in audit_corpus
        ],
        "avg_score": 0.5, "high_count": 0, "low_count": 0,
    }
    return build_intelligence_report(
        query=QUERY, search_mode="smart_general", model="qwen3-max",
        llm_output=LLM_OUTPUT, results=audit_corpus,
        source_counts={"Baidu": 7, "Bing": 6, "AI科技评论": 3, "Solidot": 2},
        source_stats={}, credibility_data=cred,
        kg_entities=KG_ENTITIES, kg_relations=KG_RELATIONS,
        conflicts=[], scraped={},
        # 程序化风险定级（与 search_worker 的调用形态一致）
        risk_level=LEVEL_INSUFFICIENT,
        risk_reason="未采集到漏洞/威胁情报/冲突等客观威胁证据，不做风险定级",
        # 授权闸门：该查询针对具名在营实体且未声明授权
        authorization={"requires_authorization": True, "authorized": False,
                       "scope_note": "未声明授权：本次分析降级为纯公开信息（OSINT）收集。"},
    )


# LLM 原始输出（形态与审计报告一致，含无法核验的 Expedia 引用）
LLM_OUTPUT = """## 二、核心摘要

**【事实】**：搜索结果中出现华尔道夫酒店的预订页面标题。

## 六、证据链分析

**结论 1**：公开渠道存在可见信息。
- E1：Agoda 页面标题显示预订信息（来源：Agoda，来源等级：B，支持度：中）
- E2：Expedia 页面标题显示点评（来源：Expedia，来源等级：B，支持度：中）
**综合置信度**：中

## 八、舆情趋势

**舆情比例**：正面 45%，中性 40%，负面 15%

## 九、影响评估

**技术影响**：[★★☆☆☆] 无

## 十二、攻击面分析

**1. API/接口层**
- 风险点：预订接口鉴权不足
"""

# 审计报告中的真实噪声实体
KG_ENTITIES = [
    {"id": "曼哈顿市中心", "name": "曼哈顿市中心", "type": "UNKNOWN", "importance": 1.0},
    {"id": "hotel_washington", "name": "Hotel Washington", "type": "ORG", "importance": 0.25},
]
KG_RELATIONS = [
    {"subject_id": "hotel_washington", "predicate": "co_occur",
     "object_id": "在华盛顿特区远离科技"},
]


# ===========================================================================
# 缺陷 1：语料污染
# ===========================================================================

def _section(report, start, end):
    return report.split(start)[1].split(end)[0]


@pytest.fixture
def key_intel(report):
    return _section(report, "## 五、关键情报", "## 六、")


@pytest.fixture
def appendix(report):
    return _section(report, "## 十五、原始证据", "\x00")


class TestNoiseNoLongerPollutes:
    @pytest.mark.parametrize("title", RSS_NOISE)
    def test_rss_noise_not_in_key_intelligence(self, key_intel, title):
        assert title not in key_intel

    @pytest.mark.parametrize("title", OFF_TARGET)
    def test_off_target_subject_not_in_key_intelligence(self, key_intel, title):
        assert title not in key_intel

    def test_timeline_has_no_rss_dates(self, report):
        timeline = _section(report, "## 八、事件演化", "## 九、")
        assert "2026-09-15" not in timeline

    def test_evidence_appendix_marks_weak_items(self, appendix):
        """弱相关条目保留在原始证据中供溯源，但必须标注未纳入分析。"""
        assert "弱相关（未纳入结论推导）" in appendix

    def test_relevant_target_clue_kept(self, key_intel):
        assert "华尔道夫酒店" in key_intel


# ===========================================================================
# 缺陷 2：风险语义
# ===========================================================================

class TestRiskSemantics:
    def test_corpus_without_threat_evidence_is_insufficient(self, audit_corpus):
        risk, _ = compute_risk_level(collect_risk_evidence(audit_corpus))
        assert risk == LEVEL_INSUFFICIENT

    def test_report_does_not_label_medium_risk(self, report):
        section = report.split("## 十一、风险评估")[1].split("## 十二、")[0]
        assert "程序化风险定级" in section
        assert LEVEL_INSUFFICIENT in section
        assert "**程序化风险定级**：中" not in section


# ===========================================================================
# 缺陷 3：未授权侦察
# ===========================================================================

class TestAuthorization:
    def test_query_requires_authorization(self):
        assert assess_authorization(QUERY)["requires_authorization"] is True

    def test_attack_surface_replaced_by_notice(self, report):
        section = report.split("## 十二、攻击面分析")[1].split("## 十三、")[0]
        assert "API/接口层" not in section
        assert "未声明授权" in section

    def test_overview_declares_authorization_state(self, report):
        assert "**授权状态**：未声明授权" in report


# ===========================================================================
# 缺陷 4：来源口径
# ===========================================================================

class TestSourceDimension:
    def test_channel_and_publisher_separated(self, report):
        section = report.split("## 四、来源分析")[1].split("## 五、")[0]
        assert "检索渠道" in section
        assert "出版方质量评分" in section
        assert "agoda.com" in section

    def test_unresolved_wrapper_flagged(self, report):
        section = report.split("## 四、来源分析")[1].split("## 五、")[0]
        assert "出版方未解析" in section


# ===========================================================================
# 缺陷 5：实体图谱
# ===========================================================================

class TestEntityGraph:
    def test_generic_fragment_not_an_entity(self, report):
        section = report.split("## 七、实体关系图谱")[1].split("## 八、")[0]
        assert "曼哈顿市中心" not in section

    def test_dangling_relation_hidden(self, report):
        section = report.split("## 七、实体关系图谱")[1].split("## 八、")[0]
        assert "在华盛顿特区远离科技" not in section

    def test_hotel_washington_present(self, report):
        section = report.split("## 七、实体关系图谱")[1].split("## 八、")[0]
        assert "Hotel Washington" in section


# ===========================================================================
# 缺陷 6：渲染一致性 + 证据可核验
# ===========================================================================

class TestRendering:
    def test_section_numbering_starts_at_one(self, report):
        assert "## 一、报告概览" in report
        assert "## 二、核心摘要" in report

    def test_mode_label_translated(self, report):
        assert "**分析模式**：智能通用" in report

    def test_heat_penalized_by_relevance_ratio(self, report):
        profile = report.split("## 三、事件画像")[1].split("## 四、")[0]
        heat_line = [l for l in profile.splitlines() if l.startswith("**热度**")][0]
        heat = int(heat_line.split()[-1])
        # 19 条中 7 条弱相关 → 相关率约 0.63，热度应显著低于旧口径的 71
        assert heat <= 60, heat_line

    def test_unverifiable_citation_flagged(self, report):
        section = report.split("## 六、证据链分析")[1].split("## 七、")[0]
        assert "Expedia" in section
        assert "未核验" in section

    def test_duration_has_no_stray_unit(self, report):
        assert "未知 天" not in report
