"""
AI简报模板
=========
定义简报的Markdown和HTML格式模板
"""

import html
import re
from datetime import datetime


# ========== Markdown简报模板 ==========
MARKDOWN_TEMPLATE = """
# 🔐 AI领域每日情报简报

**{generated_date}**
**{organization_name}**

---

## 📌 近日要闻TOP3

{top3_section}

---

## 🏛️ 美欧机构AI应用动态

{ai_gov_usage_section}

---

## 🇨🇳 涉我AI舆论动态

{ai_china_narrative_section}

---

## 📜 AI新法案与政策

{ai_legislation_section}

---

## 🔒 AI数据泄露与安全事件

{ai_data_leak_section}

---

## 💡 趋势研判与防护建议

{insights_section}

---

## 📚 重要链接

{links_section}

---

*本简报基于公开信息整理，不构成投资或其他专业建议。*
*{organization_name}*
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
<h1 style="color:#1F4E88;margin:0;font-size:24px;">🔐 AI领域每日情报简报</h1>
<p style="color:#666;font-size:14px;margin:10px 0 0;">{generated_date}</p>
<p style="color:#888;font-size:12px;margin:5px 0 0;">{organization_name}</p>
</td></tr>
<!-- TOP3 -->
<tr><td style="padding:25px 30px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">📌 近日要闻TOP3</h2>
{top3_html}
</td></tr>
<!-- 美欧机构AI应用动态 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">🏛️ 美欧机构AI应用动态</h2>
{ai_gov_usage_html}
</td></tr>
<!-- 涉我AI舆论动态 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">🇨🇳 涉我AI舆论动态</h2>
{ai_china_narrative_html}
</td></tr>
<!-- AI新法案与政策 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">📜 AI新法案与政策</h2>
{ai_legislation_html}
</td></tr>
<!-- AI数据泄露与安全事件 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">🔒 AI数据泄露与安全事件</h2>
{ai_data_leak_html}
</td></tr>
<!-- 趋势研判与防护建议 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">💡 趋势研判与防护建议</h2>
{insights_html}
</td></tr>
<!-- 重要链接 -->
<tr><td style="padding:0 30px 25px;">
<h2 style="color:#1F4E88;border-left:4px solid #1F4E88;padding-left:10px;font-size:18px;margin:0 0 15px;">📚 重要链接</h2>
{links_html}
</td></tr>
<!-- Footer -->
<tr><td style="padding:20px 30px;border-top:1px solid #ddd;text-align:center;color:#888;font-size:12px;">
<p style="margin:5px 0;">本简报基于公开信息整理，不构成投资或其他专业建议。</p>
<p style="margin:5px 0;">{organization_name}</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def _md_to_html(text: str) -> str:
    """
    简单的 Markdown 转 HTML（内联样式，兼容邮件客户端）
    对用户/LLM内容做HTML转义，防止XSS。
    
    Args:
        text: Markdown格式的文本
    
    Returns:
        str: 带内联样式的HTML
    """
    lines = text.strip().split("\n")
    html_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append('<p style="margin:5px 0;height:16px;">&nbsp;</p>')
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
        # 分割线
        elif stripped == "---":
            html_lines.append('<hr style="border:none;border-top:1px solid #ddd;margin:15px 0;">')
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
    
    return "\n".join(html_lines)


def render_markdown_briefing(
    generated_date: str,
    organization_name: str,
    top3_content: str,
    ai_gov_usage_content: str,
    ai_china_narrative_content: str,
    ai_legislation_content: str,
    ai_data_leak_content: str,
    insights_content: str,
    links_content: str
) -> str:
    """
    渲染Markdown格式的简报
    
    Returns:
        str: Markdown格式的简报内容
    """
    return MARKDOWN_TEMPLATE.format(
        generated_date=generated_date,
        organization_name=organization_name,
        top3_section=top3_content,
        ai_gov_usage_section=ai_gov_usage_content,
        ai_china_narrative_section=ai_china_narrative_content,
        ai_legislation_section=ai_legislation_content,
        ai_data_leak_section=ai_data_leak_content,
        insights_section=insights_content,
        links_section=links_content
    )


def render_email_html(
    generated_date: str,
    organization_name: str,
    top3_html: str,
    ai_gov_usage_html: str,
    ai_china_narrative_html: str,
    ai_legislation_html: str,
    ai_data_leak_html: str,
    insights_html: str,
    links_html: str
) -> str:
    """
    渲染HTML格式的邮件简报
    
    Returns:
        str: HTML格式的简报内容
    """
    return EMAIL_HTML_TEMPLATE.format(
        generated_date=generated_date,
        organization_name=organization_name,
        top3_html=top3_html,
        ai_gov_usage_html=ai_gov_usage_html,
        ai_china_narrative_html=ai_china_narrative_html,
        ai_legislation_html=ai_legislation_html,
        ai_data_leak_html=ai_data_leak_html,
        insights_html=insights_html,
        links_html=links_html
    )


def markdown_to_html_sections(markdown_content: str) -> dict:
    """
    将Markdown内容转换为HTML各部分内容
    
    Args:
        markdown_content: 完整的Markdown简报内容
    
    Returns:
        dict: 各部分的HTML内容
    """
    sections = {
        "top3_html": "",
        "ai_gov_usage_html": "",
        "ai_china_narrative_html": "",
        "ai_legislation_html": "",
        "ai_data_leak_html": "",
        "insights_html": "",
        "links_html": ""
    }
    
    lines = markdown_content.split("\n")
    current_section = None
    section_content = []
    
    for line in lines:
        if "近日要闻TOP3" in line:
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "top3_html"
            section_content = []
        elif "美欧机构AI应用动态" in line:
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "ai_gov_usage_html"
            section_content = []
        elif "涉我AI舆论动态" in line:
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "ai_china_narrative_html"
            section_content = []
        elif "AI新法案与政策" in line:
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "ai_legislation_html"
            section_content = []
        elif "AI数据泄露与安全事件" in line:
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "ai_data_leak_html"
            section_content = []
        elif "趋势研判与防护建议" in line:
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "insights_html"
            section_content = []
        elif "重要链接" in line:
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "links_html"
            section_content = []
        elif current_section:
            section_content.append(line)
    
    if current_section and section_content:
        sections[current_section] = "\n".join(section_content)
    
    # 将每个section的Markdown内容转换为HTML
    for key in sections:
        if sections[key]:
            sections[key] = _md_to_html(sections[key])
    
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
    <title>AI情报简报 - {generated_date}</title>
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
            <h1>🔐 AI领域每日情报简报</h1>
            <p class="subtitle">{generated_date} | {organization_name}</p>
        </div>
        
        <div class="section">
            <h2>📌 近日要闻TOP3</h2>
            {top3_content}
        </div>
        
        <div class="section">
            <h2>🏛️ 美欧机构AI应用动态</h2>
            {ai_gov_usage_content}
        </div>
        
        <div class="section">
            <h2>🇨🇳 涉我AI舆论动态</h2>
            {ai_china_narrative_content}
        </div>
        
        <div class="section">
            <h2>📜 AI新法案与政策</h2>
            {ai_legislation_content}
        </div>
        
        <div class="section">
            <h2>🔒 AI数据泄露与安全事件</h2>
            {ai_data_leak_content}
        </div>
        
        <div class="section">
            <h2>💡 趋势研判与防护建议</h2>
            {insights_content}
        </div>
        
        <div class="section">
            <h2>📚 重要链接</h2>
            {links_content}
        </div>
        
        <div class="footer">
            <p>本简报基于公开信息整理，不构成投资或其他专业建议。</p>
            <p>{organization_name}</p>
        </div>
    </div>
</body>
</html>"""


def render_standalone_html(
    generated_date: str,
    organization_name: str,
    top3_content: str,
    ai_gov_usage_content: str,
    ai_china_narrative_content: str,
    ai_legislation_content: str,
    ai_data_leak_content: str,
    insights_content: str,
    links_content: str
) -> str:
    """渲染简报独立HTML（浏览器/PDF用）"""
    return BRIEFING_STANDALONE_HTML.format(
        generated_date=generated_date,
        organization_name=organization_name,
        top3_content=top3_content,
        ai_gov_usage_content=ai_gov_usage_content,
        ai_china_narrative_content=ai_china_narrative_content,
        ai_legislation_content=ai_legislation_content,
        ai_data_leak_content=ai_data_leak_content,
        insights_content=insights_content,
        links_content=links_content
    )
