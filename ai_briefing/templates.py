"""
AI简报模板
=========
定义简报的Markdown和HTML格式模板
"""

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


# ========== 邮件HTML模板 ==========
EMAIL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        .header {{
            text-align: center;
            border-bottom: 2px solid #1F4E88;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #1F4E88;
            margin: 0;
        }}
        .header .date {{
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }}
        .header .org {{
            color: #888;
            font-size: 12px;
        }}
        .section {{
            margin-bottom: 25px;
        }}
        .section h2 {{
            color: #1F4E88;
            border-left: 4px solid #1F4E88;
            padding-left: 10px;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        .section h3 {{
            color: #2E5A88;
            margin-top: 15px;
            font-size: 15px;
        }}
        .news-item {{
            margin-bottom: 15px;
            padding: 12px;
            background-color: #f9f9f9;
            border-radius: 6px;
            border-left: 3px solid #1F4E88;
        }}
        .news-item .tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 5px;
        }}
        .tag-important {{ background-color: #e3f2fd; color: #1565c0; }}
        .tag-warning {{ background-color: #fff3e0; color: #e65100; }}
        .tag-danger {{ background-color: #ffebee; color: #c62828; }}
        .tag-info {{ background-color: #e8f5e9; color: #2e7d32; }}
        .tag-new {{ background-color: #f3e5f5; color: #7b1fa2; }}
        .source {{
            color: #888;
            font-size: 12px;
            margin-top: 5px;
        }}
        .insight-box {{
            background-color: #e8f4fd;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .insight-box h4 {{
            color: #1F4E88;
            margin-top: 0;
        }}
        .links {{
            margin-top: 20px;
        }}
        .links a {{
            color: #1F4E88;
            text-decoration: none;
            display: block;
            margin-bottom: 5px;
        }}
        .links a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #888;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 AI领域每日情报简报</h1>
            <div class="date">{generated_date}</div>
            <div class="org">{organization_name}</div>
        </div>
        
        <div class="section">
            <h2>📌 近日要闻TOP3</h2>
            {top3_html}
        </div>
        
        <div class="section">
            <h2>🏛️ 美欧机构AI应用动态</h2>
            {ai_gov_usage_html}
        </div>
        
        <div class="section">
            <h2>🇨🇳 涉我AI舆论动态</h2>
            {ai_china_narrative_html}
        </div>
        
        <div class="section">
            <h2>📜 AI新法案与政策</h2>
            {ai_legislation_html}
        </div>
        
        <div class="section">
            <h2>🔒 AI数据泄露与安全事件</h2>
            {ai_data_leak_html}
        </div>
        
        <div class="section">
            <h2>💡 趋势研判与防护建议</h2>
            {insights_html}
        </div>
        
        <div class="section">
            <h2>📚 重要链接</h2>
            <div class="links">
                {links_html}
            </div>
        </div>
        
        <div class="footer">
            <p>本简报基于公开信息整理，不构成投资或其他专业建议。</p>
            <p>{organization_name}</p>
        </div>
    </div>
</body>
</html>
"""


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


def format_news_item_html(title: str, content: str, source: str, date: str, tag: str = "") -> str:
    """
    格式化单条新闻为HTML格式
    
    Args:
        title: 新闻标题
        content: 新闻内容
        source: 来源
        date: 日期
        tag: 标签
    
    Returns:
        str: 格式化的HTML内容
    """
    tag_class = "tag-info"
    if "重要" in tag:
        tag_class = "tag-important"
    elif "高危" in tag or "数据泄露" in tag:
        tag_class = "tag-danger"
    elif "新发布" in tag:
        tag_class = "tag-new"
    
    tag_html = f'<span class="tag {tag_class}">{tag}</span> ' if tag else ""
    
    return f"""<div class="news-item">
{tag_html}<strong>{title}</strong>
<p>{content}</p>
<div class="source">来源：{source} / {date}</div>
</div>
"""
