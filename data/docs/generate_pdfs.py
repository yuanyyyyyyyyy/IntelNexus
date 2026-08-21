"""
Markdown to PDF converter using reportlab with Chinese font support.
"""
import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def setup_fonts():
    font_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    try:
        pdfmetrics.registerFont(TTFont("YaHei", os.path.join(font_dir, "msyh.ttc"), subfontIndex=0))
        return "YaHei"
    except:
        pass
    try:
        pdfmetrics.registerFont(TTFont("SimSun", os.path.join(font_dir, "simsun.ttc"), subfontIndex=0))
        return "SimSun"
    except:
        pass
    return "Helvetica"


def get_styles(font_name):
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "MdH1", parent=styles["Title"], fontName=font_name, fontSize=18,
        spaceAfter=10, textColor=HexColor("#1a1a1a"), leading=24
    ))
    styles.add(ParagraphStyle(
        "MdH2", parent=styles["Heading1"], fontName=font_name, fontSize=14,
        spaceBefore=16, spaceAfter=8, textColor=HexColor("#2a2a2a"), leading=18
    ))
    styles.add(ParagraphStyle(
        "MdH3", parent=styles["Heading2"], fontName=font_name, fontSize=12,
        spaceBefore=12, spaceAfter=6, textColor=HexColor("#3a3a3a"), leading=16
    ))
    styles.add(ParagraphStyle(
        "MdBody", parent=styles["Normal"], fontName=font_name, fontSize=9,
        spaceBefore=2, spaceAfter=4, leading=14, textColor=HexColor("#333333")
    ))
    styles.add(ParagraphStyle(
        "MdBullet", parent=styles["Normal"], fontName=font_name, fontSize=9,
        leftIndent=16, spaceBefore=1, spaceAfter=2, leading=14,
        bulletIndent=6, textColor=HexColor("#333333")
    ))
    styles.add(ParagraphStyle(
        "MdQuote", parent=styles["Normal"], fontName=font_name, fontSize=9,
        leftIndent=12, spaceBefore=4, spaceAfter=4, leading=14,
        textColor=HexColor("#666666"), backColor=HexColor("#f5f5f5")
    ))
    styles.add(ParagraphStyle(
        "MdCode", fontName="Courier", fontSize=8,
        spaceBefore=4, spaceAfter=4, leading=11,
        backColor=HexColor("#f5f5f5"), leftIndent=8
    ))
    return styles


def clean_md(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier" size="8">\1</font>', text)
    return text


def md_to_pdf(md_path, pdf_path):
    font_name = setup_fonts()
    styles = get_styles(font_name)

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )

    story = []

    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    in_code = False
    code_buf = []

    while i < len(lines):
        line = lines[i].rstrip("\n")

        # Code block
        if line.strip().startswith("```"):
            if in_code:
                code_text = clean_md("\n".join(code_buf))
                story.append(Paragraph(code_text.replace("\n", "<br/>"), styles["MdCode"]))
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Empty
        if not line.strip():
            story.append(Spacer(1, 4))
            i += 1
            continue

        # HR
        if line.strip() in ("---", "***", "___"):
            story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#dddddd"),
                                     spaceBefore=8, spaceAfter=8))
            i += 1
            continue

        # H1
        if line.startswith("# ") and not line.startswith("## "):
            story.append(Paragraph(clean_md(line[2:]), styles["MdH1"]))
            i += 1
            continue

        # H2
        if line.startswith("## ") and not line.startswith("### "):
            story.append(Paragraph(clean_md(line[3:]), styles["MdH2"]))
            i += 1
            continue

        # H3
        if line.startswith("### "):
            story.append(Paragraph(clean_md(line[4:]), styles["MdH3"]))
            i += 1
            continue

        # Table
        if "|" in line and line.strip().startswith("|"):
            table_data = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if re.match(r"^\|[\s\-:|]+\|$", row):
                    i += 1
                    continue
                cells = [c.strip().replace("**", "") for c in row.split("|")[1:-1]]
                table_data.append(cells)
                i += 1

            if table_data and any(len(r) > 0 for r in table_data):
                # Convert to Paragraphs for proper wrapping
                tbl_style_data = [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e0e0e0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#dddddd")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]

                styled_data = []
                for ri, row in enumerate(table_data):
                    styled_row = []
                    for cell in row:
                        if ri == 0:
                            styled_row.append(Paragraph(f"<b>{clean_md(cell)}</b>", styles["MdBody"]))
                        else:
                            styled_row.append(Paragraph(clean_md(cell), styles["MdBody"]))
                    styled_data.append(styled_row)

                ncols = max(len(r) for r in styled_data) if styled_data else 1
                col_w = (170*mm) / ncols if ncols > 0 else 170*mm
                t = Table(styled_data, colWidths=[col_w]*ncols)
                t.setStyle(TableStyle(tbl_style_data))
                story.append(Spacer(1, 6))
                story.append(t)
                story.append(Spacer(1, 6))
            continue

        # Blockquote
        if line.startswith("> "):
            story.append(Paragraph(clean_md(line[2:]), styles["MdQuote"]))
            i += 1
            continue

        # Bullet
        if re.match(r"^[-*]\s", line):
            text = re.sub(r"^[-*]\s", "", line)
            story.append(Paragraph(f"\u2022  {clean_md(text)}", styles["MdBullet"]))
            i += 1
            continue

        # Numbered list
        if re.match(r"^\d+\.\s", line):
            m = re.match(r"^(\d+)\.\s(.+)", line)
            story.append(Paragraph(f"{m.group(1)}. {clean_md(m.group(2))}", styles["MdBullet"]))
            i += 1
            continue

        # Normal
        story.append(Paragraph(clean_md(line), styles["MdBody"]))
        i += 1

    doc.build(story)
    print(f"OK: {pdf_path}")


if __name__ == "__main__":
    d = os.path.dirname(os.path.abspath(__file__))
    for md, pdf in [
        ("architecture-one-pager-cn.md", "architecture-one-pager-cn.pdf"),
        ("architecture-one-pager-en.md", "architecture-one-pager-en.pdf"),
        ("interview-qa-cn.md", "interview-qa-cn.pdf"),
        ("interview-qa-en.md", "interview-qa-en.pdf"),
    ]:
        p1 = os.path.join(d, md)
        p2 = os.path.join(d, pdf)
        if os.path.exists(p1):
            try:
                md_to_pdf(p1, p2)
            except Exception as e:
                print(f"Error {md}: {e}")
