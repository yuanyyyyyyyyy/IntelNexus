import os
import arxiv
import requests
import re
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import random

try:
    from semanticscholar import SemanticScholar
except ImportError:
    SemanticScholar = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
]


class AcademicSearch:
    def __init__(self, semantic_scholar_key: Optional[str] = None):
        self.semantic_scholar_key = semantic_scholar_key
        if SemanticScholar and semantic_scholar_key:
            try:
                self.sch_client = SemanticScholar(api_key=semantic_scholar_key)
            except:
                self.sch_client = None
        else:
            self.sch_client = None
    
    def search_arxiv(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            for paper in client.results(search):
                results.append({
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors],
                    "summary": paper.summary[:500] if paper.summary else "",
                    "published": str(paper.published.date()) if paper.published else "",
                    "pdf_url": paper.pdf_url,
                    "arxiv_id": paper.entry_id.split("/")[-1] if paper.entry_id else "",
                    "categories": paper.categories if paper.categories else [],
                    "source": "arXiv",
                    "url": paper.entry_id if paper.entry_id else paper.pdf_url
                })
        except Exception as e:
            print(f"ArXiv search error: {e}")
        return results
    
    def search_semantic_scholar(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        if not self.sch_client:
            return results
        
        try:
            papers = self.sch_client.search_paper(query, limit=max_results)
            for paper in papers:
                results.append({
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors] if paper.authors else [],
                    "summary": paper.abstract[:500] if paper.abstract else "",
                    "published": str(paper.year) if paper.year else "",
                    "pdf_url": paper.url or "",
                    "citation_count": paper.citation_count or 0,
                    "source": "Semantic Scholar",
                    "url": paper.url or ""
                })
        except Exception as e:
            print(f"Semantic Scholar search error: {e}")
        return results
    
    def search_pubmed(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance"
            }
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            response = requests.get(base_url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                
                if ids:
                    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                    fetch_params = {
                        "db": "pubmed",
                        "id": ",".join(ids),
                        "retmode": "json"
                    }
                    fetch_response = requests.get(fetch_url, params=fetch_params, headers=headers, timeout=15)
                    if fetch_response.status_code == 200:
                        summary_data = fetch_response.json()
                        for pubmed_id in ids:
                            try:
                                result = summary_data.get("result", {}).get(pubmed_id, {})
                                if result.get("uid"):
                                    results.append({
                                        "title": result.get("title", ""),
                                        "authors": [a.get("name", "") for a in result.get("authors", [])],
                                        "summary": result.get("summary", "")[:500],
                                        "published": result.get("pubdate", ""),
                                        "pdf_url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
                                        "pubmed_id": pubmed_id,
                                        "source": "PubMed",
                                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
                                    })
                            except:
                                continue
        except Exception as e:
            print(f"PubMed search error: {e}")
        return results
    
    def search_google_scholar(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            url = "https://scholar.google.com/scholar"
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml"
            }
            params = {"q": query, "num": min(max_results, 10), "hl": "en"}
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                for item in soup.select("div.gs_r")[:max_results]:
                    try:
                        title_elem = item.select_one("h3.gs_rt")
                        title = title_elem.get_text(strip=True) if title_elem else ""
                        title = re.sub(r'\[.*?\]', '', title)
                        
                        link_elem = item.select_one("h3.gs_rt a")
                        link = link_elem.get("href", "") if link_elem else ""
                        
                        snippet = item.select_one("div.gs_rs")
                        summary = snippet.get_text(strip=True) if snippet else ""
                        
                        if title and link:
                            results.append({
                                "title": title,
                                "authors": [],
                                "summary": summary[:500],
                                "published": "",
                                "pdf_url": "",
                                "source": "Google Scholar",
                                "url": link
                            })
                    except:
                        continue
        except Exception as e:
            print(f"Google Scholar search error: {e}")
        return results
    
    def search_ieee(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            url = "https://ieeexplore.ieee.org/rest/search"
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "newsearch": True,
                "queryText": query,
                "matchPubs": True,
                "maxRecords": max_results,
                "returnFacets": ["ALL"]
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])
                
                for record in records:
                    try:
                        results.append({
                            "title": record.get("articleTitle", ""),
                            "authors": [a.get("name", "") for a in record.get("authors", [])],
                            "summary": record.get("abstract", "")[:500],
                            "published": record.get("publicationDate", ""),
                            "pdf_url": record.get("pdfUrl", ""),
                            "ieee_id": record.get("articleNumber", ""),
                            "source": "IEEE Xplore",
                            "url": record.get("documentUrl", "")
                        })
                    except:
                        continue
        except Exception as e:
            print(f"IEEE search error: {e}")
        return results
    
    def search_doaj(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        try:
            url = "https://doaj.org/api/v2/search/articles"
            params = {
                "query": query,
                "pageSize": max_results,
                "sort": "relevance"
            }
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                articles = data.get("results", [])
                
                for article in articles:
                    try:
                        results.append({
                            "title": article.get("title", ""),
                            "authors": [a.get("name", "") for a in article.get("authors", [])],
                            "summary": article.get("abstract", "")[:500],
                            "published": article.get("publishedDate", ""),
                            "pdf_url": article.get("pdfUrl", ""),
                            "doi": article.get("doi", ""),
                            "source": "DOAJ",
                            "url": article.get("url", "")
                        })
                    except:
                        continue
        except Exception as e:
            print(f"DOAJ search error: {e}")
        return results
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        all_results = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self.search_arxiv, query, max_results),
                executor.submit(self.search_semantic_scholar, query, max_results),
                executor.submit(self.search_pubmed, query, max_results),
                executor.submit(self.search_google_scholar, query, max_results),
                executor.submit(self.search_doaj, query, max_results),
            ]
            
            for future in as_completed(futures):
                try:
                    results = future.result()
                    if results:
                        all_results.extend(results)
                except Exception as e:
                    print(f"Search error: {e}")
        
        all_results.sort(key=lambda x: x.get("published", ""), reverse=True)
        return all_results[:max_results * 3]


def get_academic_results(query: str, max_results: int = 10, api_key: Optional[str] = None) -> List[Dict]:
    searcher = AcademicSearch(semantic_scholar_key=api_key)
    return searcher.search(query, max_results)
