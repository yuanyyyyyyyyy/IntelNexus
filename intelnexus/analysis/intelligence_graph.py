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
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


# 模块级 EntityExtractor 单例，避免每次搜索都重建（spaCy 模型加载代价极高）
_shared_extractor = None
_extractor_lock = threading.Lock()

# 知识图谱节点标签中文字体族（CSS 字体栈，依赖浏览器本地字体回落，
# 不引入任何在线字体依赖，保持离线部署能力）
_GRAPH_CJK_FONT_FACE = "'Noto Serif SC', 'Source Han Serif SC', 'HarmonyOS Sans SC', 'Microsoft YaHei', serif"

# ============================================================================
# 噪声实体过滤层
# ============================================================================
# 网页结构词 / JSON 字段 / 程序变量 / 导航词 / 通用停用词
# 这些词常被 spaCy 或正则误判为实体，必须剔除
_ENTITY_BLACKLIST = frozenset({
    # HTML / JSON / API 字段名
    'user', 'role', 'content', 'data', 'id', 'type', 'name', 'value',
    'key', 'status', 'code', 'message', 'result', 'items', 'list',
    'array', 'object', 'string', 'number', 'boolean', 'null', 'true',
    'false', 'token', 'session', 'header', 'body', 'request', 'response',
    'url', 'uri', 'path', 'query', 'param', 'args', 'kwargs',
    # 程序变量 / 类型名
    'i', 'j', 'k', 'x', 'y', 'z', 'n', 'm', 'len', 'str', 'int',
    'float', 'dict', 'set', 'tuple', 'range', 'map', 'filter',
    'var', 'func', 'fn', 'obj', 'cls', 'self', 'this',
    # 导航 / UI 词
    'menu', 'nav', 'home', 'back', 'next', 'prev', 'page', 'login',
    'logout', 'search', 'submit', 'cancel', 'ok', 'yes', 'no',
    'click', 'button', 'link', 'form', 'input', 'select', 'option',
    'div', 'span', 'table', 'tr', 'td', 'th', 'img', 'a', 'p',
    'html', 'head', 'body', 'script', 'style', 'css', 'js',
    # 通用英文停用词（常被正则误抽为大写短语）
    'the', 'this', 'that', 'with', 'from', 'have', 'been',
    'will', 'would', 'could', 'should', 'their', 'there',
    'about', 'also', 'after', 'again', 'against', 'all', 'am', 'an',
    'and', 'any', 'are', 'as', 'at', 'be', 'because', 'but', 'by',
    'can', 'do', 'does', 'did', 'don', 'each', 'few', 'for', 'further',
    'had', 'has', 'he', 'her', 'here', 'hers', 'herself', 'him',
    'himself', 'his', 'how', 'if', 'in', 'into', 'is', 'it', 'its',
    'itself', 'just', 'me', 'might', 'more', 'most', 'my', 'myself',
    'nor', 'not', 'now', 'of', 'off', 'on', 'once', 'only', 'or',
    'other', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 're',
    'same', 'she', 'so', 'some', 'such', 'than', 'them', 'themselves',
    'then', 'these', 'they', 'those', 'through', 'to', 'too', 'under',
    'until', 'up', 'us', 'very', 'was', 'we', 'were', 'what', 'when',
    'where', 'which', 'while', 'who', 'whom', 'why', 'won', 'you',
    'your', 'yours', 'yourself', 'yourselves',
    # 中文噪声词
    '用户', '角色', '内容', '数据', '类型', '名称', '值', '状态',
    '代码', '消息', '结果', '列表', '对象', '字符串', '数字',
    '首页', '返回', '下一页', '上一页', '页面', '登录', '退出',
    '搜索', '提交', '取消', '确定', '是', '否', '点击', '按钮',
    '链接', '表单', '输入', '选择', '选项',
})

# 噪声实体正则模式：匹配纯数字、纯符号、过短文本等
_NOISE_PATTERNS = [
    re.compile(r'^[\d\s\W]+$'),          # 纯数字/符号/空白
    re.compile(r'^[a-z]$'),              # 单个小写字母
    re.compile(r'^[A-Z]$'),              # 单个大写字母
    re.compile(r'^\d{4}$'),              # 纯四位数字（年份误判）
    re.compile(r'^v\d+\.\d+', re.I),     # 版本号 v1.0, v2.3
]


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

    @staticmethod
    def _is_noise_entity(name: str) -> bool:
        """判断实体名是否为噪声（网页结构词 / JSON 字段 / 程序变量 / 停用词）。

        返回 True 表示应过滤掉该实体。
        """
        if not name or len(name.strip()) < 2:
            return True
        clean = name.strip()
        # 黑名单精确匹配（不区分大小写）
        if clean.lower() in _ENTITY_BLACKLIST:
            return True
        # 正则模式匹配
        for pat in _NOISE_PATTERNS:
            if pat.match(clean):
                return True
        return False

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
        spacy_used = False

        for url, text in scraped_content.items():
            if not text or len(text) < 50:
                continue

            lang = self._detect_lang(text)
            nlp = self._load_nlp(lang)
            if nlp is not None:
                spacy_used = True
                self._extract_spacy(nlp, text, url, all_entities, all_relations)
            else:
                # Fallback: regex-based entity extraction
                self._extract_regex(text, url, all_entities, all_relations)

        # If spaCy was never used and we still have no entities, try search result titles
        if not spacy_used and not all_entities:
            logger.info("spaCy models unavailable, using regex fallback for entity extraction")

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

    def _extract_spacy(self, nlp, text, url, all_entities, all_relations):
        """Extract entities using spaCy NLP pipeline."""
        doc = nlp(text[:5000])

        for ent in doc.ents:
            if ent.label_ in ('PERSON', 'ORG', 'GPE', 'LOC', 'EVENT',
                              'DATE', 'PRODUCT', 'MONEY', 'NORP', 'LAW'):
                if self._is_noise_entity(ent.text):
                    continue
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
                and not self._is_noise_entity(e.text)
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

    def _extract_regex(self, text, url, all_entities, all_relations):
        """Fallback regex-based entity extraction when spaCy is unavailable.

        Extracts:
        - Quoted names: "Entity Name" or 'Entity Name'
        - Capitalized multi-word phrases (English)
        - Known patterns: company suffixes, product names
        - Chinese organization/person patterns
        """
        # Pattern 1: Quoted entities
        for m in re.finditer(r'[""\']([^""\'\']{2,30})[""\'\']', text[:5000]):
            name = m.group(1).strip()
            if len(name) >= 2 and not self._is_noise_entity(name):
                eid = self._canonical_id(name)
                if eid not in all_entities:
                    etype = self._guess_entity_type(name)
                    all_entities[eid] = {
                        "id": eid, "name": name, "type": etype,
                        "mentions": [{"source_url": url, "context": "", "sentence": ""}],
                        "importance": 0
                    }
                else:
                    all_entities[eid]["mentions"].append(
                        {"source_url": url, "context": "", "sentence": ""})

        # Pattern 2: English capitalized phrases (multi-word)
        for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b', text[:5000]):
            name = m.group(1).strip()
            # Filter out common false positives
            if self._is_noise_entity(name):
                continue
            eid = self._canonical_id(name)
            if eid not in all_entities:
                etype = self._guess_entity_type(name)
                all_entities[eid] = {
                    "id": eid, "name": name, "type": etype,
                    "mentions": [{"source_url": url, "context": "", "sentence": ""}],
                    "importance": 0
                }
            else:
                all_entities[eid]["mentions"].append(
                    {"source_url": url, "context": "", "sentence": ""})

        # Pattern 3: Chinese organization patterns (XX公司, XX科技, etc.)
        zh_patterns = [
            r'([\u4e00-\u9fff]{2,8}(?:公司|集团|科技|技术|网络|安全|实验室|中心|研究院))',
            r'([\u4e00-\u9fff]{2,6}(?:漏洞|攻击|恶意软件|勒索|钓鱼|木马))',
        ]
        for pattern in zh_patterns:
            for m in re.finditer(pattern, text[:5000]):
                name = m.group(1).strip()
                if self._is_noise_entity(name):
                    continue
                eid = self._canonical_id(name)
                if eid not in all_entities:
                    etype = "ORG" if "公司" in name or "集团" in name else "PRODUCT"
                    all_entities[eid] = {
                        "id": eid, "name": name, "type": etype,
                        "mentions": [{"source_url": url, "context": "", "sentence": ""}],
                        "importance": 0
                    }
                else:
                    all_entities[eid]["mentions"].append(
                        {"source_url": url, "context": "", "sentence": ""})

        # Pattern 4: Build relations from co-occurrence in paragraphs
        paragraphs = re.split(r'\n\s*\n', text[:5000])
        entity_ids_in_para = []
        for para in paragraphs:
            para_entities = []
            for eid in all_entities:
                name = all_entities[eid]["name"]
                if name.lower() in para.lower():
                    para_entities.append(eid)
            if len(para_entities) >= 2:
                for i in range(len(para_entities)):
                    for j in range(i + 1, len(para_entities)):
                        entity_ids_in_para.append(
                            (para_entities[i], para_entities[j], url))

        for src_id, tgt_id, src_url in entity_ids_in_para[:50]:
            all_relations.append({
                "subject_id": src_id,
                "predicate": "co_occur",
                "object_id": tgt_id,
                "confidence": 0.4,
                "sources": [src_url]
            })

    def _guess_entity_type(self, name: str) -> str:
        """Guess entity type from name patterns."""
        org_suffixes = ('Inc', 'Corp', 'Ltd', 'LLC', 'Company', 'Group',
                        '公司', '集团', '科技', '实验室')
        if any(name.endswith(s) for s in org_suffixes):
            return "ORG"
        if any(kw in name for kw in ('AI', 'Model', 'OS', 'API', 'SDK', 'GPT', 'LLM')):
            return "PRODUCT"
        if any(kw in name for kw in ('漏洞', '攻击', 'CVE', 'exploit')):
            return "EVENT"
        return "ORG"  # Default to ORG for capitalized phrases

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
