"""
简报PDF导出
============
将《AI 与网络安全每日情报简报》Markdown 导出为品牌化 PDF：
- 每页 running 页眉（标题 | 机构）与页脚（机构 · 每日情报简报 第 N 页）
- 封面（标题 + 日期 + 机构 + 出品单位）
- 章节/子章节标题、CVE 表格、落款块
- 品牌信息来自 organization 配置，不写死任何品牌
"""

import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# CVE 表格列宽（合计约 16cm，匹配 A4 内容区）
_CVE_COL_WIDTHS = [3.2 * cm, 3.0 * cm, 2.6 * cm, 1.4 * cm, 2.4 * cm, 3.4 * cm]


def export_briefing_pdf(briefing_md: str, output_path: str, organization: dict = None) -> str:
    """
    将简报Markdown导出为品牌化PDF

    Args:
        briefing_md: 简报Markdown内容
        output_path: 输出PDF路径
        organization: BRIEFING_CONFIG["organization"] 字典（None 时读取配置）

    Returns:
        str: 输出文件路径
    """
    try:
        from intelnexus.briefing.config import BRIEFING_CONFIG

        org = organization or BRIEFING_CONFIG.get("organization", {})
        org_name = org.get("name", "")

        _register_chinese_font()
        styles = getSampleStyleSheet()
        _add_chinese_styles(styles)

        header_text = f"AI 与网络安全每日情报简报  |  {org_name}"
        footer_base = f"{org_name} · 每日情报简报"

        story = _build_story(briefing_md, styles)

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=2.5 * cm, rightMargin=2.5 * cm,
            topMargin=2.0 * cm, bottomMargin=2.0 * cm,
            title="AI 与网络安全每日情报简报"
        )

        def _decorate(canvas, d):
            _on_page(canvas, d, header_text, footer_base)

        doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
        logger.info(f"Briefing PDF exported: {output_path}")
        return output_path

    except ImportError:
        logger.error("reportlab not installed. Cannot export PDF.")
        raise
    except Exception as e:
        logger.error(f"Error exporting PDF: {e}")
        raise


def _on_page(canvas, doc, header_text: str, footer_base: str):
    """每页页眉/页脚回调"""
    canvas.saveState()
    w, h = A4

    # 页眉
    canvas.setFont("ChineseFont", 9)
    canvas.setFillColorRGB(0.45, 0.45, 0.45)
    canvas.drawString(2.5 * cm, h - 1.2 * cm, header_text)
    canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
    canvas.line(2.5 * cm, h - 1.4 * cm, w - 2.5 * cm, h - 1.4 * cm)

    # 页脚
    canvas.drawString(2.5 * cm, 1.2 * cm, footer_base)
    canvas.drawRightString(w - 2.5 * cm, 1.2 * cm, f"第 {doc.page} 页")
    canvas.restoreState()


def _build_story(md: str, styles) -> list:
    """将 Markdown 解析为 reportlab flowables"""
    story = []
    lines = md.strip().split("\n")
    n = len(lines)
    i = 0
    cover_done = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 封面（首个 H1）
        if stripped.startswith("# ") and not cover_done:
            title = _clean_md_inline(stripped[2:])
            story.append(Paragraph(title, styles["ChCoverTitle"]))

            # 消费紧随其后的 **副标题** 行，直到 --- 或空行
            j = i + 1
            subs = []
            while j < n:
                s2 = lines[j].strip()
                if s2.startswith("---") or s2 == "":
                    j += 1
                    break
                if s2.startswith("**") and s2.endswith("**"):
                    subs.append(_clean_md_inline(s2[2:-2]))
                    j += 1
                else:
                    break
            for s in subs:
                story.append(Paragraph(s, styles["ChCoverSub"]))

            story.append(Spacer(1, 14))
            story.append(HRFlowable(
                width="100%", color=colors.HexColor("#1F4E88"),
                thickness=1.5, spaceAfter=12
            ))
            i = j
            cover_done = True
            continue

        # 落款块（<!-- FOOTER --> 或 — 简报结束 —）
        if stripped == "<!-- FOOTER -->" or stripped == "— 简报结束 —":
            story.append(Spacer(1, 12))
            k = i + 1 if stripped == "<!-- FOOTER -->" else i
            footer_lines = []
            while k < n:
                t = lines[k].strip()
                if t:
                    footer_lines.append(_clean_md_inline(t))
                k += 1
            for fl in footer_lines:
                story.append(Paragraph(fl, styles["ChFooter"]))
            break

        # CVE 表格
        if "|" in stripped and i + 1 < n and _is_table_sep(lines[i + 1].strip()):
            header_cells = _split_md_row(stripped)
            j = i + 2
            body = []
            while j < n and "|" in lines[j].strip() and lines[j].strip():
                body.append(_split_md_row(lines[j].strip()))
                j += 1
            story.append(_make_cve_table(header_cells, body, styles))
            i = j
            continue

        # 标题
        if stripped.startswith("## "):
            story.append(Paragraph(_clean_md_inline(stripped[3:]), styles["ChHeading2"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(_clean_md_inline(stripped[4:]), styles["ChHeading3"]))
        elif stripped.startswith("# "):
            story.append(Paragraph(_clean_md_inline(stripped[2:]), styles["ChTitle"]))
        elif stripped == "---":
            story.append(Spacer(1, 8))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            story.append(Paragraph("• " + _clean_md_inline(stripped[2:]), styles["ChNormal"]))
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".):":
            story.append(Paragraph(
                stripped[0] + ". " + _clean_md_inline(stripped[2:].strip()),
                styles["ChNormal"]
            ))
        else:
            story.append(Paragraph(_clean_md_inline(stripped), styles["ChNormal"]))

        i += 1

    return story


def _make_cve_table(header: list, body: list, styles) -> Table:
    """渲染 CVE 漏洞表格"""
    data = [[Paragraph(c, styles["ChCellHead"]) for c in header]]
    for row in body:
        data.append([Paragraph(c, styles["ChCell"]) for c in row])

    t = Table(data, colWidths=_CVE_COL_WIDTHS, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3fb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _clean_md_inline(text: str) -> str:
    """清理Markdown内联格式，保留纯文本（并转义XML特殊字符）"""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text


def _is_table_sep(line: str) -> bool:
    if "|" not in line:
        return False
    cleaned = line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
    return cleaned == ""


def _split_md_row(line: str) -> list:
    parts = line.split("|")
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _register_chinese_font():
    """注册中文字体"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", path))
                return
            except Exception:
                continue

    logger.warning("No Chinese font found, PDF may not display Chinese correctly")


def _add_chinese_styles(styles):
    """添加中文样式"""
    styles.add(ParagraphStyle(
        "ChTitle", parent=styles["Title"],
        fontName="ChineseFont", fontSize=18, spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        "ChCoverTitle", parent=styles["Title"],
        fontName="ChineseFont", fontSize=22, alignment=TA_CENTER,
        textColor=colors.HexColor("#1F4E88"), spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        "ChCoverSub", parent=styles["Normal"],
        fontName="ChineseFont", fontSize=11, alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"), spaceAfter=4, leading=16
    ))
    styles.add(ParagraphStyle(
        "ChHeading2", parent=styles["Heading2"],
        fontName="ChineseFont", fontSize=15, spaceBefore=10, spaceAfter=8,
        textColor=colors.HexColor("#1F4E88")
    ))
    styles.add(ParagraphStyle(
        "ChHeading3", parent=styles["Heading3"],
        fontName="ChineseFont", fontSize=12.5, spaceBefore=8, spaceAfter=6,
        textColor=colors.HexColor("#2E5A88")
    ))
    styles.add(ParagraphStyle(
        "ChNormal", parent=styles["Normal"],
        fontName="ChineseFont", fontSize=10, leading=15
    ))
    styles.add(ParagraphStyle(
        "ChFooter", parent=styles["Normal"],
        fontName="ChineseFont", fontSize=9.5, alignment=TA_CENTER,
        textColor=colors.HexColor("#888888"), spaceAfter=3, leading=14
    ))
    styles.add(ParagraphStyle(
        "ChCellHead", parent=styles["Normal"],
        fontName="ChineseFont", fontSize=9, leading=12,
        textColor=colors.HexColor("#1F4E88")
    ))
    styles.add(ParagraphStyle(
        "ChCell", parent=styles["Normal"],
        fontName="ChineseFont", fontSize=9, leading=12
    ))
