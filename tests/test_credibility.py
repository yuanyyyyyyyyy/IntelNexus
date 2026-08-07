"""Tests for credibility scoring, consistency analysis, and conflict detection."""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np


class MockSentenceModel:
    """Mock sentence-transformers model for testing."""

    def __init__(self, embeddings=None):
        self._embeddings = embeddings

    def encode(self, texts, show_progress_bar=False):
        if self._embeddings is not None:
            return self._embeddings[:len(texts)]
        # Generate deterministic mock embeddings based on text content
        result = []
        for t in texts:
            h = hash(t) % 1000
            vec = np.array([float(h + i) for i in range(384)])
            vec = vec / (np.linalg.norm(vec) + 1e-10)
            result.append(vec)
        return np.array(result)


@pytest.fixture
def mock_model():
    return MockSentenceModel()


@pytest.fixture
def scorer(mock_model):
    with patch("src.analysis.credibility.load_sentence_model", return_value=mock_model):
        from intelnexus.analysis.credibility import SourceScorer
        return SourceScorer()


@pytest.fixture
def consistency_analyzer(mock_model):
    with patch("src.analysis.credibility.load_sentence_model", return_value=mock_model):
        from intelnexus.analysis.credibility import ConsistencyAnalyzer
        return ConsistencyAnalyzer()


class TestSourceScorer:
    """Tests for SourceScorer.evaluate()."""

    def test_evaluate_adds_scores(self, scorer, sample_search_results, sample_scraped_content):
        """Each result should get credibility_score and credibility_details."""
        results = scorer.evaluate(sample_search_results, sample_scraped_content)
        for r in results:
            assert "credibility_score" in r
            assert "credibility_details" in r
            assert 0 <= r["credibility_score"] <= 1

    def test_gov_domain_high_score(self, scorer):
        """www.example.gov domain should get high domain authority via .gov TLD."""
        results = [{"title": "test", "link": "https://www.example.gov/report", "source": "gov"}]
        scraped = {"https://www.example.gov/report": "A" * 500}
        results = scorer.evaluate(results, scraped)
        assert results[0]["credibility_details"]["domain_score"] >= 0.7

    def test_edu_domain_high_score(self, scorer):
        """edu domain should get high domain authority."""
        results = [{"title": "test", "link": "https://stanford.edu/research", "source": "Stanford"}]
        scraped = {"https://stanford.edu/research": "A" * 500}
        results = scorer.evaluate(results, scraped)
        assert results[0]["credibility_details"]["domain_score"] >= 0.7

    def test_trusted_domain_high_score(self, scorer):
        """reuters.com should get high domain authority."""
        results = [{"title": "test", "link": "https://www.reuters.com/article", "source": "Reuters"}]
        scraped = {"https://www.reuters.com/article": "A" * 500}
        results = scorer.evaluate(results, scraped)
        assert results[0]["credibility_details"]["domain_score"] >= 0.7

    def test_unknown_domain_low_score(self, scorer):
        """Unknown domains should get default low score."""
        results = [{"title": "test", "link": "https://random-blog.com/post", "source": "Blog"}]
        scraped = {"https://random-blog.com/post": "A" * 500}
        results = scorer.evaluate(results, scraped)
        assert results[0]["credibility_details"]["domain_score"] == 0.4

    def test_aggregator_source(self, scorer):
        """Aggregator sources (Bing, Google) should get 0.5."""
        results = [{"title": "test", "link": "https://bing.com/search", "source": "Bing"}]
        scraped = {"https://bing.com/search": "A" * 500}
        results = scorer.evaluate(results, scraped)
        assert results[0]["credibility_details"]["domain_score"] == 0.5

    def test_news_source_freshness(self, scorer):
        """News sources should get freshness 0.8."""
        results = [{"title": "test", "link": "https://techcrunch.com/article", "source": "TechCrunch"}]
        scraped = {"https://techcrunch.com/article": "A" * 500}
        results = scorer.evaluate(results, scraped)
        assert results[0]["credibility_details"]["freshness_score"] == 0.8

    def test_non_news_source_freshness(self, scorer):
        """Non-news sources should get freshness 0.5."""
        results = [{"title": "test", "link": "https://example.com/page", "source": "Example"}]
        scraped = {"https://example.com/page": "A" * 500}
        results = scorer.evaluate(results, scraped)
        assert results[0]["credibility_details"]["freshness_score"] == 0.5

    def test_content_depth_scaling(self, scorer):
        """Content depth score should scale with text length."""
        test_cases = [
            ("https://short.com/page", "A" * 50, 0.1),
            ("https://medium.com/page", "A" * 200, 0.3),
            ("https://good.com/page", "A" * 600, 0.5),
            ("https://rich.com/page", "A" * 1500, 0.7),
            ("https://deep.com/page", "A" * 2500, 1.0),
        ]
        results = [{"title": "t", "link": url, "source": "S"} for url, _, _ in test_cases]
        scraped = {url: text for url, text, _ in test_cases}
        results = scorer.evaluate(results, scraped)
        for (_, _, expected), r in zip(test_cases, results):
            assert r["credibility_details"]["content_depth_score"] == expected

    def test_score_range(self, scorer, sample_search_results, sample_scraped_content):
        """Final score must be between 0 and 1."""
        results = scorer.evaluate(sample_search_results, sample_scraped_content)
        for r in results:
            assert 0 <= r["credibility_score"] <= 1


class TestConsistencyAnalyzer:
    """Tests for ConsistencyAnalyzer.analyze()."""

    def test_analyze_returns_structure(self, consistency_analyzer, sample_search_results, sample_scraped_content):
        result = consistency_analyzer.analyze(sample_search_results, sample_scraped_content)
        assert "overall_consistency" in result
        assert "outlier_indices" in result
        assert "source_labels" in result
        assert 0 <= result["overall_consistency"] <= 1

    def test_single_source(self, consistency_analyzer):
        """Single source should return consistency 1.0."""
        results = [{"title": "t", "link": "u", "source": "S"}]
        scraped = {"u": "text"}
        result = consistency_analyzer.analyze(results, scraped)
        assert result["overall_consistency"] == 1.0

    def test_empty_content(self, consistency_analyzer):
        """No scraped content should return consistency 1.0."""
        results = [
            {"title": "t1", "link": "u1", "source": "S1"},
            {"title": "t2", "link": "u2", "source": "S2"},
        ]
        scraped = {}
        result = consistency_analyzer.analyze(results, scraped)
        assert result["overall_consistency"] == 1.0


class TestConflictDetector:
    """Tests for ConflictDetector.detect()."""

    def test_no_conflict_similar_texts(self):
        """Similar texts should produce no conflicts."""
        from intelnexus.analysis.credibility import ConflictDetector
        detector = ConflictDetector()
        results = [
            {"title": "t1", "link": "u1", "source": "S1"},
            {"title": "t2", "link": "u2", "source": "S2"},
        ]
        scraped = {
            "u1": "AI market size reached 500 billion dollars in 2025",
            "u2": "AI market size reached 500 billion dollars in 2025",
        }
        conflicts = detector.detect(results, scraped)
        numeric = [c for c in conflicts if c["type"] == "numeric"]
        assert len(numeric) == 0

    def test_numeric_conflict(self):
        """Large numeric differences should produce numeric conflicts."""
        from intelnexus.analysis.credibility import ConflictDetector
        detector = ConflictDetector()
        results = [
            {"title": "t1", "link": "u1", "source": "S1"},
            {"title": "t2", "link": "u2", "source": "S2"},
        ]
        scraped = {
            "u1": "Investment was 100 billion dollars",
            "u2": "Investment was 10 billion dollars",
        }
        conflicts = detector.detect(results, scraped)
        numeric = [c for c in conflicts if c["type"] == "numeric"]
        assert len(numeric) > 0
        assert numeric[0]["severity"] > 0.5

    def test_temporal_conflict(self):
        """Years differing by >= 2 should produce temporal conflicts."""
        from intelnexus.analysis.credibility import ConflictDetector
        detector = ConflictDetector()
        results = [
            {"title": "t1", "link": "u1", "source": "S1"},
            {"title": "t2", "link": "u2", "source": "S2"},
        ]
        scraped = {
            "u1": "The event happened in 2020",
            "u2": "The event happened in 2023",
        }
        conflicts = detector.detect(results, scraped)
        temporal = [c for c in conflicts if c["type"] == "temporal"]
        assert len(temporal) > 0
        assert temporal[0]["severity"] == 0.8

    def test_stance_conflict(self):
        """Positive vs negative stance should produce stance conflicts."""
        from intelnexus.analysis.credibility import ConflictDetector
        detector = ConflictDetector()
        results = [
            {"title": "t1", "link": "u1", "source": "S1"},
            {"title": "t2", "link": "u2", "source": "S2"},
        ]
        scraped = {
            "u1": "This is a positive breakthrough with great success and growth",
            "u2": "This is a negative failure with serious risk and decline",
        }
        conflicts = detector.detect(results, scraped)
        stance = [c for c in conflicts if c["type"] == "stance"]
        assert len(stance) > 0
        assert stance[0]["severity"] == 0.6

    def test_single_source_no_conflicts(self):
        """Single source should produce no conflicts."""
        from intelnexus.analysis.credibility import ConflictDetector
        detector = ConflictDetector()
        results = [{"title": "t1", "link": "u1", "source": "S1"}]
        scraped = {"u1": "Some text"}
        conflicts = detector.detect(results, scraped)
        assert conflicts == []

    def test_conflict_structure(self):
        """Each conflict should have required keys."""
        from intelnexus.analysis.credibility import ConflictDetector
        detector = ConflictDetector()
        results = [
            {"title": "t1", "link": "u1", "source": "S1"},
            {"title": "t2", "link": "u2", "source": "S2"},
        ]
        scraped = {
            "u1": "Investment was 100 billion dollars",
            "u2": "Investment was 10 billion dollars",
        }
        conflicts = detector.detect(results, scraped)
        for c in conflicts:
            assert "type" in c
            assert "severity" in c
            assert "claim" in c
            assert "description" in c
            assert "sources" in c
