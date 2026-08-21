"""
Credibility Assessment Module
============================
M-SCORE: Multi-Source Credibility Oriented Ranking & Evaluation
CIDAR: Cross-source Inconsistency Detection with Adaptive Reasoning

Provides source credibility scoring, cross-source consistency analysis,
and conflict detection for multi-source intelligence analysis.
"""

import re
import numpy as np
from urllib.parse import urlparse

from intelnexus.analysis import load_sentence_model
from intelnexus.analysis.embed_cache import encode_texts


class SourceScorer:
    """
    M-SCORE: Multi-Source Credibility Oriented Ranking & Evaluation

    Scores each search result on a 0-1 scale based on:
      - Domain authority (30%)
      - Content freshness (25%)
      - Content depth (20%)
      - Cross-source consistency (25%)
    """

    TLD_SCORES = {
        '.gov': 0.90, '.gov.cn': 0.90, '.mil': 0.85, '.int': 0.75,
        '.edu': 0.80, '.edu.cn': 0.80, '.org': 0.70, '.org.cn': 0.70,
    }

    TRUSTED_DOMAINS = {
        # 权威媒体
        'reuters.com': 0.90, 'ap.org': 0.90,
        'bbc.com': 0.85, 'bbc.co.uk': 0.85,
        'nytimes.com': 0.85, 'bloomberg.com': 0.85,
        'wsj.com': 0.85, 'economist.com': 0.85,
        'washingtonpost.com': 0.85, 'ft.com': 0.85,
        'cnn.com': 0.80, 'nbcnews.com': 0.80,
        # 科技媒体
        'arstechnica.com': 0.85, 'techcrunch.com': 0.85,
        'theverge.com': 0.80, 'wired.com': 0.85,
        'zdnet.com': 0.80, 'infoworld.com': 0.80,
        'computerworld.com': 0.80, 'theregister.com': 0.80,
        'arstechnica.com': 0.85, 'hackernews.com': 0.75,
        # 安全媒体
        'darkreading.com': 0.85, 'securityweek.com': 0.85,
        'scmagazine.com': 0.80, 'cyberscoop.com': 0.80,
        'bleepingcomputer.com': 0.85, 'krebsonsecurity.com': 0.90,
        'securityweek.com': 0.85, 'threatpost.com': 0.80,
        # 安全厂商
        'kaspersky.com': 0.85, 'symantec.com': 0.85,
        'crowdstrike.com': 0.85, 'mandiant.com': 0.90,
        'fireeye.com': 0.85, 'paloaltonetworks.com': 0.85,
        'fortinet.com': 0.80, 'checkpoint.com': 0.80,
        'trendmicro.com': 0.80, 'mcafee.com': 0.80,
        'sophos.com': 0.80, 'recordedfuture.com': 0.85,
        # 学术与研究
        'nature.com': 0.90, 'ieee.org': 0.85, 'acm.org': 0.85,
        'springer.com': 0.80, 'sciencedirect.com': 0.85,
        'scholar.google.com': 0.80, 'arxiv.org': 0.85,
        # 漏洞库与标准组织
        'nvd.nist.gov': 0.95, 'cve.mitre.org': 0.95,
        'cisa.gov': 0.95, 'nist.gov': 0.90,
        'enisa.europa.eu': 0.90, 'owasp.org': 0.85,
        'first.org': 0.85, 'exploit-db.com': 0.75,
        # 中国政府与机构
        'cert.org.cn': 0.90, 'isc.org.cn': 0.85,
        'tc260.org.cn': 0.85, 'gov.cn': 0.90,
        'miit.gov.cn': 0.85, 'cac.gov.cn': 0.85,
        # 新闻聚合
        'news.ycombinator.com': 0.75, 'reddit.com': 0.65,
        'medium.com': 0.70, 'substack.com': 0.70,
    }

    AGGREGATOR_SOURCES = {'Bing', 'Google', 'DuckDuckGo', 'Yahoo', 'Yandex', 'Baidu'}

    NEWS_SOURCES = {'Google News', 'Bing News', 'Yahoo News',
                    'Reuters', 'TechCrunch', 'The Verge', 'Wired', 'BBC', 'CNN',
                    'BleepingComputer', 'SecurityWeek', 'Dark Reading', 'The Hacker News',
                    'FreeBuf', 'Solidot', 'IT之家', 'InfoQ', 'AI科技评论',
                    'CyberScoop', 'The Record', 'Ars Technica', 'ZDNet'}

    def __init__(self):
        self._model = load_sentence_model()

    def evaluate(self, results, scraped_content, emb_by_url=None):
        """
        Add credibility scores to each result dict in-place.

        Args:
            results: list of dicts with keys (title, link/source, source, description)
            scraped_content: dict of {url: scraped_text}
            emb_by_url: 可选，预计算的 {url: embedding}（来自 embed_cache），
                        传入可避免重复编码同一批文本

        Returns:
            The same results list with added keys:
              - credibility_score: float 0-1
              - credibility_details: dict with sub-scores and reason
        """
        # 批量编码所有文本一次（共享 embed_cache，避免 O(N²) 重复编码）
        url_list = list(scraped_content.keys())
        text_list = [scraped_content[u] for u in url_list]
        emb_cache = dict(emb_by_url) if emb_by_url else {}
        if self._model is not None and text_list and not emb_cache:
            try:
                embs = encode_texts(text_list)
                if embs is not None:
                    for u, e in zip(url_list, embs):
                        emb_cache[u] = e
            except Exception:
                emb_cache = {}

        # Precompute pairwise similarity matrix for O(1) lookups
        pairwise_sim = self._precompute_pairwise_similarity(emb_cache)

        for r in results:
            url = r.get("link") or r.get("url", "")
            source_name = r.get("source", "Unknown")
            detail = self._build_detail(url, source_name, scraped_content, emb_cache, pairwise_sim, r)
            r["credibility_score"] = detail["final_score"]
            r["credibility_details"] = detail

        return results

    def _precompute_pairwise_similarity(self, emb_cache):
        """Precompute O(N) average similarity for each URL using batch matrix ops."""
        urls = list(emb_cache.keys())
        n = len(urls)
        if n < 2:
            return {}

        import numpy as np
        embs = np.array([emb_cache[u] for u in urls])
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        normed = embs / (norms + 1e-10)
        sim_matrix = np.dot(normed, normed.T)
        np.fill_diagonal(sim_matrix, 0)

        avg_sims = sim_matrix.sum(axis=1) / max(n - 1, 1)
        return {u: float(avg_sims[i]) for i, u in enumerate(urls)}

    def _build_detail(self, url, source_name, scraped, emb_cache, pairwise_sim, result=None):
        domain_score = self._domain_authority(url, source_name)
        freshness_score = self._freshness(source_name, result)
        depth_score = self._content_depth(url, scraped)
        consis_score = pairwise_sim.get(url, 0.5)

        final = (domain_score * 0.30 + freshness_score * 0.25
                 + depth_score * 0.20 + consis_score * 0.25)

        parts = []
        if domain_score >= 0.7:
            parts.append("高权威域名")
        elif domain_score < 0.4:
            parts.append("低权威域名")
        if freshness_score >= 0.7:
            parts.append("时效性好")
        if depth_score >= 0.7:
            parts.append("内容丰富")
        elif depth_score < 0.3:
            parts.append("内容单薄")
        if consis_score >= 0.7:
            parts.append("与其他来源高度一致")
        elif consis_score < 0.3:
            parts.append("与其他来源差异大")

        return {
            "domain_score": round(domain_score, 3),
            "freshness_score": round(freshness_score, 3),
            "content_depth_score": round(depth_score, 3),
            "consistency_score": round(consis_score, 3),
            "final_score": round(final, 3),
            "reason": ", ".join(parts) if parts else "无明显特征"
        }

    def _domain_authority(self, url, source_name):
        # Try to extract real domain from URL first (not just source/engine name)
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain and domain not in ('', 'localhost', '127.0.0.1'):
                if domain.startswith('www.'):
                    domain = domain[4:]
                for trusted, score in self.TRUSTED_DOMAINS.items():
                    if domain == trusted or domain.endswith('.' + trusted):
                        return score
                for tld, score in self.TLD_SCORES.items():
                    if domain.endswith(tld):
                        return score
        except Exception:
            pass

        # Fallback: score by source type
        if source_name in self.NEWS_SOURCES:
            return 0.7
        if source_name in self.AGGREGATOR_SOURCES:
            return 0.5
        return 0.4

    def _freshness(self, source_name, result=None):
        """Compute freshness from published_at date, falling back to source type."""
        import re
        if result:
            published = result.get("published_at") or result.get("published") or result.get("date")
            if published:
                try:
                    from datetime import datetime
                    if isinstance(published, str):
                        # 尝试多种日期格式
                        for fmt in (
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%dT%H:%M:%S%z",
                            "%Y-%m-%d",
                            "%Y/%m/%d",
                            "%d/%m/%Y",
                            "%m/%d/%Y",
                            "%Y年%m月%d日",
                            "%Y年%m月%d日 %H:%M:%S",
                            "%b %d, %Y",       # Aug 21, 2026
                            "%B %d, %Y",       # August 21, 2026
                            "%d %b %Y",        # 21 Aug 2026
                            "%d %B %Y",        # 21 August 2026
                            "%Y-%m-%dT%H:%M:%S.%f",
                            "%Y-%m-%dT%H:%M:%S.%fZ",
                        ):
                            try:
                                pub_dt = datetime.strptime(published[:19] if len(published) >= 19 else published, fmt)
                                delta = (datetime.now() - pub_dt).total_seconds()
                                if delta < 0:
                                    return 0.5  # 未来日期，可能是解析错误
                                if delta < 86400:
                                    return 1.0          # within 24h
                                if delta < 604800:
                                    return 0.85          # within 7 days
                                if delta < 2592000:
                                    return 0.7           # within 30 days
                                if delta < 7776000:
                                    return 0.5           # within 90 days
                                return 0.3               # older
                            except (ValueError, IndexError):
                                continue

                        # 尝试中文日期格式：2026年08月21日
                        cn_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', published)
                        if cn_match:
                            try:
                                year, month, day = int(cn_match.group(1)), int(cn_match.group(2)), int(cn_match.group(3))
                                pub_dt = datetime(year, month, day)
                                delta = (datetime.now() - pub_dt).total_seconds()
                                if delta < 0:
                                    return 0.5
                                if delta < 86400:
                                    return 1.0
                                if delta < 604800:
                                    return 0.85
                                if delta < 2592000:
                                    return 0.7
                                if delta < 7776000:
                                    return 0.5
                                return 0.3
                            except (ValueError, IndexError):
                                pass

                        # 尝试使用dateutil解析（如果可用）
                        try:
                            from dateutil import parser as dateutil_parser
                            pub_dt = dateutil_parser.parse(published)
                            delta = (datetime.now() - pub_dt).total_seconds()
                            if delta < 0:
                                return 0.5
                            if delta < 86400:
                                return 1.0
                            if delta < 604800:
                                return 0.85
                            if delta < 2592000:
                                return 0.7
                            if delta < 7776000:
                                return 0.5
                            return 0.3
                        except ImportError:
                            pass
                        except (ValueError, TypeError):
                            pass
                except Exception:
                    pass
        return 0.8 if source_name in self.NEWS_SOURCES else 0.5

    def _content_depth(self, url, scraped):
        text = scraped.get(url, "")
        length = len(text)
        if length >= 2000:
            return 1.0
        if length >= 1000:
            return 0.7
        if length >= 500:
            return 0.5
        if length >= 100:
            return 0.3
        return 0.1

    def _consistency(self, url, scraped, emb_cache):
        """Compute consistency using pre-computed embeddings (no re-encoding)."""
        if len(emb_cache) < 2:
            return 0.5
        emb = emb_cache.get(url)
        if emb is None:
            return 0.5
        try:
            similarities = []
            for other_url, other_emb in emb_cache.items():
                if other_url == url or other_emb is None:
                    continue
                sim = float(np.dot(emb, other_emb) / (
                    np.linalg.norm(emb) * np.linalg.norm(other_emb) + 1e-10))
                similarities.append(sim)
            return float(np.mean(similarities)) if similarities else 0.5
        except Exception:
            return 0.5


class ConsistencyAnalyzer:
    """
    Computes cross-source consistency matrix and identifies outlier sources.
    """

    def __init__(self):
        self._model = load_sentence_model()

    def analyze(self, results, scraped_content, emb_by_url=None):
        """
        Args:
            results: list of result dicts
            scraped_content: dict of {url: text}
            emb_by_url: 可选，预计算的 {url: embedding}（来自 embed_cache）

        Returns:
            dict with keys:
              - consistency_matrix: NxN list of lists
              - overall_consistency: float
              - outlier_indices: list of int
              - source_labels: list of str
        """
        texts = []
        labels = []
        for r in results:
            url = r.get("link") or r.get("url", "")
            t = scraped_content.get(url, "")
            texts.append(t if len(t) > 50 else "")
            labels.append(r.get("source", "Unknown"))

        valid_indices = [i for i, t in enumerate(texts) if t]
        valid_texts = [texts[i] for i in valid_indices]

        if len(valid_texts) < 2:
            return {
                "consistency_matrix": [[1.0]],
                "overall_consistency": 1.0,
                "outlier_indices": [],
                "source_labels": labels
            }

        if self._model is None:
            return {
                "consistency_matrix": [[1.0]],
                "overall_consistency": 1.0,
                "outlier_indices": [],
                "source_labels": labels
            }

        try:
            # 优先复用预编码 embedding（按 url 对齐），否则统一批量编码一次
            embs = None
            if emb_by_url:
                embs = np.array([emb_by_url[results[i].get("link") or results[i].get("url", "")]
                                 for i in valid_indices], dtype=np.float32)
                if embs.shape[0] != len(valid_texts):
                    embs = None
            if embs is None:
                embs = encode_texts(valid_texts)
            if embs is None:
                return {
                    "consistency_matrix": [[1.0]],
                    "overall_consistency": 1.0,
                    "outlier_indices": [],
                    "source_labels": labels
                }
            n = len(valid_texts)
            matrix = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    matrix[i][j] = float(np.dot(embs[i], embs[j]) / (
                        np.linalg.norm(embs[i]) * np.linalg.norm(embs[j]) + 1e-10))

            avg_sims = [
                sum(matrix[i][j] for j in range(n) if j != i) / max(n - 1, 1)
                for i in range(n)
            ]
            overall = float(np.mean(avg_sims)) if avg_sims else 1.0
            outliers = [valid_indices[i] for i in range(n) if avg_sims[i] < 0.3]

            return {
                "consistency_matrix": matrix,
                "overall_consistency": round(overall, 3),
                "outlier_indices": outliers,
                "source_labels": [labels[i] for i in valid_indices]
            }
        except Exception:
            return {
                "consistency_matrix": [[1.0]],
                "overall_consistency": 1.0,
                "outlier_indices": [],
                "source_labels": labels
            }


class ConflictDetector:
    """
    CIDAR: Detects numeric, temporal, and stance conflicts across sources.
    """

    def detect(self, results, scraped_content):
        """
        Args:
            results: list of result dicts
            scraped_content: dict of {url: text}

        Returns:
            list of conflict dicts with keys:
              - type: "numeric" | "temporal" | "stance"
              - description: str
              - severity: float 0-1
              - claim: str
              - sources: list of {"index": int, "name": str, "value": str}
        """
        texts = []
        for r in results:
            url = r.get("link") or r.get("url", "")
            texts.append(scraped_content.get(url, ""))

        if len(texts) < 2:
            return []

        conflicts = []
        conflicts.extend(self._detect_numeric(texts, results))
        conflicts.extend(self._detect_temporal(texts, results))
        conflicts.extend(self._detect_stance(texts, results))
        return conflicts

    def _detect_numeric(self, texts, results):
        conflicts = []
        entries = []
        # 扩展正则：支持更多中文数量词
        pattern = r'(\d+(?:\.\d+)?)\s*(billion|million|trillion|千亿|百亿|十亿|万亿|亿|千万|百万|十万|万|%)'

        for i, t in enumerate(texts):
            for m in re.finditer(pattern, t, re.IGNORECASE):
                try:
                    num = float(m.group(1))
                    unit = m.group(2).lower()
                    # 修复映射：亿=1e8，billion=1e9
                    if unit == 'billion':
                        norm = num * 1e9
                    elif unit == 'trillion':
                        norm = num * 1e12
                    elif unit == 'million':
                        norm = num * 1e6
                    elif unit == '千亿':
                        norm = num * 1e11
                    elif unit == '百亿':
                        norm = num * 1e10
                    elif unit == '十亿':
                        norm = num * 1e9
                    elif unit == '万亿':
                        norm = num * 1e12
                    elif unit == '亿':
                        norm = num * 1e8  # 修复：亿=1e8，不是1e9
                    elif unit == '千万':
                        norm = num * 1e7
                    elif unit == '百万':
                        norm = num * 1e6
                    elif unit == '十万':
                        norm = num * 1e5
                    elif unit == '万':
                        norm = num * 1e4
                    else:
                        norm = num
                    ctx_start = max(0, m.start() - 30)
                    ctx_end = min(len(t), m.end() + 30)
                    context = t[ctx_start:ctx_end]
                    entries.append((i, context, norm, unit))
                except Exception:
                    continue

        for a in range(len(entries)):
            for b in range(a + 1, len(entries)):
                idx_a, ctx_a, n_a, u_a = entries[a]
                idx_b, ctx_b, n_b, u_b = entries[b]
                if idx_a == idx_b:
                    continue
                max_n = max(n_a, n_b)
                if max_n == 0:
                    continue
                # 过滤：两个数值都 <= 10 时不判定冲突（小数值波动属正常）
                if max_n <= 10:
                    continue
                ratio = abs(n_a - n_b) / max_n
                # 阈值 0.7：同一事件不同表述（如 398 vs 近400）不应判定为冲突
                if ratio > 0.7:
                    conflicts.append({
                        "type": "numeric",
                        "severity": round(min(ratio, 1.0), 2),
                        "claim": f"数值冲突: {n_a:.1f} vs {n_b:.1f}",
                        "description": f"来源间存在数值差异 ({u_a}级别)",
                        "sources": [
                            {"index": idx_a,
                             "name": results[idx_a].get("source", "Unknown"),
                             "value": ctx_a.strip()[:80]},
                            {"index": idx_b,
                             "name": results[idx_b].get("source", "Unknown"),
                             "value": ctx_b.strip()[:80]}
                        ]
                    })
        return conflicts

    def _detect_temporal(self, texts, results):
        conflicts = []
        entries = []
        pattern = r'((?:19|20)\d{2})'

        for i, t in enumerate(texts):
            years = set(re.findall(pattern, t))
            for y in years:
                try:
                    year_val = int(y)
                    pos = t.find(y)
                    ctx_start = max(0, pos - 20)
                    ctx_end = min(len(t), pos + 20)
                    context = t[ctx_start:ctx_end]
                    entries.append((i, year_val, context.strip()))
                except Exception:
                    continue

        for a in range(len(entries)):
            for b in range(a + 1, len(entries)):
                idx_a, y_a, ctx_a = entries[a]
                idx_b, y_b, ctx_b = entries[b]
                if idx_a == idx_b:
                    continue
                if abs(y_a - y_b) >= 2:
                    conflicts.append({
                        "type": "temporal",
                        "severity": 0.8,
                        "claim": f"时间冲突: {y_a} vs {y_b}",
                        "description": f"来源间对同一事件的时间描述相差 {abs(y_a - y_b)} 年",
                        "sources": [
                            {"index": idx_a,
                             "name": results[idx_a].get("source", "Unknown"),
                             "value": ctx_a[:80]},
                            {"index": idx_b,
                             "name": results[idx_b].get("source", "Unknown"),
                             "value": ctx_b[:80]}
                        ]
                    })
        return conflicts

    def _detect_stance(self, texts, results):
        pos_words = {'同意', '支持', '利好', '成功', '突破', 'positive', 'success',
                     'breakthrough', 'approve', 'benefit', 'growth', 'promising',
                     'innovation', '领先', '进步', '优势'}
        neg_words = {'反对', '质疑', '失败', '风险', '问题', 'negative', 'fail',
                     'risk', 'concern', 'decline', 'loss', 'controversial',
                     'danger', '危机', '缺陷', '隐患', '挑战'}

        stances = []
        for i, t in enumerate(texts):
            t_lower = t.lower()
            pos_count = sum(1 for w in pos_words if w in t_lower)
            neg_count = sum(1 for w in neg_words if w in t_lower)
            if pos_count > neg_count:
                stances.append(('positive', pos_count - neg_count))
            elif neg_count > pos_count:
                stances.append(('negative', neg_count - pos_count))
            else:
                stances.append(('neutral', 0))

        conflicts = []
        for a in range(len(stances)):
            for b in range(a + 1, len(stances)):
                s_a, _ = stances[a]
                s_b, _ = stances[b]
                if s_a == 'positive' and s_b == 'negative':
                    severity = 0.6
                elif s_a == 'negative' and s_b == 'positive':
                    severity = 0.6
                else:
                    continue
                conflicts.append({
                    "type": "stance",
                    "severity": severity,
                    "claim": "立场冲突",
                    "description": f"来源间存在立场分歧 ({s_a} vs {s_b})",
                    "sources": [
                        {"index": a,
                         "name": results[a].get("source", "Unknown")},
                        {"index": b,
                         "name": results[b].get("source", "Unknown")}
                    ]
                })
        return conflicts
