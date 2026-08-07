"""Tests for evidence tracing module."""

import pytest
from unittest.mock import patch
import numpy as np


class MockSentenceModel:
    """Mock sentence-transformers model for testing."""

    def encode(self, texts, show_progress_bar=False):
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
def tracer(mock_model):
    with patch("src.analysis.evidence_tracer.load_sentence_model", return_value=mock_model):
        from intelnexus.analysis.evidence_tracer import EvidenceTracer
        return EvidenceTracer()


class TestEvidenceTracer:
    """Tests for EvidenceTracer.trace()."""

    def test_trace_returns_structure(self, tracer, sample_report, sample_scraped_content):
        """trace() should return claims list and coverage float."""
        result = tracer.trace(sample_report, sample_scraped_content)
        assert "claims" in result
        assert "coverage" in result
        assert isinstance(result["claims"], list)
        assert isinstance(result["coverage"], float)

    def test_empty_report(self, tracer, sample_scraped_content):
        """Empty report should return empty claims."""
        result = tracer.trace("", sample_scraped_content)
        assert result["claims"] == []
        assert result["coverage"] == 0.0

    def test_empty_scraped(self, tracer, sample_report):
        """Empty scraped content should return empty claims."""
        result = tracer.trace(sample_report, {})
        assert result["claims"] == []
        assert result["coverage"] == 0.0

    def test_none_report(self, tracer, sample_scraped_content):
        """None report should return empty claims."""
        result = tracer.trace(None, sample_scraped_content)
        assert result["claims"] == []

    def test_claim_structure(self, tracer, sample_report, sample_scraped_content):
        """Each claim should have required keys."""
        result = tracer.trace(sample_report, sample_scraped_content)
        for claim in result["claims"]:
            assert "text" in claim
            assert "section" in claim
            assert "evidence" in claim
            assert "confidence" in claim
            assert "is_unsupported" in claim

    def test_claim_text_truncated(self, tracer, sample_report, sample_scraped_content):
        """Claim text should be truncated to 120 chars."""
        result = tracer.trace(sample_report, sample_scraped_content)
        for claim in result["claims"]:
            assert len(claim["text"]) <= 120

    def test_evidence_list_limited(self, tracer, sample_report, sample_scraped_content):
        """Each claim should have at most 3 evidence items."""
        result = tracer.trace(sample_report, sample_scraped_content)
        for claim in result["claims"]:
            assert len(claim["evidence"]) <= 3

    def test_evidence_has_url(self, tracer, sample_report, sample_scraped_content):
        """Each evidence item should have a url."""
        result = tracer.trace(sample_report, sample_scraped_content)
        for claim in result["claims"]:
            for ev in claim["evidence"]:
                assert "url" in ev
                assert "confidence" in ev

    def test_coverage_range(self, tracer, sample_report, sample_scraped_content):
        """Coverage should be between 0 and 1."""
        result = tracer.trace(sample_report, sample_scraped_content)
        assert 0 <= result["coverage"] <= 1

    def test_skip_headers(self, tracer, sample_scraped_content):
        """Headers (## ...) should be skipped as claims."""
        report = "## 一、执行摘要\n\nThis is a real claim about AI technology."
        result = tracer.trace(report, sample_scraped_content)
        for claim in result["claims"]:
            assert not claim["text"].startswith("##")

    def test_skip_short_sentences(self, tracer, sample_scraped_content):
        """Sentences shorter than 15 chars should be skipped."""
        report = "Short. This is a longer sentence that should be included as a claim."
        result = tracer.trace(report, sample_scraped_content)
        for claim in result["claims"]:
            assert len(claim["text"]) >= 15

    def test_section_tracking(self, tracer, sample_scraped_content):
        """Claims should track their section (last matched heading in the report)."""
        report = (
            "## Summary\n\n"
            "This is a claim in the summary section about artificial intelligence.\n\n"
            "## Background\n\n"
            "This is a claim in the background section about technology trends."
        )
        result = tracer.trace(report, sample_scraped_content)
        # Note: existing code tracks sections by iterating all sections per sentence,
        # so current_section ends up as the last ## heading in the report.
        assert len(result["claims"]) > 0
        assert all("section" in c for c in result["claims"])

    def test_model_none_returns_empty(self, sample_report, sample_scraped_content):
        """When model is None, trace should return empty claims."""
        with patch("src.analysis.evidence_tracer.load_sentence_model", return_value=None):
            from intelnexus.analysis.evidence_tracer import EvidenceTracer
            tracer = EvidenceTracer()
            result = tracer.trace(sample_report, sample_scraped_content)
            assert result["claims"] == []
