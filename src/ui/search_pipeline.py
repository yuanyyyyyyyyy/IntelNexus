import os
import streamlit as st
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from src.logger import get_logger
from src.search.web import get_web_results
from src.search.news import get_news_results
from src.search.darkweb import get_darkweb_results, is_available as darkweb_available
from src.search.scraper import scrape_multiple
from src.llm.core import get_llm, refine_query, expand_query_for_search, generate_summary
from src.llm.utils import BufferedStreamingHandler
from src.analysis.credibility import SourceScorer, ConsistencyAnalyzer, ConflictDetector
from src.analysis.intelligence_graph import EntityExtractor, IntelligenceGraph
from src.analysis.evidence_tracer import EvidenceTracer
from src.ui.helpers import DEFAULT_TOR_PORT
from src.ui.i18n import get_text

logger = get_logger(__name__)


@st.cache_data(ttl=200, show_spinner=False)
def cached_search(mode, refined_query, threads, advanced_mode=False, tor_port=DEFAULT_TOR_PORT, ui_sites=None):
    results = []
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        
        if mode in ["web", "all"]:
            futures.append(executor.submit(get_web_results, refined_query, threads, 25))
        
        if mode in ["news", "all"]:
            futures.append(executor.submit(get_news_results, refined_query, 15))
        
        if mode in ["darkweb", "all"]:
            if darkweb_available():
                futures.append(executor.submit(get_darkweb_results, refined_query, threads, advanced_mode, tor_port, ui_sites))
            else:
                logger.warning("暗网搜索已启用但Tor未连接或Ahmia不可用")
        
        for f in futures:
            try:
                results.extend(f.result())
            except Exception as e:
                logger.warning(f"Search error: {e}")
    
    return results


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

    with status_slot.container():
        with st.spinner(get_text("loading")):
            llm = get_llm(model)

    with status_slot.container():
        with st.spinner(get_text("refining")):
            query_variants = refine_query(query)
            st.session_state.refined = query
            search_query = expand_query_for_search(query_variants)

    st.markdown(f"""
    <div class="result-card">
        <div class="section-header">{get_text("refined_query")}</div>
        <div class="result-title">原始查询: {query}</div>
        <div class="result-title" style="color: var(--morandi-blue);">多语言查询: {search_query}</div>
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
        <div class="stat-label" style="margin-top: 10px;">数据来源: {source_info}</div>
    </div>
    """, unsafe_allow_html=True)

    st.session_state.filtered = st.session_state.results[:20]

    with status_slot.container():
        with st.spinner(get_text("scraping")):
            st.session_state.scraped = cached_scrape(st.session_state.filtered, threads)
            logger.debug(f"Filtered results count: {len(st.session_state.filtered)}")
            logger.debug(f"Scraped keys: {list(st.session_state.scraped.keys())[:5]}")
            if st.session_state.scraped:
                first_content = list(st.session_state.scraped.values())[0]
                logger.debug(f"First content length: {len(first_content)}")
                logger.debug(f"First content preview: {first_content[:300]}")

    with status_slot.container():
        with st.spinner("评估来源可信度..."):
            try:
                scorer = SourceScorer()
                st.session_state.results = scorer.evaluate(
                    st.session_state.results, st.session_state.scraped)

                analyzer = ConsistencyAnalyzer()
                consistency_data = analyzer.analyze(
                    st.session_state.results, st.session_state.scraped)

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
                        f"- {s['name']}: 可信度 {s['score']:.2f} ({s['reason']})")
                credibility_context = "\n".join(cred_lines)

                conflicts_context = ""
                if st.session_state.conflicts:
                    c_lines = []
                    for c in st.session_state.conflicts[:5]:
                        c_lines.append(
                            f"- ⚠️ [{c['type']}] {c['description']} (严重度: {c['severity']:.2f})")
                    conflicts_context = "\n".join(c_lines)
            except Exception as e:
                logger.error(f"可信度评估失败: {e}")
                st.session_state.credibility_data = None
                st.session_state.conflicts = []
                credibility_context = ""
                conflicts_context = ""

    with status_slot.container():
        with st.spinner("构建知识图谱..."):
            try:
                extractor = EntityExtractor()
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
                kg_context = "\n".join(kg_lines)
            except Exception as e:
                logger.error(f"知识图谱构建失败: {e}")
                st.session_state.kg_entities = []
                st.session_state.kg_html_path = ""
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
        with st.spinner("追踪证据链..."):
            try:
                tracer = EvidenceTracer()
                st.session_state.evidence_data = tracer.trace(
                    st.session_state.streamed_summary,
                    st.session_state.scraped)
            except Exception as e:
                logger.error(f"证据链追踪失败: {e}")
                st.session_state.evidence_data = None
