import os
import html
import re
import time
import streamlit as st
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from intelnexus.core.logger import get_logger
from intelnexus.core.search.registry import SearchSourceRegistry, get_registry
from intelnexus.core.search.scraper import scrape_multiple
from intelnexus.core.llm.core import get_llm, expand_query, expand_query_for_search, generate_summary
from intelnexus.core.llm.utils import BufferedStreamingHandler, check_ollama_model_available, is_vision_model, is_ollama_local_model
from intelnexus.analysis.credibility import SourceScorer, ConsistencyAnalyzer, ConflictDetector
from intelnexus.analysis.intelligence_graph import get_entity_extractor, IntelligenceGraph
from intelnexus.analysis.evidence_tracer import EvidenceTracer
from intelnexus.analysis import warm_up_models
from intelnexus.analysis.embed_cache import encode_texts
from intelnexus.analysis.relevance import compute_query_relevance
from intelnexus.core.settings.result_cache import build_key, get_result, set_result
from intelnexus.knowledge.retrieval import retrieve_relevant, build_kb_context
from intelnexus.core.ui.helpers import DEFAULT_TOR_PORT
from intelnexus.ui.icons import icon
from intelnexus.ui.i18n import get_text
# 动态解析：data/search_settings.json(UI 显式保存) > 环境变量(.env 兜底)
# 别名保持与旧 config.NEWS_API_KEY 相同的调用形态；使用时以 NEWS_API_KEY() 取值
from intelnexus.config.search_settings import get_news_api_key as NEWS_API_KEY

logger = get_logger(__name__)

# 预检 / 网络相关超时（秒），避免 Ollama 未启动时长时间无响应
_PREFLIGHT_TIMEOUT = 3.0

# TL;DR 速览卡提取：与 core.llm.core._build_system_prompt 的报告模板对应
_TLDR_PATTERN = re.compile(
    r"##\s*TL;DR\s*情报速览\s*\n(.*?)(?=\n---|\n## |\Z)", re.DOTALL)


def _extract_tldr_card(report: str) -> str:
    """从报告中提取「## TL;DR 情报速览」卡片段落。

    无速览段或输入为空时返回空串。供管线第 9 阶段渲染速览卡使用。
    """
    if not report:
        return ""
    m = _TLDR_PATTERN.search(report)
    return m.group(1).strip() if m else ""


@st.cache_data(ttl=200, show_spinner=False)
def cached_search(mode, refined_query, threads, advanced_mode=False, tor_port=DEFAULT_TOR_PORT, ui_sites=None):
    """按 mode 遍历注册表并发检索（统一源抽象，无硬编码分支）。

    复用进程内 SearchSourceRegistry 单例（get_registry），
    避免每次检索都重建注册表并重新读取用户源磁盘文件。
    """
    registry = get_registry(
        news_api_key=NEWS_API_KEY(),
        darkweb_advanced=advanced_mode,
        tor_port=tor_port,
        ui_sites=ui_sites or [],
        web_threads=threads,
    )
    results = registry.collect(mode, refined_query, max_results=25, threads=threads)
    # F10：记录本次真实检索完成时刻；cache_data 命中时本行不执行，
    # last_search_completed_at 保持旧值，UI 以此判定缓存命中。
    import time as _time
    globals()["last_search_completed_at"] = _time.time()
    return results


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape(filtered, threads):
    return scrape_multiple(filtered, max_workers=threads)


def run_search_pipeline(query, search_mode, model, threads, status_slot):
    """执行完整搜索流程。

    智能路由：sidebar 返回的 "smart" 在此按查询主题解析为具体模式，
    下游缓存键与 LLM 模式描述均使用解析后的真实模式。

    重构要点：
    - 开头先做 Ollama 模型可用性预检，模型不可用时立即给出中文提示，避免进入耗时阶段。
    - 使用 ``st.status`` 分阶段展示进度，每段独立 ``try/except``，任一阶段失败仍保留已完成中间产物。
    - 检索无结果时提前提示，并继续展示已拿到的原始结果，不再整体挂起。
    - 报告生成独立异常边界：即便报告失败，前面的搜索结果仍可渲染。
    """
    # 方案一智能路由：smart -> 按查询分类解析为 threat / smart_general / all
    from intelnexus.core.search.modes import SMART_MODE_KEY, resolve_mode
    if search_mode == SMART_MODE_KEY:
        search_mode = resolve_mode(query)
    import time as _time_mod
    _search_started_at = _time_mod.time()  # F10：缓存命中判定基准（真实检索会更新到更晚）
    st.session_state.query_cache = query
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
            # 仅本地 Ollama 直连模型才做 Ollama 预检；云端自定义模型（如
            # DeepSeek API）跳过，否则会误报「无法连接 Ollama 服务」
            if is_ollama_local_model(model):
                available, msg = check_ollama_model_available(model, timeout=_PREFLIGHT_TIMEOUT)
                if not available:
                    pre_st.update(label=get_text("preflight_failed"), state="error")
                    status_slot.error(msg)
                    st.session_state.search_completed = False
                    return
            pre_st.update(label=get_text("preflight_ok"), state="complete")
    except Exception as e:
        logger.error(f"模型预检失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.error(f"{get_text('search_failed')}: 模型预检失败 — {type(e).__name__}: {e}")
        st.session_state.search_completed = False
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
        return

    st.markdown(f"""
    <div class="result-card">
        <div class="section-header">{get_text("refined_query")}</div>
        <div class="result-title">{get_text("original_query")} {html.escape(query)}</div>
    </div>
    """, unsafe_allow_html=True)

    # 3) 检索
    try:
        with status_slot.status(get_text("searching"), expanded=False) as search_st:
            advanced_mode = st.session_state.get("advanced_mode", False)
            tor_port = st.session_state.get("tor_port", DEFAULT_TOR_PORT)
            ui_sites = st.session_state.get("custom_onion_sites", [])
            st.session_state.results = cached_search(search_mode, search_query, threads, advanced_mode, tor_port, ui_sites)
            # F6：从注册表单例取回本次各源成败/跳过统计，供下方透明度条展示。
            # st.cache_data 命中时（200s 内同参）不会执行到这里的新检索，统计保留上次的。
            try:
                from intelnexus.core.search.registry import get_registry as _get_reg
                st.session_state.source_stats = _get_reg().last_search_stats
            except Exception as e:
                logger.debug(f"读取源级统计失败: {e}")
            search_st.update(label=get_text("search_done").format(count=len(st.session_state.results)), state="complete")
    except Exception as e:
        logger.error(f"检索失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.error(f"{get_text('search_failed')}: {type(e).__name__} — {e}")
        st.session_state.search_completed = False
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

    # F6 源完整性透明度条：N 源成功 / M 跳过，跳过原因内联展示
    _stats = st.session_state.get("source_stats") or {}
    if _stats:
        ok_sources = [n for n, s in _stats.items() if s.get("status") == "ok"]
        skipped = [(n, s.get("status")) for n, s in _stats.items()
                   if s.get("status") != "ok"]
        if skipped:
            reason_map = {"timeout": get_text("src_skip_timeout"),
                          "no_proxy": get_text("src_skip_no_proxy"),
                          "error": get_text("src_skip_error"),
                          "skipped": get_text("src_skip_skipped")}
            detail = ", ".join(f"{n} ({reason_map.get(s, s)})"
                               for n, s in skipped)
            st.info(get_text("source_integrity").format(
                ok=len(ok_sources), skip=len(skipped)) +
                f"　<sub>{html.escape(detail[:200])}</sub>")
        else:
            st.success(get_text("all_sources_ok").format(ok=len(ok_sources)))

    # F10 缓存命中提示：st.cache_data 200s 内同参数搜索直接复用（绕过新检索）
    _ran_at = globals().get("last_search_completed_at", 0)
    if _ran_at < _search_started_at:
        st.caption(get_text("cache_hit_note"))

    # 无结果：提前提示，但仍保留 results 空列表，下面结果区会显示“无结果”而不是整页空白
    if results_count == 0:
        status_slot.warning(get_text("no_results"))
        st.session_state.filtered = []
        st.session_state.search_completed = True
        st.session_state.report_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return

    # 方案A+C：语义相关性排序 + 弱相关降权标注
    # 在抓取之前完成，保证进报告/KG 的是最相关内容；模型不可用时降级到 results[:20]。
    ranked = compute_query_relevance(query, st.session_state.results)
    if ranked is not None:
        st.session_state.results = ranked
        # 高相关进 filtered 主干（弱相关沉底，不进主干统计/报告）
        st.session_state.filtered = [r for r in ranked if not r.get("weak_related", False)][:20]
        weak_count = sum(1 for r in ranked if r.get("weak_related", False))
        if weak_count:
            logger.info("相关性过滤：%d 条弱相关结果被降权（不进报告主干）", weak_count)
    else:
        # 降级：沿用原有 top-20 行为，不阻断搜索
        st.session_state.filtered = st.session_state.results[:20]

    # F8 弱相关折叠展示：兑现 relevance.py「保留可追溯」的设计承诺。
    # 弱相关条目不进报告主干，但折叠面板里可见可取证。
    _weak = [r for r in st.session_state.get("results", [])
             if r.get("weak_related", False)]
    if _weak:
        with st.expander(get_text("weak_related_expander").format(n=len(_weak))):
            for wr in _weak[:15]:
                _wscore = wr.get("relevance_score", 0.0)
                st.markdown(
                    f"- [{_wscore:.2f}] {html.escape(str(wr.get('title', ''))[:70])} "
                    f"({html.escape(str(wr.get('source', '')))})")
            if len(_weak) > 15:
                st.caption(get_text("weak_related_more").format(rest=len(_weak) - 15))

    # 查询级结果缓存：同一 (mode, query, model, threads, ...) 命中时，
    # 直接复用上次的搜索结果 + 抓取内容，跳过最耗时的 IO 阶段
    cached_payload = None
    try:
        result_key = build_key(
            search_mode, search_query, model, threads,
            st.session_state.get("advanced_mode", False),
            st.session_state.get("tor_port", DEFAULT_TOR_PORT),
            ui_sites=st.session_state.get("custom_onion_sites", []))
        cached_payload = get_result(result_key)
    except Exception as e:
        logger.error(f"读取查询缓存失败 [{type(e).__name__}]: {e}", exc_info=True)
        status_slot.warning(f"缓存读取失败，将重新检索：{e}")

    credibility_context = ""
    conflicts_context = ""
    kg_context = ""
    # 知识库 RAG：检索与本次查询相关的历史收藏，注入报告上下文；
    # 知识库为空或编码模型不可用时返回空串，行为与原管线一致
    kb_context = ""
    try:
        kb_context = build_kb_context(retrieve_relevant(query))
        if kb_context:
            logger.info("知识库命中相关条目，注入历史参考上下文")
    except Exception as e:
        logger.warning(f"知识库检索失败，跳过注入: {e}")
    cache_restored = False  # 命中缓存且已恢复报告/证据链时置 True，跳过阶段 6/7 重跑
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
            # 用缓存中的排序结果重建 filtered（弱相关沉底，不进抓取/报告主干）
            _cached_ranked = st.session_state.results
            if isinstance(_cached_ranked, list) and _cached_ranked:
                st.session_state.filtered = [
                    r for r in _cached_ranked if not r.get("weak_related", False)
                ][:20]
            # 命中缓存时一并恢复报告全文与证据链，确保与本次查询严格绑定
            # （独立于 filtered 重建，即使 results 为空也应恢复，避免跨查询串味）
            if "streamed_summary" in cached_payload or "evidence_data" in cached_payload:
                st.session_state.streamed_summary = cached_payload.get("streamed_summary", "")
                st.session_state.evidence_data = cached_payload.get("evidence_data")
                logger.info("命中查询缓存，已恢复报告全文与证据链产物")
            # 缓存的报告为空（旧版时序缺陷：阶段5先写缓存、报告尚未生成）
            # 或缓存根本没有报告字段：都触发补跑，避免用户看到空白报告。
            if not st.session_state.get("streamed_summary"):
                if cached_payload.get("streamed_summary", "") == "" and (
                        "streamed_summary" in cached_payload or "evidence_data" in cached_payload):
                    logger.warning("缓存中的报告为空（疑似旧版写入时序缺陷产物），触发补跑降级")
                else:
                    logger.info("命中查询缓存但缺少报告/证据链字段，触发补跑降级")
                try:
                    st.session_state.streamed_summary = generate_summary(
                        llm, query, st.session_state.scraped, search_mode,
                        credibility_context=credibility_context,
                        kg_context=kg_context,
                        conflicts_context=conflicts_context,
                        kb_context=kb_context) or ""
                    if st.session_state.streamed_summary:
                        tracer = EvidenceTracer()
                        st.session_state.evidence_data = tracer.trace(
                            st.session_state.streamed_summary, st.session_state.scraped)
                    else:
                        st.session_state.evidence_data = None
                except Exception as e:
                    logger.error(f"缓存补跑报告/证据链失败: {e}", exc_info=True)
                    st.session_state.streamed_summary = ""
                    st.session_state.evidence_data = None
            st.session_state.cache_restored = bool(st.session_state.get("streamed_summary"))
            if cache_restored:
                st.success(get_text("cache_restored_full"))
            else:
                st.success(get_text("cache_restored_partial"))
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
                                f"- {s['name']}: credibility_score {s['score']:.2f} ({s['reason']})")
                        credibility_context = "\n".join(cred_lines)

                        conflicts_context = ""
                        if _conflicts:
                            c_lines = []
                            for c in _conflicts[:5]:
                                c_lines.append(
                                    f"- [{c['type']}] {c['description']} (severity: {c['severity']:.2f})")
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
                # 注意：此刻报告尚未生成，streamed_summary 为空——报告完成后会二次回写，
                # 避免把「空报告」固化进缓存（旧版时序缺陷曾导致缓存命中后白屏）。
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
                    "kb_context": kb_context,
                    # 报告全文与证据链产物随查询级缓存一并保存，
                    # 与 results/scraped 视为同一查询的原子产物，避免跨查询串味
                    "streamed_summary": st.session_state.get("streamed_summary", ""),
                    "evidence_data": st.session_state.get("evidence_data"),
                })
                analyze_st.update(label=get_text("analyze_done"), state="complete")
        except Exception as e:
            logger.error(f"分析阶段异常边界外失败 [{type(e).__name__}]: {e}", exc_info=True)
            # 分析失败不阻断，继续生成报告（使用空上下文）
            credibility_context = ""
            conflicts_context = ""
            kg_context = ""

    st.markdown(f"""
    <div class="report-section">
        <div class="report-title">{get_text("report_title")}</div>
    </div>
    """, unsafe_allow_html=True)

    # 命中查询缓存且已恢复报告/证据链时，跳过阶段 6/7 重跑，直接渲染已恢复内容
    if not cache_restored:
        st.session_state.streamed_summary = ""

        def ui_emit(chunk):
            st.session_state.streamed_summary += chunk
            summary_slot.markdown(st.session_state.streamed_summary)

        # 6) 生成报告（独立异常边界：即便失败，前面结果仍可渲染）
        try:
            with status_slot.status(get_text("generating"), expanded=False) as gen_st:
                stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
                llm.callbacks = [stream_handler]
                generated = generate_summary(llm, query, st.session_state.scraped, search_mode,
                                             credibility_context=credibility_context,
                                             kg_context=kg_context,
                                             conflicts_context=conflicts_context,
                                             kb_context=kb_context)
                # generate_summary 在超时/异常时返回错误模板文本而非抛异常
                if generated:
                    st.session_state.streamed_summary = generated
                gen_st.update(label=get_text("report_done"), state="complete")
        except Exception as e:
            logger.error(f"报告生成失败 [{type(e).__name__}]: {e}", exc_info=True)
            status_slot.error(f"{get_text('report_failed')}: {type(e).__name__} — {e}")

    # 命中缓存时已恢复 evidence_data；未命中/重跑时此处确保证据链存在
    if not cache_restored or not st.session_state.get("evidence_data"):
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

    # 报告与证据链就绪后二次回写查询级缓存：把阶段5写入的「空报告」占位
    # 替换为完整产物。TTL 内重复同查询时可直接恢复全文（P0 时序缺陷修复）。
    if result_key and st.session_state.get("streamed_summary") \
            and cached_payload is not None:
        try:
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
                "kb_context": kb_context,
                "streamed_summary": st.session_state.streamed_summary,
                "evidence_data": st.session_state.get("evidence_data"),
            })
        except Exception as e:
            logger.warning(f"回写报告到查询缓存失败: {e}")

    # 8) 证据角标注入（在证据链追踪完成后）
    try:
        if st.session_state.get("evidence_data") and st.session_state.get("streamed_summary"):
            from intelnexus.analysis.evidence_annotator import annotate_report
            annotated = annotate_report(
                st.session_state.streamed_summary, st.session_state.evidence_data)
            if annotated != st.session_state.streamed_summary:
                st.session_state.streamed_summary = annotated
                summary_slot.markdown(st.session_state.streamed_summary)
    except Exception as e:
        logger.warning(f"证据角标注入失败: {e}")

    # 8.5) 可视化图表注入
    try:
        if st.session_state.get("evidence_data") or st.session_state.get("scraped"):
            from config import ENABLE_VISUALIZATION
            if ENABLE_VISUALIZATION:
                from intelnexus.analysis.visualizer import generate_threat_chart, generate_timeline_chart, inject_visuals
                charts = {}
                if st.session_state.get("evidence_data"):
                    charts["threat"] = generate_threat_chart(st.session_state.evidence_data)
                if st.session_state.get("scraped"):
                    charts["timeline"] = generate_timeline_chart(st.session_state.scraped)
                if any(charts.values()):
                    st.session_state.streamed_summary = inject_visuals(
                        st.session_state.streamed_summary, charts)
                    summary_slot.markdown(st.session_state.streamed_summary)
    except Exception as e:
        logger.warning(f"可视化图表注入失败: {e}")

    # 8.6) 行动项提取
    try:
        if st.session_state.get("streamed_summary"):
            from intelnexus.analysis.action_extractor import extract_actions
            st.session_state.action_items = extract_actions(st.session_state.streamed_summary)
    except Exception as e:
        logger.warning(f"行动项提取失败: {e}")

    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    st.session_state.report_timestamp = now

    # 9) TL;DR 速览卡提取与渲染（报告完成后）
    try:
        _tldr = _extract_tldr_card(st.session_state.get("streamed_summary", ""))
        if _tldr:
            _escaped = html.escape(_tldr)
            _escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _escaped)
            _escaped = re.sub(r"(?m)^- ", "• ", _escaped)
            summary_slot.markdown(
                f'<div class="tldr-card" style="background:var(--bg-card);border-radius:8px;'
                f'padding:16px;margin-bottom:16px;border-left:4px solid var(--border-light);">'
                f'{_escaped.replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True
            )
    except Exception as e:
        logger.warning(f"TL;DR 速览卡提取失败: {e}")

    st.session_state.search_completed = True
    st.session_state.export_format_choice = "md"

    status_slot.success(get_text("complete"))
