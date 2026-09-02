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
# 语义关系类型定义
# ============================================================================
# 根据上下文关键词推断实体间的语义关系
_RELATION_PATTERNS = [
    # (关系类型，中文关键词，英文关键词)
    ("developed_by", ["开发", "研发", "创造", "构建"], ["developed by", "created by", "built by"]),
    ("released_on", ["发布", "推出", "上线"], ["released on", "launched on", "announced on"]),
    ("competes_with", ["竞争", "对手", "竞品"], ["competes with", "rival", "competitor"]),
    ("derived_from", ["基于", "源自", "派生"], ["based on", "derived from", "forked from"]),
    ("mentioned_by", ["报道", "提及", "引用"], ["reported by", "mentioned by", "cited by"]),
    ("tested_by", ["测试", "评估", "验证"], ["tested by", "evaluated by", "verified by"]),
    ("risk_related", ["风险", "威胁", "漏洞"], ["risk", "threat", "vulnerability"]),
    ("owned_by", ["拥有", "所属", "旗下"], ["owned by", "belongs to", "subsidiary of"]),
    ("partnered_with", ["合作", "联盟", "伙伴"], ["partnered with", "alliance", "partnership"]),
    ("acquired_by", ["收购", "并购", "投资"], ["acquired by", "merged with", "invested by"]),
]

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
    # 通用概念词（不是具体实体）
    'clear', 'model', 'rating', 'terms', 'privacy', 'support',
    'documentation', 'about', 'contact', 'blog', 'careers',
    'elo rating', 'stealth model terms', 'zero data retention generous',
    # prompt 残片（LLM 系统提示词泄漏到网页内容中）
    'you are', 'system prompt', 'assistant', 'human', 'chatgpt',
    # 泛化技术概念（不是具体产品/组织/人物）
    'context window', 'live status', 'token', 'tokens', 'benchmark',
    'multi-agent', 'inference', 'fine-tuning', 'pre-training',
    # 无关技术词（搜索结果中可能混入的跑题内容）
    '量子微波测量技术', '微波测量', '卡丁车游戏', '体素场景',
    # API 端点/产品术语（不是具体组织/人物/地点）
    'chat completions', 'stealth model', 'agentic work',
    'hermes agent', 'openrouter', 'opencode',
    # 网页抓取残片（句子片段不应作为实体）
    'grith', 'freiburg fc', 'texas tech softball',
})

# 噪声实体正则模式：匹配纯数字、纯符号、过短文本等
_NOISE_PATTERNS = [
    re.compile(r'^[\d\s\W]+$'),          # 纯数字/符号/空白
    re.compile(r'^[a-z]$'),              # 单个小写字母
    re.compile(r'^[A-Z]$'),              # 单个大写字母
    re.compile(r'^\d{4}$'),              # 纯四位数字（年份误判）
    re.compile(r'^v\d+\.\d+', re.I),     # 版本号 v1.0, v2.3
    re.compile(r'^[\w-]+/[\w-]+$'),       # URL 路径片段（如 stealth/ox-alpha）
    re.compile(r'^[a-z0-9]+(?:_[a-z0-9]+)+$'),  # 下划线 slug（网站导航/URL 残片，如 about_get、try_now）
    re.compile(r'^(首次|这种|这类|该项|这些|那些|其次|此外|本次|相关|有关)'),  # 中文指示词开头的伪实体（如「首次」「这种技术」）
    re.compile(r'^(you are|system|assistant|human)\b', re.I),  # prompt 残片
    re.compile(r'^(miwn|mshale|jzkv|freiburg)', re.I),  # Google News 注入的随机标签
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
        # 长度过滤：超过 40 字符的实体通常是标题片段或描述词，不是有效实体
        if len(clean) > 40:
            return True
        # URL 过滤：包含协议符、斜杠路径或 www. 的实体
        if any(pattern in clean for pattern in ('://', 'http', 'www.', '/api/', '/v1', '/v2')):
            return True
        # 中文句子过滤：包含中文字符且长度 >10 的实体大概率是句子片段
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in clean)
        if has_chinese and len(clean) > 10:
            return True
        # 黑名单精确匹配（不区分大小写）
        if clean.lower() in _ENTITY_BLACKLIST:
            return True
        # 正则模式匹配
        for pat in _NOISE_PATTERNS:
            if pat.match(clean):
                return True
        return False

    @staticmethod
    def _normalize_entity_name(name: str) -> str:
        """规范化实体名称（去重、清理）。
        
        处理：
        - 移除重复词（如 "Ox Alpha Ox Alpha" → "Ox Alpha"）
        - 移除首尾空白
        """
        if not name:
            return name
        
        # 移除重复词（保留首次出现顺序）
        words = name.strip().split()
        if len(words) > 1:
            seen = set()
            deduped = []
            for w in words:
                w_lower = w.lower()
                if w_lower not in seen:
                    seen.add(w_lower)
                    deduped.append(w)
            return ' '.join(deduped)
        
        return name.strip()

    def extract(self, scraped_content, search_results=None):
        """
        Extract entities and relations from all scraped content.

        Args:
            scraped_content: dict of {url: scraped_text}
            search_results: optional list of search result dicts (for fallback)

        Returns:
            dict with keys:
              - entities: list of entity dicts
              - relations: list of relation dicts
        """
        all_entities = {}
        all_relations = []
        spacy_used = False

        # 降低最小长度要求，允许短标题/摘要参与抽取
        for url, text in scraped_content.items():
            if not text or len(text) < 20:
                continue

            lang = self._detect_lang(text)
            nlp = self._load_nlp(lang)
            if nlp is not None:
                spacy_used = True
                self._extract_spacy(nlp, text, url, all_entities, all_relations)
            else:
                # Fallback: regex-based entity extraction
                self._extract_regex(text, url, all_entities, all_relations)

        # 如果抓取内容未找到实体，尝试从搜索结果标题/摘要中抽取
        if not all_entities and search_results:
            logger.info("从搜索结果标题/摘要中抽取实体（降级方案）")
            for r in search_results:
                title = r.get('title', '')
                snippet = r.get('snippet', '')
                text = f"{title}. {snippet}" if snippet else title
                if len(text) >= 15:
                    self._extract_regex(text, r.get('url', ''), all_entities, all_relations)

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

        # 尝试推断更语义化的关系类型
        for rel in unique_rels:
            if rel["predicate"] == "co_occur":
                # 从源文本中查找关系线索
                for src_url in rel.get("sources", []):
                    if src_url in all_entities.get(rel["subject_id"], {}).get("mentions", [{}])[0].get("source_url", ""):
                        context = all_entities.get(rel["subject_id"], {}).get("mentions", [{}])[0].get("sentence", "")
                        inferred = self._infer_relation_type(context)
                        if inferred:
                            rel["predicate"] = inferred
                            rel["confidence"] = min(1.0, rel.get("confidence", 0.5) + 0.1)
                        break

        # 规范化实体名称（去重、清理）
        for e in all_entities.values():
            e["name"] = self._normalize_entity_name(e["name"])

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

    def _infer_relation_type(self, context: str) -> str:
        """从上下文推断关系类型。

        Args:
            context: 包含两个实体的句子/段落

        Returns:
            关系类型字符串，或空字符串（无法推断时）
        """
        if not context:
            return ""

        context_lower = context.lower()

        for rel_type, zh_keywords, en_keywords in _RELATION_PATTERNS:
            # 检查中文关键词
            if any(kw in context for kw in zh_keywords):
                return rel_type
            # 检查英文关键词
            if any(kw in context_lower for kw in en_keywords):
                return rel_type

        return ""

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

    @staticmethod
    def _canonical_id(name):
        # 统一连字符和下划线为空格，然后转小写+下划线；
        # 先去掉尾部标点，避免 "Ox Alpha" 与 "Ox Alpha." 生成两个实体
        normalized = name.strip().rstrip('.。,，;；!！?？·：:').lower().replace('-', ' ').replace('_', ' ')
        return re.sub(r'\s+', '_', normalized)[:50]


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
