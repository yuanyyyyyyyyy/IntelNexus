"""
知识图谱层测试（intel-search/src/analysis/intelligence_graph.py，
经 src.analysis.intelligence_graph 薄包装暴露）。

覆盖：
- EntityExtractor：降级（spaCy 不可用）、正常抽取实体与关系、短文本跳过、importance 归一化
- IntelligenceGraph：build / compute_centrality / detect_communities / export_html / to_dict / 空图处理

spaCy / pyvis 行为均通过 mock 或临时目录隔离，离线、快速、确定性。
"""
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from src.analysis.intelligence_graph import EntityExtractor, IntelligenceGraph


# ---------------------------------------------------------------------------
# EntityExtractor
# ---------------------------------------------------------------------------
class TestEntityExtractor:
    def test_fallback_when_nlp_unavailable(self):
        """spaCy 模型不可用时，extract 安全返回空结构。"""
        ex = EntityExtractor()
        with patch.object(ex, "_load_nlp", return_value=None):
            result = ex.extract({"https://x.com/a": "这是一条关于某组织的安全事件通报，内容足够长以通过长度阈值。" * 3})
        assert result["entities"] == []
        assert result["relations"] == []

    def test_skips_short_text(self):
        ex = EntityExtractor()
        with patch.object(ex, "_load_nlp", return_value=MagicMock()) as mock_nlp:
            result = ex.extract({"https://x.com/a": "太短"})
        mock_nlp.assert_not_called()
        assert result["entities"] == []

    def test_skips_empty_and_none(self):
        ex = EntityExtractor()
        with patch.object(ex, "_load_nlp", return_value=MagicMock()) as mock_nlp:
            result = ex.extract({"u1": "", "u2": None})
        mock_nlp.assert_not_called()
        assert result["entities"] == []

    def test_extract_entities_and_relations(self):
        """mock 一个 nlp，返回带两个 ORG 实体的 doc，应产生 1 条 co_occur 关系。"""
        ex = EntityExtractor()

        # 构造假 entity / sentence / doc
        def make_ent(text, label):
            ent = MagicMock()
            ent.text = text
            ent.label_ = label
            ent.start_char = 0
            ent.end_char = len(text)
            ent.sent = MagicMock()
            ent.sent.start = 0
            ent.sent.end = 1
            ent.sent.text = f"{text} 与 Alpha 合作。"
            return ent

        e1 = make_ent("Beta", "ORG")
        e2 = make_ent("Alpha", "ORG")
        sent = MagicMock()
        sent.ents = [e1, e2]

        doc = MagicMock()
        doc.ents = [e1, e2]
        doc.sents = [sent]

        fake_nlp = MagicMock(return_value=doc)
        with patch.object(ex, "_load_nlp", return_value=fake_nlp):
            result = ex.extract({
                "https://x.com/a": "Beta 与 Alpha 合作开展网络安全研究项目。" * 5,
                "https://x.com/b": "Beta 与 Alpha 合作开展网络安全研究项目。" * 5,
            })

        # 两个文档都提到 Beta/Alpha，importance 应归一化到 1.0
        ids = {e["id"]: e for e in result["entities"]}
        assert "beta" in ids and "alpha" in ids
        assert ids["beta"]["importance"] == 1.0
        assert ids["beta"]["type"] == "ORG"
        # 每个 url 各提一次，mentions 应为 2
        assert len(ids["beta"]["mentions"]) == 2
        # 关系去重：同一对只出现一次
        rel_keys = {(r["subject_id"], r["object_id"]) for r in result["relations"]}
        assert len(rel_keys) == 1
        assert all(r["predicate"] == "co_occur" for r in result["relations"])

    def test_canonical_id_normalizes(self):
        ex = EntityExtractor()
        assert ex._canonical_id("  Open AI ") == "open_ai"
        assert ex._canonical_id("A" * 100) == ("a" * 50)

    def test_detect_lang(self):
        ex = EntityExtractor()
        assert ex._detect_lang("这是中文内容 AI 安全") == "zh"
        assert ex._detect_lang("This is English AI security") == "en"


# ---------------------------------------------------------------------------
# IntelligenceGraph
# ---------------------------------------------------------------------------
def _sample_graph():
    kg = IntelligenceGraph()
    entities = [
        {"id": "alpha", "name": "Alpha", "type": "ORG", "importance": 1.0},
        {"id": "beta", "name": "Beta", "type": "ORG", "importance": 0.8},
        {"id": "gamma", "name": "Gamma", "type": "GPE", "importance": 0.5},
    ]
    relations = [
        {"subject_id": "alpha", "object_id": "beta", "predicate": "co_occur", "confidence": 0.9, "sources": ["u1", "u2"]},
        {"subject_id": "beta", "object_id": "gamma", "predicate": "located_in", "confidence": 0.6, "sources": ["u3"]},
    ]
    kg.build(entities, relations)
    return kg


class TestIntelligenceGraph:
    def test_build_creates_nodes_and_edges(self):
        kg = _sample_graph()
        assert kg.graph.number_of_nodes() == 3
        assert kg.graph.number_of_edges() == 2
        assert kg.graph.nodes["alpha"]["name"] == "Alpha"
        assert kg.graph.nodes["alpha"]["type"] == "ORG"
        # sources 应被截断到前 3 个
        edge_data = kg.graph.get_edge_data("alpha", "beta")
        assert edge_data["sources"] == ["u1", "u2"]

    def test_compute_centrality(self):
        kg = _sample_graph()
        pr = kg.compute_centrality()
        assert set(pr.keys()) == {"alpha", "beta", "gamma"}
        # 中心性按值降序
        vals = list(pr.values())
        assert vals == sorted(vals, reverse=True)

    def test_detect_communities(self):
        kg = _sample_graph()
        communities = kg.detect_communities()
        assert isinstance(communities, list)
        # 全连通图通常为一个社区
        total = sum(len(c) for c in communities)
        assert total == 3

    def test_to_dict(self):
        kg = _sample_graph()
        d = kg.to_dict()
        assert len(d["nodes"]) == 3
        assert len(d["edges"]) == 2
        assert d["edges"][0]["source"] == "alpha"
        assert d["edges"][0]["target"] == "beta"
        assert d["edges"][0]["predicate"] == "co_occur"

    def test_export_html_generates_file(self, tmp_path):
        kg = _sample_graph()
        out = tmp_path / "graph.html"
        result = kg.export_html(str(out))
        assert result == str(out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "Alpha" in content or "vis" in content.lower()

    def test_empty_graph_centrality_returns_empty(self):
        kg = IntelligenceGraph()
        assert kg.compute_centrality() == {}

    def test_empty_graph_communities_returns_empty(self):
        kg = IntelligenceGraph()
        assert kg.detect_communities() == []

    def test_empty_graph_export_html_returns_empty(self, tmp_path):
        kg = IntelligenceGraph()
        assert kg.export_html(str(tmp_path / "x.html")) == ""

    def test_empty_graph_to_dict(self):
        kg = IntelligenceGraph()
        d = kg.to_dict()
        assert d["nodes"] == []
        assert d["edges"] == []

    def test_single_node_no_community(self):
        kg = IntelligenceGraph()
        kg.build([{"id": "solo", "name": "Solo", "type": "ORG", "importance": 1.0}], [])
        assert kg.detect_communities() == []
        assert kg.compute_centrality() == {"solo": pytest.approx(1.0, rel=0.01)}


# ---------------------------------------------------------------------------
# 端到端：EntityExtractor -> IntelligenceGraph
# ---------------------------------------------------------------------------
class TestEndToEnd:
    def test_extract_then_build(self):
        ex = EntityExtractor()
        e1 = MagicMock(); e1.text = "Alpha"; e1.label_ = "ORG"
        e1.start_char = 0; e1.end_char = 5
        e1.sent = MagicMock(); e1.sent.start = 0; e1.sent.end = 1
        e1.sent.text = "Alpha 与 Beta 合作。"
        e2 = MagicMock(); e2.text = "Beta"; e2.label_ = "ORG"
        e2.start_char = 0; e2.end_char = 4
        e2.sent = MagicMock(); e2.sent.start = 0; e2.sent.end = 1
        e2.sent.text = "Alpha 与 Beta 合作。"
        sent = MagicMock(); sent.ents = [e1, e2]
        doc = MagicMock(); doc.ents = [e1, e2]; doc.sents = [sent]
        fake_nlp = MagicMock(return_value=doc)

        with patch.object(ex, "_load_nlp", return_value=fake_nlp):
            extracted = ex.extract({"https://x.com/a": "Alpha 与 Beta 合作开展研究。" * 5})

        kg = IntelligenceGraph()
        kg.build(extracted["entities"], extracted["relations"])
        assert kg.graph.number_of_nodes() >= 1
        d = kg.to_dict()
        assert len(d["nodes"]) >= 1
