"""Intelligence report export tests (Markdown / PDF / Word / Excel)."""
import os

import pytest

from intelnexus.export import report as report_module


SAMPLE_CONTENT = """# 摘要
IntelNexus 是一个 AI 驱动的多源网络情报分析平台。
## 关键发现
- 支持网页、新闻与暗网检索
- 集成可信度评估与知识图谱
- 提供多格式报告导出
"""


def test_export_markdown_writes_file(tmp_path):
    out = tmp_path / "report.md"
    path = report_module.export_markdown(SAMPLE_CONTENT, "AI 平台", str(out))
    assert os.path.exists(path)
    text = out.read_text(encoding="utf-8")
    assert "IntelNexus 智能情报报告" in text
    assert "AI 平台" in text
    assert "摘要" in text


def test_export_markdown_keeps_given_path(tmp_path):
    # export_markdown 不会自动追加扩展名（由 export_report 分发层负责）
    out = tmp_path / "report"
    path = report_module.export_markdown(SAMPLE_CONTENT, "q", str(out))
    assert os.path.exists(path)
    assert out.read_text(encoding="utf-8")


def test_export_pdf_writes_file(tmp_path):
    out = tmp_path / "report.pdf"
    path = report_module.export_pdf(SAMPLE_CONTENT, "AI 平台", str(out))
    assert os.path.exists(path)
    assert out.read_bytes()[:5].startswith(b"%PDF")


def test_export_pdf_requires_extension_or_uses_export_report(tmp_path):
    # export_pdf 本身不追加扩展名，由 export_report 分发层负责
    out = tmp_path / "report.pdf"
    path = report_module.export_pdf(SAMPLE_CONTENT, "q", str(out))
    assert path.endswith(".pdf")
    assert os.path.exists(path)


def test_export_word_writes_file(tmp_path):
    out = tmp_path / "report.docx"
    path = report_module.export_word(SAMPLE_CONTENT, "AI 平台", str(out))
    assert os.path.exists(path)
    assert out.read_bytes()[:2] == b"PK"


def test_export_word_requires_extension_or_uses_export_report(tmp_path):
    # export_word 本身不追加扩展名，由 export_report 分发层负责
    out = tmp_path / "report.docx"
    path = report_module.export_word(SAMPLE_CONTENT, "q", str(out))
    assert path.endswith(".docx")
    assert os.path.exists(path)


def test_export_excel_writes_file(tmp_path):
    out = tmp_path / "report.xlsx"
    path = report_module.export_excel(SAMPLE_CONTENT, "AI 平台", str(out))
    assert os.path.exists(path)
    assert out.read_bytes()[:2] == b"PK"


def test_export_excel_appends_xlsx_extension(tmp_path):
    out = tmp_path / "report"
    path = report_module.export_excel(SAMPLE_CONTENT, "q", str(out))
    assert path.endswith(".xlsx")


def test_export_report_dispatches_formats(tmp_path):
    md = report_module.export_report(SAMPLE_CONTENT, "q", str(tmp_path / "a.md"), "md")
    pdf = report_module.export_report(SAMPLE_CONTENT, "q", str(tmp_path / "a.pdf"), "pdf")
    docx = report_module.export_report(SAMPLE_CONTENT, "q", str(tmp_path / "a.docx"), "docx")
    xlsx = report_module.export_report(SAMPLE_CONTENT, "q", str(tmp_path / "a.xlsx"), "xlsx")
    for p in (md, pdf, docx, xlsx):
        assert os.path.exists(p)


def test_export_report_defaults_to_markdown(tmp_path):
    out = tmp_path / "default"
    path = report_module.export_report(SAMPLE_CONTENT, "q", str(out))
    assert path.endswith(".md")
    assert os.path.exists(path)


def test_export_report_unknown_format_falls_back_to_markdown(tmp_path):
    out = tmp_path / "fallback"
    path = report_module.export_report(SAMPLE_CONTENT, "q", str(out), "unsupported")
    assert path.endswith(".md")
    assert os.path.exists(path)


def test_get_export_formats_always_includes_md():
    formats = report_module.get_export_formats()
    assert "md" in formats
    # 已安装的可选格式应出现（环境依赖）
    if report_module.REPORTLAB_AVAILABLE:
        assert "pdf" in formats
    if report_module.Document:
        assert "docx" in formats
    if report_module.OPENPYXL_AVAILABLE:
        assert "xlsx" in formats


def test_export_pdf_truncates_very_long_content(tmp_path, monkeypatch):
    long_content = "情报内容 " * 5000  # 远超 15000 字符上限
    out = tmp_path / "long.pdf"
    path = report_module.export_pdf(long_content, "q", str(out))
    assert os.path.exists(path)
    assert out.read_bytes()[:5].startswith(b"%PDF")


def test_clean_content_removes_special_chars():
    dirty = "正常文本■★✓异常符号"
    cleaned = report_module._clean_content(dirty)
    assert "■" not in cleaned
    assert "★" not in cleaned
    assert "正常文本" in cleaned


def test_clean_markdown_for_word_strips_symbols():
    md = "# 标题\n**粗体** 与 *斜体* 和 `代码`"
    cleaned = report_module._clean_markdown_for_word(md)
    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "粗体" in cleaned
    assert "代码" in cleaned
