"""
行动项提取模块
=============
从报告的 ## 六、风险与建议 部分提取可执行行动项，
按优先级和时限分类，格式化为 Markdown 待办清单。
"""
import re
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger
from intelnexus.ui.icons import icon, status_icon

logger = get_logger(__name__)

# 优先级关键词映射
_PRIORITY_KEYWORDS = {
    "high": ["立即", "紧急", "immediately", "urgent", "critical", "严重", "必须"],
    "medium": ["尽快", "本周", "asap", "this week", "重要", "should"],
    "low": ["建议", "考虑", "suggest", "consider", "可选", "optional"],
}

# 时限关键词映射
_DEADLINE_KEYWORDS = {
    "immediate": ["立即", "马上", "immediately", "now", "紧急"],
    "this_week": ["本周", "一周内", "this week", "within a week"],
    "this_month": ["本月", "一个月", "this month", "within a month"],
}

# 角色关键词映射
_ROLE_KEYWORDS = {
    "developer": ["开发者", "开发", "developer", "编程", "代码", "测试"],
    "enterprise": ["企业", "公司", "enterprise", "组织", "团队", "生产环境"],
    "researcher": ["研究", "researcher", "学术", "分析", "评估"],
    "security": ["安全", "security", "防护", "运维", "ops"],
}


def _classify_priority(text: str) -> str:
    text_lower = text.lower()
    for priority, keywords in _PRIORITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return priority
    return "low"


def _classify_deadline(text: str) -> str:
    text_lower = text.lower()
    for deadline, keywords in _DEADLINE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return deadline
    return "this_month"


def _classify_role(text: str) -> str:
    """根据行动项内容推断目标角色。"""
    text_lower = text.lower()
    for role, keywords in _ROLE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return role
    return "general"  # 通用建议


def extract_actions(report: str) -> List[Dict]:
    """从报告中提取行动项。

    Returns:
        [{"priority": "high|medium|low", "action": "...", "deadline": "...", "role": "..."}]
    """
    if not report:
        return []

    # 定位 "风险与建议" 或 "行动建议" 章节
    section_patterns = [
        r'##\s*六 [、.]?\s*风险与建议\s*(.*?)(?=\n##\s|\Z)',
        r'##\s*六 [、.]?\s*(.*?)(?=\n##\s|\Z)',
        r'###\s*6\.2\s*行动建议\s*(.*?)(?=\n##\s|\n###\s|\Z)',
        r'##\s*行动建议\s*(.*?)(?=\n##\s|\Z)',
    ]

    section_text = ""
    for pattern in section_patterns:
        m = re.search(pattern, report, re.DOTALL | re.IGNORECASE)
        if m:
            section_text = m.group(1)
            break

    if not section_text:
        return []

    # 提取列表项（支持 - / * / 数字。格式）
    items = re.findall(r'(?:^|\n)\s*[-*]\s+(.+?)(?=\n\s*[-*]|\n\n|\Z)', section_text, re.DOTALL)
    if not items:
        items = re.findall(r'(?:^|\n)\s*\d+[.)]\s+(.+?)(?=\n\s*\d+[.)]|\n\n|\Z)', section_text, re.DOTALL)

    actions = []
    for item in items:
        text = item.strip()
        if len(text) < 5:
            continue
        actions.append({
            "priority": _classify_priority(text),
            "action": text,
            "deadline": _classify_deadline(text),
            "role": _classify_role(text),
        })

    return actions


def format_actions(actions: List[Dict]) -> str:
    """格式化为 Markdown 待办清单。"""
    if not actions:
        return ""

    priority_labels = {"high": "紧急", "medium": "重要", "low": "建议"}
    deadline_labels = {"immediate": "立即", "this_week": "本周", "this_month": "本月"}
    role_labels = {
        "developer": "开发者",
        "enterprise": "企业",
        "researcher": "研究员",
        "security": "安全",
        "general": "通用",
    }

    lines = ["## 行动项清单\n"]
    for a in actions:
        svg_icon = status_icon(a["priority"], size="sm")
        label = priority_labels.get(a["priority"], "建议")
        deadline = deadline_labels.get(a["deadline"], "本月")
        role = role_labels.get(a.get("role", "general"), "通用")
        lines.append(f"- {svg_icon} **[{label}]** {a['action']} *(时限：{deadline} | 角色：{role})*")

    return "\n".join(lines)
