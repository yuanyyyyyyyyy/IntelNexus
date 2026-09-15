"""图3　质量—成本帕累托前沿（R9）。

数据来源：reports/aggregate.json 中各配置的 ROUGE-L（质量）与单次折算成本。
成本缺失（pricing.yaml 未填）时不绘图，避免用假数据画图。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.common import read_json
from experiments.logging_utils import get_logger
from experiments.metrics.aggregate import PRIMARY_METRIC
from experiments.paths import AGGREGATE, FIGURES_DIR

logger = get_logger("exp.fig3")

# 图内标签用论文口径的中文名，避免出现 cloud_flagship 这类配置 id
LABELS = {
    "qwen3:8b": "本地 8B",
    "cloud_flagship": "云端旗舰档",
    "cloud_light": "云端轻量档",
    "baseline_keyword": "关键词规则",
    "baseline_textrank": "TextRank",
    "baseline_tfidf": "TF-IDF 聚类",
}


def _pareto(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """成本越小越好、质量越大越好 → 前沿 = 按成本升序后质量递增的点。"""
    ordered = sorted(points, key=lambda p: p["cost"])
    front: List[Dict[str, Any]] = []
    best = -1.0
    for p in ordered:
        if p["quality"] > best:
            front.append(p)
            best = p["quality"]
    return front


def draw(out: Optional[Path] = None, agg_path: Optional[Path] = None) -> Optional[Path]:
    agg = read_json(Path(agg_path) if agg_path else AGGREGATE) if AGGREGATE.exists() else {}
    configs = agg.get("configs") or {}
    groups = agg.get("groups") or {}
    points: List[Dict[str, Any]] = []
    for cfg, v in configs.items():
        # 质量轴用论文主指标（实体 F1）；ROUGE-L 因跨语言不匹配绝对值偏低，不用于绘图
        q = (v.get(PRIMARY_METRIC) or {}).get("mean")
        c = v.get("cost_per_item_mean")
        if q is None or c is None:
            continue
        points.append({"config": cfg, "quality": float(q), "cost": float(c),
                       "group": groups.get(cfg, "unknown")})
    if len(points) < 2:
        logger.warning("可用于绘图的配置不足（需要同时有质量与成本数据），跳过图3")
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # noqa: BLE001
        logger.warning("matplotlib 不可用，跳过图3: %s", e)
        return None

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(out) if out else FIGURES_DIR / "fig3_pareto.png"

    # 中文字体：matplotlib 默认字体无 CJK 字形，会把标签渲染成方框
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    colors = {"local": "#1f77b4", "cloud": "#d62728", "baseline": "#7f7f7f"}
    markers = {"local": "o", "cloud": "s", "baseline": "^"}
    fig, ax = plt.subplots(figsize=(6.2, 4.2), dpi=200)
    for g in ("baseline", "local", "cloud"):
        pts = [p for p in points if p["group"] == g]
        if not pts:
            continue
        ax.scatter([p["cost"] for p in pts], [p["quality"] for p in pts],
                   c=colors[g], marker=markers[g], s=42, label={"local": "本地模型", "cloud": "云端 API",
                                                                "baseline": "非大模型基线"}[g])
    front = _pareto(points)
    if len(front) > 1:
        ax.plot([p["cost"] for p in front], [p["quality"] for p in front],
                "--", color="#2ca02c", linewidth=1.2, label="帕累托前沿")
    for p in points:
        dominated = p not in front
        # 被支配的点画在右侧边界附近，标签放左侧，免得被坐标轴切掉
        offset = (-8, -3) if dominated else (-2, 6)
        ax.annotate(LABELS.get(p["config"], p["config"]), (p["cost"], p["quality"]),
                    fontsize=6.6, xytext=offset,
                    textcoords="offset points", ha="right" if dominated else "center",
                    color="#666666" if dominated else "#111111")
    if any(p not in front for p in points):
        ax.annotate("被云端旗舰档支配",
                    xy=(next(p["cost"] for p in points if p not in front),
                        next(p["quality"] for p in points if p not in front)),
                    xytext=(-6, 14), textcoords="offset points", fontsize=6.2,
                    color="#666666", ha="right",
                    arrowprops={"arrowstyle": "-", "color": "#999999", "linewidth": 0.6})

    ax.set_xlabel("单次简报折算成本 / 元")
    # 质量轴用的是论文主指标（安全实体 F1），此前误标为 ROUGE-L
    ax.set_ylabel("安全实体 F1")
    ax.set_title("质量—成本帕累托前沿（安全实体 F1 对单次折算成本）")
    ax.grid(alpha=0.25, linestyle=":")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    logger.info("图3 已生成: %s（%d 个配置）", out_path, len(points))
    return out_path


if __name__ == "__main__":
    draw()
