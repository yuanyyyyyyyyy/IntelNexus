"""
AI简报模板
=========
定义简报的Markdown、邮件HTML、独立HTML模板。
目标风格：《AI 与网络安全每日情报简报》（封面 + 双主板块 + CVE 表格 + 落款）。
品牌落款全部来自 organization 配置，不写死任何品牌。
"""

import html
import re


# ========== Markdown简报模板 ==========
MARKDOWN_TEMPLATE = """
# AI 与网络安全每日情报简报

**{generated_date}**
**{org_name}**
{producer_unit_cover}
---

## 近日要闻 TOP3

{top3_content}

---

## 本期增量速览（对比上期）

{delta_content}

---

## AI 领域动态

{ai_dynamic_content}

---

## 网络安全动态

{cyber_dynamic_content}

---

## 近日新增安全漏洞预警

{cve_table_content}

---

## 趋势研判与防护建议

{insights_content}

---

## 重要链接

{links_content}

---
<!-- FOOTER -->
— 简报结束 —

{disclaimer}

{footer_qr_block}
{org_name_footer}
{producer_unit_footer}
{contact_footer}
"""


# ========== 邮件HTML模板（table布局，兼容Gmail/Outlook） ==========
EMAIL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:'Microsoft YaHei','Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;">
<tr><td align="center" style="padding:20px;">
<table width="800" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;">
<!-- Header -->
<tr><td style="text-align:center;padding:30px 30px 20px;border-bottom:2px solid #1F4E88;">
<h1 style="color:#1F4E88;margin:0;font-size:24px;">AI 与网络安全每日情报简报</h1>
<p style="color:#666;font-size:14px;margin:10px 0 0;">{generated_date}</p>
<p style="color:#888;font-size:12px;margin:5px 0 0;">{org_name}{producer_unit_header}</p>
</td></tr>
<!-- TOP3 -->
<tr><td style="padding:25px 30px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">近日要闻 TOP3</h2>
{top3_html}
</td></tr>
<!-- 本期增量速览 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">本期增量速览（对比上期）</h2>
{delta_html}
</td></tr>
<!-- AI 领域动态 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">AI 领域动态</h2>
{ai_dynamic_html}
</td></tr>
<!-- 网络安全动态 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">网络安全动态</h2>
{cyber_dynamic_html}
</td></tr>
<!-- 近日新增安全漏洞预警 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">近日新增安全漏洞预警</h2>
{cve_table_html}
</td></tr>
<!-- 趋势研判与防护建议 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">趋势研判与防护建议</h2>
{insights_html}
</td></tr>
<!-- 重要链接 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">重要链接</h2>
{links_html}
</td></tr>
<!-- Footer -->
<tr><td style="padding:20px 30px;border-top:1px solid #ddd;text-align:center;color:#888;font-size:12px;">
<p style="margin:5px 0;">— 简报结束 —</p>
<p style="margin:5px 0;">{disclaimer}</p>
{footer_qr_html}
<p style="margin:5px 0;">{org_name}</p>
{producer_unit_footer_html}
{contact_footer_html}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def _md_to_html(text: str) -> str:
    """
    简单的 Markdown 转 HTML（内联样式，兼容邮件客户端）。
    支持：标题、分割线、有序/无序列表、粗体、以及 Markdown 表格（| 分隔）。
    对用户/LLM内容做HTML转义，防止XSS。
    """
    lines = text.strip().split("\n")
    html_lines = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            html_lines.append('<p style="margin:5px 0;height:16px;">&nbsp;</p>')
            i += 1
            continue

        # Markdown 表格检测：`|` 行 + 下一行分隔符 `|---|`
        if "|" in stripped and i + 1 < n and _is_table_sep(lines[i + 1].strip()):
            header_cells = _split_md_row(stripped)
            j = i + 2
            body = []
            while j < n:
                s2 = lines[j].strip()
                if "|" in s2 and s2:
                    body.append(_split_md_row(s2))
                    j += 1
                else:
                    break
            thead = "<tr>" + "".join(
                f"<th style='border:1px solid #ccc;padding:5px 8px;background:#eef3fb;color:#1F4E88;'>{html.escape(c)}</th>"
                for c in header_cells
            ) + "</tr>"
            tbody = ""
            for r in body:
                tbody += "<tr>" + "".join(
                    f"<td style='border:1px solid #ccc;padding:5px 8px;'>{html.escape(c)}</td>"
                    for c in r
                ) + "</tr>"
            html_lines.append(
                f"<table style='border-collapse:collapse;width:100%;font-size:13px;"
                f"margin:10px 0;'>{thead}{tbody}</table>"
            )
            i = j
            continue

        # 分割线
        if stripped == "---" or stripped == "<!-- FOOTER -->":
            html_lines.append('<hr style="border:none;border-top:1px solid #ddd;margin:15px 0;">')
            i += 1
            continue

        # 标题
        if stripped.startswith("### "):
            safe = html.escape(stripped[4:])
            html_lines.append(
                f'<h3 style="color:#2E5A88;font-size:15px;margin:15px 0 8px;">{safe}</h3>'
            )
        elif stripped.startswith("## "):
            safe = html.escape(stripped[3:])
            html_lines.append(
                f'<h2 style="color:#1F4E88;font-size:18px;margin:20px 0 10px;">{safe}</h2>'
            )
        elif stripped.startswith("# "):
            safe = html.escape(stripped[2:])
            html_lines.append(
                f'<h1 style="color:#1F4E88;font-size:24px;margin:20px 0 10px;">{safe}</h1>'
            )
        # 无序列表
        elif stripped.startswith("- ") or stripped.startswith("* "):
            item = html.escape(stripped[2:])
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            html_lines.append(
                f'<p style="margin:5px 0;padding-left:20px;">• {item}</p>'
            )
        # 有序列表（简单处理）
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.):':
            item = html.escape(stripped[2:].strip())
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            num = stripped[0]
            html_lines.append(
                f'<p style="margin:5px 0;padding-left:20px;">{num}. {item}</p>'
            )
        # 粗体段落
        elif stripped.startswith("**") and stripped.endswith("**"):
            safe = html.escape(stripped[2:-2])
            html_lines.append(
                f'<p style="margin:8px 0;"><strong>{safe}</strong></p>'
            )
        # 普通段落（处理行内粗体）
        else:
            processed = html.escape(stripped)
            processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', processed)
            html_lines.append(f'<p style="margin:5px 0;">{processed}</p>')

        i += 1

    return "\n".join(html_lines)


def _is_table_sep(line: str) -> bool:
    """判断是否为 Markdown 表格分隔行，如 | --- | --- |"""
    if "|" not in line:
        return False
    cleaned = line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
    return cleaned == ""


def _split_md_row(line: str) -> list:
    """拆分 Markdown 表格行，去除首尾空单元格"""
    parts = line.split("|")
    # 去掉行首/行尾因边界 | 产生的空串
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def render_markdown_briefing(
    generated_date: str,
    organization: dict,
    top3_content: str,
    delta_content: str = "",
    ai_dynamic_content: str = "",
    cyber_dynamic_content: str = "",
    cve_table_content: str = "",
    insights_content: str = "",
    links_content: str = ""
) -> str:
    """
    渲染Markdown格式的简报

    Args:
        generated_date: 中文星期日期
        organization: BRIEFING_CONFIG["organization"] 字典
        ...各板块内容

    Returns:
        str: Markdown格式的简报内容
    """
    org_name = organization.get("name", "")
    producer_unit = organization.get("producer_unit", "")
    contact = organization.get("contact", "")
    footer_qr = organization.get("footer_qr_text", "")
    disclaimer = organization.get(
        "disclaimer", "本简报基于公开信息整理，不构成投资或其他专业建议。"
    )

    producer_unit_cover = f"**出品单位：** {producer_unit}\n" if producer_unit else ""
    footer_qr_block = f"扫码关注 · {footer_qr}\n" if footer_qr else ""
    producer_unit_footer = f"出品单位：{producer_unit}\n" if producer_unit else ""
    contact_footer = f"联系人：{contact}\n" if contact else ""

    return MARKDOWN_TEMPLATE.format(
        generated_date=generated_date,
        org_name=org_name,
        producer_unit_cover=producer_unit_cover,
        top3_content=top3_content,
        delta_content=delta_content,
        ai_dynamic_content=ai_dynamic_content,
        cyber_dynamic_content=cyber_dynamic_content,
        cve_table_content=cve_table_content,
        insights_content=insights_content,
        links_content=links_content,
        disclaimer=disclaimer,
        footer_qr_block=footer_qr_block,
        org_name_footer=org_name,
        producer_unit_footer=producer_unit_footer,
        contact_footer=contact_footer
    )


def render_email_html(
    generated_date: str,
    organization: dict,
    top3_html: str,
    delta_html: str = "",
    ai_dynamic_html: str = "",
    cyber_dynamic_html: str = "",
    cve_table_html: str = "",
    insights_html: str = "",
    links_html: str = ""
) -> str:
    """
    渲染HTML格式的邮件简报

    Args:
        generated_date: 中文星期日期
        organization: BRIEFING_CONFIG["organization"] 字典
        ...各板块HTML
    """
    org_name = organization.get("name", "")
    producer_unit = organization.get("producer_unit", "")
    contact = organization.get("contact", "")
    footer_qr = organization.get("footer_qr_text", "")
    disclaimer = organization.get(
        "disclaimer", "本简报基于公开信息整理，不构成投资或其他专业建议。"
    )

    producer_unit_header = f" · 出品单位：{producer_unit}" if producer_unit else ""
    footer_qr_html = f"<p style='margin:5px 0;'>扫码关注 · {html.escape(footer_qr)}</p>" if footer_qr else ""
    producer_unit_footer_html = f"<p style='margin:5px 0;'>出品单位：{html.escape(producer_unit)}</p>" if producer_unit else ""
    contact_footer_html = f"<p style='margin:5px 0;'>联系人：{html.escape(contact)}</p>" if contact else ""

    return EMAIL_HTML_TEMPLATE.format(
        generated_date=generated_date,
        org_name=org_name,
        producer_unit_header=producer_unit_header,
        top3_html=top3_html,
        delta_html=delta_html,
        ai_dynamic_html=ai_dynamic_html,
        cyber_dynamic_html=cyber_dynamic_html,
        cve_table_html=cve_table_html,
        insights_html=insights_html,
        links_html=links_html,
        disclaimer=html.escape(disclaimer),
        footer_qr_html=footer_qr_html,
        producer_unit_footer_html=producer_unit_footer_html,
        contact_footer_html=contact_footer_html
    )


SECTION_MAP = {
    "近日要闻 TOP3": "top3_html",
    "本期增量速览（对比上期）": "delta_html",
    "AI 领域动态": "ai_dynamic_html",
    "网络安全动态": "cyber_dynamic_html",
    "近日新增安全漏洞预警": "cve_table_html",
    "趋势研判与防护建议": "insights_html",
    "重要链接": "links_html",
}


def markdown_to_html_sections(markdown_content: str) -> dict:
    """
    将Markdown内容转换为HTML各部分内容

    Args:
        markdown_content: 完整的Markdown简报内容

    Returns:
        dict: 各部分的HTML内容
    """
    sections = {key: "" for key in SECTION_MAP.values()}

    lines = markdown_content.split("\n")
    current_section = None
    section_content = []

    for line in lines:
        # 遇到页脚标记，停止向链接板块追加（页脚由邮件/独立HTML模板单独渲染）
        if line.strip() == "<!-- FOOTER -->":
            if current_section and section_content:
                sections[current_section] = _md_to_html("\n".join(section_content))
            break

        matched = False
        for header_text, section_key in SECTION_MAP.items():
            if header_text in line:
                if current_section and section_content:
                    sections[current_section] = _md_to_html("\n".join(section_content))
                current_section = section_key
                section_content = []
                matched = True
                break
        if not matched and current_section:
            section_content.append(line)

    if current_section and section_content and current_section not in sections:
        sections[current_section] = _md_to_html("\n".join(section_content))

    # 确保全部 section 都有 HTML（未命中的保持空串）
    for key in sections:
        if not sections[key]:
            sections[key] = ""

    return sections


def format_news_item(title: str, content: str, source: str, date: str, tag: str = "") -> str:
    """
    格式化单条新闻为Markdown格式

    Args:
        title: 新闻标题
        content: 新闻内容
        source: 来源
        date: 日期
        tag: 标签（如 [重要]、[新发布]等）

    Returns:
        str: 格式化的Markdown内容
    """
    tag_str = f"**{tag}** " if tag else ""
    return f"""{tag_str}**{title}**
{content}
（来源：{source} / {date}）
"""


# ========== 简报独立HTML模板（浏览器/PDF用） ==========
BRIEFING_STANDALONE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 与网络安全每日情报简报 - {generated_date}</title>
    <style>
        :root {{
            --bg-primary: #f8f9fa;
            --bg-card: #ffffff;
            --accent: #1F4E88;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --border: #dee2e6;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Source Han Sans SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.8;
            padding: 40px 20px;
        }}

        .container {{ max-width: 900px; margin: 0 auto; }}

        .header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 3px solid var(--accent);
            margin-bottom: 30px;
        }}

        h1 {{
            font-size: 2rem;
            color: var(--accent);
            margin-bottom: 10px;
        }}

        .subtitle {{ color: var(--text-secondary); }}

        .section {{
            background: var(--bg-card);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .section h2 {{
            font-size: 1.3rem;
            color: var(--accent);
            border-left: 4px solid var(--accent);
            padding-left: 12px;
            margin-bottom: 16px;
        }}

        .section h3 {{
            font-size: 1.1rem;
            color: #495057;
            margin: 16px 0 8px;
        }}

        .section ul {{ padding-left: 20px; }}
        .section li {{ margin-bottom: 12px; }}

        table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 12px 0; }}
        th, td {{ border: 1px solid var(--border); padding: 6px 8px; text-align: left; }}
        th {{ background: #eef3fb; color: var(--accent); }}

        .footer {{
            text-align: center;
            padding: 30px 0;
            margin-top: 40px;
            border-top: 1px solid var(--border);
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        @media print {{
            body {{ padding: 0; background: white; }}
            .section {{ box-shadow: none; border: 1px solid var(--border); break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI 与网络安全每日情报简报</h1>
            <p class="subtitle">{generated_date} | {org_name}{producer_unit_header}</p>
        </div>

        <div class="section">
            <h2>近日要闻 TOP3</h2>
            {top3_content}
        </div>

        <div class="section">
            <h2>本期增量速览（对比上期）</h2>
            {delta_content}
        </div>

        <div class="section">
            <h2>AI 领域动态</h2>
            {ai_dynamic_content}
        </div>

        <div class="section">
            <h2>网络安全动态</h2>
            {cyber_dynamic_content}
        </div>

        <div class="section">
            <h2>近日新增安全漏洞预警</h2>
            {cve_table_content}
        </div>

        <div class="section">
            <h2>趋势研判与防护建议</h2>
            {insights_content}
        </div>

        <div class="section">
            <h2>重要链接</h2>
            {links_content}
        </div>

        <div class="footer">
            <p>— 简报结束 —</p>
            <p>{disclaimer}</p>
            {footer_qr_html}
            <p>{org_name}</p>
            {producer_unit_footer_html}
            {contact_footer_html}
        </div>
    </div>
</body>
</html>"""


def render_standalone_html(
    generated_date: str,
    organization: dict,
    top3_content: str,
    delta_content: str = "",
    ai_dynamic_content: str = "",
    cyber_dynamic_content: str = "",
    cve_table_content: str = "",
    insights_content: str = "",
    links_content: str = ""
) -> str:
    """渲染简报独立HTML（浏览器/PDF用）"""
    org_name = organization.get("name", "")
    producer_unit = organization.get("producer_unit", "")
    contact = organization.get("contact", "")
    footer_qr = organization.get("footer_qr_text", "")
    disclaimer = organization.get(
        "disclaimer", "本简报基于公开信息整理，不构成投资或其他专业建议。"
    )

    producer_unit_header = f" · 出品单位：{producer_unit}" if producer_unit else ""
    footer_qr_html = f"<p>扫码关注 · {html.escape(footer_qr)}</p>" if footer_qr else ""
    producer_unit_footer_html = f"<p>出品单位：{html.escape(producer_unit)}</p>" if producer_unit else ""
    contact_footer_html = f"<p>联系人：{html.escape(contact)}</p>" if contact else ""

    return BRIEFING_STANDALONE_HTML.format(
        generated_date=generated_date,
        org_name=org_name,
        producer_unit_header=producer_unit_header,
        top3_content=top3_content,
        delta_content=delta_content,
        ai_dynamic_content=ai_dynamic_content,
        cyber_dynamic_content=cyber_dynamic_content,
        cve_table_content=cve_table_content,
        insights_content=insights_content,
        links_content=links_content,
        disclaimer=html.escape(disclaimer),
        footer_qr_html=footer_qr_html,
        producer_unit_footer_html=producer_unit_footer_html,
        contact_footer_html=contact_footer_html
    )
