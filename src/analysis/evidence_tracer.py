"""
Evidence Tracing Module
======================
STREAM: Source Traceability & Evidence-Aware Mapping

Maps each claim in an LLM-generated report back to its original source
evidence using semantic similarity, providing provenance tracking and
coverage analysis.
"""

import re
import numpy as np

from src.analysis import load_sentence_model


class EvidenceTracer:
    """
    STREAM: Source Traceability & Evidence-Aware Mapping

    Traces each claim in the report to semantically similar passages
    in the scraped source content.
    """

    def __init__(self):
        self._model = load_sentence_model()

    def trace(self, report, scraped_content):
        """
        Trace report claims back to source evidence.

        Args:
            report: str, LLM-generated markdown intelligence report
            scraped_content: dict of {url: scraped_text}

        Returns:
            dict with keys:
              - claims: list of claim dicts
              - coverage: float (proportion of claims with strong evidence)
        """
        if not report or not scraped_content:
            return {"claims": [], "coverage": 0.0}

        sentences = re.findall(r'[^。！？\n.!?]+[。！？\n.!?]', report)

        skip_patterns = [r'^\d+\.\s', r'^\*\*', r'^#{1,3}\s', r'^[——\-]']

        sections = re.split(r'(##\s+\S[^\n]*)', report)
        current_section = "未知"

        if self._model is None:
            return {"claims": [], "coverage": 0.0}

        claims = []
        for sent in sentences:
            sent = sent.strip()
            if not sent or len(sent) < 15:
                continue
            if any(re.match(p, sent) for p in skip_patterns):
                continue

            for s in sections:
                if s.startswith("##"):
                    current_section = s.strip("# ").strip()

            evidence_list = []
            for url, text in scraped_content.items():
                if not text:
                    continue
                sim = self._similarity(sent, text[:2000])
                if sim > 0.3:
                    evidence_list.append({
                        "url": url,
                        "confidence": round(sim, 3),
                        "source_text": text[:150]
                    })

            evidence_list.sort(key=lambda x: x["confidence"], reverse=True)
            evidence_list = evidence_list[:3]
            best_conf = evidence_list[0]["confidence"] if evidence_list else 0.0

            claims.append({
                "text": sent[:120],
                "section": current_section,
                "evidence": evidence_list,
                "confidence": round(best_conf, 3),
                "is_unsupported": best_conf < 0.3
            })

        total = len(claims)
        supported = sum(1 for c in claims if not c["is_unsupported"])
        coverage = round(supported / total, 3) if total > 0 else 0.0

        return {"claims": claims, "coverage": coverage}

    def _similarity(self, text_a, text_b):
        if self._model is None:
            return 0.0
        try:
            emb = self._model.encode([text_a, text_b], show_progress_bar=False)
            sim = float(np.dot(emb[0], emb[1]) / (
                np.linalg.norm(emb[0]) * np.linalg.norm(emb[1]) + 1e-10))
            return sim
        except Exception:
            return 0.0
