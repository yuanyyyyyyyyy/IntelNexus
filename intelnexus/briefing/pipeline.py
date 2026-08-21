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

from intelnexus.briefing.config import BRIEFING_CONFIG
from intelnexus.briefing.collector import AIBriefingCollector
from intelnexus.briefing.analyzer import AIBriefingAnalyzer
from intelnexus.briefing.notifier import AIBriefingNotifier
from intelnexus.core.logger import get_logger

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
    from intelnexus.core.llm.core import get_llm
    llm = None
    if model:
        try:
            llm = get_llm(model)
        except Exception as e:
            logger.warning(f"Failed to load LLM '{model}': {e}; 将以降级模式生成。")
            on_progress("llm_error", f"LLM 加载失败，将以降级模式生成: {type(e).__name__}: {str(e)[:100]}", 0.4)
    else:
        on_progress("llm_skipped", "未指定 LLM 模型，将以降级模式生成", 0.4)

    analyzer = AIBriefingAnalyzer(llm=llm)
    md, warnings = analyzer.generate_briefing(
        all_collected,
        organization_name=org_name,
        with_warnings=True,
        on_progress=on_progress,
    )

    # ---- 2.5 生成 HTML 版本（用于邮件推送）----
    briefing_html = None
    try:
        from intelnexus.briefing.templates import render_email_html, markdown_to_html_sections
        from intelnexus.briefing.analyzer import format_briefing_date
        org_cfg = dict(BRIEFING_CONFIG["organization"])
        generated_date = format_briefing_date()
        sections = markdown_to_html_sections(md)
        briefing_html = render_email_html(
            generated_date=generated_date,
            organization=org_cfg,
            **sections
        )
    except Exception as e:
        logger.warning(f"Could not generate HTML for email: {e}")

    # ---- 3. 保存历史 + 条目数据（反向飞轮：供取证快速入口）----
    on_progress("save", "保存简报历史...", 0.95)
    from intelnexus.config.briefing_history import get_briefing_history
    history = get_briefing_history()
    filename = history.save_briefing(
        markdown_content=md,
        organization_name=org_name or BRIEFING_CONFIG["organization"].get("name", ""),
        categories=list(all_collected.keys()),
    )

    # 保存条目数据（含可信度评分），供简报预览中「一键取证」
    on_progress("save_entries", "保存条目数据...", 0.96)
    entries_data = _build_briefing_entries(all_collected)
    history.save_briefing_data(filename, entries_data)

    # ---- 4. 推送 ----
    pushed = 0
    if push_enabled:
        on_progress("push", "推送订阅者...", 0.97)
        from intelnexus.config.subscriptions import get_active_subscribers
        subscribers = get_active_subscribers()
        if subscribers:
            notifier = AIBriefingNotifier(email_config=email_config)
            for sub in subscribers:
                try:
                    results = notifier.notify(sub, md, briefing_html)
                    if any(results.values()):
                        pushed += 1
                    else:
                        # 记录推送失败原因
                        active_channels = [k for k, v in sub.get("channels", {}).items()
                                           if isinstance(v, dict) and v.get("enabled")]
                        if not active_channels:
                            logger.warning(f"订阅者 {sub.get('name')} 无启用的推送渠道")
                        else:
                            logger.warning(f"订阅者 {sub.get('name')} 渠道 {active_channels} 推送失败")
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


def _build_briefing_entries(collected_data: dict) -> list:
    """将采集数据展平为条目列表，附加可信度评分与冲突信息。

    反向飞轮基础：每条条目携带 credibility_score 和高冲突标记，
    供简报 UI 展示「一键取证」入口。

    Returns:
        list[dict]: 每条含 {title, url, source, category, credibility_score,
                    has_conflict, conflict_severity, ...}
    """
    entries = []
    for cat_id, items in collected_data.items():
        for it in items:
            entries.append({
                "title": it.get("title", ""),
                "url": it.get("url", ""),
                "source": it.get("source", "Unknown"),
                "category": cat_id,
                "description": it.get("description", "")[:300],
            })

    if not entries:
        return entries

    # 运行可信度评估
    try:
        scraped = {}
        for it_list in collected_data.values():
            for it in it_list:
                url = it.get("url") or it.get("link", "")
                text = it.get("content") or it.get("description", "")
                if url and text:
                    scraped[url] = text

        from intelnexus.analysis.credibility import SourceScorer, ConflictDetector
        scorer = SourceScorer()
        scored = scorer.evaluate(
            [dict(e, **{k: e.get(k, "") for k in ("link", "url")}) for e in entries],
            scraped,
        )
        detector = ConflictDetector()
        conflicts = detector.detect(scored, scraped)

        # 建立 URL→冲突严重度 的快速索引
        conflict_map = {}
        for c in conflicts:
            for s in c.get("sources", []):
                idx = s.get("index", -1)
                if 0 <= idx < len(scored):
                    url = scored[idx].get("url") or scored[idx].get("link", "")
                    if url:
                        current = conflict_map.get(url, 0.0)
                        conflict_map[url] = max(current, c.get("severity", 0.0))

        # 附加评分到条目
        for i, e in enumerate(entries):
            if i < len(scored):
                e["credibility_score"] = scored[i].get("credibility_score", 0.5)
            else:
                e["credibility_score"] = 0.5
            url = e.get("url", "")
            e["has_conflict"] = url in conflict_map
            e["conflict_severity"] = conflict_map.get(url, 0.0)

    except Exception as ex:
        logger.warning(f"简报条目可信度评估失败，跳过附加字段: {ex}")
        for e in entries:
            e["credibility_score"] = 0.5
            e["has_conflict"] = False
            e["conflict_severity"] = 0.0

    return entries
