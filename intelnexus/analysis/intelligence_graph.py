"""
Intelligence Knowledge Graph Module
===================================
Entity extraction from scraped content and knowledge graph construction
for multi-source intelligence analysis.

Provides:
  - EntityExtractor: NER via spaCy with Chinese + English support
  - IntelligenceGraph: NetworkX-based graph with pyvis visualization
"""

import re
import os
import threading
import networkx as nx


# 模块级 EntityExtractor 单例，避免每次搜索都重建（spaCy 模型加载代价极高）
_shared_extractor = None
_extractor_lock = threading.Lock()

# 知识图谱节点标签中文字体族（CSS 字体栈，依赖浏览器本地字体回落，
# 不引入任何在线字体依赖，保持离线部署能力）
_GRAPH_CJK_FONT_FACE = "'HarmonyOS Sans SC', 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', sans-serif"


def get_entity_extractor():
    """获取进程内复用的 EntityExtractor 单例（双检锁）。"""
    global _shared_extractor
    if _shared_extractor is None:
        with _extractor_lock:
            if _shared_extractor is None:
                _shared_extractor = EntityExtractor()
    return _shared_extractor


class EntityExtractor:
    """
    Extract named entities from scraped content using spaCy NER.

    Supports Chinese (zh_core_web_sm) and English (en_core_web_sm).
    Falls back gracefully if spaCy models are not installed.
    """

    def __init__(self):
        self._nlp_zh = None
        self._nlp_en = None

    def extract(self, scraped_content):
        """
        Extract entities and relations from all scraped content.

        Args:
            scraped_content: dict of {url: scraped_text}

        Returns:
            dict with keys:
              - entities: list of entity dicts
              - relations: list of relation dicts
        """
        all_entities = {}
        all_relations = []

        for url, text in scraped_content.items():
            if not text or len(text) < 50:
                continue

            lang = self._detect_lang(text)
            nlp = self._load_nlp(lang)
            if nlp is None:
                continue

            doc = nlp(text[:5000])

            for ent in doc.ents:
                if ent.label_ in ('PERSON', 'ORG', 'GPE', 'LOC', 'EVENT',
                                  'DATE', 'PRODUCT', 'MONEY', 'NORP', 'LAW'):
                    eid = self._canonical_id(ent.text)
                    if eid not in all_entities:
                        all_entities[eid] = {
                            "id": eid,
                            "name": ent.text,
                            "type": ent.label_,
                            "mentions": [],
                            "importance": 0
                        }
                    ctx_start = max(0, ent.start_char - 40)
                    ctx_end = min(len(text), ent.end_char + 40)
                    all_entities[eid]["mentions"].append({
                        "source_url": url,
                        "context": text[ctx_start:ctx_end],
                        "sentence": doc[ent.sent.start:ent.sent.end].text
                    })

            for sent in doc.sents:
                sent_entities = [
                    e for e in sent.ents
                    if e.label_ in ('PERSON', 'ORG', 'GPE', 'PRODUCT')
                ]
                if len(sent_entities) >= 2:
                    for i in range(len(sent_entities)):
                        for j in range(i + 1, len(sent_entities)):
                            src_id = self._canonical_id(sent_entities[i].text)
                            tgt_id = self._canonical_id(sent_entities[j].text)
                            if src_id and tgt_id and src_id != tgt_id:
                                all_relations.append({
                                    "subject_id": src_id,
                                    "predicate": "co_occur",
                                    "object_id": tgt_id,
                                    "confidence": 0.5,
                                    "sources": [url]
                                })

        seen_rels = set()
        unique_rels = []
        for rel in all_relations:
            key = (rel["subject_id"], rel["predicate"], rel["object_id"])
            if key not in seen_rels:
                seen_rels.add(key)
                unique_rels.append(rel)

        max_mentions = max(
            (len(e["mentions"]) for e in all_entities.values()), default=1
        )
        for e in all_entities.values():
            e["importance"] = round(len(e["mentions"]) / max_mentions, 3)

        return {
            "entities": sorted(
                all_entities.values(), key=lambda x: x["importance"], reverse=True
            ),
            "relations": unique_rels
        }

    def _detect_lang(self, text):
        return 'zh' if any('\u4e00' <= c <= '\u9fff' for c in text[:200]) else 'en'

    def _load_nlp(self, lang):
        try:
            import spacy
            if lang == 'zh':
                if self._nlp_zh is None:
                    self._nlp_zh = spacy.load(
                        'zh_core_web_sm', disable=['parser', 'lemmatizer']
                    )
                    self._nlp_zh.add_pipe('sentencizer')
                return self._nlp_zh
            else:
                if self._nlp_en is None:
                    self._nlp_en = spacy.load(
                        'en_core_web_sm', disable=['parser', 'lemmatizer']
                    )
                    self._nlp_en.add_pipe('sentencizer')
                return self._nlp_en
        except (OSError, ValueError, ImportError):
            return None

    def _canonical_id(self, name):
        return re.sub(r'\s+', '_', name.strip().lower())[:50]


class IntelligenceGraph:
    """
    NetworkX-based knowledge graph with centrality analysis and HTML export.

    Usage:
        kg = IntelligenceGraph()
        kg.build(entities, relations)
        kg.compute_centrality()
        kg.export_html("output.html")
    """

    def __init__(self):
        self.graph = nx.Graph()

    def build(self, entities, relations):
        for e in entities:
            self.graph.add_node(
                e["id"],
                name=e["name"],
                type=e["type"],
                importance=e["importance"]
            )
        for r in relations:
            self.graph.add_edge(
                r["subject_id"], r["object_id"],
                predicate=r.get("predicate", "related"),
                confidence=r.get("confidence", 0.5),
                sources=r.get("sources", [])[:3]
            )

    def compute_centrality(self):
        if self.graph.number_of_nodes() == 0:
            return {}
        try:
            pr = nx.pagerank(self.graph, alpha=0.85)
            return dict(sorted(pr.items(), key=lambda x: x[1], reverse=True))
        except Exception:
            return {}

    def detect_communities(self):
        if self.graph.number_of_nodes() < 2:
            return []
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            communities = greedy_modularity_communities(self.graph)
            return [sorted(list(c)) for c in communities]
        except Exception:
            return []

    def export_html(self, output_path):
        if self.graph.number_of_nodes() == 0:
            return ""
        try:
            from pyvis.network import Network
            net = Network(
                height="600px", width="100%",
                bgcolor="#FAFAFA", font_color="#1A1A1A"
            )
            # 全局节点标签中文字体。直接赋 dict 型 options（pyvis 会 json.dumps 原样渲染）；
            # 不能用 set_options：其 Options.set 会剔除字符串内全部空格，
            # 导致 'HarmonyOS Sans SC' 这类含空格的字体名损坏。
            net.options = {"nodes": {"font": {"face": _GRAPH_CJK_FONT_FACE}}}

            type_colors = {
                "PERSON": "#1A1A1A", "ORG": "#0055FF", "GPE": "#4ADE80",
                "EVENT": "#EF5350", "DATE": "#666666", "PRODUCT": "#0055FF",
                "MONEY": "#4ADE80", "NORP": "#666666", "LAW": "#CCCCCC",
                "LOC": "#4ADE80", "UNKNOWN": "#999999",
            }

            # 计算中心度和社区
            centrality = self.compute_centrality()
            communities = self.detect_communities()
            node_community = {}
            for i, comm in enumerate(communities):
                for n in comm:
                    node_community[n] = i

            for n, data in self.graph.nodes(data=True):
                sz = data.get("importance", 0.5) * 30 + 10
                c = type_colors.get(data.get("type", ""), "#999999")
                label = data.get("name", n)
                cent = centrality.get(n, 0.0)
                comm = node_community.get(n, -1)
                title = f"{label} ({data.get('type', '?')})\n中心度: {cent:.3f}\n社区: {comm if comm >= 0 else '无'}"
                net.add_node(n, label=label, title=title, size=sz, color=c)

            for u, v, data in self.graph.edges(data=True):
                net.add_edge(
                    u, v,
                    title=data.get("predicate", "related"),
                    value=data.get("confidence", 0.5) * 3
                )

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            net.save_graph(output_path)
            return output_path
        except Exception:
            return ""

    def to_dict(self):
        nodes = []
        for n, data in self.graph.nodes(data=True):
            nodes.append({
                "id": n,
                "name": data.get("name", n),
                "type": data.get("type", "UNKNOWN"),
                "importance": data.get("importance", 0.5)
            })
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "predicate": data.get("predicate", "related"),
                "confidence": data.get("confidence", 0.5)
            })

        # 计算中心度和社区检测
        centrality = self.compute_centrality()
        communities = self.detect_communities()

        # 为每个节点添加中心度和社区信息
        for node in nodes:
            node["centrality"] = centrality.get(node["id"], 0.0)
            node["community"] = -1
            for i, comm in enumerate(communities):
                if node["id"] in comm:
                    node["community"] = i
                    break

        return {
            "nodes": nodes,
            "edges": edges,
            "centrality": centrality,
            "communities": communities
        }
