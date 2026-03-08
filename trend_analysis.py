"""
Trend Analysis Module
====================
Analyze research trends and topics from search results.
"""

import re
from typing import List, Dict, Optional
from collections import Counter
from datetime import datetime, timedelta
import json
import os


TRENDING_KEYWORDS = {
    "ai": ["machine learning", "deep learning", "neural network", "GPT", "LLM", "transformer", "AI"],
    "tech": ["quantum", "blockchain", "web3", "metaverse", "AR", "VR"],
    "science": ["climate", "CRISPR", "fusion", "space", "astronomy"],
    "security": ["cybersecurity", "privacy", "encryption", "zero-day"],
}


class TrendAnalyzer:
    def __init__(self):
        self.trend_data_file = "data/trends.json"
    
    def analyze_results(self, results: List[Dict]) -> Dict:
        """Analyze search results for trends."""
        if not results:
            return {"error": "No results to analyze"}
        
        keywords = self._extract_keywords(results)
        sources = self._analyze_sources(results)
        topics = self._identify_topics(results)
        timeline = self._estimate_timeline(results)
        
        return {
            "keywords": keywords,
            "sources": sources,
            "topics": topics,
            "timeline": timeline,
            "total_results": len(results)
        }
    
    def _extract_keywords(self, results: List[Dict]) -> List[Dict]:
        """Extract and count keywords from results."""
        all_text = ""
        
        for result in results:
            all_text += result.get("title", "") + " "
            all_text += result.get("summary", "") + " "
            all_text += result.get("description", "") + " "
            all_text += result.get("content", "") + " "
        
        words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
        
        stopwords = {
            "this", "that", "with", "from", "have", "been", "will", "were",
            "they", "their", "what", "about", "which", "when", "make", "like",
            "time", "just", "know", "take", "people", "into", "year", "your",
            "good", "some", "could", "them", "see", "other", "than", "then",
            "now", "look", "only", "come", "its", "over", "think", "also"
        }
        
        words = [w for w in words if w not in stopwords]
        word_counts = Counter(words)
        
        top_keywords = [
            {"keyword": word, "count": count}
            for word, count in word_counts.most_common(15)
        ]
        
        return top_keywords
    
    def _analyze_sources(self, results: List[Dict]) -> Dict:
        """Analyze distribution of sources."""
        source_counts = Counter()
        
        for result in results:
            source = result.get("source", "Unknown")
            source_counts[source] += 1
        
        return {
            "distribution": dict(source_counts),
            "total_sources": len(source_counts)
        }
    
    def _identify_topics(self, results: List[Dict]) -> List[Dict]:
        """Identify main topics from results."""
        text = ""
        for result in results:
            text += result.get("title", "") + " "
        
        text_lower = text.lower()
        
        topics = []
        for category, keywords in TRENDING_KEYWORDS.items():
            matched = []
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    matched.append(keyword)
            if matched:
                topics.append({
                    "category": category,
                    "keywords": matched,
                    "relevance": len(matched) / len(keywords)
                })
        
        topics.sort(key=lambda x: x["relevance"], reverse=True)
        return topics[:5]
    
    def _estimate_timeline(self, results: List[Dict]) -> Dict:
        """Estimate timeline of results."""
        dates = []
        
        for result in results:
            published = result.get("published") or result.get("published_at") or ""
            if published:
                try:
                    if "T" in published:
                        date = published.split("T")[0]
                    else:
                        date = published[:10]
                    dates.append(date)
                except:
                    pass
        
        if not dates:
            return {"range": "Unknown", "recent": 0}
        
        dates.sort()
        
        now = datetime.now()
        recent_count = 0
        for date in dates:
            try:
                d = datetime.strptime(date[:10], "%Y-%m-%d")
                if (now - d).days < 30:
                    recent_count += 1
            except:
                pass
        
        return {
            "earliest": dates[0] if dates else None,
            "latest": dates[-1] if dates else None,
            "recent_30_days": recent_count,
            "total_dated": len(dates)
        }
    
    def get_trending(self) -> Dict:
        """Get overall trending data."""
        if not os.path.exists(self.trend_data_file):
            return {"trending_keywords": [], "recent_searches": []}
        
        try:
            with open(self.trend_data_file, 'r') as f:
                return json.load(f)
        except:
            return {"trending_keywords": [], "recent_searches": []}
    
    def save_trend(self, query: str, keywords: List[str]):
        """Save trend data."""
        data = self.get_trending()
        
        if "trending_keywords" not in data:
            data["trending_keywords"] = []
        if "recent_searches" not in data:
            data["recent_searches"] = []
        
        for kw in keywords[:5]:
            data["trending_keywords"].append({
                "keyword": kw,
                "timestamp": datetime.now().isoformat()
            })
        
        data["recent_searches"].insert(0, {
            "query": query,
            "timestamp": datetime.now().isoformat()
        })
        
        data["trending_keywords"] = data["trending_keywords"][-100:]
        data["recent_searches"] = data["recent_searches"][:50]
        
        os.makedirs("data", exist_ok=True)
        with open(self.trend_data_file, 'w') as f:
            json.dump(data, f, indent=2)


def analyze_trends(results: List[Dict]) -> Dict:
    """Quick trend analysis function."""
    analyzer = TrendAnalyzer()
    return analyzer.analyze_results(results)
