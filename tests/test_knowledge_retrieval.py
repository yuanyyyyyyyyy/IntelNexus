"""knowledge.retrieval 模块单测：语义检索 + 上下文格式化 + 降级路径。"""

import numpy as np
import pytest

from intelnexus.knowledge import retrieval
from intelnexus.config import knowledge_base


@pytest.fixture
def kb_file(tmp_path, monkeypatch):
    """把知识库存储指向临时文件。"""
    kb = tmp_path / "knowledge_base.json"
    monkeypatch.setattr(knowledge_base, "KB_FILE", str(kb))
    yield kb


def _make_items():
    return [
        {
            "id": "kb_1", "type": "search_result", "title": "GPT-5 发布",
            "url": "https://a.com", "content": "OpenAI 发布 GPT-5 模型",
            "source": "TechCrunch", "category": "ai", "tags": ["AI"],
            "created_at": "2026-08-01T00:00:00", "updated_at": "2026-08-01T00:00:00",
            "metadata": {},
        },
        {
            "id": "kb_2", "type": "briefing_entry", "title": "CVE-2026-1234 高危漏洞",
            "url": "https://b.com", "content": "某产品远程代码执行漏洞",
            "source": "NVD", "category": "cyber", "tags": ["漏洞"],
            "created_at": "2026-08-02T00:00:00", "updated_at": "2026-08-02T00:00:00",
            "metadata": {},
        },
    ]


class TestRetrieveRelevant:
    def test_empty_kb_returns_empty(self, kb_file, monkeypatch):
        monkeypatch.setattr(retrieval, "encode_texts", lambda texts, use_cache=True: None)
        assert retrieval.retrieve_relevant("AI") == []

    def test_model_unavailable_degrades(self, kb_file, monkeypatch):
        knowledge_base.add_item("note", "标题", content="内容")
        monkeypatch.setattr(retrieval, "encode_texts", lambda texts, use_cache=True: None)
        assert retrieval.retrieve_relevant("标题") == []

    def test_ranking_and_similarity(self, kb_file, monkeypatch):
        for item in _make_items():
            knowledge_base.add_item(
                item["type"], item["title"], url=item["url"],
                content=item["content"], tags=item["tags"])

        # 简单可控向量：条目1 沿 x 轴，条目2 沿 y 轴
        vecs = {
            "GPT-5 发布\nOpenAI 发布 GPT-5 模型": np.array([1.0, 0.0]),
            "CVE-2026-1234 高危漏洞\n某产品远程代码执行漏洞": np.array([0.0, 1.0]),
        }

        def fake_encode(texts, use_cache=True):
            if texts and texts[0] in vecs:
                return np.array([vecs[t] for t in texts])
            # query 编码
            if texts:
                q = np.array([0.9, 0.1])
                q = q / np.linalg.norm(q)
                return np.array([q])
            return None

        monkeypatch.setattr(retrieval, "encode_texts", fake_encode)

        hits = retrieval.retrieve_relevant("GPT-5", top_k=5, min_similarity=0.5)
        assert len(hits) == 1
        assert hits[0]["title"] == "GPT-5 发布"
        assert hits[0]["kb_similarity"] >= 0.5

    def test_top_k_limit(self, kb_file, monkeypatch):
        for item in _make_items():
            knowledge_base.add_item(
                item["type"], item["title"], url=item["url"],
                content=item["content"], tags=item["tags"])

        def fake_encode(texts, use_cache=True):
            return np.ones((len(texts), 4)) if texts else None

        monkeypatch.setattr(retrieval, "encode_texts", fake_encode)
        hits = retrieval.retrieve_relevant("任意", top_k=1)
        assert len(hits) == 1

    def test_empty_query_returns_empty(self, kb_file):
        assert retrieval.retrieve_relevant("  ") == []


class TestBuildKbContext:
    def test_empty(self):
        assert retrieval.build_kb_context([]) == ""

    def test_formatting(self):
        items = [{
            "title": "标题A", "created_at": "2026-08-01T10:00:00",
            "source": "Reuters", "content": "内容" * 200, "tags": ["AI"],
        }]
        ctx = retrieval.build_kb_context(items)
        assert "标题A" in ctx
        assert "2026-08-01" in ctx
        assert "Reuters" in ctx
        assert "…" in ctx  # 摘要截断

    def test_max_chars(self):
        items = [{"title": f"标题{i}", "content": "长内容" * 100} for i in range(20)]
        assert len(retrieval.build_kb_context(items, max_chars=500)) <= 510
