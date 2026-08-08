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
from intelnexus.core.llm.utils import BufferedStreamingHandler
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
    """执行完整搜索流程"""
    st.session_state.query_cache = query
    st.session_state.search_mode_cache = search_mode
    st.session_state.threads_cache = threads
    st.session_state.model_cache = model

    for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
        st.session_state.pop(k, None)

    # 模型为空（未配置任何可用 LLM）时，避免 get_llm(None) 抛 ValueError 中断整页
    if not model:
        logger.warning("搜索中止：未配置可用模型")
        status_slot.error(get_text("no_model_error"))
        st.session_state.search_completed = False
        return

    try:
        with status_slot.container():
            with st.spinner(get_text("loading")):
                # 预热重模型（sentence-transformers 单例），把冷启动代价前置
                warm_up_models()
                llm = get_llm(model)

            with status_slot.container():
                with st.spinner(get_text("refining")):
                    query_variants = expand_query(query)
                    st.session_state.refined = query
                    search_query = expand_query_for_search(query_variants)
        
            st.markdown(f"""
            <div class="result-card">
                <div class="section-header">{get_text("refined_query")}</div>
                <div class="result-title">{get_text("original_query")} {html.escape(query)}</div>
                <div class="result-title" style="color: var(--morandi-blue);">{get_text("multilingual_query")} {html.escape(search_query)}</div>
            </div>
            """, unsafe_allow_html=True)
        
            with status_slot.container():
                with st.spinner(get_text("searching")):
                    advanced_mode = st.session_state.get("advanced_mode", False)
                    tor_port = st.session_state.get("tor_port", DEFAULT_TOR_PORT)
                    ui_sites = st.session_state.get("custom_onion_sites", [])
                    st.session_state.results = cached_search(search_mode, search_query, threads, advanced_mode, tor_port, ui_sites)
        
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
        
            st.session_state.filtered = st.session_state.results[:20]
        
            # 查询级结果缓存：同一 (mode, query, model, threads, ...) 命中时，
            # 直接复用上次的搜索结果 + 抓取内容，跳过最耗时的 IO 阶段
            result_key = build_key(
                search_mode, search_query, model, threads,
                st.session_state.get("advanced_mode", False),
                st.session_state.get("tor_port", DEFAULT_TOR_PORT))
            cached_payload = get_result(result_key)
            if cached_payload is not None:
                st.session_state.results = cached_payload.get("results", st.session_state.results)
                st.session_state.scraped = cached_payload.get("scraped", {})
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
            else:
                with status_slot.container():
                    with st.spinner(get_text("scraping")):
                        st.session_state.scraped = cached_scrape(st.session_state.filtered, threads)
                        logger.debug(f"Filtered results count: {len(st.session_state.filtered)}")
                        logger.debug(f"Scraped keys: {list(st.session_state.scraped.keys())[:5]}")
                        if st.session_state.scraped:
                            first_content = next(iter(st.session_state.scraped.values()))
                            logger.debug(f"First content length: {len(first_content)}")
                            logger.debug(f"First content preview: {first_content[:300]}")
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
        
            # 可信度评估与知识图谱构建都只依赖 scraped，二者相互独立，
            # 并行执行以缩短抓取后的等待时间
            with status_slot.container():
                with st.spinner(get_text("evaluating_credibility") + " · " + get_text("building_kg")):
                    _cred_ctx = {"credibility_context": "", "conflicts_context": ""}
        
                    def _run_credibility():
                        try:
                            _scraped_urls = list(st.session_state.scraped.keys())
                            _scraped_texts = [st.session_state.scraped[u] for u in _scraped_urls]
                            _embs = encode_texts(_scraped_texts)
                            _emb_by_url = dict(zip(_scraped_urls, _embs)) if _embs is not None else {}
        
                            scorer = SourceScorer()
                            st.session_state.results = scorer.evaluate(
                                st.session_state.results, st.session_state.scraped,
                                emb_by_url=_emb_by_url)
        
                            analyzer = ConsistencyAnalyzer()
                            consistency_data = analyzer.analyze(
                                st.session_state.results, st.session_state.scraped,
                                emb_by_url=_emb_by_url)
        
                            detector = ConflictDetector()
                            st.session_state.conflicts = detector.detect(
                                st.session_state.results, st.session_state.scraped)
        
                            scores_list = []
                            for r in st.session_state.results[:30]:
                                d = r.get("credibility_details", {})
                                scores_list.append({
                                    "name": r.get("source", "Unknown"),
                                    "score": r.get("credibility_score", 0.5),
                                    "reason": d.get("reason", ""),
                                    "domain": d.get("domain_score", 0)
                                })
                            avg = (sum(s["score"] for s in scores_list) / len(scores_list)
                                   if scores_list else 0.5)
                            st.session_state.credibility_data = {
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
                            if st.session_state.conflicts:
                                c_lines = []
                                for c in st.session_state.conflicts[:5]:
                                    c_lines.append(
                                        f"- ⚠️ [{c['type']}] {c['description']} ({get_text('severity')}: {c['severity']:.2f})")
                                conflicts_context = "\n".join(c_lines)
                            _cred_ctx["credibility_context"] = credibility_context
                            _cred_ctx["conflicts_context"] = conflicts_context
                        except Exception as e:
                            logger.error(f"可信度评估失败: {e}")
                            st.session_state.credibility_data = None
                            st.session_state.conflicts = []
                            _cred_ctx["credibility_context"] = ""
                            _cred_ctx["conflicts_context"] = ""
        
                    def _run_kg():
                        try:
                            extractor = get_entity_extractor()
                            kg_raw = extractor.extract(st.session_state.scraped)
        
                            kg = IntelligenceGraph()
                            kg.build(kg_raw["entities"], kg_raw["relations"])
        
                            st.session_state.kg_entities = [
                                {"name": e["name"], "type": e["type"],
                                 "importance": e["importance"]}
                                for e in kg_raw["entities"][:30]
                            ]
                            st.session_state.kg_relations = kg_raw["relations"]
        
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            os.makedirs("temp", exist_ok=True)
                            kg_path = kg.export_html(f"temp/kg_{timestamp}.html")
                            st.session_state.kg_html_path = kg_path
        
                            top_entities = sorted(
                                st.session_state.kg_entities,
                                key=lambda x: x["importance"], reverse=True)[:10]
                            kg_lines = [f"- {e['name']} ({e['type']})"
                                       for e in top_entities]
                            st.session_state.kg_context = "\n".join(kg_lines)
                        except Exception as e:
                            logger.error(f"知识图谱构建失败: {e}")
                            st.session_state.kg_entities = []
                            st.session_state.kg_html_path = ""
                            st.session_state.kg_context = ""
        
                    if st.session_state.scraped:
                        with ThreadPoolExecutor(max_workers=2) as _ex:
                            _f_cred = _ex.submit(_run_credibility)
                            _f_kg = _ex.submit(_run_kg)
                            _f_cred.result()
                            _f_kg.result()
                    else:
                        # 无抓取内容时仅跑可信度（KG 无意义）
                        _run_credibility()
                        st.session_state.kg_context = ""
        
                    credibility_context = _cred_ctx["credibility_context"]
                    conflicts_context = _cred_ctx["conflicts_context"]
                    kg_context = st.session_state.get("kg_context", "")
        
            st.session_state.streamed_summary = ""
        
            def ui_emit(chunk):
                st.session_state.streamed_summary += chunk
                summary_slot.markdown(st.session_state.streamed_summary)
        
            st.markdown(f"""
            <div class="report-section">
                <div class="report-title">{get_text("report_title")}</div>
            </div>
            """, unsafe_allow_html=True)
            summary_slot = st.empty()
        
            with status_slot.container():
                with st.spinner(get_text("generating")):
                    stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
                    llm.callbacks = [stream_handler]
                    _ = generate_summary(llm, query, st.session_state.scraped, search_mode,
                                         credibility_context=credibility_context,
                                         kg_context=kg_context,
                                         conflicts_context=conflicts_context)

        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        st.session_state.report_timestamp = now

        st.session_state.search_completed = True
        st.session_state.status_slot = "complete"
        st.session_state.export_format_choice = "md"

        status_slot.success(get_text("complete"))

        with status_slot.container():
            with st.spinner(get_text("tracing_evidence")):
                try:
                    tracer = EvidenceTracer()
                    st.session_state.evidence_data = tracer.trace(
                        st.session_state.streamed_summary,
                        st.session_state.scraped)
                except Exception as e:
                    logger.error(f"证据链追踪失败: {e}")
                    st.session_state.evidence_data = None
    except Exception as e:
        # 任意阶段抛异常（模型加载/检索/抓取/抓取后分析/报告）都转为页面可见提示，
        # 避免 Streamlit 脚本运行中断导致「点击搜索无反应」。
        logger.error(f"搜索流水线失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.error(f"{get_text('search_failed')}: {type(e).__name__} — {e}")
        st.session_state.search_completed = False
        st.session_state.status_slot = "error"
