"""知识库条目一键转 Topic 的单元测试。"""

import pytest

from intelnexus.topics import store as topic_store


@pytest.fixture
def topics_file(tmp_path, monkeypatch):
    """把 Topic 存储指向临时文件。"""
    f = tmp_path / "topics.json"
    monkeypatch.setattr(topic_store, "TOPICS_FILE", str(f))
    yield f


def _convert(item):
    # 与 ui/knowledge_base._convert_item_to_topic 相同的导入路径
    from intelnexus.ui.knowledge_base import _convert_item_to_topic
    return _convert_item_to_topic(item)


def _item(title="GPT-5 安全风险分析", tags=None):
    return {
        "id": "kb_1", "type": "search_result", "title": title,
        "url": "https://a.com", "content": "内容", "tags": tags or ["AI"],
        "metadata": {},
    }


class TestConvertItemToTopic:
    def test_creates_topic(self, topics_file):
        topic_id = _convert(_item())
        assert topic_id and topic_id.startswith("topic_")
        kb_topics = [t for t in topic_store.get_all_topics() if t.origin == "kb_item"]
        assert len(kb_topics) == 1
        assert kb_topics[0].search_queries == ["GPT-5 安全风险分析"]
        # 标签并入中文关键词
        assert "AI" in kb_topics[0].keywords_zh

    def test_idempotent_when_exists(self, topics_file):
        first = _convert(_item())
        assert first is not None
        # 已存在同类 Topic 时返回 None（UI 显示"已在巡防中"）
        assert _convert(_item()) is None
        kb_topics = [t for t in topic_store.get_all_topics() if t.origin == "kb_item"]
        assert len(kb_topics) == 1

    def test_different_titles_create_distinct_topics(self, topics_file):
        assert _convert(_item("主题A"))
        assert _convert(_item("主题B"))
        kb_topics = [t for t in topic_store.get_all_topics() if t.origin == "kb_item"]
        assert len({t.id for t in kb_topics}) == 2

    def test_empty_title_returns_none(self, topics_file):
        assert _convert(_item(title="  ")) is None
