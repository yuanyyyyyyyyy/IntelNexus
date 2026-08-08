import os
import html
import time
import streamlit as st
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from intelnexus.core.logger import get_logger
from intelnexus.core.search.registry import SearchSourceRegistry, get_registry
from intelnexus.core.search.scraper import scrape_multiple
from intelnexus.core.llm.core import get_llm, expand_query, expand_query_for_search, generate_summary
from intelnexus.core.llm.utils import BufferedStreamingHandler, check_ollama_model_available, is_vision_model
from intelnexus.analysis.credibility import SourceScorer, ConsistencyAnalyzer, ConflictDetector
from intelnexus.analysis.intelligence_graph import get_entity_extractor, IntelligenceGraph
from intelnexus.analysis.evidence_tracer import EvidenceTracer
from intelnexus.analysis import warm_up_models
from intelnexus.analysis.embed_cache import encode_texts
from intelnexus.core.settings.result_cache import build_key, get_result, set_result
from intelnexus.core.ui.helpers import DEFAULT_TOR_PORT
from intelnexus.ui.i18n import get_text
from config import NEWS_API_KEY

logger = get_logger(__name__)

# 预检 / 网络相关超时（秒），避免 Ollama 未启动时长时间无响应
_PREFLIGHT_TIMEOUT = 3.0


@st.cache_data(ttl=200, show_spinner=False)
def cached_search(mode, refined_query, threads, advanced_mode=False, tor_port=DEFAULT_TOR_PORT, ui_sites=None):
    """按 mode 遍历注册表并发检索（统一源抽象，无硬编码分支）。

    复用进程内 SearchSourceRegistry 单例（get_registry），
    避免每次检索都重建注册表并重新读取用户源磁盘文件。
    """
    registry = get_registry(
        news_api_key=NEWS_API_KEY,
        darkweb_advanced=advanced_mode,
        tor_port=tor_port,
        ui_sites=ui_sites or [],
        web_threads=threads,
    )
    return registry.collect(mode, refined_query, max_results=25, threads=threads)


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape(filtered, threads):
    return scrape_multiple(filtered, max_workers=threads)


def run_search_pipeline(query, search_mode, model, threads, status_slot):
    """执行完整搜索流程。

    重构要点：
    - 开头先做 Ollama 模型可用性预检，模型不可用时立即给出中文提示，避免进入耗时阶段。
    - 使用 ``st.status`` 分阶段展示进度，每段独立 ``try/except``，任一阶段失败仍保留已完成中间产物。
    - 检索无结果时提前提示，并继续展示已拿到的原始结果，不再整体挂起。
    - 报告生成独立异常边界：即便报告失败，前面的搜索结果仍可渲染。
    """
    print(f">>> run_search_pipeline CALLED query={query!r} model={model!r}", flush=True)
    st.session_state.query_cache = query
    st.session_state.search_mode_cache = search_mode
    st.session_state.threads_cache = threads
    st.session_state.model_cache = model

    for k in ["refined", "results", "filtered", "scraped", "streamed_summary",
              "credibility_data", "conflicts", "kg_entities", "kg_relations",
              "kg_html_path", "kg_context", "evidence_data"]:
        st.session_state.pop(k, None)

    # 模型为空（未配置任何可用 LLM）时，避免 get_llm(None) 抛 ValueError 中断整页
    if not model:
        logger.warning("搜索中止：未配置可用模型")
        status_slot.error(get_text("no_model_error"))
        st.session_state.search_completed = False
        return

    # 阶段级状态容器，便于分别提示
    preflight_placeholder = status_slot.empty()

    # 1) 预检：Ollama 服务可达 + 模型已加载
    try:
        with preflight_placeholder.status(get_text("checking_model"), expanded=True) as pre_st:
            if is_vision_model(model):
                st.warning(get_text("vision_model_warning").format(model=model))
            available, msg = check_ollama_model_available(model, timeout=_PREFLIGHT_TIMEOUT)
            if not available:
                pre_st.update(label=get_text("preflight_failed"), state="error")
                status_slot.error(msg)
                st.session_state.search_completed = False
                st.session_state.status_slot = "error"
                return
            pre_st.update(label=get_text("preflight_ok"), state="complete")
    except Exception as e:
        logger.error(f"模型预检失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.error(f"{get_text('search_failed')}: 模型预检失败 — {type(e).__name__}: {e}")
        st.session_state.search_completed = False
        st.session_state.status_slot = "error"
        return

    # 2) 加载模型（含预热重模型） + 查询优化
    summary_slot = st.empty()
    llm = None
    search_query = ""
    try:
        with status_slot.status(get_text("loading"), expanded=False) as load_st:
            # 预热重模型（sentence-transformers 单例，带超时降级）
            warm_up_models()
            llm = get_llm(model)
            load_st.update(label=get_text("refining"), state="running")
            query_variants = expand_query(query)
            st.session_state.refined = query
            search_query = expand_query_for_search(query_variants)
            load_st.update(label=get_text("refining_done"), state="complete")
    except Exception as e:
        logger.error(f"模型加载/查询优化失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.error(f"{get_text('search_failed')}: {type(e).__name__} — {e}")
        st.session_state.search_completed = False
        st.session_state.status_slot = "error"
        return

    st.markdown(f"""
    <div class="result-card">
        <div class="section-header">{get_text("refined_query")}</div>
        <div class="result-title">{get_text("original_query")} {html.escape(query)}</div>
        <div class="result-title" style="color: var(--morandi-blue);">{get_text("multilingual_query")} {html.escape(search_query)}</div>
    </div>
    """, unsafe_allow_html=True)

    # 3) 检索
    try:
        with status_slot.status(get_text("searching"), expanded=False) as search_st:
            advanced_mode = st.session_state.get("advanced_mode", False)
            tor_port = st.session_state.get("tor_port", DEFAULT_TOR_PORT)
            ui_sites = st.session_state.get("custom_onion_sites", [])
            st.session_state.results = cached_search(search_mode, search_query, threads, advanced_mode, tor_port, ui_sites)
            search_st.update(label=get_text("search_done").format(count=len(st.session_state.results)), state="complete")
    except Exception as e:
        logger.error(f"检索失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.error(f"{get_text('search_failed')}: {type(e).__name__} — {e}")
        st.session_state.search_completed = False
        st.session_state.status_slot = "error"
        return

    source_counts = {}
    for r in st.session_state.results:
        src = r.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    results_count = len(st.session_state.results)

    source_info = " | ".join([f"{k}: {v}" for k, v in source_counts.items()])
    st.markdown(f"""
    <div class="result-card">
        <div class="result-stats">
            <div class="stat-item">
                <div class="stat-value">{results_count}</div>
                <div class="stat-label">{get_text("results_count")}</div>
            </div>
        </div>
        <div class="stat-label" style="margin-top: 10px;">{get_text("data_source_label")} {html.escape(source_info)}</div>
    </div>
    """, unsafe_allow_html=True)

    # 无结果：提前提示，但仍保留 results 空列表，下面结果区会显示“无结果”而不是整页空白
    if results_count == 0:
        status_slot.warning(get_text("no_results"))
        st.session_state.filtered = []
        st.session_state.search_completed = True
        st.session_state.status_slot = "no_results"
        st.session_state.report_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return

    st.session_state.filtered = st.session_state.results[:20]

    # 查询级结果缓存：同一 (mode, query, model, threads, ...) 命中时，
    # 直接复用上次的搜索结果 + 抓取内容，跳过最耗时的 IO 阶段
    cached_payload = None
    try:
        result_key = build_key(
            search_mode, search_query, model, threads,
            st.session_state.get("advanced_mode", False),
            st.session_state.get("tor_port", DEFAULT_TOR_PORT))
        cached_payload = get_result(result_key)
    except Exception as e:
        logger.error(f"读取查询缓存失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.warning(f"缓存读取失败，将重新检索：{e}")

    credibility_context = ""
    conflicts_context = ""
    kg_context = ""
    if cached_payload is not None:
        try:
            st.session_state.results = cached_payload.get("results", st.session_state.results)
            st.session_state.scraped = cached_payload.get("scraped", st.session_state.get("scraped", {}))
            # 命中缓存时一并恢复可信度与 KG 中间产物，彻底跳过重算
            st.session_state.credibility_data = cached_payload.get("credibility_data")
            st.session_state.conflicts = cached_payload.get("conflicts", [])
            st.session_state.kg_entities = cached_payload.get("kg_entities", [])
            st.session_state.kg_relations = cached_payload.get("kg_relations", [])
            st.session_state.kg_html_path = cached_payload.get("kg_html_path", "")
            st.session_state.kg_context = cached_payload.get("kg_context", "")
            credibility_context = cached_payload.get("credibility_context", "")
            conflicts_context = cached_payload.get("conflicts_context", "")
            kg_context = cached_payload.get("kg_context", "")
            st.success("✅ 命中查询缓存，跳过重复检索与抓取")
        except Exception as e:
            logger.error(f"恢复缓存失败 [{type(e).__name__}]: {e}", exc_info=True)
            status_slot.warning(f"缓存数据不完整，将重新分析：{e}")
            cached_payload = None
    else:
        # 4) 抓取
        try:
            with status_slot.status(get_text("scraping"), expanded=False) as scrape_st:
                st.session_state.scraped = cached_scrape(st.session_state.filtered, threads)
                logger.debug(f"Filtered results count: {len(st.session_state.filtered)}")
                logger.debug(f"Scraped keys: {list(st.session_state.scraped.keys())[:5]}")
                scrape_st.update(
                    label=get_text("scrape_done").format(count=len(st.session_state.scraped)),
                    state="complete")
        except Exception as e:
            logger.error(f"抓取失败 [{type(e).__name__}]: {e}", exc_info=True)
            status_slot.error(f"{get_text('search_failed')}: {type(e).__name__} — {e}")
            st.session_state.search_completed = False
            st.session_state.status_slot = "error"
            return

        # 5) 可信度评估 + 知识图谱构建（并行，独立错误边界，失败不阻断）
        # 注意：后台线程内不可访问 st.session_state（无 ScriptRunContext），
        # 因此将 scraped/results 以参数传入，结果通过返回值回传主线程再写入。
        try:
            with status_slot.status(get_text("evaluating_credibility") + " · " + get_text("building_kg"), expanded=False) as analyze_st:
                _scraped = st.session_state.get("scraped", {}) or {}
                _base_results = st.session_state.get("results", []) or []

                def _run_credibility(scraped, base_results):
                    try:
                        _scraped_urls = list(scraped.keys())
                        _scraped_texts = [scraped[u] for u in _scraped_urls]
                        _embs = encode_texts(_scraped_texts)
                        _emb_by_url = dict(zip(_scraped_urls, _embs)) if _embs is not None else {}

                        scorer = SourceScorer()
                        _results = scorer.evaluate(
                            base_results, scraped, emb_by_url=_emb_by_url)

                        analyzer = ConsistencyAnalyzer()
                        consistency_data = analyzer.analyze(
                            _results, scraped, emb_by_url=_emb_by_url)

                        detector = ConflictDetector()
                        _conflicts = detector.detect(_results, scraped)

                        scores_list = []
                        for r in _results[:30]:
                            d = r.get("credibility_details", {})
                            scores_list.append({
                                "name": r.get("source", "Unknown"),
                                "score": r.get("credibility_score", 0.5),
                                "reason": d.get("reason", ""),
                                "domain": d.get("domain_score", 0)
                            })
                        avg = (sum(s["score"] for s in scores_list) / len(scores_list)
                               if scores_list else 0.5)
                        _credibility_data = {
                            "scores": scores_list,
                            "avg_score": round(avg, 3),
                            "high_count": sum(1 for s in scores_list if s["score"] >= 0.7),
                            "low_count": sum(1 for s in scores_list if s["score"] < 0.4),
                            "overall_consistency": consistency_data.get(
                                "overall_consistency", 1.0)
                        }

                        cred_lines = []
                        for s in scores_list[:15]:
                            cred_lines.append(
                                f"- {s['name']}: {get_text('credibility_score')} {s['score']:.2f} ({s['reason']})")
                        credibility_context = "\n".join(cred_lines)

                        conflicts_context = ""
                        if _conflicts:
                            c_lines = []
                            for c in _conflicts[:5]:
                                c_lines.append(
                                    f"- ⚠️ [{c['type']}] {c['description']} ({get_text('severity')}: {c['severity']:.2f})")
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

                def _run_kg(scraped):
                    try:
                        extractor = get_entity_extractor()
                        kg_raw = extractor.extract(scraped)

                        kg = IntelligenceGraph()
                        kg.build(kg_raw["entities"], kg_raw["relations"])

                        _kg_entities = [
                            {"name": e["name"], "type": e["type"],
                             "importance": e["importance"]}
                            for e in kg_raw["entities"][:30]
                        ]
                        _kg_relations = kg_raw["relations"]

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        os.makedirs("temp", exist_ok=True)
                        kg_path = kg.export_html(f"temp/kg_{timestamp}.html")

                        top_entities = sorted(
                            _kg_entities,
                            key=lambda x: x["importance"], reverse=True)[:10]
                        kg_lines = [f"- {e['name']} ({e['type']})"
                                   for e in top_entities]
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

                _cred_ctx = {"credibility_context": "", "conflicts_context": ""}
                if _scraped:
                    with ThreadPoolExecutor(max_workers=2) as _ex:
                        _f_cred = _ex.submit(_run_credibility, _scraped, _base_results)
                        _f_kg = _ex.submit(_run_kg, _scraped)
                        _cred_out = _f_cred.result()
                        _kg_out = _f_kg.result()
                else:
                    # 无抓取内容时仅跑可信度（KG 无意义）
                    _cred_out = _run_credibility(_scraped, _base_results)
                    _kg_out = {
                        "kg_entities": [], "kg_relations": [],
                        "kg_html_path": "", "kg_context": "",
                    }

                # 主线程统一写回 session state（后台线程不可写 st.session_state）
                st.session_state.results = _cred_out["results"]
                st.session_state.conflicts = _cred_out["conflicts"]
                st.session_state.credibility_data = _cred_out["credibility_data"]
                st.session_state.kg_entities = _kg_out["kg_entities"]
                st.session_state.kg_relations = _kg_out["kg_relations"]
                st.session_state.kg_html_path = _kg_out["kg_html_path"]
                st.session_state.kg_context = _kg_out["kg_context"]

                credibility_context = _cred_out["credibility_context"]
                conflicts_context = _cred_out["conflicts_context"]
                kg_context = _kg_out["kg_context"]

                # 缓存搜索结果 + 抓取内容 + 可信度/KG 中间产物，供后续相同查询直接复用
                set_result(result_key, {
                    "results": st.session_state.results,
                    "scraped": st.session_state.scraped,
                    "credibility_data": st.session_state.get("credibility_data"),
                    "conflicts": st.session_state.get("conflicts", []),
                    "kg_entities": st.session_state.get("kg_entities", []),
                    "kg_relations": st.session_state.get("kg_relations", []),
                    "kg_html_path": st.session_state.get("kg_html_path", ""),
                    "kg_context": st.session_state.get("kg_context", ""),
                    "credibility_context": credibility_context,
                    "conflicts_context": conflicts_context,
                })
                analyze_st.update(label=get_text("analyze_done"), state="complete")
        except Exception as e:
            logger.error(f"分析阶段异常边界外失败 [{type(e).__name__}]: {e}", exc_info=True)
            # 分析失败不阻断，继续生成报告（使用空上下文）
            credibility_context = ""
            conflicts_context = ""
            kg_context = ""

    st.session_state.streamed_summary = ""

    def ui_emit(chunk):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    st.markdown(f"""
    <div class="report-section">
        <div class="report-title">{get_text("report_title")}</div>
    </div>
    """, unsafe_allow_html=True)

    # 6) 生成报告（独立异常边界：即便失败，前面结果仍可渲染）
    try:
        with status_slot.status(get_text("generating"), expanded=False) as gen_st:
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            generated = generate_summary(llm, query, st.session_state.scraped, search_mode,
                                         credibility_context=credibility_context,
                                         kg_context=kg_context,
                                         conflicts_context=conflicts_context)
            # generate_summary 在超时/异常时返回错误模板文本而非抛异常
            if generated:
                st.session_state.streamed_summary = generated
            gen_st.update(label=get_text("report_done"), state="complete")
    except Exception as e:
        logger.error(f"报告生成失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.error(f"{get_text('report_failed')}: {type(e).__name__} — {e}")

    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    st.session_state.report_timestamp = now

    st.session_state.search_completed = True
    st.session_state.status_slot = "complete"
    st.session_state.export_format_choice = "md"

    status_slot.success(get_text("complete"))

    # 7) 证据链追踪（独立异常边界，失败不阻断）
    try:
        with status_slot.status(get_text("tracing_evidence"), expanded=False) as ev_st:
            if st.session_state.get("streamed_summary"):
                tracer = EvidenceTracer()
                st.session_state.evidence_data = tracer.trace(
                    st.session_state.streamed_summary,
                    st.session_state.scraped)
            ev_st.update(label=get_text("evidence_done"), state="complete")
    except Exception as e:
        logger.error(f"证据链追踪失败: {e}")
        st.session_state.evidence_data = None
