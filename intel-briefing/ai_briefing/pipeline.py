"""
AI 简报生成流水线（公共执行器）
============================
将「采集 → 生成 → 保存历史 → 推送」收拢为单一入口，供三处 UI 按钮复用。

设计目标（对应改进计划 P1-P10）：
- 消除三处重复逻辑（P1）
- 全链路进度反馈（P2）：on_progress(stage, message, percent)
- 采集并行化复用 collector.collect_all_categories（P3）
- 模型由 UI 传入（P4）
- 默认采集全部 6 个类目（P5）
- 错误隔离：单板块失败不影响整体，收集 warnings（P6）
- 推送可关闭（P7）
- 可选类目（P8 简化版）
- 返回结果统计供 UI 展示（P9）
"""

import time
from typing import Callable, List, Optional

from ai_briefing.config import BRIEFING_CONFIG
from ai_briefing.collector import AIBriefingCollector
from ai_briefing.analyzer import AIBriefingAnalyzer
from ai_briefing.notifier import AIBriefingNotifier
from shared.logger import get_logger

logger = get_logger(__name__)

# 进度回调签名：(stage: str, message: str, percent: Optional[float]) -> None
ProgressCallback = Callable[[str, str, Optional[float]], None]

_DEFAULT_EMAIL_CONFIG = {
    "smtp_server": "", "smtp_port": 587,
    "username": "", "password": "", "use_tls": True,
}


def _noop_progress(stage: str, message: str, percent: Optional[float] = None):
    logger.info(f"[pipeline:{stage}] {message}")


def run_briefing_pipeline(
    model: str,
    categories: Optional[List[str]] = None,
    push_enabled: bool = True,
    org_name: Optional[str] = None,
    email_config: Optional[dict] = None,
    on_progress: ProgressCallback = _noop_progress,
) -> dict:
    """
    生成一份简报并（可选）推送。

    Args:
        model: LLM 模型名（如 "qwen2.5:7b"），由 UI 选择后传入
        categories: 本次采集的分类 ID 列表；None 表示全部 WATCH_CATEGORIES
        push_enabled: 是否推送订阅者
        org_name: 组织名称（覆盖配置）
        email_config: 邮件推送配置（用于 email 渠道）
        on_progress: 进度回调 (stage, message, percent)

    Returns:
        dict: {
            "md": 简报 markdown,
            "warnings": [警告文本列表],
            "collected_counts": {cat_id: 条数},
            "pushed": 成功推送人数,
            "elapsed": 耗时(秒, 浮点),
            "categories": [实际采集的分类],
        }
    """
    start = time.time()
    email_config = email_config or dict(_DEFAULT_EMAIL_CONFIG)

    # ---- 1. 采集（并行）----
    on_progress("collect_start", "开始采集情报数据...", 0.0)
    collector = AIBriefingCollector()
    all_collected = collector.collect_all_categories()

    if categories:
        all_collected = {k: v for k, v in all_collected.items() if k in categories}

    collected_counts = {k: len(v) for k, v in all_collected.items()}
    total_items = sum(collected_counts.values())
    on_progress(
        "collect_done",
        f"采集完成：{len(all_collected)} 个类目，共 {total_items} 条情报",
        0.4,
    )

    # ---- 2. 生成 ----
    on_progress("generate_start", "开始生成简报...", 0.4)
    from shared.llm.core import get_llm
    try:
        llm = get_llm(model) if model else None
    except Exception as e:
        logger.warning(f"Failed to load LLM '{model}': {e}; 将以降级模式生成。")
        llm = None

    analyzer = AIBriefingAnalyzer(llm=llm)
    md, warnings = analyzer.generate_briefing(
        all_collected,
        organization_name=org_name,
        with_warnings=True,
        on_progress=on_progress,
    )

    # ---- 3. 保存历史 ----
    on_progress("save", "保存简报历史...", 0.95)
    from src.config.briefing_history import get_briefing_history
    get_briefing_history().save_briefing(
        markdown_content=md,
        organization_name=org_name or BRIEFING_CONFIG["organization"].get("name", ""),
        categories=list(all_collected.keys()),
    )

    # ---- 4. 推送 ----
    pushed = 0
    if push_enabled:
        on_progress("push", "推送订阅者...", 0.97)
        from src.config.subscriptions import get_active_subscribers
        subscribers = get_active_subscribers()
        if subscribers:
            notifier = AIBriefingNotifier(email_config=email_config)
            for sub in subscribers:
                try:
                    results = notifier.notify(sub, md)
                    if any(results.values()):
                        pushed += 1
                except Exception as e:
                    logger.error(f"Push failed for {sub.get('name', '?')}: {e}")
            on_progress(
                "push_done",
                f"已推送 {pushed}/{len(subscribers)} 个订阅者",
                1.0,
            )
        else:
            on_progress("push_no_subs", "暂无启用推送的订阅者", 1.0)
    else:
        on_progress("push_skipped", "已跳过推送", 1.0)

    elapsed = round(time.time() - start, 1)
    return {
        "md": md,
        "warnings": warnings,
        "collected_counts": collected_counts,
        "pushed": pushed,
        "elapsed": elapsed,
        "categories": list(all_collected.keys()),
    }
