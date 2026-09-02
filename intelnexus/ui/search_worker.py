"""
搜索管线纯计算层（后台线程安全）
===================================
从 search_pipeline.py 提取的计算逻辑，不含任何 st.* 调用。
在 TaskRunner 的后台线程中执行，通过 progress_callback 上报进度。

返回值为 dict，包含原管线写入 session_state 的全部字段，
由主线程在任务完成后一次性写回 session_state 并渲染 UI。
"""

import os
import re
import html
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[str, str, float], None]

# TL;DR 速览卡提取正则
_TLDR_PATTERN = re.compile(
    r"##\s*TL;DR\s*情报速览\s*\n(.*?)(?=\n---|\n## |\Z)", re.DOTALL)


def _extract_tldr_card(report: str, structured_summary: dict = None) -> str:
    """提取或生成 TL;DR 速览卡。

    优先从 LLM 输出的 TL;DR 章节提取，若无则从结构化摘要生成。

    Args:
        report: LLM 生成的完整报告
        structured_summary: 结构化摘要 dict（可选）

    Returns:
        TL;DR 文本
    """
    if not report:
        return ""

    # 优先从 LLM 输出提取
    m = _TLDR_PATTERN.search(report)
    if m:
        return m.group(1).strip()

    # 降级：从结构化摘要生成
    if structured_summary:
        facts = structured_summary.get("facts", [])
        analyses = structured_summary.get("analyses", [])
        overall = structured_summary.get("overall_confidence", 0.5)

        if facts:
            # 取第一个事实作为核心
            core_fact = facts[0].get("text", "")
            if len(core_fact) > 80:
                core_fact = core_fact[:77] + "..."

            # 生成简短摘要
            tldr = f"核心事实：{core_fact}"
            if analyses:
                analysis = analyses[0].get("text", "")
                if len(analysis) > 60:
                    analysis = analysis[:57] + "..."
                tldr += f" | 分析：{analysis}"
            tldr += f" | 置信度：{overall:.0%}"
            return tldr

    return ""


def _zero_results_is_failure(stats) -> bool:
    if not stats:
        return False
    return not any((s or {}).get("status") == "ok" for s in stats.values())


def run_search_computation(
    progress_callback: ProgressCallback,
    *,
    query: str,
    search_mode: str,
    model: str,
    threads: int,
    advanced_mode: bool = False,
    tor_port: int = 9050,
    ui_sites: list = None,
) -> Dict[str, Any]:
    """搜索管线纯计算入口（后台线程安全）。

    阶段：
    1. 预检 Ollama 模型可达
    2. 加载模型 + 查询优化
    3. 多源检索
    4. 内容抓取
    5. 可信度 + 知识图谱（并行）
    6. 报告生成（LLM）
    7. 证据链追踪
    8. 后处理（角标 / 可视化 / 行动项 / TL;DR）

    Returns:
        dict: 包含所有原 session_state 字段 + 元信息，包括：
        - success: bool
        - error: str (失败时的错误信息)
        - refined, results, filtered, scraped, source_stats
        - credibility_data, conflicts, kg_entities, kg_relations, kg_html_path, kg_context
        - streamed_summary, evidence_data, action_items
        - tldr_card, report_timestamp
        - source_counts, source_info
        - weak_results (弱相关条目)
        - cache_restored: bool
        - all_sources_ok: bool
        - zero_results: bool
        - all_failed: bool
    """
    ui_sites = ui_sites or []
    result = {
        "success": False,
        "error": "",
        "query": query,
        "search_mode": search_mode,
        "model": model,
    }

    # 智能路由
    from intelnexus.core.search.modes import SMART_MODE_KEY, resolve_mode
    if search_mode == SMART_MODE_KEY:
        search_mode = resolve_mode(query)
        result["search_mode"] = search_mode

    # ---- 1. 预检 ----
    progress_callback("preflight", "检查模型可用性...", 0.02)
    from intelnexus.core.llm.utils import check_ollama_model_available, is_vision_model, is_ollama_local_model
    from intelnexus.core.llm.core import get_llm, expand_query, expand_query_for_search, generate_summary

    if is_ollama_local_model(model):
        available, msg = check_ollama_model_available(model, timeout=3.0)
        if not available:
            result["error"] = msg
            return result

    # ---- 2. 加载模型 + 查询优化 ----
    progress_callback("refining", "优化查询...", 0.05)
    from intelnexus.analysis import warm_up_models
    warm_up_models()
    llm = get_llm(model)
    query_variants = expand_query(query)
    search_query = expand_query_for_search(query_variants)
    result["refined"] = query
    result["refined_display"] = query

    # ---- 3. 多源检索 ----
    progress_callback("searching", "检索多源数据...", 0.1)
    from intelnexus.core.search.registry import get_registry
    from intelnexus.config.search_settings import get_news_api_key as NEWS_API_KEY
    import config as app_config

    registry = get_registry(
        news_api_key=NEWS_API_KEY(),
        darkweb_advanced=advanced_mode,
        tor_port=tor_port,
        ui_sites=ui_sites,
        web_threads=threads,
    )
    search_results = registry.collect(search_mode, search_query, max_results=25, threads=threads)

    try:
        result["source_stats"] = registry.last_search_stats
    except Exception:
        result["source_stats"] = {}

    result["results"] = search_results
    results_count = len(search_results)

    # 源统计
    source_counts = {}
    for r in search_results:
        src = r.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    result["source_counts"] = source_counts
    result["source_info"] = " | ".join([f"{k}: {v}" for k, v in source_counts.items()])
    result["zero_results"] = results_count == 0
    result["all_failed"] = results_count == 0 and _zero_results_is_failure(result.get("source_stats"))
    result["all_sources_ok"] = not any(
        s.get("status") != "ok" for s in (result.get("source_stats") or {}).values()
    )

    if results_count == 0:
        result["success"] = True  # 空结果也算成功（非错误）
        result["filtered"] = []
        result["report_timestamp"] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return result

    # ---- 4. 相关性排序 ----
    progress_callback("ranking", "语义相关性排序...", 0.25)
    from intelnexus.analysis.relevance import compute_query_relevance
    ranked = compute_query_relevance(query, search_results)
    if ranked is not None:
        result["results"] = ranked
        result["filtered"] = [r for r in ranked if not r.get("weak_related", False)][:20]
        weak_count = sum(1 for r in ranked if r.get("weak_related", False))
    else:
        result["filtered"] = search_results[:20]

    # 弱相关条目
    result["weak_results"] = [
        r for r in result.get("results", []) if r.get("weak_related", False)
    ][:15]

    # ---- 5. 内容抓取 ----
    progress_callback("scraping", "抓取网页内容...", 0.3)
    from intelnexus.core.search.scraper import scrape_multiple
    scraped = scrape_multiple(result["filtered"], max_workers=threads)
    result["scraped"] = scraped

    # ---- 5.5 重定向 URL 回填（baidu/link 等包装在抓取时才解析出真实地址）----
    # 结果与 scraped 字典必须同步换键，否则可信度评估会因 URL 错位而全部落空
    try:
        from intelnexus.core.search.web import canonical_result_url
        _remap = {}
        for _r in result.get("results", []):
            _resolved = _r.pop("resolved_url", None) or canonical_result_url(_r.get("url", ""))
            if _resolved and _resolved != _r.get("url"):
                _remap[_r.get("url", "")] = _resolved
                _r["url"] = _resolved
        if _remap and result.get("scraped"):
            result["scraped"] = {
                _remap.get(_k, _k): _v for _k, _v in result["scraped"].items()
            }
    except Exception as e:
        logger.debug(f"重定向 URL 回填失败（不影响主流程）: {e}")

    # ---- 6. 知识库 RAG ----
    progress_callback("kb_retrieval", "检索知识库...", 0.45)
    kb_context = ""
    try:
        from intelnexus.knowledge.retrieval import retrieve_relevant, build_kb_context
        kb_context = build_kb_context(retrieve_relevant(query))
    except Exception as e:
        logger.warning(f"知识库检索失败，跳过: {e}")
    result["kb_context"] = kb_context

    # ---- 7. 可信度 + 知识图谱（并行）----
    progress_callback("analyzing", "可信度评估 + 知识图谱构建...", 0.5)
    _scraped = scraped or {}
    _base_results = result.get("results", []) or []

    def _run_credibility(scraped_data, base_results):
        try:
            from intelnexus.analysis.embed_cache import encode_texts
            from intelnexus.analysis.credibility import SourceScorer, ConsistencyAnalyzer, ConflictDetector

            _scraped_urls = list(scraped_data.keys())
            _scraped_texts = [scraped_data[u] for u in _scraped_urls]
            _embs = encode_texts(_scraped_texts)
            _emb_by_url = dict(zip(_scraped_urls, _embs)) if _embs is not None else {}

            scorer = SourceScorer()
            _results = scorer.evaluate(base_results, scraped_data, emb_by_url=_emb_by_url)

            analyzer = ConsistencyAnalyzer()
            consistency_data = analyzer.analyze(_results, scraped_data, emb_by_url=_emb_by_url)

            detector = ConflictDetector()
            _conflicts = detector.detect(_results, scraped_data)

            scores_list = []
            for r in _results[:30]:
                d = r.get("credibility_details", {})
                scores_list.append({
                    "name": r.get("source", "Unknown"),
                    "score": r.get("credibility_score", 0.5),
                    "reason": d.get("reason", ""),
                    "domain": d.get("domain_score", 0),
                })
            avg = (sum(s["score"] for s in scores_list) / len(scores_list)
                   if scores_list else 0.5)
            _credibility_data = {
                "scores": scores_list,
                "avg_score": round(avg, 3),
                "high_count": sum(1 for s in scores_list if s["score"] >= 0.7),
                "low_count": sum(1 for s in scores_list if s["score"] < 0.4),
                "overall_consistency": consistency_data.get("overall_consistency", 1.0),
            }

            cred_lines = []
            for s in scores_list[:15]:
                cred_lines.append(f"- {s['name']}: credibility_score {s['score']:.2f} ({s['reason']})")
            credibility_context = "\n".join(cred_lines)

            conflicts_context = ""
            if _conflicts:
                c_lines = []
                for c in _conflicts[:5]:
                    c_lines.append(f"- [{c['type']}] {c['description']} (severity: {c['severity']:.2f})")
                conflicts_context = "\n".join(c_lines)

            return {
                "results": _results,
                "conflicts": _conflicts,
                "credibility_data": _credibility_data,
                "credibility_context": credibility_context,
                "conflicts_context": conflicts_context,
            }
        except Exception as e:
            logger.error(f"可信度评估失败: {e}")
            return {
                "results": base_results,
                "conflicts": [],
                "credibility_data": None,
                "credibility_context": "",
                "conflicts_context": "",
            }

    def _run_kg(scraped_data, base_results=None):
        try:
            from intelnexus.analysis.intelligence_graph import get_entity_extractor, IntelligenceGraph
            extractor = get_entity_extractor()
            kg_raw = extractor.extract(scraped_data, search_results=base_results)
            kg = IntelligenceGraph()
            kg.build(kg_raw["entities"], kg_raw["relations"])

            _kg_entities = [
                {"name": e["name"], "type": e["type"], "importance": e["importance"]}
                for e in kg_raw["entities"][:30]
            ]
            _kg_relations = kg_raw["relations"]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs("temp", exist_ok=True)
            kg_path = kg.export_html(f"temp/kg_{timestamp}.html")

            top_entities = sorted(_kg_entities, key=lambda x: x["importance"], reverse=True)[:10]
            kg_lines = [f"- {e['name']} ({e['type']})" for e in top_entities]
            _kg_context = "\n".join(kg_lines)

            return {
                "kg_entities": _kg_entities,
                "kg_relations": _kg_relations,
                "kg_html_path": kg_path,
                "kg_context": _kg_context,
            }
        except Exception as e:
            logger.error(f"知识图谱构建失败: {e}")
            return {
                "kg_entities": [],
                "kg_relations": [],
                "kg_html_path": "",
                "kg_context": "",
            }

    if _scraped:
        with ThreadPoolExecutor(max_workers=2) as _ex:
            _f_cred = _ex.submit(_run_credibility, _scraped, _base_results)
            _f_kg = _ex.submit(_run_kg, _scraped, _base_results)
            _cred_out = _f_cred.result()
            _kg_out = _f_kg.result()
    else:
        _cred_out = _run_credibility(_scraped, _base_results)
        _kg_out = {"kg_entities": [], "kg_relations": [], "kg_html_path": "", "kg_context": ""}

    result["results"] = _cred_out["results"]
    result["conflicts"] = _cred_out["conflicts"]
    result["credibility_data"] = _cred_out["credibility_data"]
    result["kg_entities"] = _kg_out["kg_entities"]
    result["kg_relations"] = _kg_out["kg_relations"]
    result["kg_html_path"] = _kg_out["kg_html_path"]
    result["kg_context"] = _kg_out["kg_context"]

    credibility_context = _cred_out["credibility_context"]
    conflicts_context = _cred_out["conflicts_context"]
    kg_context = _kg_out["kg_context"]

    # 缓存中间产物（查询级缓存）
    try:
        from intelnexus.core.settings.result_cache import build_key, set_result
        from intelnexus.core.ui.helpers import DEFAULT_TOR_PORT
        result_key = build_key(
            search_mode, search_query, model, threads,
            advanced_mode, tor_port, ui_sites=ui_sites)
        set_result(result_key, {
            "results": result["results"],
            "scraped": result["scraped"],
            "credibility_data": result.get("credibility_data"),
            "conflicts": result.get("conflicts", []),
            "kg_entities": result.get("kg_entities", []),
            "kg_relations": result.get("kg_relations", []),
            "kg_html_path": result.get("kg_html_path", ""),
            "kg_context": result.get("kg_context", ""),
            "credibility_context": credibility_context,
            "conflicts_context": conflicts_context,
            "kb_context": kb_context,
            "streamed_summary": "",
            "evidence_data": None,
        })
    except Exception as e:
        logger.warning(f"缓存中间产物失败: {e}")
        result_key = None

    # ---- 8. 报告生成 ----
    progress_callback("generating", "生成情报报告...", 0.7)
    try:
        # 后台模式不使用流式输出（无 UI callback）
        generated = generate_summary(
            llm, query, result["scraped"], search_mode,
            credibility_context=credibility_context,
            kg_context=kg_context,
            conflicts_context=conflicts_context,
            kb_context=kb_context,
        )
        # 保存 LLM 原始输出（供证据链追踪、行动项提取、TL;DR 提取使用）
        result["llm_raw_output"] = generated or ""
        result["streamed_summary"] = generated or ""
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        result["llm_raw_output"] = ""
        result["streamed_summary"] = ""

    # ---- 9. 证据链追踪 ----
    progress_callback("evidence", "追踪证据链...", 0.85)
    try:
        if result.get("llm_raw_output"):
            from intelnexus.analysis.evidence_tracer import EvidenceTracer
            tracer = EvidenceTracer()
            result["evidence_data"] = tracer.trace(
                result["llm_raw_output"], result["scraped"])
        else:
            result["evidence_data"] = None
    except Exception as e:
        logger.error(f"证据链追踪失败: {e}")
        result["evidence_data"] = None

    # ---- 10. 后处理 ----
    progress_callback("finalizing", "后处理...", 0.92)

    # 证据角标注入
    try:
        if result.get("evidence_data") and result.get("streamed_summary"):
            from intelnexus.analysis.evidence_annotator import annotate_report
            annotated = annotate_report(result["streamed_summary"], result["evidence_data"])
            if annotated != result["streamed_summary"]:
                result["streamed_summary"] = annotated
    except Exception as e:
        logger.warning(f"证据角标注入失败: {e}")

    # 可视化图表注入
    try:
        from config import ENABLE_VISUALIZATION
        if ENABLE_VISUALIZATION and (result.get("evidence_data") or result.get("scraped")):
            from intelnexus.analysis.visualizer import generate_threat_chart, generate_timeline_chart, generate_credibility_radar, inject_visuals
            charts = {}
            if result.get("evidence_data"):
                charts["threat"] = generate_threat_chart(result["evidence_data"])
            if result.get("scraped"):
                charts["timeline"] = generate_timeline_chart(result["scraped"])
            if result.get("credibility_data"):
                radar = generate_credibility_radar(result["credibility_data"])
                if radar:
                    charts["credibility_radar"] = radar
                    result["credibility_radar_chart"] = radar  # 供 UI 直接展示
            if any(charts.values()):
                result["streamed_summary"] = inject_visuals(result["streamed_summary"], charts)
    except Exception as e:
        logger.warning(f"可视化图表注入失败: {e}")

    # 行动项提取（基于 LLM 原始输出）
    try:
        if result.get("llm_raw_output"):
            from intelnexus.analysis.action_extractor import extract_actions
            result["action_items"] = extract_actions(result["llm_raw_output"])
    except Exception as e:
        logger.warning(f"行动项提取失败: {e}")

    # 结构化摘要（事实/分析/推测）
    try:
        if result.get("llm_raw_output"):
            from intelnexus.analysis.structured_summary import extract_structured_summary
            result["structured_summary"] = extract_structured_summary(result["llm_raw_output"])
    except Exception as e:
        logger.warning(f"结构化摘要提取失败：{e}")
        result["structured_summary"] = None

    # TL;DR 速览卡（基于 LLM 原始输出，降级使用结构化摘要）
    try:
        result["tldr_card"] = _extract_tldr_card(
            result.get("llm_raw_output", ""),
            result.get("structured_summary")
        )
    except Exception:
        result["tldr_card"] = ""

    # ---- 11. 事件存储与增量变化检测（必须在报告组装之前） ----
    try:
        from intelnexus.analysis.event_store import get_event_store
        store = get_event_store()

        # 构建快照
        results_list = result.get("results", [])
        scores = [r.get("credibility_score", 0.5) for r in results_list if r.get("credibility_score")]
        avg_score = sum(scores) / len(scores) if scores else 0.5

        # 从 LLM 输出推断身份状态（LLM 空白时回退到搜索结果标题/摘要）
        llm_out = result.get("llm_raw_output", "").lower()
        # 如果 LLM 输出太短，也从搜索结果中查找线索
        search_text = llm_out
        if len(search_text) < 200:
            titles_and_snippets = []
            for r in results_list:
                titles_and_snippets.append(r.get("title", ""))
                titles_and_snippets.append(r.get("snippet", ""))
            search_text += " ".join(titles_and_snippets).lower()
        
        if any(kw in search_text for kw in ("确认", "confirmed", "证实", "z.ai", "zai", "智谱", "glm")):
            identity_status = "confirmed"
        elif any(kw in search_text for kw in ("疑似", "suspected", "可能", "推测")):
            identity_status = "suspected"
        elif any(kw in search_text for kw in ("争议", "disputed", "质疑")):
            identity_status = "disputed"
        else:
            identity_status = "unknown"

        # 风险等级
        risk_level = "低"
        if avg_score < 0.4:
            risk_level = "高"
        elif avg_score < 0.6:
            risk_level = "中"

        # 热度口径与报告事件画像一致（去重独立文章数 + 跨源广度）
        from intelnexus.export.report_builder import compute_heat_level
        snapshot = {
            "identity_status": identity_status,
            "heat_level": compute_heat_level(results_list, len(result.get("source_counts", {}))),
            "risk_level": risk_level,
            "key_findings": [r.get("title", "") for r in results_list[:5] if r.get("title")],
            "source_count": len(result.get("source_counts", {})),
            "result_count": len(results_list),
        }

        # 先检测变化（在保存之前）
        changes = store.detect_changes(query, snapshot)
        result["event_changes"] = changes

        # 保存快照
        store.save_snapshot(query, snapshot)

        if changes:
            logger.info(
                f"事件变化检测: {query} - "
                f"身份: {changes.get('identity_change', '无变化')}, "
                f"热度: {changes.get('heat_change', '无变化')}, "
                f"风险: {changes.get('risk_change', '无变化')}"
            )
    except Exception as e:
        logger.debug(f"事件存储失败: {e}")
        result["event_changes"] = None

    # ---- 12. 组装 14 板块结构化报告 ----
    progress_callback("finalizing", "组装结构化报告...", 0.95)

    # 报告编号：按当日历史条数自增（旧实现用 now.second % 1000，编号实为
    # 随机秒数，不唯一也不连续）。组装先于 add_search 执行，因此
    # 「当日已有条数 + 1」即本次的当日序号。
    report_id = None
    try:
        from intelnexus.config.history import get_history_manager
        _now = datetime.now()
        _today = _now.strftime("%Y-%m-%d")
        _today_count = sum(
            1 for e in get_history_manager().get_history(limit=9999, include_deleted=True)
            if str(e.get("timestamp", "")).startswith(_today)
        )
        report_id = f"INTEL-{_now.strftime('%Y%m%d')}-{_today_count + 1:03d}"
    except Exception as e:
        logger.debug(f"生成报告编号失败，回退默认规则: {e}")

    try:
        from intelnexus.export.report_builder import build_intelligence_report
        assembled = build_intelligence_report(
            query=query,
            search_mode=search_mode,
            model=model,
            llm_output=result.get("llm_raw_output", ""),
            results=result.get("results", []),
            source_counts=result.get("source_counts", {}),
            source_stats=result.get("source_stats", {}),
            credibility_data=result.get("credibility_data"),
            kg_entities=result.get("kg_entities", []),
            kg_relations=result.get("kg_relations", []),
            conflicts=result.get("conflicts", []),
            action_items=result.get("action_items", []),
            scraped=result.get("scraped", {}),
            event_changes=result.get("event_changes"),
            report_id=report_id,
        )
        result["streamed_summary"] = assembled
    except Exception as e:
        logger.warning(f"结构化报告组装失败，回退到 LLM 原始输出: {e}")
        # 回退：保持 streamed_summary 为 LLM 原始输出

    # 记录搜索历史
    try:
        from intelnexus.config.history import get_history_manager
        ranked_results = result.get("results", [])
        top_url = ""
        if ranked_results:
            top = ranked_results[0]
            top_url = top.get("url") or top.get("link") or ""
        get_history_manager().add_search(
            query, search_mode, results_count, model or "",
            selected_url=top_url,
            report_content=result.get("streamed_summary", ""),
        )
    except Exception as e:
        logger.debug(f"记录搜索历史失败: {e}")

    result["report_timestamp"] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result["success"] = True
    progress_callback("done", "完成", 1.0)
    return result
