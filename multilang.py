"""
Multi-Language Support Module
============================
Support for multi-language search and translation.
"""

import re
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


LANGUAGE_CODES = {
    "en": "English",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "hi": "Hindi",
}

SEARCH_ENGINES_BY_LANG = {
    "en": [
        {"name": "Google", "url": "https://www.google.com/search?q={query}"},
        {"name": "Bing", "url": "https://www.bing.com/search?q={query}"},
    ],
    "zh": [
        {"name": "Baidu", "url": "https://www.baidu.com/s?wd={query}"},
        {"name": "Bing Chinese", "url": "https://cn.bing.com/search?q={query}"},
    ],
    "es": [
        {"name": "Google Spain", "url": "https://www.google.es/search?q={query}"},
        {"name": "Bing Spain", "url": "https://www.bing.com/search?q={query}&setlang=es"},
    ],
    "ja": [
        {"name": "Google Japan", "url": "https://www.google.co.jp/search?q={query}"},
        {"name": "Yahoo Japan", "url": "https://search.yahoo.co.jp/search?p={query}"},
    ],
}

ACADEMIC_SOURCES = {
    "en": ["arXiv", "Semantic Scholar", "Google Scholar"],
    "zh": ["CNKI", "Wanfang", "Paper with Code"],
    "ja": ["CiNii", "J-STAGE"],
}


class LanguageDetector:
    def __init__(self):
        self.chinese_chars = re.compile(r'[\u4e00-\u9fff]')
        self.japanese_chars = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
        self.korean_chars = re.compile(r'[\uac00-\ud7af]')
        self.arabic_chars = re.compile(r'[\u0600-\u06ff]')
        self.cyrillic_chars = re.compile(r'[\u0400-\u04ff]')
    
    def detect(self, text: str) -> Tuple[str, float]:
        """Detect language of text."""
        if not text:
            return "en", 0.0
        
        text = text.lower()
        
        scores = defaultdict(int)
        
        if self.chinese_chars.search(text):
            scores["zh"] += len(self.chinese_chars.findall(text)) * 2
        
        if self.japanese_chars.search(text):
            scores["ja"] += len(self.japanese_chars.findall(text)) * 2
        
        if self.korean_chars.search(text):
            scores["ko"] += len(self.korean_chars.findall(text)) * 2
        
        if self.arabic_chars.search(text):
            scores["ar"] += len(self.arabic_chars.findall(text)) * 2
        
        english_words = len([w for w in text.split() if w in "the a is are was were be been have has had do does did"])
        scores["en"] += english_words
        
        if not scores:
            return "en", 0.5
        
        total = sum(scores.values())
        detected_lang = max(scores, key=scores.get)
        confidence = scores[detected_lang] / total if total > 0 else 0.5
        
        return detected_lang, min(confidence, 1.0)
    
    def get_language_name(self, code: str) -> str:
        """Get language name from code."""
        return LANGUAGE_CODES.get(code, code.upper())


class MultiLanguageSearch:
    def __init__(self):
        self.detector = LanguageDetector()
    
    def detect_query_language(self, query: str) -> Dict:
        """Detect the language of a search query."""
        lang_code, confidence = self.detector.detect(query)
        
        return {
            "code": lang_code,
            "name": self.detector.get_language_name(lang_code),
            "confidence": round(confidence, 2)
        }
    
    def get_search_engines(self, language: str = "en") -> List[Dict]:
        """Get search engines for specific language."""
        return SEARCH_ENGINES_BY_LANG.get(language, SEARCH_ENGINES_BY_LANG["en"])
    
    def get_academic_sources(self, language: str = "en") -> List[str]:
        """Get academic sources for specific language."""
        return ACADEMIC_SOURCES.get(language, ACADEMIC_SOURCES["en"])
    
    def suggest_translations(self, query: str, target_langs: List[str] = None) -> Dict:
        """Suggest query translations for other languages."""
        if target_langs is None:
            target_langs = ["en", "zh", "es", "fr", "de", "ja"]
        
        current_lang, _ = self.detector.detect(query)
        
        suggestions = {}
        for lang in target_langs:
            if lang != current_lang:
                suggestions[lang] = {
                    "code": lang,
                    "name": self.detector.get_language_name(lang),
                    "note": f"Translation to {self.detector.get_language_name(lang)} recommended"
                }
        
        return {
            "original": {
                "query": query,
                "language": current_lang,
                "name": self.detector.get_language_name(current_lang)
            },
            "alternatives": suggestions
        }
    
    def get_supported_languages(self) -> List[Dict]:
        """Get list of supported languages."""
        return [
            {"code": code, "name": name}
            for code, name in LANGUAGE_CODES.items()
        ]


def detect_language(text: str) -> Tuple[str, float]:
    """Quick language detection."""
    detector = LanguageDetector()
    return detector.detect(text)


def get_language_name(code: str) -> str:
    """Get language name from code."""
    return LANGUAGE_CODES.get(code, code.upper())
