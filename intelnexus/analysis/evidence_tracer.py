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

from intelnexus.analysis import load_sentence_model
from intelnexus.analysis.embed_cache import encode_texts, encode_single


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

        # 预批量 encode 所有 scraped 文本（O(M) 而非 O(N*M)）
        # 共享 embed_cache，与 SourceScorer/ConsistencyAnalyzer 复用同一批编码
        url_list = list(scraped_content.keys())
        text_list = [scraped_content[u][:2000] for u in url_list]
        valid_indices = [i for i, t in enumerate(text_list) if t]
        valid_texts = [text_list[i] for i in valid_indices]
        valid_urls = [url_list[i] for i in valid_indices]

        scraped_embeddings = None
        if valid_texts:
            scraped_embeddings = encode_texts(valid_texts)
            if scraped_embeddings is not None:
                scraped_embeddings = np.asarray(scraped_embeddings, dtype=np.float32)
                norms = np.linalg.norm(scraped_embeddings, axis=1, keepdims=True)
                scraped_embeddings = scraped_embeddings / (norms + 1e-10)

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

            # encode claim 一次，与所有预计算 embedding 做余弦相似度
            evidence_list = []
            if scraped_embeddings is not None and len(scraped_embeddings) > 0:
                try:
                    claim_emb = encode_single(sent)
                    if claim_emb is None:
                        continue
                    claim_norm = claim_emb / (np.linalg.norm(claim_emb) + 1e-10)
                    sims = np.dot(scraped_embeddings, claim_norm)

                    top_indices = np.argsort(sims)[::-1]
                    for idx in top_indices:
                        if sims[idx] > 0.3:
                            evidence_list.append({
                                "url": valid_urls[idx],
                                "confidence": round(float(sims[idx]), 3),
                                "source_text": valid_texts[idx][:150]
                            })
                        if len(evidence_list) >= 3:
                            break
                except Exception:
                    pass

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
