"""
结构化摘要解析器
================
从 LLM 输出中提取事实/分析/推测的结构化数据。

用于：
- 机器可读的情报摘要
- 自动更新和纠错
- 历史变化检测
"""
import json
import re
from typing import Dict, List, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 匹配 ```json ... ``` 代码块
_JSON_BLOCK_PATTERN = re.compile(
    r'```json\s*\n(.*?)\n```', re.DOTALL)

# 匹配 ## 二、结构化摘要 章节
_STRUCTURED_SECTION_PATTERN = re.compile(
    r'## 二、结构化摘要[（(]机器可读[)）].*?(?=## |\Z)', re.DOTALL)


def extract_structured_summary(llm_output: str) -> Optional[Dict]:
    """从 LLM 输出中提取结构化摘要。

    Args:
        llm_output: LLM 生成的完整报告文本

    Returns:
        结构化摘要 dict，或 None（未找到时）
        {
            "facts": [{"text": ..., "confidence": ..., "sources": [...]}],
            "analyses": [{"text": ..., "confidence": ..., "based_on": [...]}],
            "speculations": [{"text": ..., "confidence": ..., "condition": ...}],
            "overall_confidence": 0.80
        }
    """
    if not llm_output:
        return None

    # 尝试提取 JSON 代码块
    m = _JSON_BLOCK_PATTERN.search(llm_output)
    if not m:
        # 尝试在整个结构化摘要章节中查找 JSON
        section_m = _STRUCTURED_SECTION_PATTERN.search(llm_output)
        if section_m:
            section_text = section_m.group(0)
            m = _JSON_BLOCK_PATTERN.search(section_text)

    if not m:
        return None

    json_str = m.group(1).strip()

    # 清理可能的格式问题
    json_str = json_str.replace('，', ',')  # 中文逗号
    json_str = json_str.replace('：', ':')  # 中文冒号

    try:
        data = json.loads(json_str)

        # 验证基本结构
        if not isinstance(data, dict):
            return None

        # 确保必要字段存在
        result = {
            "facts": data.get("facts", []),
            "analyses": data.get("analyses", []),
            "speculations": data.get("speculations", []),
            "overall_confidence": data.get("overall_confidence", 0.5),
        }

        # 验证数据类型
        if not isinstance(result["facts"], list):
            result["facts"] = []
        if not isinstance(result["analyses"], list):
            result["analyses"] = []
        if not isinstance(result["speculations"], list):
            result["speculations"] = []

        # 验证 confidence 范围
        for fact in result["facts"]:
            if isinstance(fact, dict):
                conf = fact.get("confidence", 0.5)
                if isinstance(conf, (int, float)):
                    fact["confidence"] = max(0.0, min(1.0, float(conf)))

        for analysis in result["analyses"]:
            if isinstance(analysis, dict):
                conf = analysis.get("confidence", 0.5)
                if isinstance(conf, (int, float)):
                    analysis["confidence"] = max(0.0, min(1.0, float(conf)))

        for spec in result["speculations"]:
            if isinstance(spec, dict):
                conf = spec.get("confidence", 0.5)
                if isinstance(conf, (int, float)):
                    spec["confidence"] = max(0.0, min(1.0, float(conf)))

        overall = result["overall_confidence"]
        if isinstance(overall, (int, float)):
            result["overall_confidence"] = max(0.0, min(1.0, float(overall)))

        return result

    except json.JSONDecodeError as e:
        logger.warning(f"结构化摘要 JSON 解析失败：{e}")
        logger.debug(f"JSON 内容：{json_str[:500]}")
        return None


def format_structured_summary_for_display(data: Dict) -> str:
    """将结构化摘要格式化为 Markdown 用于 UI 展示。

    Args:
        data: extract_structured_summary 返回的 dict

    Returns:
        Markdown 字符串
    """
    if not data:
        return ""

    lines = []

    # 总体置信度
    overall = data.get("overall_confidence", 0.5)
    if overall >= 0.8:
        level = "高"
        color = "sage"
    elif overall >= 0.6:
        level = "中"
        color = "warning"
    else:
        level = "低"
        color = "terracotta"

    lines.append(f"**总体置信度**：{overall:.0%}（{level}）")
    lines.append("")

    # 事实
    facts = data.get("facts", [])
    if facts:
        lines.append("**【事实】**")
        lines.append("")
        for i, fact in enumerate(facts, 1):
            text = fact.get("text", "")
            conf = fact.get("confidence", 0.5)
            sources = fact.get("sources", [])
            source_str = "、".join(sources[:3]) if sources else "未知"
            lines.append(f"{i}. {text}")
            lines.append(f"   - 置信度：{conf:.0%} | 来源：{source_str}")
        lines.append("")

    # 分析判断
    analyses = data.get("analyses", [])
    if analyses:
        lines.append("**【分析判断】**")
        lines.append("")
        for i, analysis in enumerate(analyses, 1):
            text = analysis.get("text", "")
            conf = analysis.get("confidence", 0.5)
            based_on = analysis.get("based_on", [])
            basis_str = "、".join(based_on[:3]) if based_on else "综合推断"
            lines.append(f"{i}. {text}")
            lines.append(f"   - 置信度：{conf:.0%} | 依据：{basis_str}")
        lines.append("")

    # 推测
    speculations = data.get("speculations", [])
    if speculations:
        lines.append("**【推测】**")
        lines.append("")
        for i, spec in enumerate(speculations, 1):
            text = spec.get("text", "")
            conf = spec.get("confidence", 0.5)
            condition = spec.get("condition", "")
            lines.append(f"{i}. {text}")
            if condition:
                lines.append(f"   - 置信度：{conf:.0%} | 条件：{condition}")
            else:
                lines.append(f"   - 置信度：{conf:.0%}")
        lines.append("")

    return "\n".join(lines)
