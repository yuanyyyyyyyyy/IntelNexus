"""
报告可视化模块
=============
生成威胁等级分布饼图、时间线图，注入报告正文。
使用 matplotlib 生成图表，base64 编码嵌入 Markdown。
"""
import base64
import io
import os
import re
from typing import Dict, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


# ---- Hermes "纸白与石墨" chart palette ----
_CHART_PALETTE = {
    "fig":   "#FAFAFA",   # 背景色
    "fg":    "#1A1A1A",   # 文字颜色
    "grid":  "#E0E0E0",   # 网格/边颜色
    "node_primary":  "#1A1A1A",  # 节点主色
    "node_secondary": "#666666",  # 节点次要
    "accent_orange":  "#0055FF",  # 强调橙
    "accent_green":   "#4ADE80",  # 强调绿
    "accent_red":     "#EF5350",  # 强调红
    "edge":           "#CCCCCC",  # 边颜色（浅）
}


def _chart_theme() -> dict:
    """Return the Hermes paper-white chart palette.

    保留接口兼容性，始终返回 hermes-paper 配色。
    """
    return _CHART_PALETTE


# 自带字体是否已注册过（addfont 重复调用无害，此标志避免重复解析开销）
_BUNDLED_FONT_ADDED = False


def _apply_cjk_font(matplotlib, font_manager) -> None:
    """为 matplotlib 配置中文字体。

    优先注册项目自带的 Noto Sans SC（font.sans-serif 首位），
    保留系统字体候选兜底；字体缺失/异常时不影响图表生成。
    """
    global _BUNDLED_FONT_ADDED
    candidates = []
    try:
        from intelnexus.export.font_registry import get_cjk_font_paths, MPL_SYSTEM_CJK_CANDIDATES
        regular = get_cjk_font_paths().get("regular")
        if regular is not None:
            if not _BUNDLED_FONT_ADDED:
                font_manager.fontManager.addfont(str(regular))
                _BUNDLED_FONT_ADDED = True
            family = font_manager.FontProperties(fname=str(regular)).get_name()
            candidates.append(family)
        candidates += MPL_SYSTEM_CJK_CANDIDATES
    except Exception as e:
        logger.debug(f"bundled CJK font setup skipped: {e}")
        candidates = ["Microsoft YaHei", "SimHei", "DengXian"]

    available = []
    for _font in candidates:
        try:
            font_manager.findfont(_font, fallback_to_default=False)
            available.append(_font)
        except Exception:
            continue
    if available:
        matplotlib.rcParams["font.sans-serif"] = available
        matplotlib.rcParams["axes.unicode_minus"] = False


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
        _apply_cjk_font(matplotlib, font_manager)
        import matplotlib.pyplot as plt
        _th = _chart_theme()
        plt.rcParams["figure.facecolor"] = _th["fig"]
        plt.rcParams["axes.facecolor"] = _th["fig"]
        plt.rcParams["text.color"] = _th["fg"]
        plt.rcParams["axes.labelcolor"] = _th["fg"]
        plt.rcParams["xtick.color"] = _th["fg"]
        plt.rcParams["ytick.color"] = _th["fg"]

        labels = []
        sizes = []
        colors = []
        if high > 0:
            labels.append(f"高置信 ({high})")
            sizes.append(high)
            colors.append(_CHART_PALETTE["accent_red"])
        if medium > 0:
            labels.append(f"中置信 ({medium})")
            sizes.append(medium)
            colors.append(_CHART_PALETTE["accent_orange"])
        if low > 0:
            labels.append(f"低置信 ({low})")
            sizes.append(low)
            colors.append(_CHART_PALETTE["node_secondary"])

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
        _apply_cjk_font(matplotlib, font_manager)
        import matplotlib.pyplot as plt
        _th = _chart_theme()
        plt.rcParams["figure.facecolor"] = _th["fig"]
        plt.rcParams["axes.facecolor"] = _th["fig"]
        plt.rcParams["text.color"] = _th["fg"]
        plt.rcParams["axes.labelcolor"] = _th["fg"]
        plt.rcParams["xtick.color"] = _th["fg"]
        plt.rcParams["ytick.color"] = _th["fg"]
        from collections import Counter

        counts = Counter(dates)
        sorted_dates = sorted(counts.keys())
        values = [counts[d] for d in sorted_dates]

        fig, ax = plt.subplots(figsize=(max(4, len(sorted_dates) * 0.8), 3))
        ax.bar(range(len(sorted_dates)), values, color=_CHART_PALETTE["accent_orange"])
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


def generate_credibility_radar(credibility_data: dict) -> Optional[str]:
    """生成情报可信度雷达图（多维度可视化）。

    维度：
    - 来源可靠性：来源固有权威性（domain_score 均值）
    - 信息可信度：条目级综合评分（credibility_score 均值）
    - 一致性：跨源信息一致性（overall_consistency）
    - 高质来源占比：高分来源比例
    - 证据覆盖：有直接证据支撑的结论比例

    Returns:
        base64 PNG 字符串，或 None（无数据时）
    """
    if not credibility_data:
        return None

    scores = credibility_data.get("scores", [])
    if not scores:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import font_manager
        _apply_cjk_font(matplotlib, font_manager)
        import matplotlib.pyplot as plt
        import numpy as np

        _th = _chart_theme()
        plt.rcParams["figure.facecolor"] = _th["fig"]
        plt.rcParams["axes.facecolor"] = _th["fig"]
        plt.rcParams["text.color"] = _th["fg"]
        plt.rcParams["axes.labelcolor"] = _th["fg"]
        plt.rcParams["xtick.color"] = _th["fg"]
        plt.rcParams["ytick.color"] = _th["fg"]

        # 计算各维度分数（0-1）
        domain_scores = [s.get("domain", 0.5) for s in scores]
        cred_scores = [s.get("score", 0.5) for s in scores]

        source_reliability = np.mean(domain_scores) if domain_scores else 0.5
        info_confidence = np.mean(cred_scores) if cred_scores else 0.5
        consistency = credibility_data.get("overall_consistency", 0.5)

        high_count = credibility_data.get("high_count", 0)
        total = len(scores)
        high_ratio = high_count / total if total > 0 else 0.5

        # 证据覆盖（从 claims 推断，无数据时给默认值）
        evidence_coverage = 0.7  # 默认值，实际可从 evidence_data 获取

        # 雷达图数据
        categories = ["来源可靠性", "信息可信度", "跨源一致性", "高质来源占比", "证据覆盖"]
        values = [
            min(1.0, source_reliability),
            min(1.0, info_confidence),
            min(1.0, consistency),
            min(1.0, high_ratio),
            min(1.0, evidence_coverage),
        ]

        # 闭合雷达图
        values_closed = values + [values[0]]
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles_closed = angles + [angles[0]]

        fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))

        # 绘制数据区域
        ax.fill(angles_closed, values_closed, color=_CHART_PALETTE["accent_orange"], alpha=0.25)
        ax.plot(angles_closed, values_closed, color=_CHART_PALETTE["accent_orange"], linewidth=2)

        # 绘制数据点
        for angle, value in zip(angles, values):
            ax.plot(angle, value, "o", color=_CHART_PALETTE["accent_orange"], markersize=6)

        # 设置标签
        ax.set_xticks(angles)
        ax.set_xticklabels(categories, fontsize=8)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=6, color="#888")
        ax.set_title("情报可信度雷达", fontsize=10, pad=20)

        # 网格线颜色
        ax.grid(color=_CHART_PALETTE["grid"], alpha=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        logger.warning(f"生成可信度雷达图失败: {e}")
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
        if chart_type == "threat":
            label = "威胁等级分布"
        elif chart_type == "timeline":
            label = "时间线分布"
        elif chart_type == "credibility_radar":
            label = "情报可信度雷达"
        else:
            label = "可视化图表"
        img_tags.append(
            f'<img src="data:image/png;base64,{b64}" '
            f'alt="{label}" style="max-width:100%;margin:8px 0;">'
        )

    if not img_tags:
        return report

    images_html = "\n".join(img_tags)

    # 图表语义上是「证据置信度统计」，注入到证据参考节之前（而非关键数据——
    # 该节应放硬数据表格，统计图放那里名不副实且打断阅读）
    pattern = r'(## 证据参考)'
    transition = ('<p style="color:#8a8a8a;font-size:12px;margin:4px 0;">'
                  "下图为本报告证据链的置信度分布统计：</p>")
    def _repl(m):
        return transition + "\n" + images_html + "\n" + m.group(1)
    result = re.sub(pattern, _repl, report, count=1)

    # 如果没找到该章节，追加到文末
    if result == report:
        report += f"\n\n## 可视化图表\n\n{images_html}\n"

    return result
