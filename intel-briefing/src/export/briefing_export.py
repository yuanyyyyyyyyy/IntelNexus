"""
简报PDF导出
============
将简报Markdown转换为PDF文件
"""

import os
import re
from src.logger import get_logger

logger = get_logger(__name__)


def export_briefing_pdf(briefing_md: str, output_path: str) -> str:
    """
    将简报Markdown导出为PDF

    Args:
        briefing_md: 简报Markdown内容
        output_path: 输出PDF路径

    Returns:
        str: 输出文件路径
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics

        _register_chinese_font()

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=2.5*cm, rightMargin=2.5*cm,
            topMargin=2.5*cm, bottomMargin=2.5*cm
        )

        styles = getSampleStyleSheet()
        _add_chinese_styles(styles)

        story = []
        lines = briefing_md.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 12))
                continue

            if line.startswith("# "):
                text = _clean_md_inline(line[2:])
                story.append(Paragraph(text, styles['ChTitle']))
            elif line.startswith("## "):
                text = _clean_md_inline(line[3:])
                story.append(Paragraph(text, styles['ChHeading2']))
            elif line.startswith("### "):
                text = _clean_md_inline(line[4:])
                story.append(Paragraph(text, styles['ChHeading3']))
            elif line.startswith("- ") or line.startswith("* "):
                text = _clean_md_inline(line[2:])
                story.append(Paragraph(f"\u2022 {text}", styles['ChNormal']))
            elif line.startswith("---"):
                story.append(Spacer(1, 6))
            else:
                text = _clean_md_inline(line)
                story.append(Paragraph(text, styles['ChNormal']))

        doc.build(story)
        logger.info(f"Briefing PDF exported: {output_path}")
        return output_path

    except ImportError:
        logger.error("reportlab not installed. Cannot export PDF.")
        raise
    except Exception as e:
        logger.error(f"Error exporting PDF: {e}")
        raise


def _clean_md_inline(text: str) -> str:
    """清理Markdown内联格式，保留纯文本"""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text


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
                pdfmetrics.registerFont(TTFont('ChineseFont', path))
                return
            except Exception:
                continue

    logger.warning("No Chinese font found, PDF may not display Chinese correctly")


def _add_chinese_styles(styles):
    """添加中文样式"""
    from reportlab.lib.styles import ParagraphStyle

    styles.add(ParagraphStyle(
        'ChTitle', parent=styles['Title'],
        fontName='ChineseFont', fontSize=18, spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        'ChHeading2', parent=styles['Heading2'],
        fontName='ChineseFont', fontSize=14, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        'ChHeading3', parent=styles['Heading3'],
        fontName='ChineseFont', fontSize=12, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'ChNormal', parent=styles['Normal'],
        fontName='ChineseFont', fontSize=10, leading=16
    ))
