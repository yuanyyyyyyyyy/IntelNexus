# IntelNexus V1.0 – 系统代码

________________________________________

## 截图索引（15+张）

请将截图文件放入 `docs/images/` 文件夹：

| 编号 | 截图内容 | 位置 |
|------|----------|------|
| 图1 | CLI帮助命令输出 | 文档开头 |
| 图2 | Web界面启动 | 文档开头 |
| 图3 | 搜索输入框和搜索按钮 | main.py搜索函数 |
| 图4 | 模型选择下拉菜单 | ui.py设置区域 |
| 图5 | 线程数设置 | ui.py高级设置 |
| 图6 | 暗网Tor设置界面 | ui.py暗网模式 |
| 图7 | Tor状态检测结果 | ui.py暗网模式 |
| 图8 | LLM模型加载中 | ui.py搜索流程 |
| 图9 | 查询优化结果 | ui.py搜索流程 |
| 图10 | 搜索结果统计 | ui.py搜索流程 |
| 图11 | 报告生成中流式输出 | ui.py搜索流程 |
| 图12 | 最终报告内容 | ui.py搜索流程 |
| 图13 | 下载选项和按钮 | ui.py下载区域 |
| 图14 | 搜索结果详情列表 | ui.py结果区域 |
| 图15 | 分页导航 | ui.py结果区域 |

![图1：CLI帮助命令输出](./images/01_cli_help.png)
![图2：Web界面启动](./images/02_web_ui_start.png)

# =====
# 文件: .\main.py
# =====

 // 功能: CLI和Web UI入口
 // 创建时间: 2025年2月6日
 // 最后修改: 2025年2月6日
 // 行数: 148行
 
 """
 IntelNexus - AI Multi-Source Network Intelligence Platform
 =========================================================
 A unified search interface for news and web content.
 """

 import os
 import click
 from datetime import datetime
 from concurrent.futures import ThreadPoolExecutor, as_completed

 from scrape import scrape_multiple
 from web_search import get_web_results
 from news_search import get_news_results
 from darkweb_search import get_darkweb_results, is_available as darkweb_available

 from llm import get_llm, refine_query, generate_summary
 from llm_utils import get_model_choices

 
 MODEL_CHOICES = get_model_choices()

 SEARCH_MODES = {
     "web": "Web Search",
     "news": "News Articles",
     "darkweb": "Dark Web (Optional)",
     "all": "All Sources"
 }

 def execute_search(mode, query, max_workers):
     results = []
     
     with ThreadPoolExecutor(max_workers=max_workers) as executor:
         futures = []
         
         if mode in ["web", "all"]:
             futures.append(executor.submit(get_web_results, query, max_workers, 20))
         
         if mode in ["news", "all"]:
             futures.append(executor.submit(get_news_results, query, 15))
         
         if mode in ["darkweb", "all"] and darkweb_available():
             futures.append(executor.submit(get_darkweb_results, query, max_workers))
         
         for future in as_completed(futures):
             try:
                 source = future.result()
                 if source:
                     results.extend(source)
             except Exception as e:
                 print(f"Search error: {e}")
     
     return results

 
 @click.group()
 @click.version_option()
 def intelnexus():
     """IntelNexus: AI-Powered Multi-Source Network Intelligence Platform."""
     pass

 @intelnexus.command()
 @click.option(
     "--model", "-m",
     default="qwen2.5:7b",
     show_default=True,
     type=click.Choice(MODEL_CHOICES),
     help="Select LLM model (local or cloud)"
 )
 @click.option("--query", "-q", required=True, type=str, help="Search query")
  @click.option(
     "--mode", "-s",
     default="all",
     type=click.Choice(["web", "news", "darkweb", "all"]),
     help="Search mode"
 )
 @click.option("--threads", "-t", default=5, show_default=True, type=int, help="Number of threads")
 @click.option("--output", "-o", type=str, help="Output filename")
 def search(model, query, mode, threads, output):
     """Run IntelNexus in CLI mode."""
     
     click.echo(f"IntelNexus - {SEARCH_MODES.get(mode, mode)} Mode")
     click.echo(f"Model: {model}")
     click.echo(f"Query: {query}")
     
     llm = get_llm(model)
     
     click.echo("[1/4] Refining query...")
     refined_query = refine_query(llm, query)
     click.echo(f"    Refined: {refined_query}")
     
     click.echo(f"[2/4] Searching {mode}...")
     search_results = execute_search(mode, refined_query, threads)
     click.echo(f"    Found {len(search_results)} results")
     
     if not search_results:
         click.echo("No results found.")
         return
     
     # 保留所有搜索结果（不过滤）
     search_filtered = search_results
     click.echo(f"[3/4] Keeping all {len(search_filtered)} results")
     
     click.echo("[4/4] Scraping content...")
     scraped_results = scrape_multiple(search_filtered, max_workers=threads)
     click.echo("    Done")
     
     click.echo("[5/5] Generating summary...")
     summary = generate_summary(llm, query, scraped_results)
     
     if not output:
         now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
         filename = f"report_{now}.md"
     else:
         filename = output + ".md"
     
     with open(filename, "w", encoding="utf-8") as f:
         f.write(summary)
         click.echo(f"\n[OUTPUT] Report saved to {filename}")

 
 @intelnexus.command()
 @click.option("--ui-port", default=8501, show_default=True, type=int, help="Port for Streamlit UI")
 @click.option("--ui-host", default="localhost", show_default=True, type=str, help="Host for Streamlit UI")
 def ui(ui_port, ui_host):
     """Run IntelNexus in Web UI mode."""
     import sys, os
     from streamlit.web import cli as stcli
     
     if getattr(sys, "frozen", False):
         base = sys._MEIPASS
     else:
         base = os.path.dirname(__file__)
     
     ui_script = os.path.join(base, "ui.py")
     sys.argv = [
         "streamlit", "run", ui_script,
         f"--server.port={ui_port}",
         f"--server.address={ui_host}",
         "--global.developmentMode=false",
     ]
     sys.exit(stcli.main())

 
 if __name__ == "__main__":
     intelnexus()

     


# =====
# 文件: .\config.py
# =====

 // 功能: 环境变量配置
 // 创建时间: 2025年2月6日
 // 最后修改: 2025年2月6日
 // 行数: 17行
 
 import os
 from dotenv import load_dotenv

 load_dotenv()

 OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
 GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
 ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
 OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
 OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
 OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

 
 SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
 NEWS_API_KEY = os.getenv("NEWS_API_KEY")
 TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

 ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"

     
 import requests
 import random
 import re
 from bs4 import BeautifulSoup
 from concurrent.futures import ThreadPoolExecutor, as_completed
 from requests.adapters import HTTPAdapter
 from urllib3.util.retry import Retry
 from urllib.parse import quote, urlencode
 import warnings
 warnings.filterwarnings("ignore")
 
 USER_AGENTS = [
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
 ]
 
 SEARCH_ENGINES = [
     {
         "name": "Bing",
         "url": "https://www.bing.com/search?q={query}&first={page}",
         "parser": "bing"
     },
     {
         "name": "DuckDuckGo",
         "url": "https://html.duckduckgo.com/html/?q={query}&b={page}",
         "parser": "ddg"
     },
     {
         "name": "Yahoo",
         "url": "https://search.yahoo.com/search?p={query}&b={page}",
         "parser": "yahoo"
     },
     {
         "name": "Yandex",
         "url": "https://yandex.com/search/?text={query}&page={page}",
         "parser": "yandex"
     },
     {
         "name": "Baidu",
         "url": "https://www.baidu.com/s?wd={query}&pn={page}",
         "parser": "baidu"
     },
 ]
 
 
 def get_session():
     session = requests.Session()
     retry = Retry(
         total=2,
         read=2,
         connect=2,
         backoff_factor=0.5,
         status_forcelist=[500, 502, 503, 504]
     )
     adapter = HTTPAdapter(max_retries=retry)
     session.mount("http://", adapter)
     session.mount("https://", adapter)
     return session
 
 
 def fetch_bing_results(query: str, page: int = 0):
     results = []
     try:
         encoded_query = quote(query, safe='')
         url = f"https://www.bing.com/search?q={encoded_query}&first={page * 10 + 1}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         session = get_session()
         response = session.get(url, headers=headers, timeout=20)
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for item in soup.select('li.b_algo'):
                 try:
                     # 修复：使用h2 a获取正确标题，而不是第一个链接
                     a_tag = item.select_one('h2 a')
                     if not a_tag:
                         a_tag = item.select_one('a[href]:not(.tilk)')
                     if a_tag:
                         title = a_tag.get_text(strip=True)
                         href = a_tag.get('href', '')
 
                         snippet = item.find('p')
                         description = snippet.get_text(strip=True) if snippet else ""
 
                         if href and href.startswith('http') and 'bing.com' not in href:
                             results.append({
                                 "title": title,
                                 "link": href,
                                 "description": description[:200],
                                 "source": "Bing"
                             })
                 except:
                     continue
     except Exception as e:
         print(f"Bing search error: {e}")
     return results
 
 
 def fetch_ddg_results(query: str, page: int = 0):
     results = []
     try:
         encoded_query = quote(query, safe='')
         url = f"https://html.duckduckgo.com/html/?q={encoded_query}&b={page * 11}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         session = get_session()
         response = session.get(url, headers=headers, timeout=20)
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for item in soup.select('div.result'):
                 try:
                     a_tag = item.select_one('a.result__a')
                     if a_tag:
                         title = a_tag.get_text(strip=True)
                         href = a_tag.get('href', '')
 
                         snippet = item.select_one('a.result__snippet')
                         description = snippet.get_text(strip=True) if snippet else ""
 
                         if href:
                             results.append({
                                 "title": title,
                                 "link": href,
                                 "description": description[:200],
                                 "source": "DuckDuckGo"
                             })
                 except:
                     continue
     except Exception as e:
         print(f"DuckDuckGo search error: {e}")
     return results
 
 
 def fetch_yahoo_results(query: str, page: int = 0):
     results = []
     try:
         encoded_query = quote(query, safe='')
         url = f"https://search.yahoo.com/search?p={encoded_query}&b={page * 10 + 1}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         session = get_session()
         response = session.get(url, headers=headers, timeout=20)
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for item in soup.select('div.algo'):
                 try:
                     a_tag = item.find('a')
                     if a_tag:
                         title = a_tag.get_text(strip=True)
                         href = a_tag.get('href', '')
 
                         snippet = item.find('p')
                         description = snippet.get_text(strip=True) if snippet else ""
 
                         if href and href.startswith('http'):
                             results.append({
                                 "title": title,
                                 "link": href,
                                 "description": description[:200],
                                 "source": "Yahoo"
                             })
                 except:
                     continue
     except Exception as e:
         print(f"Yahoo search error: {e}")
     return results
 
 
 def fetch_yandex_results(query: str, page: int = 0):
     results = []
     try:
         encoded_query = quote(query, safe='')
         url = f"https://yandex.com/search/?text={encoded_query}&page={page + 1}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         session = get_session()
         response = session.get(url, headers=headers, timeout=20)
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for item in soup.select('li.serp-item'):
                 try:
                     a_tag = item.select_one('a.serp-item__title')
                     if a_tag:
                         title = a_tag.get_text(strip=True)
                         href = a_tag.get('href', '')
 
                         snippet = item.select_one('div.serp-item__text')
                         description = snippet.get_text(strip=True) if snippet else ""
 
                         if href and href.startswith('http'):
                             results.append({
                                 "title": title,
                                 "link": href,
                                 "description": description[:200],
                                 "source": "Yandex"
                             })
                 except:
                     continue
     except Exception as e:
         print(f"Yandex search error: {e}")
     return results
 
 
 def fetch_baidu_results(query: str, page: int = 0):
     results = []
     try:
         encoded_query = quote(query, safe='')
         url = f"https://www.baidu.com/s?wd={encoded_query}&pn={page * 10}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         session = get_session()
         response = session.get(url, headers=headers, timeout=20)
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for item in soup.select('div.result'):
                 try:
                     a_tag = item.find('a')
                     if a_tag:
                         title = a_tag.get_text(strip=True)
                         href = a_tag.get('href', '')
 
                         if href and href.startswith('http'):
                             results.append({
                                 "title": title,
                                 "link": href,
                                 "description": "",
                                 "source": "Baidu"
                             })
                 except:
                     continue
     except Exception as e:
         print(f"Baidu search error: {e}")
     return results
 
 
 def get_web_results(query, max_workers: int = 5, max_results: int = 50) -> list:
     results = []
     pages_per_engine = 2  # 减少翻页数以提升速度
 
     # 支持多查询（列表或用|分隔的字符串）
     if isinstance(query, list):
         queries = query
     elif '|' in query:
         queries = [q.strip() for q in query.split('|')]
     else:
         queries = [query]
 
     with ThreadPoolExecutor(max_workers=max_workers) as executor:
         futures = []
 
         # 对每个查询进行搜索
         for q in queries:
             for page in range(pages_per_engine):
                 futures.append(executor.submit(fetch_bing_results, q, page))
                 futures.append(executor.submit(fetch_ddg_results, q, page))
                 futures.append(executor.submit(fetch_yahoo_results, q, page))
                 futures.append(executor.submit(fetch_yandex_results, q, page))
                 futures.append(executor.submit(fetch_baidu_results, q, page))
 
         for future in as_completed(futures):
             try:
                 result_urls = future.result()
                 results.extend(result_urls)
             except Exception as e:
                 print(f"Search error: {e}")
 
     seen_links = set()
     unique_results = []
     for res in results:
         link = res.get("link", "").rstrip('/')
         if link and link not in seen_links and len(link) > 10:
             seen_links.add(link)
             unique_results.append(res)
 
     return unique_results[:max_results]


 import os
 import requests
 from typing import List, Dict, Optional
 from datetime import datetime, timedelta
 from bs4 import BeautifulSoup
 from urllib.parse import quote, urljoin
 from concurrent.futures import ThreadPoolExecutor, as_completed
 import random
 import re
 
 try:
     from newsapi import NewsApiClient
 except ImportError:
     NewsApiClient = None
 
 USER_AGENTS = [
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
 ]
 
 RSS_SOURCES = [
     {"name": "Google News", "url": "https://news.google.com/rss/search?q={query}"},
     {"name": "Bing News", "url": "https://www.bing.com/news/search?q={query}&format=rss"},
     {"name": "Yahoo News", "url": "https://news.yahoo.com/rss/search?p={query}"},
     {"name": "Reuters", "url": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best"},
     {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
     {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
     {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
     {"name": "BBC", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"},
     {"name": "CNN", "url": "http://rss.cnn.com/rss/edition.rss"},
 ]
 
 
 class NewsSearch:
     def __init__(self, api_key: Optional[str] = None):
         self.api_key = api_key
         if NewsApiClient and api_key:
             try:
                 self.news_client = NewsApiClient(api_key=api_key)
             except Exception as e:
                 print(f"NewsAPI init error: {e}")
                 self.news_client = None
         else:
             self.news_client = None
 
     def search_newsapi(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
         if not self.news_client:
             return results
 
         try:
             response = self.news_client.get_everything(
                 q=query,
                 language="en",
                 sort_by="relevancy",
                 page_size=max_results
             )
 
             if response.get("status") == "ok":
                 for article in response.get("articles", []):
                     results.append({
                         "title": article.get("title", ""),
                         "description": article.get("description", "")[:300],
                         "content": article.get("content", ""),
                         "author": article.get("author", ""),
                         "source": article.get("source", {}).get("name", "NewsAPI"),
                         "url": article.get("url", ""),
                         "published_at": article.get("publishedAt", ""),
                         "image_url": article.get("urlToImage", "")
                     })
         except Exception as e:
             print(f"NewsAPI search error: {e}")
 
         return results
 
     def search_rss(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         query_lower = query.lower()
 
         for source in RSS_SOURCES:
             if len(results) >= max_results:
                 break
             try:
                 if "{query}" in source["url"]:
                     url = source["url"].format(query=quote(query))
                 else:
                     url = source["url"]
 
                 headers = {"User-Agent": random.choice(USER_AGENTS)}
                 response = requests.get(url, headers=headers, timeout=12)
 
                 if response.status_code == 200:
                     try:
                         soup = BeautifulSoup(response.content, "xml")
                     except:
                         soup = BeautifulSoup(response.content, "html.parser")
 
                     items = soup.find_all("item")[:max_results]
                     if not items:
                         items = soup.find_all("entry")[:max_results]
 
                     for item in items:
                         if len(results) >= max_results:
                             break
 
                         title = item.find("title")
                         link = item.find("link")
                         desc = item.find("description") or item.find("summary") or item.find("content")
                         pub_date = item.find("pubDate") or item.find("published") or item.find("dc:date")
 
                         link_text = ""
                         if link:
                             if hasattr(link, 'get_text'):
                                 link_text = link.get_text(strip=True)
                             else:
                                 link_text = str(link)
 
                         if title and link_text:
                             title_text = title.get_text(strip=True) if hasattr(title, 'get_text') else str(title)
 
                             if query_lower not in title_text.lower() and "{query}" in source["url"]:
                                 continue
 
                             results.append({
                                 "title": title_text,
                                 "description": desc.get_text(strip=True)[:300] if desc and hasattr(desc, 'get_text') else "",
                                 "content": desc.get_text(strip=True) if desc and hasattr(desc, 'get_text') else "",
                                 "author": "",
                                 "source": source["name"],
                                 "url": link_text,
                                 "published_at": pub_date.get_text(strip=True) if pub_date and hasattr(pub_date, 'get_text') else "",
                                 "image_url": ""
                             })
             except Exception as e:
                 print(f"RSS search error from {source['name']}: {e}")
 
         return results
 
     def search_bing_news(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
         try:
             url = "https://www.bing.com/news/search"
             params = {"q": query, "form": "QBRE", "sp": "-1"}
             headers = {"User-Agent": random.choice(USER_AGENTS)}
 
             response = requests.get(url, params=params, headers=headers, timeout=15)
             if response.status_code == 200:
                 soup = BeautifulSoup(response.text, "html.parser")
 
                 for item in soup.select("div.news-card")[:max_results]:
                     try:
                         title_elem = item.select_one("a.title")
                         snippet_elem = item.select_one("div.snippet")
                         source_elem = item.select_one("div.source")
 
                         if title_elem:
                             results.append({
                                 "title": title_elem.get_text(strip=True),
                                 "description": snippet_elem.get_text(strip=True)[:300] if snippet_elem else "",
                                 "content": snippet_elem.get_text(strip=True) if snippet_elem else "",
                                 "author": "",
                                 "source": source_elem.get_text(strip=True) if source_elem else "Bing News",
                                 "url": title_elem.get("href", ""),
                                 "published_at": "",
                                 "image_url": ""
                             })
                     except:
                         continue
         except Exception as e:
             print(f"Bing news search error: {e}")
         return results
 
     def search_google_news(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
         try:
             url = "https://news.google.com/rss/search"
             params = {"q": query, "hl": "en-US", "gl": "US"}
             headers = {"User-Agent": random.choice(USER_AGENTS)}
 
             response = requests.get(url, params=params, headers=headers, timeout=15)
             if response.status_code == 200:
                 soup = BeautifulSoup(response.content, "xml")
 
                 for item in soup.find_all("item")[:max_results]:
                     try:
                         title = item.find("title")
                         link = item.find("link")
                         desc = item.find("description")
                         pub_date = item.find("pubDate")
 
                         if title and link:
                             results.append({
                                 "title": title.get_text(strip=True),
                                 "description": desc.get_text(strip=True)[:300] if desc else "",
                                 "content": desc.get_text(strip=True) if desc else "",
                                 "author": "",
                                 "source": "Google News",
                                 "url": link.get_text(strip=True),
                                 "published_at": pub_date.get_text(strip=True) if pub_date else "",
                                 "image_url": ""
                             })
                     except:
                         continue
         except Exception as e:
             print(f"Google News search error: {e}")
         return results
 
     def search(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         with ThreadPoolExecutor(max_workers=4) as executor:
             futures = []
 
             if self.news_client:
                 futures.append(executor.submit(self.search_newsapi, query, max_results))
 
             futures.append(executor.submit(self.search_rss, query, max_results))
             futures.append(executor.submit(self.search_bing_news, query, max_results))
             futures.append(executor.submit(self.search_google_news, query, max_results))
 
             for future in futures:
                 try:
                     r = future.result()
                     if r:
                         results.extend(r)
                 except Exception as e:
                     print(f"Search error: {e}")
 
         seen_urls = set()
         unique_results = []
         for r in results:
             url = r.get("url", "")
             if url and url not in seen_urls:
                 seen_urls.add(url)
                 unique_results.append(r)
 
         return unique_results[:max_results * 3]
 
 
 def get_news_results(query: str, max_results: int = 10, api_key: Optional[str] = None) -> List[Dict]:
     searcher = NewsSearch(api_key=api_key)
     return searcher.search(query, max_results)


 """
 Dark Web Search Module
 ====================
 This module supports:
 1. Public dark web search engines (Ahmia, OnionLink)
 2. Custom .onion sites with optional authentication
 
 Enable via .env: ENABLE_DARKWEB=true
 
 WARNING: This module is for educational and authorized research purposes only.
 """
 
 import os
 import sys
 from dotenv import load_dotenv
 load_dotenv()
 
 import requests
 import random
 import re
 import json
 from bs4 import BeautifulSoup
 from concurrent.futures import ThreadPoolExecutor, as_completed
 from requests.adapters import HTTPAdapter
 from urllib3.util.retry import Retry
 import platform
 
 import warnings
 warnings.filterwarnings("ignore")
 
 ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"
 
 # 自定义暗网站点配置（支持认证）
 # 格式: {"name": "站点名", "url": "http://xxx.onion", "auth": {"type": "basic", "username": "xxx", "password": "xxx"}}
 CUSTOM_ONION_SITES = os.getenv("CUSTOM_ONION_SITES", "")
 
 def get_custom_onion_sites(ui_sites=None):
     """获取自定义暗网站点列表
 
     Args:
         ui_sites: 从UI传递的自定义站点列表
 
     Returns:
        站点列表
     """
     sites = []
 
     # 1. 从环境变量加载
     if CUSTOM_ONION_SITES:
         try:
             sites = json.loads(CUSTOM_ONION_SITES)
         except:
             pass
 
     # 2. 从本地文件加载
     try:
         sites_file = "data/custom_onion_sites.json"
         if os.path.exists(sites_file):
             with open(sites_file, "r", encoding="utf-8") as f:
                 file_sites = json.load(f)
                 # 合并到站点列表
                 for fs in file_sites:
                     if fs not in sites:
                         sites.append(fs)
     except:
         pass
 
     # 3. 合并UI传递的站点
     if ui_sites:
         for us in ui_sites:
             if us not in sites:
                 sites.append(us)
 
     # 4. 默认添加Breached论坛（如果配置了认证）
     breached_user = os.getenv("BREACHED_USERNAME", "")
     breached_pass = os.getenv("BREACHED_PASSWORD", "")
     if breached_user and breached_pass:
         breached_site = {
             "name": "Breached Forum",
             "url": "http://breachedmw4otc2lhx7nqe4wyxfhpvy32ooz26opvqkmmrbg73c7ooad.onion",
             "auth": {
                 "type": "basic",
                 "username": breached_user,
                 "password": breached_pass
             }
         }
         # 检查是否已存在
         if not any(s.get("name") == "Breached Forum" for s in sites):
             sites.append(breached_site)
 
     return sites
 
 
 def fetch_with_auth(url, auth=None):
     """使用认证访问暗网站点"""
     headers = {"User-Agent": random.choice(USER_AGENTS)}
 
     session = requests.Session()
     session.headers.update(headers)
 
     # 设置代理
     port = get_tor_proxy_port()
     session.proxies = {
         "http": f"socks5h://127.0.0.1:{port}",
         "https": f"socks5h://127.0.0.1:{port}"
     }
 
     if auth:
         if auth.get("type") == "basic":
             session.auth = (auth.get("username"), auth.get("password"))
         elif auth.get("type") == "cookie":
             # 使用Cookie认证
             cookies = auth.get("cookies", {})
             for k, v in cookies.items():
                 session.cookies.set(k, v)
 
     try:
         response = session.get(url, timeout=30)
         return response
     except:
         return None
 
 
 def search_custom_onion_site(site_config, query):
     """搜索自定义暗网站点"""
     results = []
     try:
         base_url = site_config.get("url", "")
         auth = site_config.get("auth")
         name = site_config.get("name", "Custom")
 
         # 尝试访问站点并搜索
         # Breached论坛搜索URL格式
         search_url = f"{base_url}?search={query}"
 
         response = fetch_with_auth(search_url, auth)
 
         if response and response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             # 提取链接
             for a in soup.find_all('a', href=True):
                 try:
                     href = str(a.get('href', ''))
                     title = a.get_text(strip=True)
 
                     if href and len(title) > 2:
                         # 检查是否包含.onion
                         if '.onion' in href.lower() or base_url.split('//')[1].split('.')[0] in href:
                             results.append({
                                 "title": title[:100] or f"{name} result",
                                 "link": href if href.startswith('http') else f"{base_url}{href}",
                                 "source": name
                             })
                 except:
                     continue
     except:
         pass
 
     return results
 
 USER_AGENTS = [
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
     "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
 ]
 
 # 完整的暗网搜索引擎列表（来自原始项目）
 DARKWEB_SEARCH_ENGINES = [
     {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"},
     {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}"},
     {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}"},
     {"name": "Amnesia", "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}"},
     {"name": "Kaizer", "url": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}"},
     {"name": "Anima", "url": "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}"},
     {"name": "Tornado", "url": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}"},
     {"name": "TorNet", "url": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}"},
     {"name": "Torland", "url": "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}"},
     {"name": "Find Tor", "url": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}"},
     {"name": "Excavator", "url": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}"},
     {"name": "Onionway", "url": "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}"},
     {"name": "Tor66", "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}"},
     {"name": "OSS", "url": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}"},
     {"name": "Torgol", "url": "http://torgolnpeouim56dykfob6jh5r2ps2j73enc42s2um4ufob3ny4fcdyd.onion/?q={query}"},
     {"name": "The Deep Searches", "url": "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}"},
 ]
 
 # Backward-compatible flat list
 DEFAULT_SEARCH_ENGINES = [e["url"] for e in DARKWEB_SEARCH_ENGINES]
 
 
 def get_tor_proxy_port():
     """获取Tor代理端口"""
     # 优先使用环境变量
     custom_port = os.getenv("TOR_PROXY_PORT")
     if custom_port:
         try:
             return int(custom_port)
         except:
             pass
 
     # 默认端口
     return 9150
 
 
 def get_tor_session():
     """创建通过Tor代理的会话"""
     session = requests.Session()
     retry = Retry(
         total=3,
         read=3,
         connect=3,
         backoff_factor=0.5,
         status_forcelist=[500, 502, 503, 504]
     )
     adapter = HTTPAdapter(max_retries=retry)
     session.mount("http://", adapter)
     session.mount("https://", adapter)
 
     port = get_tor_proxy_port()
     session.proxies = {
         "http": f"socks5h://127.0.0.1:{port}",
         "https": f"socks5h://127.0.0.1:{port}"
     }
     return session
 
 
 def fetch_ahmia_results(query):
     """从Ahmia获取暗网搜索结果（无需Tor）"""
     results = []
     try:
         url = f"https://ahmia.fi/search/?q={query}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         response = requests.get(url, headers=headers, timeout=15)
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for a in soup.find_all('a', href=True):
                 try:
                     href = str(a.get('href', ''))
                     title = a.get_text(strip=True)
                     if '.onion' in href.lower() and len(title) > 2:
                         results.append({
                             "title": title[:100] or "暗网资源",
                             "link": href,
                             "source": "Ahmia"
                         })
                 except:
                     continue
     except:
         pass
 
     return results
 
 
 def fetch_onionlink_search(query):
     """从onionlink搜索获取结果（无需Tor）"""
     results = []
     try:
         url = f"https://onionlink.net/?s={query}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         response = requests.get(url, headers=headers, timeout=15)
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for a in soup.find_all('a', href=True):
                 try:
                     href = str(a.get('href', ''))
                     title = a.get_text(strip=True)
                     if '.onion' in href.lower() and len(title) > 2 and 'http' in href:
                         results.append({
                             "title": title[:100] or "暗网资源",
                             "link": href,
                             "source": "OnionLink"
                         })
                 except:
                     continue
     except:
         pass
 
     return results
 
 
 def fetch_tordex_search(query):
     """从TorDex搜索获取结果（无需Tor）"""
     results = []
     try:
         url = f"https://tordexu72joez4ofvtvk6hxdlh3cvt7qexvzuwcyhyhj5f5xt22b5gfqd.onion/search?q={query}"
         headers = {"User-Agent": random.choice(USER_AGENTS)}
         response = requests.get(url, headers=headers, timeout=15, proxies={
             "http": "socks5h://127.0.0.1:9150",
             "https": "socks5h://127.0.0.1:9150"
         })
 
         if response.status_code == 200:
             soup = BeautifulSoup(response.text, "html.parser")
 
             for a in soup.find_all('a', href=True):
                 try:
                     href = str(a.get('href', ''))
                     title = a.get_text(strip=True)
                     if '.onion' in href.lower() and len(title) > 2:
                         results.append({
                             "title": title[:100] or "暗网资源",
                             "link": href,
                             "source": "TorDex"
                         })
                 except:
                     continue
     except:
         pass
 
     return results
 
 
 def is_available():
     """检查暗网搜索是否可用"""
     if not ENABLE_DARKWEB:
         return False
     return True
 
 
 def get_darkweb_results(refined_query, max_workers=5, advanced_mode=False, tor_port=9150, ui_sites=None):
     """获取暗网搜索结果
 
     Args:
         refined_query: 查询字符串或列表
         max_workers: 最大线程数
         advanced_mode: 是否启用高级模式（需要Tor）
         tor_port: Tor代理端口
         ui_sites: 从UI传递的自定义站点列表
     """
     if not ENABLE_DARKWEB:
         return []
 
     # 处理查询（可能是列表或字符串）
     if isinstance(refined_query, list):
         queries = refined_query
     else:
         queries = [refined_query]
 
     results = []
 
     # 对每个查询进行搜索
     for query in queries:
         # 1. 公开暗网搜索引擎（始终可用，无需Tor）
         try:
             search_results = fetch_ahmia_results(query)
             if search_results:
                 results.extend(search_results)
         except:
             pass
 
         # 2. 高级模式：使用Tor代理搜索
         if advanced_mode:
             # OnionLink搜索（需要Tor）
             try:
                 search_results = fetch_onionlink_search(query)
                 if search_results:
                     results.extend(search_results)
             except:
                 pass
 
             # TorDex搜索（需要Tor）
             try:
                 search_results = fetch_tordex_search(query)
                 if search_results:
                     results.extend(search_results)
             except:
                 pass
 
         # 3. 自定义暗网站点（支持认证）
         custom_sites = get_custom_onion_sites(ui_sites)
         for site in custom_sites:
             try:
                 site_results = search_custom_onion_site(site, query)
                 if site_results:
                     results.extend(site_results)
             except:
                 pass
 
     # 去重
     seen_links = set()
     unique_results = []
     for res in results:
         link = res.get("link", "").rstrip('/')
         if link and link not in seen_links:
             seen_links.add(link)
             unique_results.append(res)
 
     return unique_results


 import re
 import openai
 from langchain_core.prompts import ChatPromptTemplate
 from langchain_core.output_parsers import StrOutputParser
 from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
 from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
 import logging
 import re
 
 import warnings
 
 warnings.filterwarnings("ignore")
 
 
 def get_llm(model_choice):
     # Look up the configuration (cloud or local Ollama)
     config = resolve_model_config(model_choice)
 
     if config is None:  # Extra error check
         supported_models = get_model_choices()
         raise ValueError(
             f"Unsupported LLM model: '{model_choice}'. "
             f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
         )
 
     # Extract the necessary information from the configuration
     llm_class = config["class"]
     model_specific_params = config["constructor_params"]
 
     # Combine common parameters with model-specific parameters
     # Model-specific parameters will override common ones if there are any conflicts
     all_params = {**_common_llm_params, **model_specific_params}
 
     # Create the LLM instance using the gathered parameters
     llm_instance = llm_class(**all_params)
 
     return llm_instance
 
 
 def refine_query(llm, user_input):
     """
     查询优化 - 原始查询 + 多语言翻译
     返回: 原始查询 + 英文翻译 + 中文翻译（如果原文不是英文/中文）
     """
     user_input = user_input.strip()
 
     # 简单的拼写错误修复
     common_typos = {
         "sarch": "search",
         "serach": "search",
         "seaech": "search",
         "reuslt": "result",
         "resutl": "result",
     }
 
     words = user_input.split()
     fixed_words = []
     for word in words:
         if word.lower() in common_typos:
             fixed_words.append(common_typos[word.lower()])
         else:
             fixed_words.append(word)
 
     original = " ".join(fixed_words)
 
     # 只对有意义的查询添加翻译（避免短查询被膨胀）
     if len(original) < 3:
         return [original]
 
     # 检测语言并生成翻译查询
     queries = [original]  # 原始查询
 
     # 使用简单的语言检测
     has_chinese = any('\u4e00' <= c <= '\u9fff' for c in original)
     has_english = any('a' <= c.lower() <= 'z' for c in original)
 
     # 如果有中文，添加英文翻译
     if has_chinese:
         queries.append(f"{original} English")
         queries.append(f"{original} news")
 
     # 如果有英文且长度足够，添加中文翻译
     if has_english and len(original) >= 3:
         queries.append(f"{original} 中文")
         queries.append(f"{original} 新闻")
 
     return queries
 
 
 def expand_query_for_search(query_variants):
     """
     将查询变体扩展为搜索字符串
     如果是列表，用 | 分隔多个查询
     """
     if isinstance(query_variants, list):
         return " | ".join(query_variants)
     return query_variants
 
 
 def filter_results(llm, query, results):
     if not results:
         return []
 
     # 过滤掉PDF链接（LLM无法读取PDF）
     filtered = []
     for r in results:
         link = r.get("link", "") or r.get("url", "") or r.get("pdf_url", "")
         if link.lower().endswith('.pdf') or '.pdf?' in link.lower():
             continue
         filtered.append(r)
 
     if not filtered:
         return []
 
     # 如果全部是PDF，返回空
     if len(filtered) == 0:
         return []
 
     # Extract key query terms for basic filtering
     query_terms = set(query.lower().split()) if isinstance(query, str) else set()
 
     # Pre-filter: remove results with NO relevance to query
     prefiltered = []
     for r in results:
         title = r.get("title", "").lower()
         desc = r.get("description", "").lower()
         summary = r.get("summary", "").lower()
 
         # Check if any query term appears in title or description
         has_match = any(term in title or term in desc or term in summary for term in query_terms)
 
         # Also check for Chinese character overlap
         if not has_match and any('\u4e00' <= c <= '\u9fff' for c in query):
             # For Chinese queries, check if any Chinese chars appear
             has_match = any(c in title or c in desc or c in summary for c in query)
 
         if has_match:
             prefiltered.append(r)
 
     # If pre-filtering removed too many, fall back to all results
     if len(prefiltered) < len(results) * 0.3:
         prefiltered = results[:min(len(results), 50)]
 
     # Use LLM to further refine
     system_prompt = """
 You are a Network Intelligence Analyst. Given a search query and search results, select the MOST RELEVANT results.
 
 CRITICAL RULES:
 1. Only select results that are DIRECTLY related to the query topic
 2. For query "九江", do NOT select results about "AI", "人工智能", "machine learning", etc.
 3. Results must match the query's subject matter exactly
 4. Output ONLY a comma-separated list of result indices (e.g., "1,3,5")
 
 Search Query: {query}
 
 Search Results:
 """
 
     final_str = _generate_final_string(prefiltered)
 
     prompt_template = ChatPromptTemplate(
         [("system", system_prompt), ("user", "{results}")]
     )
     chain = prompt_template | llm | StrOutputParser()
     try:
         result_indices = chain.invoke({"query": query, "results": final_str})
     except openai.RateLimitError as e:
         print(f"Rate limit error: {e}")
         result_indices = ""
 
     # Parse indices
     parsed_indices = []
     for match in re.findall(r"\d+", result_indices):
         try:
             idx = int(match)
             if 1 <= idx <= len(prefiltered):
                 parsed_indices.append(idx)
         except ValueError:
             continue
 
     # Remove duplicates while preserving order
     seen = set()
     parsed_indices = [
         i for i in parsed_indices if not (i in seen or seen.add(i))
     ]
 
     if not parsed_indices:
         # Fallback: use prefiltered results directly
         parsed_indices = list(range(1, min(len(prefiltered), 20) + 1))
 
     top_results = [prefiltered[i - 1] for i in parsed_indices[:20]]
 
     return top_results
 
 
 def _generate_final_string(results, truncate=False):
     """
     Generate a formatted string from the search results for LLM processing.
     """
 
     if truncate:
         max_title_length = 30
         max_link_length = 0
 
     final_str = []
     for i, res in enumerate(results):
         title = res.get("title", "")
         link = res.get("link", "") or res.get("url", "") or res.get("pdf_url", "")
 
         title = re.sub(r"[^0-9a-zA-Z\-\.\s]", " ", str(title))
         link = re.sub(r"(?<=\.onion).*", "", str(link))
 
         if not link and not title:
             continue
 
         if truncate:
             title = title[:max_title_length] + "..." if len(title) > max_title_length else title
             link = link[:max_link_length] + "..." if len(link) > max_link_length else link
 
         final_str.append(f"{i+1}. {link} - {title}")
 
     return "\n".join(s for s in final_str)
 
 
 def generate_summary(llm, query, content, search_mode="all"):
     """生成情报报告，根据搜索模式调整分析重点"""
 
     # 调试日志
     print(f"=== LLM INPUT DEBUG ===")
     print(f"Content type: {type(content)}")
     if isinstance(content, dict):
         print(f"Content keys count: {len(content)}")
         print(f"Content keys: {list(content.keys())[:5]}")
         if content:
             first_val = list(content.values())[0]
             print(f"First value length: {len(first_val)}")
             print(f"First value preview: {first_val[:300]}")
     elif isinstance(content, list):
         print(f"Content is list, length: {len(content)}")
     print(f"=======================")
 
     # 根据搜索模式设置不同的分析重点
     mode_descriptions = {
         "all": "综合所有来源：网页、新闻、暗网",
         "web": "主要来源：网页搜索结果",
         "news": "主要来源：新闻资讯",
         "darkweb": "主要来源：暗网资源（.onion网站）",
     }
 
     mode_desc = mode_descriptions.get(search_mode, mode_descriptions["all"])
 
     # 强制生成详细分析报告的提示词
     system_prompt = f"""
 你是一位高级网络情报分析师。基于以下搜索结果，请生成一份结构清晰、内容全面的情报分析报告。
 
 查询主题：{query}
 数据来源：{mode_desc}
 
 重要要求：
 1. 报告要全面详细，涵盖所有搜索结果中的关键信息
 2. 不要对话或提问，直接给出分析报告
 3. 使用Markdown格式，以##标题组织内容
 4. 核心发现部分用流畅的段落叙述，不要用列表
 5. 每个部分都要有实质性的分析和内容
 
 报告模板结构：
 
 ## 一、执行摘要
 
 用3-5句话概括关于"{query}"的核心发现、当前状态和结论。
 
 
 ## 二、背景与概述
 
 ### 2.1 背景介绍
 [领域背景、发展历程、为什么重要]
 
 ### 2.2 基本概念
 [核心定义、关键术语解释]
 
 
 ## 三、核心发现
 
 [这是报告主体部分，应该占据最多篇幅，用流畅的段落叙述]
 
 ### 发现一：[主题]
 [详细叙述，包括：时间、地点、人物、事件、影响等]
 
 ### 发现二：[主题]
 [详细叙述]
 
 ### 发现三：[主题]
 [详细叙述]
 
 
 ## 四、多角度分析
 
 ### 4.1 技术维度
 [技术原理、现状、趋势、挑战]
 
 ### 4.2 商业维度
 [市场、盈利模式、主要玩家、投资]
 
 ### 4.3 社会维度
 [影响、公众态度、伦理]
 
 ### 4.4 政策与监管维度
 [法规、监管、合规]
 
 ### 4.5 发展趋势
 [短期、中期、长期预测]
 
 
 ## 五、关键数据
 
 [汇总表格形式的硬数据]
 
 
 ## 六、风险与建议
 
 ### 6.1 主要风险
 [1-3个核心风险及影响]
 
 ### 6.2 行动建议
 [1-3条可执行的建议]
 
 
 ## 七、信息来源
 
 [链接列表]
 
 请直接生成报告，不要有任何对话或提问。
 """
 
     prompt_template = ChatPromptTemplate(
         [("system", system_prompt), ("user", "搜索结果内容:\n{content}")]
     )
     chain = prompt_template | llm | StrOutputParser()
     return chain.invoke({"content": content})


 import requests
 from urllib.parse import urljoin
 from langchain_openai import ChatOpenAI
 from langchain_ollama import ChatOllama
 from typing import Callable, Optional, List
 from langchain_anthropic import ChatAnthropic
 from langchain_google_genai import ChatGoogleGenerativeAI
 from langchain_core.callbacks.base import BaseCallbackHandler
 from config import OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY, GOOGLE_API_KEY
 
 
 class BufferedStreamingHandler(BaseCallbackHandler):
     def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
         self.buffer = ""
         self.buffer_limit = buffer_limit
         self.ui_callback = ui_callback
 
     def on_llm_new_token(self, token: str, **kwargs) -> None:
         self.buffer += token
         if "\n" in token or len(self.buffer) >= self.buffer_limit:
             print(self.buffer, end="", flush=True)
             if self.ui_callback:
                 self.ui_callback(self.buffer)
             self.buffer = ""
 
     def on_llm_end(self, response, **kwargs) -> None:
         if self.buffer:
             print(self.buffer, end="", flush=True)
             if self.ui_callback:
                 self.ui_callback(self.buffer)
             self.buffer = ""
 
 
 # --- Configuration Data ---
 # Instantiate common dependencies once
 _common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]
 
 # Define common parameters for most LLMs
 _common_llm_params = {
     "temperature": 0,
     "streaming": True,
     "callbacks": _common_callbacks,
 }
 
 # Map input model choices (lowercased) to their configuration
 # Each config includes the class and any model-specific constructor parameters
 _llm_config_map = {
     'gpt-4.1': {
         'class': ChatOpenAI,
         'constructor_params': {'model_name': 'gpt-4.1'}
     },
     'gpt-5.1': {
         'class': ChatOpenAI,
         'constructor_params': {'model_name': 'gpt-5.1'}
     },
     'gpt-5-mini': {
         'class': ChatOpenAI,
         'constructor_params': {'model_name': 'gpt-5-mini'}
     },
     'gpt-5-nano': {
         'class': ChatOpenAI,
         'constructor_params': {'model_name': 'gpt-5-nano'}
     },
     'claude-sonnet-4-5': {
         'class': ChatAnthropic,
         'constructor_params': {'model': 'claude-sonnet-4-5'}
     },
     'claude-sonnet-4-0': {
         'class': ChatAnthropic,
         'constructor_params': {'model': 'claude-sonnet-4-0'}
     },
     'gemini-2.5-flash': {
         'class': ChatGoogleGenerativeAI,
         'constructor_params': {'model': 'gemini-2.5-flash', 'google_api_key': GOOGLE_API_KEY }
     },
     'gemini-2.5-flash-lite': {
         'class': ChatGoogleGenerativeAI,
         'constructor_params': {'model': 'gemini-2.5-flash-lite', 'google_api_key': GOOGLE_API_KEY}
     },
     'gemini-2.5-pro': {
         'class': ChatGoogleGenerativeAI,
         'constructor_params': {'model': 'gemini-2.5-pro', 'google_api_key': GOOGLE_API_KEY}
     },
     'gpt-5.1-openrouter': {
         'class': ChatOpenAI,
         'constructor_params': {
             'model_name': 'openai/gpt-5.1',
             'base_url': OPENROUTER_BASE_URL,
             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
         }
     },
     'gpt-5-mini-openrouter': {
         'class': ChatOpenAI,
         'constructor_params': {
             'model_name': 'openai/gpt-5-mini',
             'base_url': OPENROUTER_BASE_URL,
             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
         }
     },
     'claude-sonnet-4.5-openrouter': {
         'class': ChatOpenAI,
         'constructor_params': {
             'model_name': 'anthropic/claude-sonnet-4.5',
             'base_url': OPENROUTER_BASE_URL,
             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
         }
     },
     'grok-4.1-fast-openrouter': {
         'class': ChatOpenAI,
         'constructor_params': {
             'model_name': 'x-ai/grok-4.1-fast',
             'base_url': OPENROUTER_BASE_URL,
             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
         }
     },
     # 'llama3.2': {
     #     'class': ChatOllama,
     #     'constructor_params': {'model': 'llama3.2:latest', 'base_url': OLLAMA_BASE_URL}
     # },
     # 'llama3.1': {
     #     'class': ChatOllama,
     #     'constructor_params': {'model': 'llama3.1:latest', 'base_url': OLLAMA_BASE_URL}
     # },
     # 'gemma3': {
     #     'class': ChatOllama,
     #     'constructor_params': {'model': 'gemma3:latest', 'base_url': OLLAMA_BASE_URL}
     # },
     # 'deepseek-r1': {
     #     'class': ChatOllama,
     #     'constructor_params': {'model': 'deepseek-r1:latest', 'base_url': OLLAMA_BASE_URL}
     # },
 
     # Add more models here easily:
     # 'mistral7b': {
     #     'class': ChatOllama,
     #     'constructor_params': {'model': 'mistral:7b', 'base_url': OLLAMA_BASE_URL}
     # },
     # 'gpt3.5': {
     #      'class': ChatOpenAI,
     #      'constructor_params': {'model_name': 'gpt-3.5-turbo', 'base_url': OLLAMA_BASE_URL}
     # }
 }
 
 
 def _normalize_model_name(name: str) -> str:
     return name.strip().lower()
 
 
 def _get_ollama_base_url() -> Optional[str]:
     if not OLLAMA_BASE_URL:
         return None
     return OLLAMA_BASE_URL.rstrip("/") + "/"
 
 
 def fetch_ollama_models() -> List[str]:
     """
     Retrieve the list of locally available Ollama models by querying the Ollama HTTP API.
     Returns an empty list if the API isn't reachable or the base URL is not defined.
     """
     base_url = _get_ollama_base_url()
     if not base_url:
         return []
 
     try:
         resp = requests.get(urljoin(base_url, "api/tags"), timeout=3)
         resp.raise_for_status()
         models = resp.json().get("models", [])
         available = []
         for m in models:
             name = m.get("name") or m.get("model")
             if name:
                 available.append(name)
         return available
     except (requests.RequestException, ValueError):
         return []
 
 
 def get_model_choices() -> List[str]:
     """
     Combine the statically configured cloud models with the locally available Ollama models and custom models.
     """
     base_models = list(_llm_config_map.keys())
     dynamic_models = fetch_ollama_models()
 
     # Import custom models
     try:
         from custom_models import get_custom_model_names
         custom_models = get_custom_model_names()
     except ImportError:
         custom_models = []
 
     normalized = {_normalize_model_name(m): m for m in base_models}
 
     # Add Ollama models
     for dm in dynamic_models:
         key = _normalize_model_name(dm)
         if key not in normalized:
             normalized[key] = dm
 
     # Add custom models
     for cm in custom_models:
         key = _normalize_model_name(cm)
         if key not in normalized:
             normalized[key] = cm
 
     # Preserve the order: original base models first, then custom models, then dynamic ones in alphabetical order
     ordered_dynamic = sorted(
         [name for key, name in normalized.items() if name not in base_models and name not in custom_models],
         key=_normalize_model_name,
     )
     return base_models + custom_models + ordered_dynamic
 
 
 def resolve_model_config(model_choice: str):
     """
     Resolve a model choice (case-insensitive) to the corresponding configuration.
     Supports predefined remote models, locally installed Ollama models, and custom models.
     """
     model_choice_lower = _normalize_model_name(model_choice)
 
     # Check predefined models first
     config = _llm_config_map.get(model_choice_lower)
     if config:
         return config
 
     # Check Ollama models
     for ollama_model in fetch_ollama_models():
         if _normalize_model_name(ollama_model) == model_choice_lower:
             return {
                 "class": ChatOllama,
                 "constructor_params": {"model": ollama_model, "base_url": OLLAMA_BASE_URL},
             }
 
     # Check custom models
     try:
         from custom_models import get_model_config, get_custom_model_names
         for custom_model_name in get_custom_model_names():
             if _normalize_model_name(custom_model_name) == model_choice_lower:
                 model_config = get_model_config(custom_model_name)
                 if model_config:
                     model_type = model_config.get("type", "").lower()
                     config_params = model_config.get("config", {})
 
                     # Handle different custom model types
                     if model_type == "openai":
                         return {
                             "class": ChatOpenAI,
                             "constructor_params": {
                                 "model_name": config_params.get("model_name", custom_model_name),
                                 "base_url": config_params.get("base_url"),
                                 "api_key": config_params.get("api_key"),
                             }
                         }
                     elif model_type == "azure openai":
                         return {
                             "class": ChatOpenAI,
                             "constructor_params": {
                                 "model_name": config_params.get("model_name", custom_model_name),
                                 "azure_endpoint": config_params.get("base_url"),
                                 "api_key": config_params.get("api_key"),
                                 "api_version": "2024-02-01",
                             }
                         }
                     elif model_type == "ollama":
                         return {
                             "class": ChatOllama,
                             "constructor_params": {
                                 "model": config_params.get("model_name", custom_model_name),
                                 "base_url": config_params.get("base_url", OLLAMA_BASE_URL),
                             }
                         }
                     elif model_type == "anthropic":
                         return {
                             "class": ChatAnthropic,
                             "constructor_params": {
                                 "model": config_params.get("model_name", custom_model_name),
                                 "api_key": config_params.get("api_key"),
                             }
                         }
                     elif model_type == "google":
                         return {
                             "class": ChatGoogleGenerativeAI,
                             "constructor_params": {
                                 "model": config_params.get("model_name", custom_model_name),
                                 "google_api_key": config_params.get("api_key"),
                             }
                         }
                     elif model_type in ["cohere", "mistral", "deepseek", "通义千问", "智谱ai", "百度文心一言", "讯飞星火", "moonshot", "01.ai"]:
                         return {
                             "class": ChatOpenAI,
                             "constructor_params": {
                                 "model_name": config_params.get("model_name", custom_model_name),
                                 "base_url": config_params.get("base_url"),
                                 "api_key": config_params.get("api_key"),
                             }
                         }
     except ImportError:
         pass
 
     return None


 """
 IntelNexus - Web UI
 ==================
 Multi-source network intelligence search interface.
 Apple-inspired minimalist design.
 """
 
 import base64
 import socket
 import streamlit as st
 from datetime import datetime
 from concurrent.futures import ThreadPoolExecutor
 from scrape import scrape_multiple
 
 from report_export import export_report, get_export_formats
 from web_search import get_web_results
 from news_search import get_news_results
 from darkweb_search import get_darkweb_results, is_available as darkweb_available
 
 from llm_utils import BufferedStreamingHandler, get_model_choices
 from llm import get_llm, refine_query, filter_results, generate_summary, expand_query_for_search
 from custom_models import add_custom_model, get_custom_model_names, remove_custom_model
 
 
 LANG = {
     "zh": {
         "title": "IntelNexus",
         "subtitle": "多源网络情报分析平台",
         "search_placeholder": "输入搜索内容...",
         "search_button": "搜索",
         "search_mode": "搜索模式",
         "settings": "设置",
         "language": "语言",
         "llm_model": "AI模型",
         "threads": "线程数",
         "sources": "数据来源",
         "loading": "加载中...",
         "refining": "优化查询中...",
         "searching": "搜索中...",
         "filtering": "筛选中...",
         "scraping": "抓取内容...",
         "generating": "生成报告中...",
         "refined_query": "优化后的查询",
         "search_results": "搜索结果",
         "filtered_results": "筛选结果",
         "report_title": "情报报告",
         "download": "下载报告",
         "download_format": "下载格式",
         "complete": "完成",
         "darkweb_warning": "暗网搜索：基于公开索引（无需登录）",
         "mode_all": "全部来源",
         "mode_web": "网页搜索",
         "mode_news": "新闻资讯",
         "mode_darkweb": "暗网搜索",
         "results_count": "条结果",
         "zh": "中文",
         "en": "English",
         "add_custom_model": "添加自定义模型",
         "model_name": "模型名称",
         "model_type": "模型类型",
         "base_url": "Base URL (可选)",
         "api_key": "API密钥",
         "model_id": "模型ID",
         "add_model": "添加模型",
         "model_exists": "模型名称已存在或添加失败",
         "fill_fields": "请填写所有必填字段",
         "ok": "确定",
         "deleted": "已删除",
         "custom_models_list": "已添加的模型",
         "model_add_success": "模型已添加",
         "error": "错误",
         "download_ready": "准备下载",
         "download_failed": "下载失败",
         "pdf_ready": "PDF已准备",
         "word_ready": "Word已准备",
         "md_ready": "Markdown已准备",
         "ollama_base_url": "Ollama Base URL",
         "delete": "删除",
         "darkweb_settings": "暗网设置",
         "tor_status": "Tor状态",
         "tor_running": "已运行",
         "tor_not_running": "未运行",
         "tor_port": "Tor端口",
         "detect_tor": "检测Tor",
         "advanced_mode": "高级模式",
         "advanced_mode_desc": "启用Tor代理搜索（需要Tor运行）",
         "breached_forum": "Breached论坛",
         "breached_username": "用户名",
         "breached_password": "密码",
         "breached_register": "没有账号？点击注册",
         "breached_saved": "已保存",
         "tor_setup_guide": "Tor配置指引",
         "tor_download": "下载Tor浏览器",
         "default_mode": "默认模式（仅Ahmia，无需Tor）",
         "breached_hint": "💡 使用自己的账号可访问更多内容",
         "custom_onion_sites": "自定义暗网站点",
         "site_name": "站点名称",
         "site_url": "站点URL",
         "site_need_auth": "需要认证",
         "add_site": "添加站点",
         "added_sites": "已添加的站点",
         "no_sites": "暂无自定义站点",
         "site_saved": "站点已保存",
         "site_deleted": "站点已删除",
     },
     "en": {
         "title": "IntelNexus",
         "subtitle": "Multi-Source Network Intelligence Platform",
         "search_placeholder": "Enter search query...",
         "search_button": "Search",
         "search_mode": "Search Mode",
         "settings": "Settings",
         "language": "Language",
         "llm_model": "AI Model",
         "threads": "Threads",
         "sources": "Data Sources",
         "loading": "Loading...",
         "refining": "Refining query...",
         "searching": "Searching...",
         "filtering": "Filtering...",
         "scraping": "Scraping content...",
         "generating": "Generating report...",
         "refined_query": "Refined Query",
         "search_results": "Search Results",
         "filtered_results": "Filtered Results",
         "report_title": "Intelligence Report",
         "download": "Download",
         "download_format": "Format",
         "complete": "Complete",
         "darkweb_warning": "Dark web: Based on public indexes (no login required)",
         "mode_all": "All Sources",
         "mode_web": "Web Search",
         "mode_news": "News",
         "mode_darkweb": "Dark Web",
         "results_count": "results",
         "zh": "Chinese",
         "en": "English",
         "add_custom_model": "Add Custom Model",
         "model_name": "Model Name",
         "model_type": "Model Type",
         "base_url": "Base URL (optional)",
         "api_key": "API Key",
         "model_id": "Model ID",
         "add_model": "Add Model",
         "model_exists": "Model name already exists or failed to add",
         "fill_fields": "Please fill all required fields",
         "ok": "OK",
         "deleted": "Deleted",
         "custom_models_list": "Custom Models",
         "model_add_success": "Model added",
         "error": "Error",
         "download_ready": "Ready to download",
         "download_failed": "Download failed",
         "pdf_ready": "PDF Ready",
         "word_ready": "Word Ready",
         "md_ready": "Markdown Ready",
         "ollama_base_url": "Ollama Base URL",
         "delete": "Delete",
         "darkweb_settings": "Dark Web Settings",
         "tor_status": "Tor Status",
         "tor_running": "Running",
         "tor_not_running": "Not Running",
         "tor_port": "Tor Port",
         "detect_tor": "Detect Tor",
         "advanced_mode": "Advanced Mode",
         "advanced_mode_desc": "Enable Tor proxy search (requires Tor running)",
         "breached_forum": "Breached Forum",
         "breached_username": "Username",
         "breached_password": "Password",
         "breached_register": "No account? Click to register",
         "breached_saved": "Saved",
         "tor_setup_guide": "Tor Setup Guide",
         "tor_download": "Download Tor Browser",
         "default_mode": "Default mode (Ahmia only, no Tor needed)",
         "breached_hint": "💡 Use your own account to access more content",
         "custom_onion_sites": "Custom Onion Sites",
         "site_name": "Site Name",
         "site_url": "Site URL",
         "site_need_auth": "Requires Auth",
         "add_site": "Add Site",
         "added_sites": "Added Sites",
         "no_sites": "No custom sites yet",
         "site_saved": "Site saved",
         "site_deleted": "Site deleted",
     }
 }
 
 SEARCH_MODES = {
     "all": ["mode_all", "全部来源"],
     "web": ["mode_web", "网页搜索"],
     "news": ["mode_news", "新闻资讯"],
     "darkweb": ["mode_darkweb", "暗网搜索"],
 }
 
 BREACHED_URL = "http://breachedmw4otc2lhx7nqe4wyxfhpvy32ooz26opvqkmmrbg73c7ooad.onion"
 DEFAULT_TOR_PORT = 9150
 
 def check_tor_status(port=DEFAULT_TOR_PORT):
     """检测Tor代理端口是否开放"""
     try:
         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
         sock.settimeout(2)
         result = sock.connect_ex(('127.0.0.1', port))
         sock.close()
         return result == 0
     except:
         return False
 
 def get_tor_port():
     """获取Tor代理端口"""
     return st.session_state.get("tor_port", DEFAULT_TOR_PORT)
 
 
 def get_text(key):
     lang_code = st.session_state.get("lang", "zh")
     return LANG.get(lang_code, LANG["zh"]).get(key, key)
 
 
 @st.cache_data(ttl=200, show_spinner=False)
 def cached_search(mode, refined_query, threads, advanced_mode=False, tor_port=DEFAULT_TOR_PORT, ui_sites=None):
     results = []
 
     with ThreadPoolExecutor(max_workers=threads) as executor:
         futures = []
 
         if mode in ["web", "all"]:
             futures.append(executor.submit(get_web_results, refined_query, threads, 40))
 
         if mode in ["news", "all"]:
             futures.append(executor.submit(get_news_results, refined_query, 30))
 
         if mode in ["darkweb", "all"]:
             if darkweb_available():
                 futures.append(executor.submit(get_darkweb_results, refined_query, threads, advanced_mode, tor_port, ui_sites))
             else:
                 print("警告: 暗网搜索已启用但Tor未连接或Ahmia不可用")
 
         for f in futures:
             try:
                 results.extend(f.result())
             except Exception as e:
                 print(f"Search error: {e}")
 
     return results
 
 
 @st.cache_data(ttl=200, show_spinner=False)
 def cached_scrape(filtered, threads):
     return scrape_multiple(filtered, max_workers=threads)
 
 
 st.set_page_config(
     page_title="IntelNexus",
     page_icon=None,
     initial_sidebar_state="expanded",
 )
 
 # Force Light theme
 st.markdown("""
 <style>
     /* Force Light Theme */
     .stApp {
         background-color: #FFFFFF !important;
         color: #1E1E1E !important;
     }
     [data-testid="stSidebar"] {
         background-color: #F5F5F5 !important;
     }
     div[data-testid="stMarkdownContainer"] {
         color: #1E1E1E !important;
     }
     .stTextInput > div > div > input {
         background-color: #FFFFFF !important;
         color: #1E1E1E !important;
     }
     /* Remove dark theme gradient background */
     header[data-testid="stHeader"] {
         background-color: transparent !important;
     }
     .stDeployButton {
         display: none !important;
     }
 </style>
 """, unsafe_allow_html=True)
 
 if "lang" not in st.session_state:
     st.session_state.lang = "zh"
 
 if "query_cache" not in st.session_state:
     st.session_state.query_cache = ""
 
 st.markdown("""
 <style>
     @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Text:wght@300;400;500;600&display=swap');
 
     :root {
         --morandi-bg: #E8E4DF;
         --morandi-sidebar: #DCD8D3;
         --morandi-card: #F5F2EE;
         --morandi-blue: #7B9CB5;
         --morandi-green: #8FA890;
         --morandi-pink: #C4A4A4;
         --morandi-peach: #D4A5A5;
         --morandi-text: #5C5C5C;
         --morandi-text-light: #8A8A8A;
         --morandi-border: #C9C5C0;
         --morandi-accent: #9CB5B0;
     }
 
     #stDecoration {
         display: none !important;
     }
 
     * {
         font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif !important;
     }
 
     .stApp {
         background: var(--morandi-bg);
     }
 
     div[data-testid="stSidebar"] {
         background: var(--morandi-sidebar);
         border-right: 1px solid var(--morandi-border);
     }
 
     .sidebar-title {
         font-size: 20px;
         font-weight: 600;
         color: var(--morandi-text);
         padding: 20px 16px 10px;
     }
 
     .sidebar-subtitle {
         font-size: 13px;
         color: var(--morandi-text-light);
         padding: 0 16px 20px;
     }
 
     .main-title {
         font-size: 40px;
         font-weight: 600;
         color: var(--morandi-text);
         letter-spacing: -0.02em;
     }
 
     .main-subtitle {
         font-size: 19px;
         font-weight: 400;
         color: var(--morandi-text-light);
         margin-top: 4px;
     }
 
     .search-input input {
         border-radius: 14px !important;
         border: 1px solid var(--morandi-border) !important;
         padding: 14px 18px !important;
         font-size: 17px !important;
         background: #FFFFFF !important;
         color: var(--morandi-text) !important;
         transition: all 0.3s ease !important;
     }
 
     .search-input input:focus {
         border-color: var(--morandi-blue) !important;
         box-shadow: 0 0 0 3px rgba(123, 156, 181, 0.15) !important;
         outline: none !important;
     }
 
     .search-input input::placeholder {
         color: var(--morandi-text-light) !important;
     }
 
     .search-button button {
         border-radius: 14px !important;
         background: var(--morandi-blue) !important;
         border: none !important;
         padding: 14px 28px !important;
         font-size: 17px !important;
         font-weight: 500 !important;
         color: #FFFFFF !important;
         transition: all 0.3s ease !important;
     }
 
     .search-button button:hover {
         background: #6B8BA5 !important;
         transform: translateY(-1px);
     }
 
     .search-button button:active {
         transform: scale(0.98) translateY(0);
     }
 
     div[data-testid="stRadio"] > div {
         gap: 8px;
     }
 
     div[data-testid="stRadio"] label {
         border-radius: 12px !important;
         padding: 12px 16px !important;
         background: var(--morandi-sidebar) !important;
         border: 1px solid transparent !important;
         transition: all 0.2s ease !important;
         color: var(--morandi-text) !important;
     }
 
     div[data-testid="stRadio"] label:hover {
         background: var(--morandi-sidebar) !important;
     }
 
     div[data-testid="stRadio"] input:checked + div {
         background: var(--morandi-sidebar) !important;
         border-color: transparent !important;
         color: var(--morandi-text) !important;
     }
 
     div[data-testid="stSelectbox"] > div {
         background: var(--morandi-sidebar) !important;
         border: 1px solid var(--morandi-border) !important;
         border-radius: 12px !important;
     }
 
     div[data-testid="stSelectbox"] > div:focus-within {
         border-color: var(--morandi-border) !important;
         box-shadow: none !important;
     }
 
     .lang-switch {
         display: flex;
         gap: 8px;
         padding: 12px 16px;
     }
 
     .lang-btn {
         padding: 8px 16px;
         border-radius: 20px;
         font-size: 13px;
         cursor: pointer;
         border: 1px solid var(--morandi-border);
         background: var(--morandi-card);
         color: var(--morandi-text);
         transition: all 0.2s;
     }
 
     .lang-btn:hover {
         background: #E5E1DC;
     }
 
     .lang-btn.active {
         background: var(--morandi-green);
         color: #FFFFFF;
         border-color: var(--morandi-green);
     }
 
     .result-card {
         background: var(--morandi-card);
         border-radius: 18px;
         padding: 24px;
         margin: 16px 0;
         box-shadow: 0 4px 16px rgba(0,0,0,0.06);
         border: 1px solid var(--morandi-border);
     }
 
     .result-title {
         font-size: 15px;
         font-weight: 600;
         color: var(--morandi-text);
         margin-bottom: 8px;
     }
 
     .result-stats {
         display: flex;
         gap: 16px;
         margin-top: 16px;
         padding-top: 16px;
         border-top: 1px solid var(--morandi-border);
     }
 
     .stat-item {
         text-align: center;
     }
 
     .stat-value {
         font-size: 24px;
         font-weight: 600;
         color: var(--morandi-text);
     }
 
     .stat-label {
         font-size: 12px;
         color: var(--morandi-text-light);
         margin-top: 4px;
     }
 
     .report-section {
         background: var(--morandi-card);
         border-radius: 18px;
         padding: 24px;
         margin: 16px 0;
         box-shadow: 0 4px 16px rgba(0,0,0,0.06);
         border: 1px solid var(--morandi-border);
     }
 
     .report-title {
         font-size: 22px;
         font-weight: 600;
         color: var(--morandi-text);
         margin-bottom: 16px;
         padding-bottom: 12px;
         border-bottom: 1px solid var(--morandi-border);
     }
 
     .download-btn {
         display: inline-block;
         padding: 12px 24px;
         background: var(--morandi-green);
         border-radius: 12px;
         color: #FFFFFF;
         text-decoration: none;
         font-weight: 500;
         transition: all 0.3s;
     }
 
     .download-btn:hover {
         background: #7F9680;
         transform: translateY(-1px);
     }
 
     .section-header {
         font-size: 13px;
         font-weight: 600;
         color: var(--morandi-text-light);
         text-transform: uppercase;
         letter-spacing: 0.5px;
         margin-bottom: 12px;
     }
 
     div.stButton > button {
         border-radius: 12px;
     }
 
     div[data-testid="stSelectbox"] > div > div {
         border-radius: 12px;
     }
 
     div[data-testid="stSlider"] > div > div {
         border-radius: 12px;
     }
 
     .stSuccess {
         background: var(--morandi-green);
         color: #FFFFFF;
         border-radius: 12px;
     }
 
     .stSpinner > div > div {
         border-top-color: var(--morandi-blue);
     }
 
     div[data-testid="stMarkdownContainer"] p {
         color: var(--morandi-text);
     }
 
     .stTextInput > div > div > input {
         border-radius: 14px !important;
     }
 
     header {
         background: none !important;
     }
 
     [data-testid="stHeaderContainer"] {
         background: var(--morandi-bg) !important;
     }
 
     div[data-testid="stHeaderContainer"]::before {
         display: none !important;
     }
 </style>
 """, unsafe_allow_html=True)
 
 
 with st.sidebar:
     st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)
     st.markdown(f'<div class="sidebar-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
 
     st.markdown("---")
     st.markdown(f'<div class="section-header">{get_text("search_mode")}</div>', unsafe_allow_html=True)
 
     mode_options = list(SEARCH_MODES.keys())
search_mode = st.radio(
          "mode",
          mode_options,
          format_func=lambda x: get_text(SEARCH_MODES[x][0]),
          label_visibility="collapsed",
          index=0
      )

<!-- 截图说明：图3-在此处放置侧边栏搜索模式选择截图 -->

      if search_mode == "darkweb" and not darkweb_available():
          st.warning(get_text("darkweb_warning"))
 
     # 暗网设置区域
     if search_mode == "darkweb":
         st.markdown("---")
         with st.expander(f"🧅 {get_text('darkweb_settings')}", expanded=True):
             # Tor状态检测
             tor_port = st.number_input(
                 get_text("tor_port"),
                 min_value=1,
                 max_value=65535,
                 value=st.session_state.get("tor_port", DEFAULT_TOR_PORT),
                 key="tor_port"
             )
 
             # 检测Tor状态
             tor_running = check_tor_status(tor_port)
             if tor_running:
                 st.success(f"🟢 {get_text('tor_running')}")
             else:
                 st.error(f"🔴 {get_text('tor_not_running')}")
 
             col_tor1, col_tor2 = st.columns([1, 1])
             with col_tor1:
                 if st.button(get_text("detect_tor"), key="detect_tor_btn"):
                     st.rerun()
 
             # 高级模式选项
             advanced_mode = st.checkbox(
                 get_text("advanced_mode"),
                 value=st.session_state.get("advanced_mode", False),
                 help=get_text("advanced_mode_desc"),
                 key="advanced_mode"
             )
 
             if not tor_running and advanced_mode:
                 st.warning(f"⚠️ {get_text('tor_not_running')} - {get_text('default_mode')}")
 
             # Breached论坛配置
             st.markdown("---")
             st.markdown(f"**{get_text('breached_forum')}**")
 
             # 注册链接 + 提示
             st.markdown(f"""
             <a href="{BREACHED_URL}" target="_blank" style="text-decoration: none;">
                 <span style="color: #4A90D9;">🔗 {get_text('breached_register')}</span>
             </a>
             <br><br>
             <span style="color: #6B7280; font-size: 0.9em;">{get_text('breached_hint')}</span>
             """, unsafe_allow_html=True)
 
             col_breach1, col_breach2 = st.columns(2)
             with col_breach1:
                 breached_user = st.text_input(
                     get_text("breached_username"),
                     value=st.session_state.get("breached_username", ""),
                     key="breached_user"
                 )
             with col_breach2:
                 breached_pass = st.text_input(
                     get_text("breached_password"),
                     value=st.session_state.get("breached_password", ""),
                     type="password",
                     key="breached_pass"
                 )
 
             if breached_user and breached_pass:
                 st.session_state.breached_username = breached_user
                 st.session_state.breached_password = breached_pass
                 st.success(f"✓ {get_text('breached_saved')}")
 
             # 自定义暗网站点配置
             st.markdown("---")
             st.markdown(f"**{get_text('custom_onion_sites')}**")
 
             # 初始化自定义站点列表
             if "custom_onion_sites" not in st.session_state:
                 st.session_state.custom_onion_sites = []
 
             # 添加新站点表单（使用container代替expander避免嵌套）
             with st.container():
                 st.markdown(f"**{get_text('add_site')}**")
                 col_site1, col_site2 = st.columns(2)
                 with col_site1:
                     new_site_name = st.text_input(
                         get_text("site_name"),
                         key="new_site_name",
                         placeholder="My Site"
                     )
                     new_site_url = st.text_input(
                         get_text("site_url"),
                         key="new_site_url",
                         placeholder="http://xxx.onion/search?q="
                     )
                 with col_site2:
                     new_site_auth = st.checkbox(
                         get_text("site_need_auth"),
                         key="new_site_auth"
                     )
                     new_site_user = ""
                     new_site_pass = ""
                     if new_site_auth:
                         new_site_user = st.text_input(
                             get_text("breached_username"),
                             key="new_site_user"
                         )
                         new_site_pass = st.text_input(
                             get_text("breached_password"),
                             type="password",
                             key="new_site_pass"
                         )
 
                 if st.button(get_text("add_site"), key="add_site_btn"):
                     if new_site_name and new_site_url:
                         new_site = {
                             "name": new_site_name,
                             "url": new_site_url,
                         }
                         if new_site_auth and new_site_user and new_site_pass:
                             new_site["auth"] = {
                                 "type": "basic",
                                 "username": new_site_user,
                                 "password": new_site_pass
                             }
                         # 保存到session
                         st.session_state.custom_onion_sites.append(new_site)
                         # 持久化保存到文件
                         try:
                             import json
                             import os
                             os.makedirs("data", exist_ok=True)
                             sites_file = "data/custom_onion_sites.json"
                             with open(sites_file, "w", encoding="utf-8") as f:
                                 json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
                         except Exception as e:
                             print(f"保存站点失败: {e}")
                         st.success(f"✓ {get_text('site_saved')}")
                         st.rerun()
 
             # 显示已添加的站点
             # 尝试从文件加载站点
             try:
                 import json
                 sites_file = "data/custom_onion_sites.json"
                 if os.path.exists(sites_file):
                     with open(sites_file, "r", encoding="utf-8") as f:
                         loaded_sites = json.load(f)
                         if loaded_sites and not st.session_state.custom_onion_sites:
                             st.session_state.custom_onion_sites = loaded_sites
             except:
                 pass
 
             if st.session_state.custom_onion_sites:
                 st.markdown(f"**{get_text('added_sites')}**")
                 for i, site in enumerate(st.session_state.custom_onion_sites):
                     col_site, col_del = st.columns([4, 1])
                     with col_site:
                         auth_info = " 🔒" if site.get("auth") else ""
                         st.markdown(f"- {site.get('name', 'Unknown')}{auth_info}")
                     with col_del:
                         if st.button("🗑️", key=f"del_site_{i}"):
                             st.session_state.custom_onion_sites.pop(i)
                             # 更新文件
                             try:
                                 import json
                                 import os
                                 sites_file = "data/custom_onion_sites.json"
                                 with open(sites_file, "w", encoding="utf-8") as f:
                                     json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
                             except:
                                 pass
                             st.rerun()
             else:
                 st.markdown(f"_{get_text('no_sites')}_")
 
     st.markdown("---")
     st.markdown(f'<div class="section-header">{get_text("settings")}</div>', unsafe_allow_html=True)
 
     model_options = get_model_choices()
     default_model = "qwen2.5:7b" if "qwen2.5:7b" in model_options else (model_options[0] if model_options else "gpt-4o")
     model_index = model_options.index(default_model) if default_model in model_options else 0
 
     model = st.selectbox(get_text("llm_model"), model_options, index=model_index)
     threads = st.slider(get_text("threads"), 1, 16, 5)
 
     # 语言切换 - 在设置中
     lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
     current_lang_display = get_text("zh") if st.session_state.lang == "zh" else get_text("en")
     selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()),
                                   index=0 if st.session_state.lang == "zh" else 1,
                                   key="lang_selector")
     if lang_options.get(selected_lang) != st.session_state.lang:
         st.session_state.lang = lang_options[selected_lang]
         st.rerun()
 
     # 自定义模型管理
     st.markdown("---")
     with st.expander(get_text("add_custom_model")):
         col_name, col_type = st.columns(2)
         with col_name:
             custom_model_name = st.text_input(
                 get_text("model_name"),
                 key="custom_model_name"
             )
         with col_type:
             model_type = st.selectbox(
                 get_text("model_type"),
                 [
                     "OpenAI", "Azure OpenAI", "Anthropic", "Google", "Cohere",
                     "Mistral", "DeepSeek", "Ollama", "通义千问", "智谱AI",
                     "百度文心一言", "讯飞星火", "Moonshot", "01.AI"
                 ],
                 key="model_type_selector"
             )
 
         if model_type == "OpenAI":
             base_url = st.text_input(get_text("base_url"))
             api_key = st.text_input(get_text("api_key"), type="password", key="openai_api_key")
             model_id = st.text_input(get_text("model_id"))
         elif model_type == "Anthropic":
             api_key = st.text_input(get_text("api_key"), type="password", key="anthropic_api_key")
             model_id = st.text_input(get_text("model_id"))
         elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
             api_key = st.text_input(get_text("api_key"), type="password", key=f"{model_type.lower()}_api_key")
             base_url = st.text_input(get_text("base_url"), key=f"{model_type.lower()}_base_url")
             model_id = st.text_input(get_text("model_id"))
         else:  # Ollama
             base_url = st.text_input(get_text("ollama_base_url"), value="http://127.0.0.1:11434", key="ollama_base_url")
             api_key = None
             model_id = st.text_input(get_text("model_name"))
 
         if st.button(get_text("add_model")):
             if custom_model_name and model_id:
                 config = {"model_name": model_id}
                 if model_type in ["OpenAI", "Azure OpenAI"]:
                     if base_url:
                         config["base_url"] = base_url
                     if api_key:
                         config["api_key"] = api_key
                 elif model_type == "Anthropic":
                     if api_key:
                         config["api_key"] = api_key
                 elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
                     if api_key:
                         config["api_key"] = api_key
                     if base_url:
                         config["base_url"] = base_url
                 else:  # Ollama
                     config["base_url"] = base_url
 
                 if add_custom_model(custom_model_name, model_type.lower(), config):
                     st.success(get_text("model_add_success"))
                     st.rerun()
                 else:
                     st.error(get_text("model_exists"))
             else:
                 st.error(get_text("fill_fields"))
 
     # 显示已添加的自定义模型
     custom_models = get_custom_model_names()
     if custom_models:
         with st.expander(get_text("custom_models_list")):
             for custom_model in custom_models:
                 col_model, col_delete = st.columns([3, 1])
                 with col_model:
                     st.write(custom_model)
                 with col_delete:
                     if st.button(get_text("delete"), key=f"delete_{custom_model}"):
                         if remove_custom_model(custom_model):
                             st.success(get_text("deleted"))
                             st.rerun()
 
     st.markdown("---")
     st.markdown(f'<div class="section-header">{get_text("download_format")}</div>', unsafe_allow_html=True)
 
     # 初始化下载格式
     if "sidebar_download_format" not in st.session_state:
         st.session_state.sidebar_download_format = "md"
 
     # 初始化下载状态（用于解决页面消失问题）
     if "download_ready" not in st.session_state:
         st.session_state.download_ready = False
     if "download_data" not in st.session_state:
         st.session_state.download_data = None
     if "download_filename" not in st.session_state:
         st.session_state.download_filename = None
     if "download_mime" not in st.session_state:
         st.session_state.download_mime = None
 
     format_options = ["md", "pdf", "docx", "xlsx"]
     format_labels = {
         "md": "Markdown",
         "pdf": "PDF",
         "docx": "Word",
         "xlsx": "Excel"
     }
 
     sidebar_format = st.selectbox(
         "选择下载格式",
         format_options,
         format_func=lambda x: format_labels[x],
         label_visibility="collapsed",
         key="sidebar_format_select"
     )
     st.session_state.sidebar_download_format = sidebar_format
 
     st.markdown("---")
     st.markdown(f'<div class="section-header">{get_text("sources")}</div>', unsafe_allow_html=True)
     st.caption("Semantic Scholar, RSS, Reddit, Bing")
 
 
 col1, col2 = st.columns([8, 2])
 with col1:
     st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
     st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
 
 with st.form("search_form", clear_on_submit=False):
     col_input, col_button = st.columns([10, 1])
     with col_input:
         query = st.text_input(
             "query",
             placeholder=get_text("search_placeholder"),
             label_visibility="collapsed",
             key="query_input"
         )
     with col_button:
         run_button = st.form_submit_button(get_text("search_button"))
 
 status_slot = st.empty()
 
 # 搜索逻辑
 if run_button and query:
     # 保存搜索词到session_state
     st.session_state.query_cache = query
     st.session_state.search_mode_cache = search_mode
     st.session_state.threads_cache = threads
     st.session_state.model_cache = model
 
     # 清空之前的搜索结果
     for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
         st.session_state.pop(k, None)
 
with status_slot.container():
          with st.spinner(get_text("loading")):
              llm = get_llm(model)

<!-- 截图说明：图8-此处放置LLM模型加载中的截图 -->

      with status_slot.container():
          with st.spinner(get_text("refining")):
              # refine_query现在返回查询列表（原始+翻译）
              query_variants = refine_query(llm, query)
              # 保存原始查询用于导出
              st.session_state.refined = query
              # 转换为搜索字符串
search_query = expand_query_for_search(query_variants)

      st.markdown(f"""
      <div class="result-card">
          <div class="section-header">{get_text("refined_query")}</div>
          <div class="result-title">原始查询: {query}</div>
          <div class="result-title" style="color: var(--morandi-blue);">多语言查询: {search_query}</div>
      </div>
      """, unsafe_allow_html=True)
 
     with status_slot.container():
         with st.spinner(get_text("searching")):
             advanced_mode = st.session_state.get("advanced_mode", False)
             tor_port = st.session_state.get("tor_port", DEFAULT_TOR_PORT)
             ui_sites = st.session_state.get("custom_onion_sites", [])
             st.session_state.results = cached_search(search_mode, search_query, threads, advanced_mode, tor_port, ui_sites)
 
     source_counts = {}
     for r in st.session_state.results:
         src = r.get("source", "Unknown")
         source_counts[src] = source_counts.get(src, 0) + 1
 
results_count = len(st.session_state.results)

<!-- 截图说明：图10-此处放置搜索结果数量和来源统计截图 -->

      # 显示搜索源统计
     source_info = " | ".join([f"{k}: {v}" for k, v in source_counts.items()])
     st.markdown(f"""
     <div class="result-card">
         <div class="result-stats">
             <div class="stat-item">
                 <div class="stat-value">{results_count}</div>
                 <div class="stat-label">{get_text("results_count")}</div>
             </div>
         </div>
         <div class="stat-label" style="margin-top: 10px;">数据来源: {source_info}</div>
     </div>
     """, unsafe_allow_html=True)
 
     # 保留所有搜索结果（不过滤）
     st.session_state.filtered = st.session_state.results
 
     with status_slot.container():
         with st.spinner(get_text("scraping")):
             st.session_state.scraped = cached_scrape(st.session_state.filtered, threads)
             # 调试日志
             print(f"=== SCRAPING DEBUG ===")
             print(f"Filtered results count: {len(st.session_state.filtered)}")
             print(f"Scraped keys: {list(st.session_state.scraped.keys())[:5]}")
             if st.session_state.scraped:
                 first_content = list(st.session_state.scraped.values())[0]
                 print(f"First content length: {len(first_content)}")
                 print(f"First content preview: {first_content[:300]}")
 
     st.session_state.streamed_summary = ""
 
     def ui_emit(chunk):
         st.session_state.streamed_summary += chunk
         summary_slot.markdown(st.session_state.streamed_summary)
 
     st.markdown(f"""
     <div class="report-section">
         <div class="report-title">{get_text("report_title")}</div>
     </div>
     """, unsafe_allow_html=True)
     summary_slot = st.empty()
 
with status_slot.container():
          with st.spinner(get_text("generating")):
              stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
              llm.callbacks = [stream_handler]
              _ = generate_summary(llm, query, st.session_state.scraped, search_mode)

<!-- 截图说明：图11-此处放置报告生成中的流式输出截图 -->

      now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
      st.session_state.report_timestamp = now

<!-- 截图说明：图12-此处放置最终生成的报告内容截图 -->
 
     # 标记搜索已完成
     st.session_state.search_completed = True
     st.session_state.status_slot = "complete"
     st.session_state.export_format_choice = "md"
 
     status_slot.success(get_text("complete"))
 
 
 # 显示搜索结果和下载区域（独立于run_button）
 if st.session_state.get("search_completed", False) and st.session_state.get("streamed_summary"):
     st.markdown("<br>", unsafe_allow_html=True)
 
     # 获取sidebar中选择的下载格式
     download_format = st.session_state.get('sidebar_download_format', 'md')
     format_labels_display = {"md": "Markdown", "pdf": "PDF", "docx": "Word", "xlsx": "Excel"}
 
st.info(f"下载格式: **{format_labels_display.get(download_format)}**")

<!-- 截图说明：图13-此处放置报告下载选项和下载按钮截图 -->

      # 直接生成并下载，不使用rerun
     if st.button(get_text("download"), use_container_width=True, key="download_btn"):
         from pathlib import Path
 
         try:
             filename = f"report_{st.session_state.report_timestamp}"
             if download_format == 'pdf':
                 from report_export import export_pdf
                 pdf_path = export_pdf(st.session_state.streamed_summary, st.session_state.refined, filename)
                 with open(pdf_path, 'rb') as f:
                     pdf_data = f.read()
                 st.download_button(
                     label=get_text("pdf_ready"),
                     data=pdf_data,
                     file_name=f"{filename}.pdf",
                     mime="application/pdf",
                     key="pdf_download_now"
                 )
                 try:
                     Path(pdf_path).unlink()
                 except:
                     pass
 
             elif download_format == 'docx':
                 from report_export import export_word
                 docx_path = export_word(st.session_state.streamed_summary, st.session_state.refined, filename)
                 with open(docx_path, 'rb') as f:
                     docx_data = f.read()
                 st.download_button(
                     label=get_text("word_ready"),
                     data=docx_data,
                     file_name=f"{filename}.docx",
                     mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                     key="docx_download_now"
                 )
                 try:
                     Path(docx_path).unlink()
                 except:
                     pass
 
             elif download_format == 'xlsx':
                 from report_export import export_excel
                 xlsx_path = export_excel(st.session_state.streamed_summary, st.session_state.refined, filename)
                 with open(xlsx_path, 'rb') as f:
                     xlsx_data = f.read()
                 st.download_button(
                     label="Excel已准备",
                     data=xlsx_data,
                     file_name=f"{filename}.xlsx",
                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     key="xlsx_download_now"
                 )
                 try:
                     Path(xlsx_path).unlink()
                 except:
                     pass
 
             else:  # markdown
                 st.download_button(
                     label=get_text("md_ready"),
                     data=st.session_state.streamed_summary,
                     file_name=f"{filename}.md",
                     mime="text/markdown",
                     key="md_download_now"
                 )
         except Exception as e:
             st.error(f"{get_text('error')}: {str(e)}")
 
     # 显示搜索结果实际内容
     if st.session_state.get("filtered") and len(st.session_state.get("filtered", [])) > 0:
         st.markdown("---")
 
         # 初始化分页状态
         if "result_page" not in st.session_state:
             st.session_state.result_page = 1
 
         all_results = st.session_state.filtered
         total_results = len(all_results)
 
         # 每页显示数量
         ITEMS_PER_PAGE = 40
         total_pages = (total_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
 
         # 标题和分页控件
         col1, col2 = st.columns([3, 1])
         with col1:
             st.markdown(f'<div class="report-title">📋 搜索结果详情 ({total_results}条)</div>', unsafe_allow_html=True)

<!-- 截图说明：图14-此处放置搜索结果详情列表截图 -->
<!-- 截图说明：图15-此处放置分页导航截图 -->
         with col2:
             # 分页导航
             page_cols = st.columns([1, 1, 1])
             with page_cols[0]:
                 if st.session_state.result_page > 1:
                     if st.button("◀ 上一页", key="prev_page"):
                         st.session_state.result_page -= 1
                         st.rerun()
             with page_cols[1]:
                 st.markdown(f"**{st.session_state.result_page}/{total_pages}**")
             with page_cols[2]:
                 if st.session_state.result_page < total_pages:
                     if st.button("下一页 ▶", key="next_page"):
                         st.session_state.result_page += 1
                         st.rerun()
 
         # 计算当前页显示范围
         start_idx = (st.session_state.result_page - 1) * ITEMS_PER_PAGE
         end_idx = min(start_idx + ITEMS_PER_PAGE, total_results)
         page_results = all_results[start_idx:end_idx]
 
         # 按来源分组显示当前页
         source_groups = {}
         for item in page_results:
             source = item.get("source", "Unknown")
             if source not in source_groups:
                 source_groups[source] = []
             source_groups[source].append(item)
 
         for source, items in source_groups.items():
             with st.expander(f"📌 {source} ({len(items)}条)", expanded=False):
                 for i, item in enumerate(items):
                     actual_idx = start_idx + i + 1
                     st.markdown(f"**{actual_idx}. {item.get('title', '无标题')[:150]}**")
                     if item.get('description'):
                         st.markdown(f"📝 {item.get('description', '')[:500]}...")
                     elif item.get('summary'):
                         st.markdown(f"📝 {item.get('summary', '')[:500]}...")
                     if item.get('link') or item.get('url'):
                         link = item.get('link') or item.get('url')
                         st.markdown(f"🔗 [查看原文]({link})")
                     st.markdown("---")


 import random
 import requests
 import threading
 from requests.adapters import HTTPAdapter
 from urllib3.util.retry import Retry
 from bs4 import BeautifulSoup
 from concurrent.futures import ThreadPoolExecutor, as_completed
 
 import warnings
 warnings.filterwarnings("ignore")
 
 # Define a list of rotating user agents.
 USER_AGENTS = [
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
     "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
 ]
 
 def get_tor_session():
     """
     Creates a requests Session with Tor SOCKS proxy and automatic retries.
     """
     session = requests.Session()
     retry = Retry(
         total=3,
         read=3,
         connect=3,
         backoff_factor=0.3,
         status_forcelist=[500, 502, 503, 504]
     )
     adapter = HTTPAdapter(max_retries=retry)
     session.mount("http://", adapter)
     session.mount("https://", adapter)
 
     session.proxies = {
         "http": "socks5h://127.0.0.1:9150",
         "https": "socks5h://127.0.0.1:9150"
     }
     return session
 
 def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
     """
     Scrapes a single URL using a robust Tor session.
     Returns a tuple (url, scraped_text).
     """
     url = url_data['link']
 
     # 跳过PDF和其他不支持的格式
     if url.lower().endswith('.pdf') or '.pdf?' in url.lower():
         return (url, f"{url_data['title']} - [PDF文件，请直接下载查看]")
 
     use_tor = ".onion" in url
 
     headers = {
         "User-Agent": random.choice(USER_AGENTS),
         "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
     }
 
     try:
         if use_tor:
             session = get_tor_session()
             response = session.get(url, headers=headers, timeout=45)
         else:
             response = requests.get(url, headers=headers, timeout=30)
 
         if response.status_code == 200:
             # 强制使用UTF-8解码，解决中文乱码问题
             response.encoding = 'utf-8'
 
             soup = BeautifulSoup(response.text, "html.parser")
             # Clean up text: remove scripts/styles
             for script in soup(["script", "style"]):
                 script.extract()
             text = soup.get_text(separator=' ', strip=True)
             # Normalize whitespace
             text = ' '.join(text.split())
 
             # 如果抓取内容太短（少于100字符），说明可能失败了，返回标题
             if len(text) < 100:
                 scraped_text = url_data['title']
             else:
                 scraped_text = f"{url_data['title']} - {text}"
         else:
             scraped_text = url_data['title']
     except Exception as e:
         # Return title only on failure, so we don't lose the reference
         scraped_text = url_data['title']
 
     return url, scraped_text
 
 def scrape_multiple(urls_data, max_workers=5):
     """
     Scrapes multiple URLs concurrently using a thread pool.
     """
     results = {}
     max_chars = 2000  # Increased limit slightly for better context
 
     with ThreadPoolExecutor(max_workers=max_workers) as executor:
         future_to_url = {
             executor.submit(scrape_single, url_data): url_data
             for url_data in urls_data
         }
         for future in as_completed(future_to_url):
             try:
                 url, content = future.result()
                 if len(content) > max_chars:
                     content = content[:max_chars] + "...(truncated)"
                 results[url] = content
             except Exception:
                 continue
 
     return results


 """
 Report Export Module
 ===================
 Export intelligence reports to various formats (Markdown, PDF, Word).
 Supports Chinese and English with professional formatting.
 """
 
 import os
 from datetime import datetime
 from typing import Dict, List, Optional
 import re
 
 try:
     from reportlab.lib.pagesizes import letter, A4
     from reportlab.lib import colors
     from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
     from reportlab.lib.units import inch
     from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
     from reportlab.pdfgen import canvas
     from reportlab.pdfbase import pdfmetrics
     from reportlab.pdfbase.ttfonts import TTFont
     REPORTLAB_AVAILABLE = True
 except ImportError:
     REPORTLAB_AVAILABLE = False
 
 try:
     from fpdf import FPDF
 
     class PDFReport(FPDF):
         def __init__(self, is_chinese=False):
             super().__init__()
             self.is_chinese = is_chinese
             self.set_auto_page_break(auto=True, margin=15)
 
         def header(self):
             self.set_font('Helvetica', 'B', 18)
             self.cell(0, 15, 'IntelNexus Intelligence Report', 0, 1, 'C')
             self.set_draw_color(100, 100, 100)
             self.line(15, 20, 195, 20)
             self.ln(8)
 
         def footer(self):
             self.set_y(-15)
             self.set_font('Helvetica', 'I', 9)
             self.cell(0, 10, f'Page {self.page_no()}  |  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
 
     FPDF_AVAILABLE = True
 except ImportError:
     FPDF_AVAILABLE = False
     PDFReport = None
 
 FPDF2_AVAILABLE = False
 try:
     from fpdf import FPDF
 
     class FPDF2_CHINESE(FPDF):
         def footer(self):
             self.set_y(-15)
             self.set_font("Helvetica", style="I", size=9)
             self.cell(0, 10, f'Page {self.page_no()}  |  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
 
     FPDF2_AVAILABLE = True
 except ImportError:
     pass
 
 
 
 
 try:
     from docx import Document
     from docx.shared import Inches, Pt, RGBColor
     from docx.enum.text import WD_ALIGN_PARAGRAPH
 except ImportError:
     Document = None
 
 try:
     from openpyxl import Workbook
     from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
     from openpyxl.utils import get_column_letter
     OPENPYXL_AVAILABLE = True
 except ImportError:
     Workbook = None
     OPENPYXL_AVAILABLE = False
 
 
 def _format_content_for_pdf(content: str) -> str:
     """Format content for better PDF rendering."""
     # 移除markdown的某些格式符号，使其在PDF中更清晰
     lines = content.split('\n')
     formatted_lines = []
 
     for line in lines:
         # 转换markdown标题
         if line.startswith('# '):
             formatted_lines.append('\n' + line.replace('# ', '■ ').upper())
         elif line.startswith('## '):
             formatted_lines.append('\n▸ ' + line.replace('## ', '').strip())
         else:
             formatted_lines.append(line)
 
     return '\n'.join(formatted_lines)
 
 
 def export_markdown(content: str, query: str, output_path: str) -> str:
     """Export to Markdown format with enhanced structure."""
     # 清理内容，移除所有特殊字符
     content = _clean_content(content)
 
     with open(output_path, 'w', encoding='utf-8') as f:
         f.write("# IntelNexus 智能情报报告\n\n")
         f.write(f"## 报告信息\n\n")
         f.write(f"- **查询内容**: {query}\n")
         f.write(f"- **生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n")
         f.write(f"- **报告类型**: 多源网络情报分析\n\n")
         f.write("---\n\n")
         f.write("## 分析结果\n\n")
         f.write(content)
         f.write("\n\n---\n\n")
         f.write(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
         f.write("*© 2026 IntelNexus Platform - 多源网络情报分析平台*\n")
     return output_path
 
 
 def _clean_markdown_for_word(text: str) -> str:
     """清理Markdown标记符号用于Word导出。"""
     # 移除markdown标题标记
     text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
     # 处理粗体：**text** -> text
     text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
     text = re.sub(r'__(.+?)__', r'\1', text)
     # 处理斜体
     text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
     text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', text)
     # 处理代码块
     text = re.sub(r'`([^`]+)`', r'\1', text)
     text = re.sub(r'```[\s\S]*?```', '', text)
     # 处理链接
     text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1 (\2)', text)
     return text
 
 
 def _clean_content(content: str) -> str:
     """清理内容特殊字符，用于所有导出格式。"""
     if not content:
         return content
 
     # 逐个替换特殊字符
     chars_to_remove = [
         '■', '□', '▢', '▣', '▤', '▥', '▦', '▧', '▨', '▩', '▪', '▫', '▬', '▭', '▮', '▯',
         '▰', '▱', '△', '▽', '▷', '◁', '◆', '◇', '○', '●', '◐', '◑', '◒', '◓', '◔', '◕',
         '◖', '◗', '★', '☆', '☉', '♠', '♣', '♥', '♦', '♩', '♪', '♫', '⚐', '⚑', '⚡',
         '⚪', '⚫', '⚬', '✓', '✗', '✘', '✔', '✖', '✚', '✽', '✿', '❀', '❖', '❤',
     ]
     for char in chars_to_remove:
         content = content.replace(char, '')
 
     # 移除emoji范围
     try:
         emoji_pattern = re.compile("["
             u"\U0001F600-\U0001F64F"
             u"\U0001F300-\U0001F5FF"
             u"\U0001F680-\U0001F6FF"
             u"\U0001F1E0-\U0001F1FF"
             "]+", flags=re.UNICODE)
         content = emoji_pattern.sub('', content)
     except:
         pass
 
     return content
 
 
 def export_pdf(content: str, query: str, output_path: str) -> str:
     """Export to PDF format with Chinese support using fpdf2."""
     if not FPDF2_AVAILABLE:
         raise ImportError("fpdf2 is not installed. Install with: pip install fpdf2")
 
     try:
         clean_query = query[:100] if query else "[No query content]"
     except:
         clean_query = "[Query processing error]"
 
     output_dir = os.path.dirname(output_path)
     if output_dir and not os.path.exists(output_dir):
         os.makedirs(output_dir)
 
     if not output_path.endswith('.pdf'):
         output_path += '.pdf'
 
     pdf = FPDF2_CHINESE(format='A4')
     pdf.add_page()
     pdf.set_auto_page_break(True, 15)
 
     font_paths = [
         "C:/Windows/Fonts/simhei.ttf",
         "C:/Windows/Fonts/simkai.ttf",
         "C:/Windows/Fonts/simfang.ttf",
     ]
 
     font_name = "helvetica"
     for font_path in font_paths:
         if os.path.exists(font_path):
             try:
                 pdf.add_font("Chinese", "", font_path, uni=True)
                 pdf.add_font("Chinese", "B", font_path, uni=True)
                 pdf.add_font("Chinese", "I", font_path, uni=True)
                 font_name = "Chinese"
                 break
             except Exception as e:
                 print(f"Font loading error: {e}")
                 continue
 
     import warnings
     warnings.filterwarnings("ignore", category=DeprecationWarning)
 
     pdf.set_font(font_name, style="B", size=16)
     pdf.set_text_color(31, 71, 136)
     pdf.cell(0, 15, "IntelNexus Intelligence Report", 0, 1, "C")
 
     pdf.set_draw_color(200, 200, 200)
     pdf.line(15, 25, 195, 25)
     pdf.ln(5)
 
     pdf.set_font(font_name, style="B", size=12)
     pdf.set_text_color(50, 50, 50)
     pdf.cell(0, 8, "Report Information", ln=True)
     pdf.set_font(font_name, size=11)
 
     pdf.cell(40, 6, "Query: ", ln=False)
     pdf.multi_cell(0, 6, clean_query if clean_query else "[No query]")
 
     pdf.cell(40, 6, "Generated: ", ln=False)
     pdf.cell(0, 6, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ln=True)
 
     pdf.cell(40, 6, "Platform: ", ln=False)
     pdf.cell(0, 6, "IntelNexus v1.0", ln=True)
 
     pdf.cell(40, 6, "Type: ", ln=False)
     pdf.cell(0, 6, "Multi-Source Network Intelligence Analysis", ln=True)
 
     pdf.ln(5)
     pdf.set_draw_color(200, 200, 200)
     pdf.line(10, pdf.get_y(), 200, pdf.get_y())
     pdf.ln(5)
 
     pdf.set_font(font_name, style="B", size=12)
     pdf.set_text_color(31, 71, 136)
     pdf.cell(0, 8, "Analysis Results", ln=True)
     pdf.set_font(font_name, size=10)
     pdf.set_text_color(50, 50, 50)
 
     max_length = 15000
     if len(content) > max_length:
         display_content = content[:max_length] + "\n\n[Content too long. Please check the full Markdown or Word report.]"
     else:
         display_content = content
 
     display_content = _clean_content(display_content)
     display_content = _clean_markdown_for_word(display_content)
 
     lines = display_content.split('\n')
     for line in lines:
         line = line.strip()
         if not line:
             pdf.ln(2)
             continue
 
         if line.startswith('# '):
             pdf.ln(2)
             pdf.set_font(font_name, style="B", size=13)
             pdf.set_text_color(31, 71, 136)
             pdf.cell(0, 8, line.replace('# ', '').strip(), ln=True)
             pdf.set_font(font_name, size=10)
             pdf.set_text_color(50, 50, 50)
         elif line.startswith('## '):
             pdf.ln(1)
             pdf.set_font(font_name, style="B", size=12)
             pdf.set_text_color(31, 71, 136)
             pdf.cell(0, 7, line.replace('## ', '').strip(), ln=True)
             pdf.set_font(font_name, size=10)
             pdf.set_text_color(50, 50, 50)
         elif line.startswith('### '):
             pdf.set_font(font_name, style="B", size=11)
             pdf.set_text_color(46, 90, 136)
             pdf.cell(0, 6, line.replace('### ', '').strip(), ln=True)
             pdf.set_font(font_name, size=10)
             pdf.set_text_color(50, 50, 50)
         else:
             if pdf.get_y() > 250:
                 pdf.add_page()
                 pdf.set_font(font_name, size=10)
                 pdf.set_text_color(50, 50, 50)
 
             pdf.cell(0, 6, line, ln=True)
 
     pdf.ln(10)
     pdf.set_draw_color(200, 200, 200)
     pdf.line(10, pdf.get_y(), 200, pdf.get_y())
     pdf.ln(2)
     pdf.set_font(font_name, style="I", size=8)
     pdf.set_text_color(128, 128, 128)
     pdf.cell(0, 5, f"© 2026 IntelNexus Platform | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 0, "C")
 
     pdf.output(output_path)
     return output_path
 
 
 
 def _get_chinese_font():
     """获取系统中可用的中文字体"""
     chinese_fonts = ['微软雅黑', 'SimHei', '黑体', 'Arial', 'Calibri']
     available_fonts = []
     try:
         from docx.enum.style import WD_STYLE_TYPE
         from docx.styles.styles import Styles
     except:
         pass
     return chinese_fonts[0]
 
 
 def _add_paragraph_with_formatting(doc, text: str, style: str = None):
     """Add a paragraph to document with markdown formatting support.
 
     Converts **text** to bold, *text* to italic, `code` to code formatting.
     """
     if not text.strip():
         return
 
     font_name = _get_chinese_font()
 
     para = doc.add_paragraph(style=style)
 
     bold_pattern = r'\*\*(.+?)\*\*'
     italic_pattern = r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)'
     code_pattern = r'`([^`]+)`'
 
     combined = f'({bold_pattern}|{italic_pattern}|{code_pattern})'
 
     last_end = 0
     for match in re.finditer(combined, text):
         if match.start() > last_end:
             run = para.add_run(text[last_end:match.start()])
             run.font.name = font_name
             run.font.size = Pt(11)
 
         if match.group(2):
             run = para.add_run(match.group(2))
             run.font.bold = True
             run.font.name = font_name
             run.font.size = Pt(11)
         elif match.group(3):
             run = para.add_run(match.group(3))
             run.font.italic = True
             run.font.name = font_name
             run.font.size = Pt(11)
         elif match.group(4):
             run = para.add_run(match.group(4))
             run.font.name = 'Courier New'
             run.font.size = Pt(10)
             run.font.color.rgb = RGBColor(128, 0, 0)
 
         last_end = match.end()
 
     if last_end < len(text):
         run = para.add_run(text[last_end:])
         run.font.name = font_name
         run.font.size = Pt(11)
 
 
 def export_word(content: str, query: str, output_path: str) -> str:
     """Export to Word format with markdown formatting rendering."""
     if Document is None:
         raise ImportError("python-docx is not installed. Install with: pip install python-docx")
 
     font_name = _get_chinese_font()
 
     doc = Document()
 
     style = doc.styles['Normal']
     style.font.name = font_name
     style.font.size = Pt(11)
 
     # 标题
     title = doc.add_heading('IntelNexus 智能情报分析报告', 0)
     title_format = title.paragraph_format
     title_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
 
     # 报告信息
     info_heading = doc.add_heading('报告信息', level=1)
 
     info_table = doc.add_table(rows=4, cols=2)
     info_table.style = 'Light Grid Accent 1'
 
     info_data = [
         ('查询内容', query if query else '[No query]'),
         ('生成时间', datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')),
         ('平台版本', 'IntelNexus v1.0'),
         ('报告类型', '多源网络情报分析')
     ]
 
     for i, (key, value) in enumerate(info_data):
         cells = info_table.rows[i].cells
         cells[0].text = key
         cells[1].text = str(value)
         # 设置格式
         for paragraph in cells[0].paragraphs:
             for run in paragraph.runs:
                 run.font.bold = True
 
     doc.add_paragraph()  # 空行
 
     # 分析结果
     result_heading = doc.add_heading('分析结果', level=1)
 
     # 清理内容，移除所有特殊字符
     content = _clean_content(content)
 
     # 处理markdown格式的内容 - 正确渲染markdown格式
     lines = content.split('\n')
     for line in lines:
         if not line.strip():
             doc.add_paragraph()
             continue
 
         # 处理标题
         if line.startswith('# '):
             title_text = line.replace('# ', '').strip()
             heading = doc.add_heading(title_text, level=1)
         elif line.startswith('## '):
             title_text = line.replace('## ', '').strip()
             heading = doc.add_heading(title_text, level=2)
         elif line.startswith('### '):
             title_text = line.replace('### ', '').strip()
             heading = doc.add_heading(title_text, level=3)
         # 处理列表
         elif re.match(r'^\d+\.\s', line):
             list_text = re.sub(r'^\d+\.\s', '', line).strip()
             _add_paragraph_with_formatting(doc, list_text, 'List Number')
         elif line.startswith('- '):
             list_text = line[2:].strip()
             _add_paragraph_with_formatting(doc, list_text, 'List Bullet')
         elif line.startswith('* '):
             list_text = line[2:].strip()
             _add_paragraph_with_formatting(doc, list_text, 'List Bullet')
         else:
             # 清理可能的markdown标题标记（处理行内或意外的情况）
             cleaned_line = _clean_markdown_for_word(line.strip())
             if cleaned_line.strip():
                 _add_paragraph_with_formatting(doc, cleaned_line)
 
     # 添加页脚
     doc.add_paragraph()
     footer_para = doc.add_paragraph()
     footer_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
     footer_run = footer_para.add_run(f"© 2026 IntelNexus Platform | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
     footer_run.italic = True
     footer_run.font.size = Pt(9)
     footer_run.font.color.rgb = RGBColor(128, 128, 128)
 
     # 确保输出目录存在
     output_dir = os.path.dirname(output_path)
     if output_dir and not os.path.exists(output_dir):
         os.makedirs(output_dir)
 
     doc.save(output_path)
     return output_path
 
 
 
 def export_report(content: str, query: str, output_path: str, format: str = 'md') -> str:
     """Export report to specified format."""
     if not output_path:
         timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
         output_path = f"report_{timestamp}"
 
     if format == 'pdf':
         if not output_path.endswith('.pdf'):
             output_path += '.pdf'
         return export_pdf(content, query, output_path)
     elif format == 'docx':
         if not output_path.endswith('.docx'):
             output_path += '.docx'
         return export_word(content, query, output_path)
     else:
         if not output_path.endswith('.md'):
             output_path += '.md'
         return export_markdown(content, query, output_path)
 
 
 def get_export_formats() -> List[str]:
     """Get list of available export formats."""
     formats = ['md']
     if FPDF2_AVAILABLE:
         formats.append('pdf')
     if Document:
         formats.append('docx')
     if OPENPYXL_AVAILABLE:
         formats.append('xlsx')
     return formats
 
 
 def export_excel(content: str, query: str, output_path: str) -> str:
     """Export to Excel format with proper formatting."""
     if Workbook is None:
         raise ImportError("openpyxl is not installed. Install with: pip install openpyxl")
 
     wb = Workbook()
     ws = wb.active
     ws.title = "情报报告"
 
     # 定义样式
     header_font = Font(name='微软雅黑', size=16, bold=True, color='FFFFFF')
     header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
     header_alignment = Alignment(horizontal='center', vertical='center')
 
     title_font = Font(name='微软雅黑', size=12, bold=True)
     title_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
 
     normal_font = Font(name='微软雅黑', size=11)
     wrap_alignment = Alignment(wrap_text=True, vertical='top')
 
     thin_border = Border(
         left=Side(style='thin'),
         right=Side(style='thin'),
         top=Side(style='thin'),
         bottom=Side(style='thin')
     )
 
     # 标题行
     ws.merge_cells('A1:B1')
     ws['A1'] = 'IntelNexus 智能情报分析报告'
     ws['A1'].font = header_font
     ws['A1'].fill = header_fill
     ws['A1'].alignment = header_alignment
     ws.row_dimensions[1].height = 30
 
     # 报告信息
     ws['A3'] = '查询内容'
     ws['B3'] = query if query else '[无查询内容]'
     ws['A4'] = '生成时间'
     ws['B4'] = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
     ws['A5'] = '平台版本'
     ws['B5'] = 'IntelNexus v1.0'
     ws['A6'] = '报告类型'
     ws['B6'] = '多源网络情报分析'
 
     for row in range(3, 7):
         ws[f'A{row}'].font = title_font
         ws[f'A{row}'].fill = title_fill
         ws[f'A{row}'].border = thin_border
         ws[f'B{row}'].border = thin_border
         ws[f'B{row}'].alignment = wrap_alignment
 
     # 分析结果标题
     ws['A8'] = '分析结果'
     ws['A8'].font = title_font
     ws['A8'].fill = title_fill
     ws.merge_cells('A8:B8')
     ws['A8'].alignment = Alignment(horizontal='center', vertical='center')
     ws['A8'].border = thin_border
     ws['B8'].border = thin_border
     ws.row_dimensions[8].height = 25
 
     # 解析内容并添加到 Excel
     start_row = 9
     current_row = start_row
 
     # 清理内容中的markdown标题标记
     clean_content = _clean_markdown_for_word(content)
 
     # 按段落添加内容
     paragraphs = clean_content.split('\n\n')
     for para in paragraphs:
         para = para.strip()
         if not para:
             continue
 
         # 检查是否是标题
         is_title = False
         if para.startswith('■ ') or para.startswith('▸ '):
             is_title = True
             para = para[2:].strip() if para.startswith('■ ') else para[2:].strip()
 
         ws[f'A{current_row}'] = para
         ws.merge_cells(f'A{current_row}:B{current_row}')
 
         if is_title:
             ws[f'A{current_row}'].font = Font(name='微软雅黑', size=11, bold=True, color='1F4E79')
         else:
             ws[f'A{current_row}'].font = normal_font
 
         ws[f'A{current_row}'].alignment = wrap_alignment
         ws[f'A{current_row}'].border = thin_border
         ws.row_dimensions[current_row].height = max(20, len(para) // 40 * 15 + 20)
 
         current_row += 1
 
     # 设置列宽
     ws.column_dimensions['A'].width = 30
     ws.column_dimensions['B'].width = 70
 
     # 添加页脚
     footer_row = current_row + 2
     ws.merge_cells(f'A{footer_row}:B{footer_row}')
     ws[f'A{footer_row}'] = f"© 2026 IntelNexus Platform | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
     ws[f'A{footer_row}'].font = Font(name='微软雅黑', size=9, italic=True, color='808080')
     ws[f'A{footer_row}'].alignment = Alignment(horizontal='center')
 
     # 确保输出目录存在
     output_dir = os.path.dirname(output_path)
     if output_dir and not os.path.exists(output_dir):
         os.makedirs(output_dir)
 
     if not output_path.endswith('.xlsx'):
         output_path += '.xlsx'
 
     wb.save(output_path)
     return output_path


 """
 Custom Models Management Module
 ==============================
 Allow users to add and manage custom LLM models.
 """
 
 import json
 import os
 from typing import Dict, List, Optional
 from pathlib import Path
 
 
 CUSTOM_MODELS_FILE = "data/custom_models.json"
 
 
 def _ensure_custom_models_file():
     """Ensure the custom models file exists."""
     Path("data").mkdir(exist_ok=True)
     if not os.path.exists(CUSTOM_MODELS_FILE):
         with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
             json.dump({"models": []}, f, ensure_ascii=False, indent=2)
 
 
 def get_custom_models() -> List[Dict[str, str]]:
     """Get all custom models."""
     _ensure_custom_models_file()
     try:
         with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
             data = json.load(f)
             return data.get("models", [])
     except Exception as e:
         print(f"Error reading custom models: {e}")
         return []
 
 
 def add_custom_model(name: str, model_type: str, config: Dict) -> bool:
     """
     Add a new custom model.
 
     Args:
         name: Model name (e.g., "my-gpt-4")
         model_type: Type of model (e.g., "openai", "ollama", "anthropic")
         config: Model configuration (API key, base URL, etc.)
 
     Returns:
         True if successful, False otherwise
     """
     if not name or not model_type:
         return False
 
     _ensure_custom_models_file()
 
     try:
         with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
             data = json.load(f)
 
         # Check if model already exists
         existing_names = [m["name"] for m in data.get("models", [])]
         if name in existing_names:
             return False
 
         # Add new model
         new_model = {
             "name": name,
             "type": model_type,
             "config": config
         }
         data.get("models", []).append(new_model)
 
         with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
             json.dump(data, f, ensure_ascii=False, indent=2)
 
         return True
     except Exception as e:
         print(f"Error adding custom model: {e}")
         return False
 
 
 def remove_custom_model(name: str) -> bool:
     """Remove a custom model by name."""
     _ensure_custom_models_file()
 
     try:
         with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
             data = json.load(f)
 
         original_count = len(data.get("models", []))
         data["models"] = [m for m in data.get("models", []) if m["name"] != name]
 
         if len(data["models"]) < original_count:
             with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
                 json.dump(data, f, ensure_ascii=False, indent=2)
             return True
         return False
     except Exception as e:
         print(f"Error removing custom model: {e}")
         return False
 
 
 def get_custom_model_names() -> List[str]:
     """Get a list of custom model names."""
     return [m["name"] for m in get_custom_models()]
 
 
 def get_model_config(name: str) -> Optional[Dict]:
     """Get the configuration for a custom model."""
     for model in get_custom_models():
         if model["name"] == name:
             return {
                 "type": model.get("type"),
                 "config": model.get("config", {})
             }
     return None


 """
 Search History Module
 ====================
 Manage search history and saved reports.
 """
 
 import os
 import json
 from datetime import datetime
 from typing import List, Dict, Optional
 from pathlib import Path
 
 
 class SearchHistory:
     def __init__(self, storage_dir: str = "data"):
         self.storage_dir = Path(storage_dir)
         self.history_file = self.storage_dir / "search_history.json"
         self.reports_dir = self.storage_dir / "reports"
         self._ensure_dirs()
 
     def _ensure_dirs(self):
         self.storage_dir.mkdir(exist_ok=True)
         self.reports_dir.mkdir(exist_ok=True)
 
     def add_search(self, query: str, mode: str, results_count: int, model: str) -> Dict:
         """Add a new search to history."""
         entry = {
             "id": self._generate_id(),
             "query": query,
             "mode": mode,
             "results_count": results_count,
             "model": model,
             "timestamp": datetime.now().isoformat(),
             "status": "completed"
         }
 
         history = self.get_history()
         history.insert(0, entry)
 
         if len(history) > 100:
             history = history[:100]
 
         self._save_history(history)
         return entry
 
     def get_history(self, limit: int = 20) -> List[Dict]:
         """Get search history."""
         if not self.history_file.exists():
             return []
 
         try:
             with open(self.history_file, 'r', encoding='utf-8') as f:
                 return json.load(f)[:limit]
         except:
             return []
 
     def save_report(self, query: str, content: str, mode: str) -> str:
         """Save a report to file."""
         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
         safe_query = "".join(c for c in query if c.isalnum() or c in " -_")[:30]
         filename = f"{safe_query}_{timestamp}.md"
         filepath = self.reports_dir / filename
 
         with open(filepath, 'w', encoding='utf-8') as f:
             f.write(f"# Intelligence Report\n\n")
             f.write(f"**Query**: {query}\n")
             f.write(f"**Mode**: {mode}\n")
             f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
             f.write("---\n\n")
             f.write(content)
 
         return str(filepath)
 
     def get_reports(self) -> List[Dict]:
         """Get list of saved reports."""
         reports = []
         if not self.reports_dir.exists():
             return reports
 
         for f in sorted(self.reports_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
             stats = f.stat()
             reports.append({
                 "name": f.name,
                 "path": str(f),
                 "size": stats.st_size,
                 "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
             })
 
         return reports
 
     def load_report(self, filename: str) -> Optional[str]:
         """Load a saved report."""
         filepath = self.reports_dir / filename
         if not filepath.exists():
             return None
 
         try:
             with open(filepath, 'r', encoding='utf-8') as f:
                 return f.read()
         except:
             return None
 
     def delete_report(self, filename: str) -> bool:
         """Delete a saved report."""
         filepath = self.reports_dir / filename
         if filepath.exists():
             filepath.unlink()
             return True
         return False
 
     def clear_history(self):
         """Clear search history."""
         self._save_history([])
 
     def _generate_id(self) -> str:
         return datetime.now().strftime("%Y%m%d%H%M%S%f")
 
     def _save_history(self, history: List[Dict]):
         with open(self.history_file, 'w', encoding='utf-8') as f:
             json.dump(history, f, ensure_ascii=False, indent=2)
 
 
 _history_instance = None
 
 def get_history_manager() -> SearchHistory:
     """Get global history manager instance."""
     global _history_instance
     if _history_instance is None:
         _history_instance = SearchHistory()
     return _history_instance

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


 """
 IntelNexus GUI
 =============
 CustomTkinter-based GUI for IntelNexus.
 """
 
 import os
 import sys
 import threading
 from datetime import datetime
 
 import customtkinter as ctk
 from tkinter import filedialog
 
 from llm import get_llm, refine_query, generate_summary
 from llm_utils import get_model_choices
 from web_search import get_web_results
 from news_search import get_news_results
 from darkweb_search import get_darkweb_results, is_available as darkweb_available
 from scrape import scrape_multiple
 from report_export import export_markdown
 
 
 ctk.set_appearance_mode("light")
 ctk.set_default_color_theme("blue")
 
 SEARCH_MODES = {
     "web": "网页搜索",
     "news": "新闻资讯",
     "darkweb": "暗网搜索",
     "all": "全部来源"
 }
 
 
 class IntelNexusGUI(ctk.CTk):
     def __init__(self):
         super().__init__()
 
         self.title("IntelNexus - 多源网络情报分析平台")
         self.geometry("1200x800")
 
         self.search_thread = None
         self.stop_search = False
 
         self.setup_ui()
 
     def setup_ui(self):
         self.grid_columnconfigure(1, weight=1)
         self.grid_rowconfigure(0, weight=1)
 
         self.create_sidebar()
         self.create_main_area()
 
     def create_sidebar(self):
         self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
         self.sidebar.grid(row=0, column=0, sticky="nsew")
         self.sidebar.grid_rowconfigure(20, weight=1)
 
         title_label = ctk.CTkLabel(
             self.sidebar,
             text="IntelNexus",
             font=ctk.CTkFont(size=24, weight="bold")
         )
         title_label.grid(row=0, column=0, padx=20, pady=(20, 10))
 
         subtitle = ctk.CTkLabel(
             self.sidebar,
             text="多源网络情报分析平台",
             font=ctk.CTkFont(size=12)
         )
         subtitle.grid(row=1, column=0, padx=20, pady=(0, 20))
 
         mode_label = ctk.CTkLabel(self.sidebar, text="搜索模式", font=ctk.CTkFont(size=14, weight="bold"))
         mode_label.grid(row=2, column=0, padx=20, pady=(10, 5))
 
         self.mode_var = ctk.StringVar(value="all")
         for i, (mode, label) in enumerate(SEARCH_MODES.items()):
             radio = ctk.CTkRadioButton(
                 self.sidebar,
                 text=label,
                 variable=self.mode_var,
                 value=mode
             )
             radio.grid(row=3 + i, column=0, padx=20, pady=5, sticky="w")
 
         model_label = ctk.CTkLabel(self.sidebar, text="AI模型", font=ctk.CTkFont(size=14, weight="bold"))
         model_label.grid(row=8, column=0, padx=20, pady=(20, 5))
 
         model_choices = get_model_choices()
         self.model_var = ctk.StringVar(value=model_choices[0] if model_choices else "qwen2.5:7b")
         self.model_combo = ctk.CTkComboBox(
             self.sidebar,
             values=model_choices,
             variable=self.model_var,
             state="readonly"
         )
         self.model_combo.grid(row=9, column=0, padx=20, pady=5, sticky="ew")
 
         threads_label = ctk.CTkLabel(self.sidebar, text="线程数", font=ctk.CTkFont(size=14, weight="bold"))
         threads_label.grid(row=10, column=0, padx=20, pady=(20, 5))
 
         self.threads_slider = ctk.CTkSlider(
             self.sidebar,
             from_=1,
             to=16,
             number_of_steps=15,
             command=self.update_threads_label
         )
         self.threads_slider.set(5)
         self.threads_slider.grid(row=11, column=0, padx=20, pady=5, sticky="ew")
 
         self.threads_label = ctk.CTkLabel(self.sidebar, text="5")
         self.threads_label.grid(row=12, column=0, padx=20, pady=(0, 10))
 
         about_label = ctk.CTkLabel(
             self.sidebar,
             text="© 2024 IntelNexus\nAI驱动的网络情报平台",
             font=ctk.CTkFont(size=10),
             text_color="gray"
         )
         about_label.grid(row=21, column=0, padx=20, pady=10)
 
     def update_threads_label(self, value):
         self.threads_label.configure(text=str(int(value)))
 
     def create_main_area(self):
         self.main_frame = ctk.CTkFrame(self, corner_radius=0)
         self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
 
         self.main_frame.grid_columnconfigure(0, weight=1)
         self.main_frame.grid_rowconfigure(2, weight=1)
 
         header = ctk.CTkLabel(
             self.main_frame,
             text="搜索查询",
             font=ctk.CTkFont(size=18, weight="bold")
         )
         header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
 
         input_frame = ctk.CTkFrame(self.main_frame)
         input_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
         input_frame.grid_columnconfigure(0, weight=1)
 
         self.query_entry = ctk.CTkEntry(
             input_frame,
             placeholder_text="输入搜索内容...",
             height=40,
             font=ctk.CTkFont(size=14)
         )
         self.query_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
 
         self.query_entry.bind("<Return>", lambda e: self.start_search())
 
         self.search_btn = ctk.CTkButton(
             input_frame,
             text="开始搜索",
             height=40,
             font=ctk.CTkFont(size=14, weight="bold"),
             command=self.start_search
         )
         self.search_btn.grid(row=0, column=1)
 
         self.status_label = ctk.CTkLabel(
             self.main_frame,
             text="就绪",
             font=ctk.CTkFont(size=12),
             text_color="gray"
         )
         self.status_label.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")
 
         self.progress_bar = ctk.CTkProgressBar(self.main_frame)
         self.progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
         self.progress_bar.set(0)
 
         result_label = ctk.CTkLabel(
             self.main_frame,
             text="分析报告",
             font=ctk.CTkFont(size=18, weight="bold")
         )
         result_label.grid(row=4, column=0, padx=20, pady=(20, 10), sticky="w")
 
         self.result_text = ctk.CTkTextbox(self.main_frame, font=ctk.CTkFont(size=12))
         self.result_text.grid(row=5, column=0, sticky="nsew", padx=20, pady=10)
 
         btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
         btn_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=10)
 
         self.save_btn = ctk.CTkButton(
             btn_frame,
             text="保存报告",
             command=self.save_report,
             state="disabled"
         )
         self.save_btn.pack(side="right")
 
     def start_search(self):
         query = self.query_entry.get().strip()
         if not query:
             return
 
         self.search_btn.configure(state="disabled", text="搜索中...")
         self.save_btn.configure(state="disabled")
         self.result_text.delete("1.0", "end")
         self.stop_search = False
 
         self.search_thread = threading.Thread(target=self.run_search, args=(query,))
         self.search_thread.start()
 
     def run_search(self, query):
         try:
             self.update_status("初始化LLM...", 0.05)
             model = self.model_var.get()
             threads = int(self.threads_slider.get())
             mode = self.mode_var.get()
 
             llm = get_llm(model)
 
             self.update_status("优化查询...", 0.1)
             query_variants = refine_query(llm, query)
             search_query = " | ".join(query_variants) if isinstance(query_variants, list) else query_variants
 
             self.update_status(f"搜索{SEARCH_MODES.get(mode, mode)}...", 0.2)
             results = []
 
             with threading.ThreadPoolExecutor(max_workers=threads) as executor:
                 futures = []
 
                 if mode in ["web", "all"]:
                     futures.append(executor.submit(get_web_results, search_query, threads, 20))
 
                 if mode in ["news", "all"]:
                     futures.append(executor.submit(get_news_results, search_query, 15))
 
                 if mode in ["darkweb", "all"] and darkweb_available():
                     futures.append(executor.submit(get_darkweb_results, search_query, threads))
 
                 for f in futures:
                     try:
                         r = f.result()
                         if r:
                             results.extend(r)
                     except Exception as e:
                         print(f"Search error: {e}")
 
             self.update_status(f"找到 {len(results)} 条结果", 0.4)
 
             if not results:
                 self.update_status("未找到结果", 0)
                 self.search_complete()
                 return
 
             self.update_status("抓取内容...", 0.6)
             scraped = scrape_multiple(results, max_workers=threads)
 
             self.update_status("生成报告...", 0.8)
             stream_handler = GUIStreamHandler(self.result_text)
             llm.callbacks = [stream_handler]
 
             summary = generate_summary(llm, query, scraped)
 
             self.update_status("完成", 1.0)
             self.search_complete()
 
         except Exception as e:
             self.update_status(f"错误: {str(e)}", 0)
             self.search_complete()
 
     def update_status(self, text, progress):
         self.after(0, lambda: self.status_label.configure(text=text))
         self.after(0, lambda: self.progress_bar.set(progress))
 
     def search_complete(self):
         self.after(0, lambda: self.search_btn.configure(state="normal", text="开始搜索"))
         self.after(0, lambda: self.save_btn.configure(state="normal"))
 
     def save_report(self):
         content = self.result_text.get("1.0", "end").strip()
         if not content:
             return
 
         timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
         filename = f"report_{timestamp}.md"
 
         filepath = filedialog.asksaveasfilename(
             defaultextension=".md",
             filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
             initialfile=filename
         )
 
         if filepath:
             try:
                 with open(filepath, "w", encoding="utf-8") as f:
                     f.write(content)
                 self.status_label.configure(text=f"已保存: {filepath}")
             except Exception as e:
                 self.status_label.configure(text=f"保存失败: {str(e)}")
 
 
 class GUIStreamHandler:
     def __init__(self, text_widget):
         self.text_widget = text_widget
 
     def on_llm_new_token(self, token, **kwargs):
         self.text_widget.insert("end", token)
         self.text_widget.see("end")
 
 
 def run_gui():
     app = IntelNexusGUI()
     app.mainloop()
 
 
 if __name__ == "__main__":
     run_gui()


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


 import subprocess
 import sys
 import os
 
 if __name__ == "__main__":
     ui_path = os.path.join(os.getcwd(), "ui.py")
     subprocess.run([sys.executable, "-m", "streamlit", "run", ui_path, "--server.port=8501", "--server.headless=true"])


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


 import os
 import sys
 import logging
 
 logging.basicConfig(level=logging.DEBUG, filename='streamlit_debug.log', filemode='w')
 
 def main():
     logging.info("=" * 50)
     logging.info("IntelNexus Starting")
     logging.info(f"Frozen: {getattr(sys, 'frozen', False)}")
     logging.info(f"sys.executable: {sys.executable}")
     logging.info(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
     logging.info(f"sys.argv: {sys.argv}")
     logging.info("=" * 50)
 
     ui_path = os.path.join(sys._MEIPASS, 'ui.py') if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.py")
 
     logging.info(f"UI path: {ui_path}")
     logging.info(f"UI exists: {os.path.exists(ui_path)}")
 
     if getattr(sys, 'frozen', False):
         sys.path.insert(0, sys._MEIPASS)
         logging.info(f"Added to sys.path: {sys._MEIPASS}")
 
     logging.info("Importing streamlit...")
     try:
         from streamlit.web import cli as stcli
         logging.info("Streamlit imported successfully")
 
         sys.argv = [
             "streamlit", "run", ui_path,
             "--server.port=8501",
             "--server.headless=true",
             "--server.autoOpenBrowser=true",
             "--global.developmentMode=false"
         ]
         logging.info(f"streamlit argv: {sys.argv}")
 
         logging.info("Calling stcli.main()...")
         stcli.main()
     except Exception as e:
         logging.error(f"Error: {e}")
         import traceback
         logging.error(traceback.format_exc())
         input("Error occurred. Press Enter to exit...")
 
 if __name__ == "__main__":
     main()


 import os
 import sys
 import subprocess
 
 if __name__ == "__main__":
     ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.py")
     subprocess.run([
         sys.executable, "-m", "streamlit", "run", ui_path,
         "--server.port=8501",
         "--server.headless=true",
         "--server.enableCors=false",
         "--server.enableXsrfProtection=false"
     ])


 from cx_Freeze import setup, Executable
 import os
 
 build_options = {
     "packages": [
         "streamlit",
         "streamlit.web.cli",
         "streamlit.runtime",
         "click",
         "altair",
         "pandas",
         "numpy",
     ],
     "excludes": [],
     "include_files": [
         "ui.py",
     ],
 }
 
 executables = [
     Executable(
         "run_nuitka.py",
         base="console",
         target_name="IntelNexus.exe",
     )
 ]
 
 setup(
     name="IntelNexus",
     version="1.0",
     description="AI-Powered Multi-Source Network Intelligence Platform",
     options={"build_exe": build_options},
     executables=executables,
 )


 import os
 import requests
 import random
 from typing import List, Dict, Optional
 from concurrent.futures import ThreadPoolExecutor, as_completed
 from bs4 import BeautifulSoup
 
 try:
     import tweepy
 except ImportError:
     tweepy = None
 
 try:
     import praw
 except ImportError:
     praw = None
 
 USER_AGENTS = [
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
 ]
 
 
 class SocialSearch:
     def __init__(self, twitter_token: Optional[str] = None, reddit_client: Optional[object] = None):
         self.twitter_token = twitter_token
         self.reddit_client = reddit_client
 
         if tweepy and twitter_token:
             try:
                 self.twitter_client = tweepy.Client(bearer_token=twitter_token)
             except Exception as e:
                 print(f"Twitter client init error: {e}")
                 self.twitter_client = None
         else:
             self.twitter_client = None
 
     def search_twitter(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         if not self.twitter_client:
             return results
 
         try:
             tweets = self.twitter_client.search_recent_tweets(
                 query=query,
                 max_results=min(max_results, 100),
                 tweet_fields=["created_at", "author_id", "public_metrics"]
             )
 
             if tweets.data:
                 for tweet in tweets.data:
                     results.append({
                         "title": tweet.text[:200],
                         "content": tweet.text,
                         "author_id": str(tweet.author_id) if tweet.author_id else "",
                         "created_at": str(tweet.created_at) if tweet.created_at else "",
                         "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
                         "retweets": tweet.public_metrics.get("retweet_count", 0) if tweet.public_metrics else 0,
                         "source": "Twitter/X"
                     })
         except Exception as e:
             print(f"Twitter search error: {e}")
 
         return results
 
     def search_reddit(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         if not self.reddit_client:
             return results
 
         try:
             subreddits = ["all", "technology", "science", "news", "worldnews"]
 
             for subreddit_name in subreddits[:2]:
                 try:
                     subreddit = self.reddit_client.subreddit(subreddit_name)
                     posts = subreddit.search(query, limit=max_results)
 
                     for post in posts:
                         results.append({
                             "title": post.title,
                             "content": post.selftext[:500] if post.selftext else "",
                             "author": str(post.author) if post.author else "",
                             "score": post.score,
                             "num_comments": post.num_comments,
                             "created_utc": str(post.created_utc),
                             "url": post.url,
                             "source": f"Reddit r/{subreddit_name}"
                         })
                 except Exception as e:
                     print(f"Reddit search error in {subreddit_name}: {e}")
         except Exception as e:
             print(f"Reddit search error: {e}")
 
         return results
 
     def search_reddit_public(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         try:
             url = f"https://www.reddit.com/search.json?q={requests.utils.quote(query)}&limit={max_results}&sort=relevance"
             headers = {
                 "User-Agent": random.choice(USER_AGENTS),
                 "Accept": "application/json"
             }
             response = requests.get(url, headers=headers, timeout=15)
 
             if response.status_code == 200:
                 data = response.json()
                 children = data.get("data", {}).get("children", [])
 
                 for child in children:
                     post = child.get("data", {})
                     if post.get("is_video") or post.get("nsfw"):
                         continue
                     results.append({
                         "title": post.get("title", ""),
                         "content": post.get("selftext", "")[:500],
                         "author": post.get("author", ""),
                         "score": post.get("score", 0),
                         "num_comments": post.get("num_comments", 0),
                         "created_utc": post.get("created_utc", ""),
                         "url": f"https://reddit.com{post.get('permalink', '')}",
                         "source": "Reddit"
                     })
         except Exception as e:
             print(f"Reddit public search error: {e}")
 
         return results
 
     def search_hackernews(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         try:
             url = f"https://hn.algolia.com/api/v1/search"
             params = {"query": query, "tags": "story", "hitsPerPage": max_results}
             headers = {"User-Agent": random.choice(USER_AGENTS)}
 
             response = requests.get(url, params=params, headers=headers, timeout=15)
 
             if response.status_code == 200:
                 data = response.json()
                 hits = data.get("hits", [])
 
                 for hit in hits:
                     results.append({
                         "title": hit.get("title", ""),
                         "content": hit.get("story_text", "")[:500] if hit.get("story_text") else "",
                         "author": hit.get("author", ""),
                         "score": hit.get("points", 0),
                         "num_comments": hit.get("num_comments", 0),
                         "created_utc": hit.get("created_at", ""),
                         "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
                         "source": "Hacker News"
                     })
         except Exception as e:
             print(f"Hacker News search error: {e}")
 
         return results
 
     def search_stackoverflow(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         try:
             url = "https://api.stackexchange.com/2.3/search/advanced"
             params = {
                 "order": "desc",
                 "sort": "relevance",
                 "q": query,
                 "site": "stackoverflow",
                 "pagesize": max_results
             }
             headers = {"User-Agent": random.choice(USER_AGENTS)}
 
             response = requests.get(url, params=params, headers=headers, timeout=15)
 
             if response.status_code == 200:
                 data = response.json()
                 items = data.get("items", [])
 
                 for item in items:
                     results.append({
                         "title": item.get("title", ""),
                         "content": item.get("body_markdown", "")[:500] if item.get("body_markdown") else "",
                         "author": item.get("owner", {}).get("display_name", ""),
                         "score": item.get("score", 0),
                         "num_comments": item.get("answer_count", 0),
                         "created_utc": item.get("creation_date", ""),
                         "url": item.get("link", ""),
                         "source": "Stack Overflow"
                     })
         except Exception as e:
             print(f"Stack Overflow search error: {e}")
 
         return results
 
     def search_zhihu(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         try:
             url = f"https://www.zhihu.com/api/v4/search_v3"
             params = {
                 "q": query,
                 "type": "topic",
                 "limit": max_results,
                 "offset": 0
             }
             headers = {
                 "User-Agent": random.choice(USER_AGENTS),
                 "Referer": "https://www.zhihu.com"
             }
 
             response = requests.get(url, params=params, headers=headers, timeout=15)
 
             if response.status_code == 200:
                 data = response.json()
                 items = data.get("data", [])
 
                 for item in items:
                     results.append({
                         "title": item.get("highlight", {}).get("title", item.get("name", "")),
                         "content": item.get("excerpt", "")[:500] if item.get("excerpt") else "",
                         "author": "",
                         "score": item.get("follower_count", 0),
                         "num_comments": item.get("discussion_count", 0),
                         "created_utc": "",
                         "url": f"https://www.zhihu.com/topic/{item.get('id', '')}",
                         "source": "知乎"
                     })
         except Exception as e:
             print(f"Zhihu search error: {e}")
 
         return results
 
     def search_weibo(self, query: str, max_results: int = 10) -> List[Dict]:
         results = []
 
         try:
             url = "https://m.weibo.cn/api/container/getIndex"
             params = {
                 "containerid": f"100103type=1&q={requests.utils.quote(query)}",
                 "page": 1
             }
             headers = {
                 "User-Agent": random.choice(USER_AGENTS),
                 "Referer": "https://m.weibo.cn"
             }
 
             response = requests.get(url, params=params, headers=headers, timeout=15)
 
             if response.status_code == 200:
                 data = response.json()
                 cards = data.get("data", {}).get("cards", [])
 
                 for card in cards:
                     if card.get("card_type") == 9:
                         mblog = card.get("mblog", {})
                         results.append({
                             "title": mblog.get("text", "")[:200],
                             "content": mblog.get("text", ""),
                             "author": mblog.get("user", {}).get("screen_name", ""),
                             "score": mblog.get("attitudes_count", 0),
                             "num_comments": mblog.get("comments_count", 0),
                             "created_utc": mblog.get("created_at", ""),
                             "url": f"https://weibo.com/detail/{mblog.get('id', '')}",
                             "source": "微博"
                         })
         except Exception as e:
             print(f"Weibo search error: {e}")
 
         return results
 
     def search(self, query: str, max_results: int = 10) -> List[Dict]:
         all_results = []
 
         with ThreadPoolExecutor(max_workers=6) as executor:
             futures = []
 
             if self.twitter_client:
                 futures.append(executor.submit(self.search_twitter, query, max_results))
 
             if self.reddit_client:
                 futures.append(executor.submit(self.search_reddit, query, max_results))
             else:
                 futures.append(executor.submit(self.search_reddit_public, query, max_results))
 
             futures.append(executor.submit(self.search_hackernews, query, max_results))
             futures.append(executor.submit(self.search_stackoverflow, query, max_results))
             futures.append(executor.submit(self.search_zhihu, query, max_results))
             futures.append(executor.submit(self.search_weibo, query, max_results))
 
             for future in as_completed(futures):
                 try:
                     results = future.result()
                     if results:
                         all_results.extend(results)
                 except Exception as e:
                     print(f"Search error: {e}")
 
         all_results.sort(key=lambda x: x.get("score", 0) + x.get("likes", 0), reverse=True)
         return all_results[:max_results * 3]
 
 
 def get_social_results(query: str, max_results: int = 10, twitter_token: Optional[str] = None) -> List[Dict]:
     searcher = SocialSearch(twitter_token=twitter_token)
     return searcher.search(query, max_results)


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
