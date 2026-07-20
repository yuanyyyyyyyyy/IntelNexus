"""
简报格式复刻冒烟测试
验证《AI 与网络安全每日情报简报》新结构：
- Markdown 含新板块标题、落款来自配置、不含旧板块
- markdown_to_html_sections 正确映射到新 SECTION_MAP，CVE 表格转 HTML，页脚不泄漏
- 无 LLM 降级路径也能产出新结构
"""

import os

from ai_briefing.config import BRIEFING_CONFIG
from ai_briefing.templates import render_markdown_briefing, markdown_to_html_sections
from ai_briefing.analyzer import AIBriefingAnalyzer

ORG = {
    "name": "测试机构",
    "team": "测试",
    "producer_unit": "测试出品单位",
    "contact": "联系人：测试",
    "footer_qr_text": "获取更多安全情报",
    "disclaimer": "测试免责声明。",
}

CVE_TABLE = (
    "| CVE编号 | 影响产品 | 漏洞类型 | CVSS | 利用状态 | 建议措施 |\n"
    "| --- | --- | --- | --- | --- | --- |\n"
    "| CVE-2026-1 | 产品P | 类型T | 8.6 | 暂无在野利用 | 升级至安全版本 |"
)


def _render_sample():
    return render_markdown_briefing(
        generated_date="2026年7月7日（星期二）",
        organization=ORG,
        top3_content="1. **标题**：描述（来源：X / 2026-07-07）",
        ai_dynamic_content="### 模型与技术\n• [新发布] x（来源：X / 2026-07-07）",
        cyber_dynamic_content="### 漏洞与威胁\n• [高危] x（来源：X / 2026-07-07）",
        cve_table_content=CVE_TABLE,
        insights_content="1. **标题**\n分析。\n\n**建议：** 建议内容。",
        links_content="• 标题: http://example.com",
    )


def test_markdown_contains_new_sections():
    md = _render_sample()
    assert "AI 与网络安全每日情报简报" in md
    assert "📌 近日要闻 TOP3" in md
    assert "🤖 AI 领域动态" in md
    assert "🛡 网络安全动态" in md
    assert "⚠ 近日新增安全漏洞预警" in md
    assert "💡 趋势研判与防护建议" in md
    assert "📎 重要链接" in md
    # 落款来自配置
    assert "测试出品单位" in md
    assert "测试免责声明。" in md
    # 不应出现旧板块
    assert "美欧机构AI应用" not in md
    assert "涉我AI舆论" not in md


def test_markdown_to_html_sections_maps():
    md = _render_sample()
    sections = markdown_to_html_sections(md)
    assert sections["top3_html"]
    assert sections["ai_dynamic_html"]
    assert sections["cyber_dynamic_html"]
    assert sections["cve_table_html"]
    assert sections["insights_html"]
    assert sections["links_html"]
    # CVE 表格应转为 HTML <table>
    assert "<table" in sections["cve_table_html"]
    # 页脚（<!-- FOOTER --> 之后）不应泄漏进 links_html
    assert "简报结束" not in sections["links_html"]


def _sample_data():
    cats = [
        "ai_gov_usage", "ai_china_narrative", "ai_legislation", "ai_data_leak",
        "cyber_vuln", "cyber_attack",
    ]
    data = {}
    for i, c in enumerate(cats):
        data[c] = [{
            "title": f"样例新闻{i}",
            "url": f"http://example.com/{i}",
            "description": f"这是第{i}条样例描述，足够长以生成内容。",
            "content": f"内容{i}",
            "source": f"来源{i}",
            "published_at": "2026-07-07",
        }]
    return data


def test_analyzer_no_llm_fallback_structure():
    analyzer = AIBriefingAnalyzer(llm=None)
    md = analyzer.generate_briefing(_sample_data(), "测试机构")
    assert "🤖 AI 领域动态" in md
    assert "🛡 网络安全动态" in md
    assert "⚠ 近日新增安全漏洞预警" in md
    assert "CVE编号" in md  # CVE 表格表头
    assert "近日要闻 TOP3" in md


def test_pdf_export_renders(tmp_path):
    """品牌化 PDF 导出链路：封面/页眉页脚/CVE 表格/落款应生成非空 PDF。"""
    md = _render_sample()
    from src.export.briefing_export import export_briefing_pdf
    out = tmp_path / "brief.pdf"
    path = export_briefing_pdf(md, str(out), organization=ORG)
    assert os.path.exists(path)
    assert os.path.getsize(path) > 1000  # 含中文/表格，体积应明显大于空壳
