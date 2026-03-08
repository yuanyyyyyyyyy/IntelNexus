"""
Keyword Extraction Module
========================
Extract and analyze keywords from search results and documents.
"""

import re
from typing import List, Dict, Set, Tuple
from collections import Counter
import math


class KeywordExtractor:
    def __init__(self):
        self.stopwords = self._load_stopwords()
    
    def _load_stopwords(self) -> Set[str]:
        """Load common stopwords."""
        return {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "this", "that", "these", "those", "i", "you", "he", "she", "it",
            "we", "they", "what", "which", "who", "whom", "whose", "where",
            "when", "why", "how", "all", "each", "every", "both", "few",
            "more", "most", "other", "some", "such", "no", "nor", "not",
            "only", "own", "same", "so", "than", "too", "very", "just",
            "also", "now", "here", "there", "then", "once", "if", "because",
            "until", "while", "about", "against", "between", "into", "through",
            "during", "before", "after", "above", "below", "up", "down", "out",
            "off", "over", "under", "again", "further", "any", "their", "them",
            "his", "her", "its", "our", "your", "my", "said", "new", "one",
            "two", "first", "last", "long", "little", "old", "great", "high",
            "small", "large", "big", "early", "young", "important", "public",
            "good", "bad", "best", "better", "well", "back", "still", "even",
            "get", "got", "made", "make", "many", "much", "may", "take", "see",
            "come", "only", "like", "way", "think", "even", "use", "used"
        }
    
    def extract_keywords(self, text: str, top_n: int = 20) -> List[Dict]:
        """Extract top keywords from text using TF-IDF-like scoring."""
        words = self._preprocess(text)
        
        if not words:
            return []
        
        word_freq = Counter(words)
        total_words = len(words)
        
        word_scores = {}
        for word, freq in word_freq.items():
            if word in self.stopwords:
                continue
            if len(word) < 3:
                continue
            
            tf = freq / total_words
            
            idf = math.log(1 + total_words / (freq + 1))
            
            word_scores[word] = tf * idf
        
        sorted_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"keyword": word, "score": round(score, 4), "frequency": word_freq[word]}
            for word, score in sorted_words[:top_n]
        ]
    
    def extract_phrases(self, text: str, top_n: int = 10) -> List[Dict]:
        """Extract key phrases (2-4 words)."""
        words = self._preprocess(text)
        
        phrases = []
        for n in [2, 3, 4]:
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i+n])
                phrases.append(phrase)
        
        if not phrases:
            return []
        
        phrase_freq = Counter(phrases)
        
        filtered = {
            p: f for p, f in phrase_freq.items()
            if not any(sw in p.split() for sw in self.stopwords)
        }
        
        sorted_phrases = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
        
        unique_phrases = []
        seen = set()
        for phrase, freq in sorted_phrases:
            words_in_phrase = set(phrase.split())
            is_subphrase = False
            for seen_phrase in seen:
                if words_in_phrase.issubset(set(seen_phrase.split())):
                    is_subphrase = True
                    break
            if not is_subphrase:
                unique_phrases.append({
                    "phrase": phrase,
                    "frequency": freq
                })
                seen.add(phrase)
            if len(unique_phrases) >= top_n:
                break
        
        return unique_phrases
    
    def extract_entities(self, text: str) -> Dict:
        """Extract named entities (simple pattern-based)."""
        entities = {
            "emails": re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text),
            "urls": re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text),
            "dates": re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text),
            "years": re.findall(r'\b(19|20)\d{2}\b', text),
            "numbers": re.findall(r'\b\d+(?:\.\d+)?(?:[kmb])?\b', text.lower()),
        }
        
        return {k: list(set(v))[:20] for k, v in entities.items() if v}
    
    def analyze_content(self, content: Dict) -> Dict:
        """Analyze content and extract all keywords, phrases, entities."""
        text = ""
        if isinstance(content, dict):
            text = " ".join(str(v) for v in content.values() if v)
        elif isinstance(content, list):
            text = " ".join(str(item) for item in content if item)
        else:
            text = str(content)
        
        return {
            "keywords": self.extract_keywords(text, 15),
            "phrases": self.extract_phrases(text, 10),
            "entities": self.extract_entities(text),
            "stats": {
                "total_words": len(text.split()),
                "total_chars": len(text)
            }
        }
    
    def _preprocess(self, text: str) -> List[str]:
        """Preprocess text for keyword extraction."""
        text = text.lower()
        
        text = re.sub(r'http\S+|www\.\S+', '', text)
        text = re.sub(r'\S+@\S+', '', text)
        
        text = re.sub(r'[^\w\s]', ' ', text)
        
        words = text.split()
        
        words = [w for w in words if w not in self.stopwords and len(w) >= 3]
        
        return words


def extract_keywords(text: str, top_n: int = 20) -> List[Dict]:
    """Quick keyword extraction function."""
    extractor = KeywordExtractor()
    return extractor.extract_keywords(text, top_n)


def analyze_keywords(results: List[Dict]) -> Dict:
    """Analyze keywords from search results."""
    extractor = KeywordExtractor()
    
    all_content = ""
    for result in results:
        all_content += result.get("title", "") + " "
        all_content += result.get("summary", "") + " "
        all_content += result.get("description", "") + " "
        all_content += result.get("content", "") + " "
    
    return {
        "keywords": extractor.extract_keywords(all_content, 20),
        "phrases": extractor.extract_phrases(all_content, 10),
        "entities": extractor.extract_entities(all_content)
    }
