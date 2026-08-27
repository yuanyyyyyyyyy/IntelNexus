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


def _extract_tldr_card(report: str) -> str:
    if not report:
        return ""
    m = _TLDR_PATTERN.search(report)
    return m.group(1).strip() if m else ""


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

    def _run_kg(scraped_data):
        try:
            from intelnexus.analysis.intelligence_graph import get_entity_extractor, IntelligenceGraph
            extractor = get_entity_extractor()
            kg_raw = extractor.extract(scraped_data)
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
            _f_kg = _ex.submit(_run_kg, _scraped)
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
        result["streamed_summary"] = generated or ""
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        result["streamed_summary"] = ""

    # ---- 9. 证据链追踪 ----
    progress_callback("evidence", "追踪证据链...", 0.85)
    try:
        if result.get("streamed_summary"):
            from intelnexus.analysis.evidence_tracer import EvidenceTracer
            tracer = EvidenceTracer()
            result["evidence_data"] = tracer.trace(
                result["streamed_summary"], result["scraped"])
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
            from intelnexus.analysis.visualizer import generate_threat_chart, generate_timeline_chart, inject_visuals
            charts = {}
            if result.get("evidence_data"):
                charts["threat"] = generate_threat_chart(result["evidence_data"])
            if result.get("scraped"):
                charts["timeline"] = generate_timeline_chart(result["scraped"])
            if any(charts.values()):
                result["streamed_summary"] = inject_visuals(result["streamed_summary"], charts)
    except Exception as e:
        logger.warning(f"可视化图表注入失败: {e}")

    # 行动项提取
    try:
        if result.get("streamed_summary"):
            from intelnexus.analysis.action_extractor import extract_actions
            result["action_items"] = extract_actions(result["streamed_summary"])
    except Exception as e:
        logger.warning(f"行动项提取失败: {e}")

    # TL;DR 速览卡
    try:
        result["tldr_card"] = _extract_tldr_card(result.get("streamed_summary", ""))
    except Exception:
        result["tldr_card"] = ""

    # 记录搜索历史
    try:
        from intelnexus.config.history import get_history_manager
        get_history_manager().add_search(query, search_mode, results_count, model or "")
    except Exception as e:
        logger.debug(f"记录搜索历史失败: {e}")

    result["report_timestamp"] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result["success"] = True
    progress_callback("done", "完成", 1.0)
    return result
