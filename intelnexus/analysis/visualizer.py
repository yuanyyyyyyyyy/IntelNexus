"""
报告可视化模块
=============
生成威胁等级分布饼图、时间线图，注入报告正文。
使用 matplotlib 生成图表，base64 编码嵌入 Markdown。
"""
import base64
import io
import re
from typing import Dict, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


def generate_threat_chart(evidence_data: dict) -> Optional[str]:
    """生成威胁等级分布饼图（基于 claim 置信度分级）。

    Returns:
        base64 PNG 字符串，或 None（无数据时）
    """
    claims = evidence_data.get("claims", [])
    if not claims:
        return None

    # 按置信度分级
    high = sum(1 for c in claims if c.get("confidence", 0) >= 0.7)
    medium = sum(1 for c in claims if 0.4 <= c.get("confidence", 0) < 0.7)
    low = sum(1 for c in claims if c.get("confidence", 0) < 0.4)

    if high + medium + low == 0:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import font_manager
        _cjk = None
        for _font in ("Microsoft YaHei", "SimHei", "DengXian"):
            try:
                font_manager.findfont(_font, fallback_to_default=False)
                _cjk = _font
                break
            except Exception:
                continue
        if _cjk:
            matplotlib.rcParams["font.sans-serif"] = [_cjk]
            matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt

        labels = []
        sizes = []
        colors = []
        if high > 0:
            labels.append(f"高置信 ({high})")
            sizes.append(high)
            colors.append("#e74c3c")
        if medium > 0:
            labels.append(f"中置信 ({medium})")
            sizes.append(medium)
            colors.append("#f39c12")
        if low > 0:
            labels.append(f"低置信 ({low})")
            sizes.append(low)
            colors.append("#95a5a6")

        fig, ax = plt.subplots(figsize=(4, 3))
        ax.pie(sizes, labels=labels, colors=colors, autopct="%1.0f%%",
               startangle=90, textprops={"fontsize": 9})
        ax.set_title("证据置信度分布", fontsize=10)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        logger.warning(f"生成威胁图表失败: {e}")
        return None


def generate_timeline_chart(scraped_data: dict) -> Optional[str]:
    """从 URL 中提取日期，生成简易时间线图。

    Returns:
        base64 PNG 字符串，或 None
    """
    dates = []
    for url in scraped_data.keys():
        # 尝试从 URL 提取日期（常见格式：/2025/07/ 或 /2025-07-01）
        m = re.search(r'/(\d{4})[/-](\d{2})[/-]?(\d{2})?', url)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            day = int(m.group(3)) if m.group(3) else 1
            dates.append(f"{year}-{month:02d}-{day:02d}")

    if len(dates) < 2:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import font_manager
        _cjk = None
        for _font in ("Microsoft YaHei", "SimHei", "DengXian"):
            try:
                font_manager.findfont(_font, fallback_to_default=False)
                _cjk = _font
                break
            except Exception:
                continue
        if _cjk:
            matplotlib.rcParams["font.sans-serif"] = [_cjk]
            matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt
        from collections import Counter

        counts = Counter(dates)
        sorted_dates = sorted(counts.keys())
        values = [counts[d] for d in sorted_dates]

        fig, ax = plt.subplots(figsize=(max(4, len(sorted_dates) * 0.8), 3))
        ax.bar(range(len(sorted_dates)), values, color="#3498db")
        ax.set_xticks(range(len(sorted_dates)))
        ax.set_xticklabels(sorted_dates, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("来源数")
        ax.set_title("信息发布时间分布", fontsize=10)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        logger.warning(f"生成时间线图表失败: {e}")
        return None


def inject_visuals(report: str, charts: Dict[str, str]) -> str:
    """在报告的 ## 五、关键数据 部分注入图表。

    Args:
        report: 原始报告文本
        charts: {"threat": base64_png, "timeline": base64_png}
    """
    if not charts:
        return report

    img_tags = []
    for chart_type, b64 in charts.items():
        if not b64:
            continue
        label = "威胁等级分布" if chart_type == "threat" else "时间线分布"
        img_tags.append(
            f'<img src="data:image/png;base64,{b64}" '
            f'alt="{label}" style="max-width:100%;margin:8px 0;">'
        )

    if not img_tags:
        return report

    images_html = "\n".join(img_tags)

    # 在 "## 五、关键数据" 段落末尾插入
    pattern = r'(## 五、关键数据\s*\n)'
    replacement = f'\\1\n{images_html}\n'
    result = re.sub(pattern, replacement, report, count=1)

    # 如果没找到该章节，追加到文末
    if result == report:
        report += f"\n\n## 可视化图表\n\n{images_html}\n"

    return result
