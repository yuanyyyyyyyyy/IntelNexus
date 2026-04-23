# IntelNexus V1.0 – 系统代码

________________________________________
第1页：.\main.py（完整148行）
00001| // ==========
00002| // 文件: .\main.py
00003| // 功能: CLI和Web UI入口
00004| // 创建时间: 2025年2月6日
00005| // 最后修改: 2025年2月6日
00006| // 行数: 148行
00007| // ==========

00008| """
00009| IntelNexus - AI Multi-Source Network Intelligence Platform
00010| =========================================================
00011| A unified search interface for news and web content.
00012| """

00013| import os
00014| import click
00015| from datetime import datetime
00016| from concurrent.futures import ThreadPoolExecutor, as_completed

00017| from scrape import scrape_multiple
00018| from web_search import get_web_results
00019| from news_search import get_news_results
00020| from darkweb_search import get_darkweb_results, is_available as darkweb_available

00021| from llm import get_llm, refine_query, generate_summary
00022| from llm_utils import get_model_choices

00023| // 进度: 第10行/共148行

00024| MODEL_CHOICES = get_model_choices()

00025| SEARCH_MODES = {
00026|     "web": "Web Search",
00027|     "news": "News Articles",
00028|     "darkweb": "Dark Web (Optional)",
00029|     "all": "All Sources"
00030| }

00031| def execute_search(mode, query, max_workers):
00032|     results = []
00033|     
00034|     with ThreadPoolExecutor(max_workers=max_workers) as executor:
00035|         futures = []
00036|         
00037|         if mode in ["web", "all"]:
00038|             futures.append(executor.submit(get_web_results, query, max_workers, 20))
00039|         
00040|         if mode in ["news", "all"]:
00041|             futures.append(executor.submit(get_news_results, query, 15))
00042|         
00043|         if mode in ["darkweb", "all"] and darkweb_available():
00044|             futures.append(executor.submit(get_darkweb_results, query, max_workers))
00045|         
00046|         for future in as_completed(futures):
00047|             try:
00048|                 source = future.result()
00049|                 if source:
00050|                     results.extend(source)
00051|             except Exception as e:
00052|                 print(f"Search error: {e}")
00053|     
00054|     return results

00055| // 进度: 第20行/共148行

00056| @click.group()
00057| @click.version_option()
00058| def intelnexus():
00059|     """IntelNexus: AI-Powered Multi-Source Network Intelligence Platform."""
00060|     pass

00061| @intelnexus.command()
00062| @click.option(
00063|     "--model", "-m",
00064|     default="qwen2.5:7b",
00065|     show_default=True,
00066|     type=click.Choice(MODEL_CHOICES),
00067|     help="Select LLM model (local or cloud)"
00068| )
00069| @click.option("--query", "-q", required=True, type=str, help="Search query")
00070| // 进度: 第30行/共148行
00071| @click.option(
00072|     "--mode", "-s",
00073|     default="all",
00074|     type=click.Choice(["web", "news", "darkweb", "all"]),
00075|     help="Search mode"
00076| )
00077| @click.option("--threads", "-t", default=5, show_default=True, type=int, help="Number of threads")
00078| @click.option("--output", "-o", type=str, help="Output filename")
00079| def search(model, query, mode, threads, output):
00080|     """Run IntelNexus in CLI mode."""
00081|     
00082|     click.echo(f"IntelNexus - {SEARCH_MODES.get(mode, mode)} Mode")
00083|     click.echo(f"Model: {model}")
00084|     click.echo(f"Query: {query}")
00085|     
00086|     llm = get_llm(model)
00087|     
00088|     click.echo("[1/4] Refining query...")
00089|     refined_query = refine_query(llm, query)
00090|     click.echo(f"    Refined: {refined_query}")
00091|     
00092|     click.echo(f"[2/4] Searching {mode}...")
00093|     search_results = execute_search(mode, refined_query, threads)
00094|     click.echo(f"    Found {len(search_results)} results")
00095|     
00096|     if not search_results:
00097|         click.echo("No results found.")
00098|         return
00099|     
00100|     # 保留所有搜索结果（不过滤）
00101|     search_filtered = search_results
00102|     click.echo(f"[3/4] Keeping all {len(search_filtered)} results")
00103|     
00104|     click.echo("[4/4] Scraping content...")
00105|     scraped_results = scrape_multiple(search_filtered, max_workers=threads)
00106|     click.echo("    Done")
00107|     
00108|     click.echo("[5/5] Generating summary...")
00109|     summary = generate_summary(llm, query, scraped_results)
00110|     
00111|     if not output:
00112|         now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
00113|         filename = f"report_{now}.md"
00114|     else:
00115|         filename = output + ".md"
00116|     
00117|     with open(filename, "w", encoding="utf-8") as f:
00118|         f.write(summary)
00119|         click.echo(f"\n[OUTPUT] Report saved to {filename}")

00120| // 进度: 第40行/共148行

00121| @intelnexus.command()
00122| @click.option("--ui-port", default=8501, show_default=True, type=int, help="Port for Streamlit UI")
00123| @click.option("--ui-host", default="localhost", show_default=True, type=str, help="Host for Streamlit UI")
00124| def ui(ui_port, ui_host):
00125|     """Run IntelNexus in Web UI mode."""
00126|     import sys, os
00127|     from streamlit.web import cli as stcli
00128|     
00129|     if getattr(sys, "frozen", False):
00130|         base = sys._MEIPASS
00131|     else:
00132|         base = os.path.dirname(__file__)
00133|     
00134|     ui_script = os.path.join(base, "ui.py")
00135|     sys.argv = [
00136|         "streamlit", "run", ui_script,
00137|         f"--server.port={ui_port}",
00138|         f"--server.address={ui_host}",
00139|         "--global.developmentMode=false",
00140|     ]
00141|     sys.exit(stcli.main())

00142| // 进度: 第50行/共148行

00143| if __name__ == "__main__":
00144|     intelnexus()

00145| // ==========
00146| // 文件结束: .\main.py
00147| // 总行数: 148行
00148| // 下一个文件: [config.py]
00149| // ==========

第2页：.\config.py（完整17行）
00150| // ==========
00151| // 文件: .\config.py
00152| // 功能: 环境变量配置
00153| // 创建时间: 2025年2月6日
00154| // 最后修改: 2025年2月6日
00155| // 行数: 17行
00156| // ==========

00157| import os
00158| from dotenv import load_dotenv

00159| load_dotenv()

00160| OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
00161| GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
00162| ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
00163| OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
00164| OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
00165| OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

00166| // 进度: 第10行/共17行

00167| SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
00168| NEWS_API_KEY = os.getenv("NEWS_API_KEY")
00169| TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

00170| ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"

00171| // ==========
00172| // 文件结束: .\config.py
00173| // 总行数: 17行
00174| // 下一个文件: [web_search.py]
00175| // ==========

第3页：.\web_search.py（完整282行）
00171| import requests
00172| import random
00173| import re
00174| from bs4 import BeautifulSoup
00175| from concurrent.futures import ThreadPoolExecutor, as_completed
00176| from requests.adapters import HTTPAdapter
00177| from urllib3.util.retry import Retry
00178| from urllib.parse import quote, urlencode
00179| import warnings
00180| warnings.filterwarnings("ignore")
00181| 
00182| USER_AGENTS = [
00183|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
00184|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
00185|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
00186|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
00187| ]
00188| 
00189| SEARCH_ENGINES = [
00190|     {
// 进度: 第20行/共282行
00191|         "name": "Bing",
00192|         "url": "https://www.bing.com/search?q={query}&first={page}",
00193|         "parser": "bing"
00194|     },
00195|     {
00196|         "name": "DuckDuckGo",
00197|         "url": "https://html.duckduckgo.com/html/?q={query}&b={page}",
00198|         "parser": "ddg"
00199|     },
00200|     {
00201|         "name": "Yahoo",
00202|         "url": "https://search.yahoo.com/search?p={query}&b={page}",
00203|         "parser": "yahoo"
00204|     },
00205|     {
00206|         "name": "Yandex",
00207|         "url": "https://yandex.com/search/?text={query}&page={page}",
00208|         "parser": "yandex"
00209|     },
00210|     {
// 进度: 第40行/共282行
00211|         "name": "Baidu",
00212|         "url": "https://www.baidu.com/s?wd={query}&pn={page}",
00213|         "parser": "baidu"
00214|     },
00215| ]
00216| 
00217| 
00218| def get_session():
00219|     session = requests.Session()
00220|     retry = Retry(
00221|         total=2,
00222|         read=2,
00223|         connect=2,
00224|         backoff_factor=0.5,
00225|         status_forcelist=[500, 502, 503, 504]
00226|     )
00227|     adapter = HTTPAdapter(max_retries=retry)
00228|     session.mount("http://", adapter)
00229|     session.mount("https://", adapter)
00230|     return session
// 进度: 第60行/共282行
00231| 
00232| 
00233| def fetch_bing_results(query: str, page: int = 0):
00234|     results = []
00235|     try:
00236|         encoded_query = quote(query, safe='')
00237|         url = f"https://www.bing.com/search?q={encoded_query}&first={page * 10 + 1}"
00238|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00239|         session = get_session()
00240|         response = session.get(url, headers=headers, timeout=20)
00241| 
00242|         if response.status_code == 200:
00243|             soup = BeautifulSoup(response.text, "html.parser")
00244| 
00245|             for item in soup.select('li.b_algo'):
00246|                 try:
00247|                     # 修复：使用h2 a获取正确标题，而不是第一个链接
00248|                     a_tag = item.select_one('h2 a')
00249|                     if not a_tag:
00250|                         a_tag = item.select_one('a[href]:not(.tilk)')
// 进度: 第80行/共282行
00251|                     if a_tag:
00252|                         title = a_tag.get_text(strip=True)
00253|                         href = a_tag.get('href', '')
00254| 
00255|                         snippet = item.find('p')
00256|                         description = snippet.get_text(strip=True) if snippet else ""
00257| 
00258|                         if href and href.startswith('http') and 'bing.com' not in href:
00259|                             results.append({
00260|                                 "title": title,
00261|                                 "link": href,
00262|                                 "description": description[:200],
00263|                                 "source": "Bing"
00264|                             })
00265|                 except:
00266|                     continue
00267|     except Exception as e:
00268|         print(f"Bing search error: {e}")
00269|     return results
00270| 
// 进度: 第100行/共282行
00271| 
00272| def fetch_ddg_results(query: str, page: int = 0):
00273|     results = []
00274|     try:
00275|         encoded_query = quote(query, safe='')
00276|         url = f"https://html.duckduckgo.com/html/?q={encoded_query}&b={page * 11}"
00277|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00278|         session = get_session()
00279|         response = session.get(url, headers=headers, timeout=20)
00280| 
00281|         if response.status_code == 200:
00282|             soup = BeautifulSoup(response.text, "html.parser")
00283| 
00284|             for item in soup.select('div.result'):
00285|                 try:
00286|                     a_tag = item.select_one('a.result__a')
00287|                     if a_tag:
00288|                         title = a_tag.get_text(strip=True)
00289|                         href = a_tag.get('href', '')
00290| 
// 进度: 第120行/共282行
00291|                         snippet = item.select_one('a.result__snippet')
00292|                         description = snippet.get_text(strip=True) if snippet else ""
00293| 
00294|                         if href:
00295|                             results.append({
00296|                                 "title": title,
00297|                                 "link": href,
00298|                                 "description": description[:200],
00299|                                 "source": "DuckDuckGo"
00300|                             })
00301|                 except:
00302|                     continue
00303|     except Exception as e:
00304|         print(f"DuckDuckGo search error: {e}")
00305|     return results
00306| 
00307| 
00308| def fetch_yahoo_results(query: str, page: int = 0):
00309|     results = []
00310|     try:
// 进度: 第140行/共282行
00311|         encoded_query = quote(query, safe='')
00312|         url = f"https://search.yahoo.com/search?p={encoded_query}&b={page * 10 + 1}"
00313|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00314|         session = get_session()
00315|         response = session.get(url, headers=headers, timeout=20)
00316| 
00317|         if response.status_code == 200:
00318|             soup = BeautifulSoup(response.text, "html.parser")
00319| 
00320|             for item in soup.select('div.algo'):
00321|                 try:
00322|                     a_tag = item.find('a')
00323|                     if a_tag:
00324|                         title = a_tag.get_text(strip=True)
00325|                         href = a_tag.get('href', '')
00326| 
00327|                         snippet = item.find('p')
00328|                         description = snippet.get_text(strip=True) if snippet else ""
00329| 
00330|                         if href and href.startswith('http'):
// 进度: 第160行/共282行
00331|                             results.append({
00332|                                 "title": title,
00333|                                 "link": href,
00334|                                 "description": description[:200],
00335|                                 "source": "Yahoo"
00336|                             })
00337|                 except:
00338|                     continue
00339|     except Exception as e:
00340|         print(f"Yahoo search error: {e}")
00341|     return results
00342| 
00343| 
00344| def fetch_yandex_results(query: str, page: int = 0):
00345|     results = []
00346|     try:
00347|         encoded_query = quote(query, safe='')
00348|         url = f"https://yandex.com/search/?text={encoded_query}&page={page + 1}"
00349|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00350|         session = get_session()
// 进度: 第180行/共282行
00351|         response = session.get(url, headers=headers, timeout=20)
00352| 
00353|         if response.status_code == 200:
00354|             soup = BeautifulSoup(response.text, "html.parser")
00355| 
00356|             for item in soup.select('li.serp-item'):
00357|                 try:
00358|                     a_tag = item.select_one('a.serp-item__title')
00359|                     if a_tag:
00360|                         title = a_tag.get_text(strip=True)
00361|                         href = a_tag.get('href', '')
00362| 
00363|                         snippet = item.select_one('div.serp-item__text')
00364|                         description = snippet.get_text(strip=True) if snippet else ""
00365| 
00366|                         if href and href.startswith('http'):
00367|                             results.append({
00368|                                 "title": title,
00369|                                 "link": href,
00370|                                 "description": description[:200],
// 进度: 第200行/共282行
00371|                                 "source": "Yandex"
00372|                             })
00373|                 except:
00374|                     continue
00375|     except Exception as e:
00376|         print(f"Yandex search error: {e}")
00377|     return results
00378| 
00379| 
00380| def fetch_baidu_results(query: str, page: int = 0):
00381|     results = []
00382|     try:
00383|         encoded_query = quote(query, safe='')
00384|         url = f"https://www.baidu.com/s?wd={encoded_query}&pn={page * 10}"
00385|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00386|         session = get_session()
00387|         response = session.get(url, headers=headers, timeout=20)
00388| 
00389|         if response.status_code == 200:
00390|             soup = BeautifulSoup(response.text, "html.parser")
// 进度: 第220行/共282行
00391| 
00392|             for item in soup.select('div.result'):
00393|                 try:
00394|                     a_tag = item.find('a')
00395|                     if a_tag:
00396|                         title = a_tag.get_text(strip=True)
00397|                         href = a_tag.get('href', '')
00398| 
00399|                         if href and href.startswith('http'):
00400|                             results.append({
00401|                                 "title": title,
00402|                                 "link": href,
00403|                                 "description": "",
00404|                                 "source": "Baidu"
00405|                             })
00406|                 except:
00407|                     continue
00408|     except Exception as e:
00409|         print(f"Baidu search error: {e}")
00410|     return results
// 进度: 第240行/共282行
00411| 
00412| 
00413| def get_web_results(query, max_workers: int = 5, max_results: int = 50) -> list:
00414|     results = []
00415|     pages_per_engine = 2  # 减少翻页数以提升速度
00416| 
00417|     # 支持多查询（列表或用|分隔的字符串）
00418|     if isinstance(query, list):
00419|         queries = query
00420|     elif '|' in query:
00421|         queries = [q.strip() for q in query.split('|')]
00422|     else:
00423|         queries = [query]
00424| 
00425|     with ThreadPoolExecutor(max_workers=max_workers) as executor:
00426|         futures = []
00427| 
00428|         # 对每个查询进行搜索
00429|         for q in queries:
00430|             for page in range(pages_per_engine):
// 进度: 第260行/共282行
00431|                 futures.append(executor.submit(fetch_bing_results, q, page))
00432|                 futures.append(executor.submit(fetch_ddg_results, q, page))
00433|                 futures.append(executor.submit(fetch_yahoo_results, q, page))
00434|                 futures.append(executor.submit(fetch_yandex_results, q, page))
00435|                 futures.append(executor.submit(fetch_baidu_results, q, page))
00436| 
00437|         for future in as_completed(futures):
00438|             try:
00439|                 result_urls = future.result()
00440|                 results.extend(result_urls)
00441|             except Exception as e:
00442|                 print(f"Search error: {e}")
00443| 
00444|     seen_links = set()
00445|     unique_results = []
00446|     for res in results:
00447|         link = res.get("link", "").rstrip('/')
00448|         if link and link not in seen_links and len(link) > 10:
00449|             seen_links.add(link)
00450|             unique_results.append(res)
// 进度: 第280行/共282行
00451| 
00452|     return unique_results[:max_results]
// ==========
// 文件结束: .\web_search.py
// 总行数: 282行
// 下一个文件: [等待添加]
// ==========


第305页：.\news_search.py（完整244行）
00453| import os
00454| import requests
00455| from typing import List, Dict, Optional
00456| from datetime import datetime, timedelta
00457| from bs4 import BeautifulSoup
00458| from urllib.parse import quote, urljoin
00459| from concurrent.futures import ThreadPoolExecutor, as_completed
00460| import random
00461| import re
00462| 
00463| try:
00464|     from newsapi import NewsApiClient
00465| except ImportError:
00466|     NewsApiClient = None
00467| 
00468| USER_AGENTS = [
00469|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
00470|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
00471|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
00472| ]
// 进度: 第20行/共244行
00473| 
00474| RSS_SOURCES = [
00475|     {"name": "Google News", "url": "https://news.google.com/rss/search?q={query}"},
00476|     {"name": "Bing News", "url": "https://www.bing.com/news/search?q={query}&format=rss"},
00477|     {"name": "Yahoo News", "url": "https://news.yahoo.com/rss/search?p={query}"},
00478|     {"name": "Reuters", "url": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best"},
00479|     {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
00480|     {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
00481|     {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
00482|     {"name": "BBC", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"},
00483|     {"name": "CNN", "url": "http://rss.cnn.com/rss/edition.rss"},
00484| ]
00485| 
00486| 
00487| class NewsSearch:
00488|     def __init__(self, api_key: Optional[str] = None):
00489|         self.api_key = api_key
00490|         if NewsApiClient and api_key:
00491|             try:
00492|                 self.news_client = NewsApiClient(api_key=api_key)
// 进度: 第40行/共244行
00493|             except Exception as e:
00494|                 print(f"NewsAPI init error: {e}")
00495|                 self.news_client = None
00496|         else:
00497|             self.news_client = None
00498| 
00499|     def search_newsapi(self, query: str, max_results: int = 10) -> List[Dict]:
00500|         results = []
00501|         if not self.news_client:
00502|             return results
00503| 
00504|         try:
00505|             response = self.news_client.get_everything(
00506|                 q=query,
00507|                 language="en",
00508|                 sort_by="relevancy",
00509|                 page_size=max_results
00510|             )
00511| 
00512|             if response.get("status") == "ok":
// 进度: 第60行/共244行
00513|                 for article in response.get("articles", []):
00514|                     results.append({
00515|                         "title": article.get("title", ""),
00516|                         "description": article.get("description", "")[:300],
00517|                         "content": article.get("content", ""),
00518|                         "author": article.get("author", ""),
00519|                         "source": article.get("source", {}).get("name", "NewsAPI"),
00520|                         "url": article.get("url", ""),
00521|                         "published_at": article.get("publishedAt", ""),
00522|                         "image_url": article.get("urlToImage", "")
00523|                     })
00524|         except Exception as e:
00525|             print(f"NewsAPI search error: {e}")
00526| 
00527|         return results
00528| 
00529|     def search_rss(self, query: str, max_results: int = 10) -> List[Dict]:
00530|         results = []
00531| 
00532|         query_lower = query.lower()
// 进度: 第80行/共244行
00533| 
00534|         for source in RSS_SOURCES:
00535|             if len(results) >= max_results:
00536|                 break
00537|             try:
00538|                 if "{query}" in source["url"]:
00539|                     url = source["url"].format(query=quote(query))
00540|                 else:
00541|                     url = source["url"]
00542| 
00543|                 headers = {"User-Agent": random.choice(USER_AGENTS)}
00544|                 response = requests.get(url, headers=headers, timeout=12)
00545| 
00546|                 if response.status_code == 200:
00547|                     try:
00548|                         soup = BeautifulSoup(response.content, "xml")
00549|                     except:
00550|                         soup = BeautifulSoup(response.content, "html.parser")
00551| 
00552|                     items = soup.find_all("item")[:max_results]
// 进度: 第100行/共244行
00553|                     if not items:
00554|                         items = soup.find_all("entry")[:max_results]
00555| 
00556|                     for item in items:
00557|                         if len(results) >= max_results:
00558|                             break
00559| 
00560|                         title = item.find("title")
00561|                         link = item.find("link")
00562|                         desc = item.find("description") or item.find("summary") or item.find("content")
00563|                         pub_date = item.find("pubDate") or item.find("published") or item.find("dc:date")
00564| 
00565|                         link_text = ""
00566|                         if link:
00567|                             if hasattr(link, 'get_text'):
00568|                                 link_text = link.get_text(strip=True)
00569|                             else:
00570|                                 link_text = str(link)
00571| 
00572|                         if title and link_text:
// 进度: 第120行/共244行
00573|                             title_text = title.get_text(strip=True) if hasattr(title, 'get_text') else str(title)
00574| 
00575|                             if query_lower not in title_text.lower() and "{query}" in source["url"]:
00576|                                 continue
00577| 
00578|                             results.append({
00579|                                 "title": title_text,
00580|                                 "description": desc.get_text(strip=True)[:300] if desc and hasattr(desc, 'get_text') else "",
00581|                                 "content": desc.get_text(strip=True) if desc and hasattr(desc, 'get_text') else "",
00582|                                 "author": "",
00583|                                 "source": source["name"],
00584|                                 "url": link_text,
00585|                                 "published_at": pub_date.get_text(strip=True) if pub_date and hasattr(pub_date, 'get_text') else "",
00586|                                 "image_url": ""
00587|                             })
00588|             except Exception as e:
00589|                 print(f"RSS search error from {source['name']}: {e}")
00590| 
00591|         return results
00592| 
// 进度: 第140行/共244行
00593|     def search_bing_news(self, query: str, max_results: int = 10) -> List[Dict]:
00594|         results = []
00595|         try:
00596|             url = "https://www.bing.com/news/search"
00597|             params = {"q": query, "form": "QBRE", "sp": "-1"}
00598|             headers = {"User-Agent": random.choice(USER_AGENTS)}
00599| 
00600|             response = requests.get(url, params=params, headers=headers, timeout=15)
00601|             if response.status_code == 200:
00602|                 soup = BeautifulSoup(response.text, "html.parser")
00603| 
00604|                 for item in soup.select("div.news-card")[:max_results]:
00605|                     try:
00606|                         title_elem = item.select_one("a.title")
00607|                         snippet_elem = item.select_one("div.snippet")
00608|                         source_elem = item.select_one("div.source")
00609| 
00610|                         if title_elem:
00611|                             results.append({
00612|                                 "title": title_elem.get_text(strip=True),
// 进度: 第160行/共244行
00613|                                 "description": snippet_elem.get_text(strip=True)[:300] if snippet_elem else "",
00614|                                 "content": snippet_elem.get_text(strip=True) if snippet_elem else "",
00615|                                 "author": "",
00616|                                 "source": source_elem.get_text(strip=True) if source_elem else "Bing News",
00617|                                 "url": title_elem.get("href", ""),
00618|                                 "published_at": "",
00619|                                 "image_url": ""
00620|                             })
00621|                     except:
00622|                         continue
00623|         except Exception as e:
00624|             print(f"Bing news search error: {e}")
00625|         return results
00626| 
00627|     def search_google_news(self, query: str, max_results: int = 10) -> List[Dict]:
00628|         results = []
00629|         try:
00630|             url = "https://news.google.com/rss/search"
00631|             params = {"q": query, "hl": "en-US", "gl": "US"}
00632|             headers = {"User-Agent": random.choice(USER_AGENTS)}
// 进度: 第180行/共244行
00633| 
00634|             response = requests.get(url, params=params, headers=headers, timeout=15)
00635|             if response.status_code == 200:
00636|                 soup = BeautifulSoup(response.content, "xml")
00637| 
00638|                 for item in soup.find_all("item")[:max_results]:
00639|                     try:
00640|                         title = item.find("title")
00641|                         link = item.find("link")
00642|                         desc = item.find("description")
00643|                         pub_date = item.find("pubDate")
00644| 
00645|                         if title and link:
00646|                             results.append({
00647|                                 "title": title.get_text(strip=True),
00648|                                 "description": desc.get_text(strip=True)[:300] if desc else "",
00649|                                 "content": desc.get_text(strip=True) if desc else "",
00650|                                 "author": "",
00651|                                 "source": "Google News",
00652|                                 "url": link.get_text(strip=True),
// 进度: 第200行/共244行
00653|                                 "published_at": pub_date.get_text(strip=True) if pub_date else "",
00654|                                 "image_url": ""
00655|                             })
00656|                     except:
00657|                         continue
00658|         except Exception as e:
00659|             print(f"Google News search error: {e}")
00660|         return results
00661| 
00662|     def search(self, query: str, max_results: int = 10) -> List[Dict]:
00663|         results = []
00664| 
00665|         with ThreadPoolExecutor(max_workers=4) as executor:
00666|             futures = []
00667| 
00668|             if self.news_client:
00669|                 futures.append(executor.submit(self.search_newsapi, query, max_results))
00670| 
00671|             futures.append(executor.submit(self.search_rss, query, max_results))
00672|             futures.append(executor.submit(self.search_bing_news, query, max_results))
// 进度: 第220行/共244行
00673|             futures.append(executor.submit(self.search_google_news, query, max_results))
00674| 
00675|             for future in futures:
00676|                 try:
00677|                     r = future.result()
00678|                     if r:
00679|                         results.extend(r)
00680|                 except Exception as e:
00681|                     print(f"Search error: {e}")
00682| 
00683|         seen_urls = set()
00684|         unique_results = []
00685|         for r in results:
00686|             url = r.get("url", "")
00687|             if url and url not in seen_urls:
00688|                 seen_urls.add(url)
00689|                 unique_results.append(r)
00690| 
00691|         return unique_results[:max_results * 3]
00692| 
// 进度: 第240行/共244行
00693| 
00694| def get_news_results(query: str, max_results: int = 10, api_key: Optional[str] = None) -> List[Dict]:
00695|     searcher = NewsSearch(api_key=api_key)
00696|     return searcher.search(query, max_results)
// ==========
// 文件结束: .\news_search.py
// 总行数: 244行
// 下一个文件: [等待添加]
// ==========


第567页：.\darkweb_search.py（完整399行）
00697| """
00698| Dark Web Search Module
00699| ====================
00700| This module supports:
00701| 1. Public dark web search engines (Ahmia, OnionLink)
00702| 2. Custom .onion sites with optional authentication
00703| 
00704| Enable via .env: ENABLE_DARKWEB=true
00705| 
00706| WARNING: This module is for educational and authorized research purposes only.
00707| """
00708| 
00709| import os
00710| import sys
00711| from dotenv import load_dotenv
00712| load_dotenv()
00713| 
00714| import requests
00715| import random
00716| import re
// 进度: 第20行/共399行
00717| import json
00718| from bs4 import BeautifulSoup
00719| from concurrent.futures import ThreadPoolExecutor, as_completed
00720| from requests.adapters import HTTPAdapter
00721| from urllib3.util.retry import Retry
00722| import platform
00723| 
00724| import warnings
00725| warnings.filterwarnings("ignore")
00726| 
00727| ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"
00728| 
00729| # 自定义暗网站点配置（支持认证）
00730| # 格式: {"name": "站点名", "url": "http://xxx.onion", "auth": {"type": "basic", "username": "xxx", "password": "xxx"}}
00731| CUSTOM_ONION_SITES = os.getenv("CUSTOM_ONION_SITES", "")
00732| 
00733| def get_custom_onion_sites(ui_sites=None):
00734|     """获取自定义暗网站点列表
00735| 
00736|     Args:
// 进度: 第40行/共399行
00737|         ui_sites: 从UI传递的自定义站点列表
00738| 
00739|     Returns:
00740|        站点列表
00741|     """
00742|     sites = []
00743| 
00744|     # 1. 从环境变量加载
00745|     if CUSTOM_ONION_SITES:
00746|         try:
00747|             sites = json.loads(CUSTOM_ONION_SITES)
00748|         except:
00749|             pass
00750| 
00751|     # 2. 从本地文件加载
00752|     try:
00753|         sites_file = "data/custom_onion_sites.json"
00754|         if os.path.exists(sites_file):
00755|             with open(sites_file, "r", encoding="utf-8") as f:
00756|                 file_sites = json.load(f)
// 进度: 第60行/共399行
00757|                 # 合并到站点列表
00758|                 for fs in file_sites:
00759|                     if fs not in sites:
00760|                         sites.append(fs)
00761|     except:
00762|         pass
00763| 
00764|     # 3. 合并UI传递的站点
00765|     if ui_sites:
00766|         for us in ui_sites:
00767|             if us not in sites:
00768|                 sites.append(us)
00769| 
00770|     # 4. 默认添加Breached论坛（如果配置了认证）
00771|     breached_user = os.getenv("BREACHED_USERNAME", "")
00772|     breached_pass = os.getenv("BREACHED_PASSWORD", "")
00773|     if breached_user and breached_pass:
00774|         breached_site = {
00775|             "name": "Breached Forum",
00776|             "url": "http://breachedmw4otc2lhx7nqe4wyxfhpvy32ooz26opvqkmmrbg73c7ooad.onion",
// 进度: 第80行/共399行
00777|             "auth": {
00778|                 "type": "basic",
00779|                 "username": breached_user,
00780|                 "password": breached_pass
00781|             }
00782|         }
00783|         # 检查是否已存在
00784|         if not any(s.get("name") == "Breached Forum" for s in sites):
00785|             sites.append(breached_site)
00786| 
00787|     return sites
00788| 
00789| 
00790| def fetch_with_auth(url, auth=None):
00791|     """使用认证访问暗网站点"""
00792|     headers = {"User-Agent": random.choice(USER_AGENTS)}
00793| 
00794|     session = requests.Session()
00795|     session.headers.update(headers)
00796| 
// 进度: 第100行/共399行
00797|     # 设置代理
00798|     port = get_tor_proxy_port()
00799|     session.proxies = {
00800|         "http": f"socks5h://127.0.0.1:{port}",
00801|         "https": f"socks5h://127.0.0.1:{port}"
00802|     }
00803| 
00804|     if auth:
00805|         if auth.get("type") == "basic":
00806|             session.auth = (auth.get("username"), auth.get("password"))
00807|         elif auth.get("type") == "cookie":
00808|             # 使用Cookie认证
00809|             cookies = auth.get("cookies", {})
00810|             for k, v in cookies.items():
00811|                 session.cookies.set(k, v)
00812| 
00813|     try:
00814|         response = session.get(url, timeout=30)
00815|         return response
00816|     except:
// 进度: 第120行/共399行
00817|         return None
00818| 
00819| 
00820| def search_custom_onion_site(site_config, query):
00821|     """搜索自定义暗网站点"""
00822|     results = []
00823|     try:
00824|         base_url = site_config.get("url", "")
00825|         auth = site_config.get("auth")
00826|         name = site_config.get("name", "Custom")
00827| 
00828|         # 尝试访问站点并搜索
00829|         # Breached论坛搜索URL格式
00830|         search_url = f"{base_url}?search={query}"
00831| 
00832|         response = fetch_with_auth(search_url, auth)
00833| 
00834|         if response and response.status_code == 200:
00835|             soup = BeautifulSoup(response.text, "html.parser")
00836| 
// 进度: 第140行/共399行
00837|             # 提取链接
00838|             for a in soup.find_all('a', href=True):
00839|                 try:
00840|                     href = str(a.get('href', ''))
00841|                     title = a.get_text(strip=True)
00842| 
00843|                     if href and len(title) > 2:
00844|                         # 检查是否包含.onion
00845|                         if '.onion' in href.lower() or base_url.split('//')[1].split('.')[0] in href:
00846|                             results.append({
00847|                                 "title": title[:100] or f"{name} result",
00848|                                 "link": href if href.startswith('http') else f"{base_url}{href}",
00849|                                 "source": name
00850|                             })
00851|                 except:
00852|                     continue
00853|     except:
00854|         pass
00855| 
00856|     return results
// 进度: 第160行/共399行
00857| 
00858| USER_AGENTS = [
00859|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
00860|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
00861|     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
00862|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
00863|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
00864|     "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
00865|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
00866|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
00867|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
00868| ]
00869| 
00870| # 完整的暗网搜索引擎列表（来自原始项目）
00871| DARKWEB_SEARCH_ENGINES = [
00872|     {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"},
00873|     {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}"},
00874|     {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}"},
00875|     {"name": "Amnesia", "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}"},
00876|     {"name": "Kaizer", "url": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}"},
// 进度: 第180行/共399行
00877|     {"name": "Anima", "url": "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}"},
00878|     {"name": "Tornado", "url": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}"},
00879|     {"name": "TorNet", "url": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}"},
00880|     {"name": "Torland", "url": "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}"},
00881|     {"name": "Find Tor", "url": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}"},
00882|     {"name": "Excavator", "url": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}"},
00883|     {"name": "Onionway", "url": "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}"},
00884|     {"name": "Tor66", "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}"},
00885|     {"name": "OSS", "url": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}"},
00886|     {"name": "Torgol", "url": "http://torgolnpeouim56dykfob6jh5r2ps2j73enc42s2um4ufob3ny4fcdyd.onion/?q={query}"},
00887|     {"name": "The Deep Searches", "url": "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}"},
00888| ]
00889| 
00890| # Backward-compatible flat list
00891| DEFAULT_SEARCH_ENGINES = [e["url"] for e in DARKWEB_SEARCH_ENGINES]
00892| 
00893| 
00894| def get_tor_proxy_port():
00895|     """获取Tor代理端口"""
00896|     # 优先使用环境变量
// 进度: 第200行/共399行
00897|     custom_port = os.getenv("TOR_PROXY_PORT")
00898|     if custom_port:
00899|         try:
00900|             return int(custom_port)
00901|         except:
00902|             pass
00903| 
00904|     # 默认端口
00905|     return 9150
00906| 
00907| 
00908| def get_tor_session():
00909|     """创建通过Tor代理的会话"""
00910|     session = requests.Session()
00911|     retry = Retry(
00912|         total=3,
00913|         read=3,
00914|         connect=3,
00915|         backoff_factor=0.5,
00916|         status_forcelist=[500, 502, 503, 504]
// 进度: 第220行/共399行
00917|     )
00918|     adapter = HTTPAdapter(max_retries=retry)
00919|     session.mount("http://", adapter)
00920|     session.mount("https://", adapter)
00921| 
00922|     port = get_tor_proxy_port()
00923|     session.proxies = {
00924|         "http": f"socks5h://127.0.0.1:{port}",
00925|         "https": f"socks5h://127.0.0.1:{port}"
00926|     }
00927|     return session
00928| 
00929| 
00930| def fetch_ahmia_results(query):
00931|     """从Ahmia获取暗网搜索结果（无需Tor）"""
00932|     results = []
00933|     try:
00934|         url = f"https://ahmia.fi/search/?q={query}"
00935|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00936|         response = requests.get(url, headers=headers, timeout=15)
// 进度: 第240行/共399行
00937| 
00938|         if response.status_code == 200:
00939|             soup = BeautifulSoup(response.text, "html.parser")
00940| 
00941|             for a in soup.find_all('a', href=True):
00942|                 try:
00943|                     href = str(a.get('href', ''))
00944|                     title = a.get_text(strip=True)
00945|                     if '.onion' in href.lower() and len(title) > 2:
00946|                         results.append({
00947|                             "title": title[:100] or "暗网资源",
00948|                             "link": href,
00949|                             "source": "Ahmia"
00950|                         })
00951|                 except:
00952|                     continue
00953|     except:
00954|         pass
00955| 
00956|     return results
// 进度: 第260行/共399行
00957| 
00958| 
00959| def fetch_onionlink_search(query):
00960|     """从onionlink搜索获取结果（无需Tor）"""
00961|     results = []
00962|     try:
00963|         url = f"https://onionlink.net/?s={query}"
00964|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00965|         response = requests.get(url, headers=headers, timeout=15)
00966| 
00967|         if response.status_code == 200:
00968|             soup = BeautifulSoup(response.text, "html.parser")
00969| 
00970|             for a in soup.find_all('a', href=True):
00971|                 try:
00972|                     href = str(a.get('href', ''))
00973|                     title = a.get_text(strip=True)
00974|                     if '.onion' in href.lower() and len(title) > 2 and 'http' in href:
00975|                         results.append({
00976|                             "title": title[:100] or "暗网资源",
// 进度: 第280行/共399行
00977|                             "link": href,
00978|                             "source": "OnionLink"
00979|                         })
00980|                 except:
00981|                     continue
00982|     except:
00983|         pass
00984| 
00985|     return results
00986| 
00987| 
00988| def fetch_tordex_search(query):
00989|     """从TorDex搜索获取结果（无需Tor）"""
00990|     results = []
00991|     try:
00992|         url = f"https://tordexu72joez4ofvtvk6hxdlh3cvt7qexvzuwcyhyhj5f5xt22b5gfqd.onion/search?q={query}"
00993|         headers = {"User-Agent": random.choice(USER_AGENTS)}
00994|         response = requests.get(url, headers=headers, timeout=15, proxies={
00995|             "http": "socks5h://127.0.0.1:9150",
00996|             "https": "socks5h://127.0.0.1:9150"
// 进度: 第300行/共399行
00997|         })
00998| 
00999|         if response.status_code == 200:
01000|             soup = BeautifulSoup(response.text, "html.parser")
01001| 
01002|             for a in soup.find_all('a', href=True):
01003|                 try:
01004|                     href = str(a.get('href', ''))
01005|                     title = a.get_text(strip=True)
01006|                     if '.onion' in href.lower() and len(title) > 2:
01007|                         results.append({
01008|                             "title": title[:100] or "暗网资源",
01009|                             "link": href,
01010|                             "source": "TorDex"
01011|                         })
01012|                 except:
01013|                     continue
01014|     except:
01015|         pass
01016| 
// 进度: 第320行/共399行
01017|     return results
01018| 
01019| 
01020| def is_available():
01021|     """检查暗网搜索是否可用"""
01022|     if not ENABLE_DARKWEB:
01023|         return False
01024|     return True
01025| 
01026| 
01027| def get_darkweb_results(refined_query, max_workers=5, advanced_mode=False, tor_port=9150, ui_sites=None):
01028|     """获取暗网搜索结果
01029| 
01030|     Args:
01031|         refined_query: 查询字符串或列表
01032|         max_workers: 最大线程数
01033|         advanced_mode: 是否启用高级模式（需要Tor）
01034|         tor_port: Tor代理端口
01035|         ui_sites: 从UI传递的自定义站点列表
01036|     """
// 进度: 第340行/共399行
01037|     if not ENABLE_DARKWEB:
01038|         return []
01039| 
01040|     # 处理查询（可能是列表或字符串）
01041|     if isinstance(refined_query, list):
01042|         queries = refined_query
01043|     else:
01044|         queries = [refined_query]
01045| 
01046|     results = []
01047| 
01048|     # 对每个查询进行搜索
01049|     for query in queries:
01050|         # 1. 公开暗网搜索引擎（始终可用，无需Tor）
01051|         try:
01052|             search_results = fetch_ahmia_results(query)
01053|             if search_results:
01054|                 results.extend(search_results)
01055|         except:
01056|             pass
// 进度: 第360行/共399行
01057| 
01058|         # 2. 高级模式：使用Tor代理搜索
01059|         if advanced_mode:
01060|             # OnionLink搜索（需要Tor）
01061|             try:
01062|                 search_results = fetch_onionlink_search(query)
01063|                 if search_results:
01064|                     results.extend(search_results)
01065|             except:
01066|                 pass
01067| 
01068|             # TorDex搜索（需要Tor）
01069|             try:
01070|                 search_results = fetch_tordex_search(query)
01071|                 if search_results:
01072|                     results.extend(search_results)
01073|             except:
01074|                 pass
01075| 
01076|         # 3. 自定义暗网站点（支持认证）
// 进度: 第380行/共399行
01077|         custom_sites = get_custom_onion_sites(ui_sites)
01078|         for site in custom_sites:
01079|             try:
01080|                 site_results = search_custom_onion_site(site, query)
01081|                 if site_results:
01082|                     results.extend(site_results)
01083|             except:
01084|                 pass
01085| 
01086|     # 去重
01087|     seen_links = set()
01088|     unique_results = []
01089|     for res in results:
01090|         link = res.get("link", "").rstrip('/')
01091|         if link and link not in seen_links:
01092|             seen_links.add(link)
01093|             unique_results.append(res)
01094| 
01095|     return unique_results
// ==========
// 文件结束: .\darkweb_search.py
// 总行数: 399行
// 下一个文件: [等待添加]
// ==========


第991页：.\llm.py（完整339行）
01096| import re
01097| import openai
01098| from langchain_core.prompts import ChatPromptTemplate
01099| from langchain_core.output_parsers import StrOutputParser
01100| from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
01101| from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
01102| import logging
01103| import re
01104| 
01105| import warnings
01106| 
01107| warnings.filterwarnings("ignore")
01108| 
01109| 
01110| def get_llm(model_choice):
01111|     # Look up the configuration (cloud or local Ollama)
01112|     config = resolve_model_config(model_choice)
01113| 
01114|     if config is None:  # Extra error check
01115|         supported_models = get_model_choices()
// 进度: 第20行/共339行
01116|         raise ValueError(
01117|             f"Unsupported LLM model: '{model_choice}'. "
01118|             f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
01119|         )
01120| 
01121|     # Extract the necessary information from the configuration
01122|     llm_class = config["class"]
01123|     model_specific_params = config["constructor_params"]
01124| 
01125|     # Combine common parameters with model-specific parameters
01126|     # Model-specific parameters will override common ones if there are any conflicts
01127|     all_params = {**_common_llm_params, **model_specific_params}
01128| 
01129|     # Create the LLM instance using the gathered parameters
01130|     llm_instance = llm_class(**all_params)
01131| 
01132|     return llm_instance
01133| 
01134| 
01135| def refine_query(llm, user_input):
// 进度: 第40行/共339行
01136|     """
01137|     查询优化 - 原始查询 + 多语言翻译
01138|     返回: 原始查询 + 英文翻译 + 中文翻译（如果原文不是英文/中文）
01139|     """
01140|     user_input = user_input.strip()
01141| 
01142|     # 简单的拼写错误修复
01143|     common_typos = {
01144|         "sarch": "search",
01145|         "serach": "search",
01146|         "seaech": "search",
01147|         "reuslt": "result",
01148|         "resutl": "result",
01149|     }
01150| 
01151|     words = user_input.split()
01152|     fixed_words = []
01153|     for word in words:
01154|         if word.lower() in common_typos:
01155|             fixed_words.append(common_typos[word.lower()])
// 进度: 第60行/共339行
01156|         else:
01157|             fixed_words.append(word)
01158| 
01159|     original = " ".join(fixed_words)
01160| 
01161|     # 只对有意义的查询添加翻译（避免短查询被膨胀）
01162|     if len(original) < 3:
01163|         return [original]
01164| 
01165|     # 检测语言并生成翻译查询
01166|     queries = [original]  # 原始查询
01167| 
01168|     # 使用简单的语言检测
01169|     has_chinese = any('\u4e00' <= c <= '\u9fff' for c in original)
01170|     has_english = any('a' <= c.lower() <= 'z' for c in original)
01171| 
01172|     # 如果有中文，添加英文翻译
01173|     if has_chinese:
01174|         queries.append(f"{original} English")
01175|         queries.append(f"{original} news")
// 进度: 第80行/共339行
01176| 
01177|     # 如果有英文且长度足够，添加中文翻译
01178|     if has_english and len(original) >= 3:
01179|         queries.append(f"{original} 中文")
01180|         queries.append(f"{original} 新闻")
01181| 
01182|     return queries
01183| 
01184| 
01185| def expand_query_for_search(query_variants):
01186|     """
01187|     将查询变体扩展为搜索字符串
01188|     如果是列表，用 | 分隔多个查询
01189|     """
01190|     if isinstance(query_variants, list):
01191|         return " | ".join(query_variants)
01192|     return query_variants
01193| 
01194| 
01195| def filter_results(llm, query, results):
// 进度: 第100行/共339行
01196|     if not results:
01197|         return []
01198| 
01199|     # 过滤掉PDF链接（LLM无法读取PDF）
01200|     filtered = []
01201|     for r in results:
01202|         link = r.get("link", "") or r.get("url", "") or r.get("pdf_url", "")
01203|         if link.lower().endswith('.pdf') or '.pdf?' in link.lower():
01204|             continue
01205|         filtered.append(r)
01206| 
01207|     if not filtered:
01208|         return []
01209| 
01210|     # 如果全部是PDF，返回空
01211|     if len(filtered) == 0:
01212|         return []
01213| 
01214|     # Extract key query terms for basic filtering
01215|     query_terms = set(query.lower().split()) if isinstance(query, str) else set()
// 进度: 第120行/共339行
01216| 
01217|     # Pre-filter: remove results with NO relevance to query
01218|     prefiltered = []
01219|     for r in results:
01220|         title = r.get("title", "").lower()
01221|         desc = r.get("description", "").lower()
01222|         summary = r.get("summary", "").lower()
01223| 
01224|         # Check if any query term appears in title or description
01225|         has_match = any(term in title or term in desc or term in summary for term in query_terms)
01226| 
01227|         # Also check for Chinese character overlap
01228|         if not has_match and any('\u4e00' <= c <= '\u9fff' for c in query):
01229|             # For Chinese queries, check if any Chinese chars appear
01230|             has_match = any(c in title or c in desc or c in summary for c in query)
01231| 
01232|         if has_match:
01233|             prefiltered.append(r)
01234| 
01235|     # If pre-filtering removed too many, fall back to all results
// 进度: 第140行/共339行
01236|     if len(prefiltered) < len(results) * 0.3:
01237|         prefiltered = results[:min(len(results), 50)]
01238| 
01239|     # Use LLM to further refine
01240|     system_prompt = """
01241| You are a Network Intelligence Analyst. Given a search query and search results, select the MOST RELEVANT results.
01242| 
01243| CRITICAL RULES:
01244| 1. Only select results that are DIRECTLY related to the query topic
01245| 2. For query "九江", do NOT select results about "AI", "人工智能", "machine learning", etc.
01246| 3. Results must match the query's subject matter exactly
01247| 4. Output ONLY a comma-separated list of result indices (e.g., "1,3,5")
01248| 
01249| Search Query: {query}
01250| 
01251| Search Results:
01252| """
01253| 
01254|     final_str = _generate_final_string(prefiltered)
01255| 
// 进度: 第160行/共339行
01256|     prompt_template = ChatPromptTemplate(
01257|         [("system", system_prompt), ("user", "{results}")]
01258|     )
01259|     chain = prompt_template | llm | StrOutputParser()
01260|     try:
01261|         result_indices = chain.invoke({"query": query, "results": final_str})
01262|     except openai.RateLimitError as e:
01263|         print(f"Rate limit error: {e}")
01264|         result_indices = ""
01265| 
01266|     # Parse indices
01267|     parsed_indices = []
01268|     for match in re.findall(r"\d+", result_indices):
01269|         try:
01270|             idx = int(match)
01271|             if 1 <= idx <= len(prefiltered):
01272|                 parsed_indices.append(idx)
01273|         except ValueError:
01274|             continue
01275| 
// 进度: 第180行/共339行
01276|     # Remove duplicates while preserving order
01277|     seen = set()
01278|     parsed_indices = [
01279|         i for i in parsed_indices if not (i in seen or seen.add(i))
01280|     ]
01281| 
01282|     if not parsed_indices:
01283|         # Fallback: use prefiltered results directly
01284|         parsed_indices = list(range(1, min(len(prefiltered), 20) + 1))
01285| 
01286|     top_results = [prefiltered[i - 1] for i in parsed_indices[:20]]
01287| 
01288|     return top_results
01289| 
01290| 
01291| def _generate_final_string(results, truncate=False):
01292|     """
01293|     Generate a formatted string from the search results for LLM processing.
01294|     """
01295| 
// 进度: 第200行/共339行
01296|     if truncate:
01297|         max_title_length = 30
01298|         max_link_length = 0
01299| 
01300|     final_str = []
01301|     for i, res in enumerate(results):
01302|         title = res.get("title", "")
01303|         link = res.get("link", "") or res.get("url", "") or res.get("pdf_url", "")
01304| 
01305|         title = re.sub(r"[^0-9a-zA-Z\-\.\s]", " ", str(title))
01306|         link = re.sub(r"(?<=\.onion).*", "", str(link))
01307| 
01308|         if not link and not title:
01309|             continue
01310| 
01311|         if truncate:
01312|             title = title[:max_title_length] + "..." if len(title) > max_title_length else title
01313|             link = link[:max_link_length] + "..." if len(link) > max_link_length else link
01314| 
01315|         final_str.append(f"{i+1}. {link} - {title}")
// 进度: 第220行/共339行
01316| 
01317|     return "\n".join(s for s in final_str)
01318| 
01319| 
01320| def generate_summary(llm, query, content, search_mode="all"):
01321|     """生成情报报告，根据搜索模式调整分析重点"""
01322| 
01323|     # 调试日志
01324|     print(f"=== LLM INPUT DEBUG ===")
01325|     print(f"Content type: {type(content)}")
01326|     if isinstance(content, dict):
01327|         print(f"Content keys count: {len(content)}")
01328|         print(f"Content keys: {list(content.keys())[:5]}")
01329|         if content:
01330|             first_val = list(content.values())[0]
01331|             print(f"First value length: {len(first_val)}")
01332|             print(f"First value preview: {first_val[:300]}")
01333|     elif isinstance(content, list):
01334|         print(f"Content is list, length: {len(content)}")
01335|     print(f"=======================")
// 进度: 第240行/共339行
01336| 
01337|     # 根据搜索模式设置不同的分析重点
01338|     mode_descriptions = {
01339|         "all": "综合所有来源：网页、新闻、暗网",
01340|         "web": "主要来源：网页搜索结果",
01341|         "news": "主要来源：新闻资讯",
01342|         "darkweb": "主要来源：暗网资源（.onion网站）",
01343|     }
01344| 
01345|     mode_desc = mode_descriptions.get(search_mode, mode_descriptions["all"])
01346| 
01347|     # 强制生成详细分析报告的提示词
01348|     system_prompt = f"""
01349| 你是一位高级网络情报分析师。基于以下搜索结果，请生成一份结构清晰、内容全面的情报分析报告。
01350| 
01351| 查询主题：{query}
01352| 数据来源：{mode_desc}
01353| 
01354| 重要要求：
01355| 1. 报告要全面详细，涵盖所有搜索结果中的关键信息
// 进度: 第260行/共339行
01356| 2. 不要对话或提问，直接给出分析报告
01357| 3. 使用Markdown格式，以##标题组织内容
01358| 4. 核心发现部分用流畅的段落叙述，不要用列表
01359| 5. 每个部分都要有实质性的分析和内容
01360| 
01361| 报告模板结构：
01362| 
01363| ## 一、执行摘要
01364| 
01365| 用3-5句话概括关于"{query}"的核心发现、当前状态和结论。
01366| 
01367| 
01368| ## 二、背景与概述
01369| 
01370| ### 2.1 背景介绍
01371| [领域背景、发展历程、为什么重要]
01372| 
01373| ### 2.2 基本概念
01374| [核心定义、关键术语解释]
01375| 
// 进度: 第280行/共339行
01376| 
01377| ## 三、核心发现
01378| 
01379| [这是报告主体部分，应该占据最多篇幅，用流畅的段落叙述]
01380| 
01381| ### 发现一：[主题]
01382| [详细叙述，包括：时间、地点、人物、事件、影响等]
01383| 
01384| ### 发现二：[主题]
01385| [详细叙述]
01386| 
01387| ### 发现三：[主题]
01388| [详细叙述]
01389| 
01390| 
01391| ## 四、多角度分析
01392| 
01393| ### 4.1 技术维度
01394| [技术原理、现状、趋势、挑战]
01395| 
// 进度: 第300行/共339行
01396| ### 4.2 商业维度
01397| [市场、盈利模式、主要玩家、投资]
01398| 
01399| ### 4.3 社会维度
01400| [影响、公众态度、伦理]
01401| 
01402| ### 4.4 政策与监管维度
01403| [法规、监管、合规]
01404| 
01405| ### 4.5 发展趋势
01406| [短期、中期、长期预测]
01407| 
01408| 
01409| ## 五、关键数据
01410| 
01411| [汇总表格形式的硬数据]
01412| 
01413| 
01414| ## 六、风险与建议
01415| 
// 进度: 第320行/共339行
01416| ### 6.1 主要风险
01417| [1-3个核心风险及影响]
01418| 
01419| ### 6.2 行动建议
01420| [1-3条可执行的建议]
01421| 
01422| 
01423| ## 七、信息来源
01424| 
01425| [链接列表]
01426| 
01427| 请直接生成报告，不要有任何对话或提问。
01428| """
01429| 
01430|     prompt_template = ChatPromptTemplate(
01431|         [("system", system_prompt), ("user", "搜索结果内容:\n{content}")]
01432|     )
01433|     chain = prompt_template | llm | StrOutputParser()
01434|     return chain.invoke({"content": content})
// ==========
// 文件结束: .\llm.py
// 总行数: 339行
// 下一个文件: [等待添加]
// ==========


第1352页：.\llm_utils.py（完整300行）
01435| import requests
01436| from urllib.parse import urljoin
01437| from langchain_openai import ChatOpenAI
01438| from langchain_ollama import ChatOllama
01439| from typing import Callable, Optional, List
01440| from langchain_anthropic import ChatAnthropic
01441| from langchain_google_genai import ChatGoogleGenerativeAI
01442| from langchain_core.callbacks.base import BaseCallbackHandler
01443| from config import OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY, GOOGLE_API_KEY
01444| 
01445| 
01446| class BufferedStreamingHandler(BaseCallbackHandler):
01447|     def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
01448|         self.buffer = ""
01449|         self.buffer_limit = buffer_limit
01450|         self.ui_callback = ui_callback
01451| 
01452|     def on_llm_new_token(self, token: str, **kwargs) -> None:
01453|         self.buffer += token
01454|         if "\n" in token or len(self.buffer) >= self.buffer_limit:
// 进度: 第20行/共300行
01455|             print(self.buffer, end="", flush=True)
01456|             if self.ui_callback:
01457|                 self.ui_callback(self.buffer)
01458|             self.buffer = ""
01459| 
01460|     def on_llm_end(self, response, **kwargs) -> None:
01461|         if self.buffer:
01462|             print(self.buffer, end="", flush=True)
01463|             if self.ui_callback:
01464|                 self.ui_callback(self.buffer)
01465|             self.buffer = ""
01466| 
01467| 
01468| # --- Configuration Data ---
01469| # Instantiate common dependencies once
01470| _common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]
01471| 
01472| # Define common parameters for most LLMs
01473| _common_llm_params = {
01474|     "temperature": 0,
// 进度: 第40行/共300行
01475|     "streaming": True,
01476|     "callbacks": _common_callbacks,
01477| }
01478| 
01479| # Map input model choices (lowercased) to their configuration
01480| # Each config includes the class and any model-specific constructor parameters
01481| _llm_config_map = {
01482|     'gpt-4.1': {
01483|         'class': ChatOpenAI,
01484|         'constructor_params': {'model_name': 'gpt-4.1'}
01485|     },
01486|     'gpt-5.1': {
01487|         'class': ChatOpenAI,
01488|         'constructor_params': {'model_name': 'gpt-5.1'}
01489|     },
01490|     'gpt-5-mini': {
01491|         'class': ChatOpenAI,
01492|         'constructor_params': {'model_name': 'gpt-5-mini'}
01493|     },
01494|     'gpt-5-nano': {
// 进度: 第60行/共300行
01495|         'class': ChatOpenAI,
01496|         'constructor_params': {'model_name': 'gpt-5-nano'}
01497|     },
01498|     'claude-sonnet-4-5': {
01499|         'class': ChatAnthropic,
01500|         'constructor_params': {'model': 'claude-sonnet-4-5'}
01501|     },
01502|     'claude-sonnet-4-0': {
01503|         'class': ChatAnthropic,
01504|         'constructor_params': {'model': 'claude-sonnet-4-0'}
01505|     },
01506|     'gemini-2.5-flash': {
01507|         'class': ChatGoogleGenerativeAI,
01508|         'constructor_params': {'model': 'gemini-2.5-flash', 'google_api_key': GOOGLE_API_KEY }
01509|     },
01510|     'gemini-2.5-flash-lite': {
01511|         'class': ChatGoogleGenerativeAI,
01512|         'constructor_params': {'model': 'gemini-2.5-flash-lite', 'google_api_key': GOOGLE_API_KEY}
01513|     },
01514|     'gemini-2.5-pro': {
// 进度: 第80行/共300行
01515|         'class': ChatGoogleGenerativeAI,
01516|         'constructor_params': {'model': 'gemini-2.5-pro', 'google_api_key': GOOGLE_API_KEY}
01517|     },
01518|     'gpt-5.1-openrouter': {
01519|         'class': ChatOpenAI,
01520|         'constructor_params': {
01521|             'model_name': 'openai/gpt-5.1',
01522|             'base_url': OPENROUTER_BASE_URL,
01523|             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
01524|         }
01525|     },
01526|     'gpt-5-mini-openrouter': {
01527|         'class': ChatOpenAI,
01528|         'constructor_params': {
01529|             'model_name': 'openai/gpt-5-mini',
01530|             'base_url': OPENROUTER_BASE_URL,
01531|             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
01532|         }
01533|     },
01534|     'claude-sonnet-4.5-openrouter': {
// 进度: 第100行/共300行
01535|         'class': ChatOpenAI,
01536|         'constructor_params': {
01537|             'model_name': 'anthropic/claude-sonnet-4.5',
01538|             'base_url': OPENROUTER_BASE_URL,
01539|             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
01540|         }
01541|     },
01542|     'grok-4.1-fast-openrouter': {
01543|         'class': ChatOpenAI,
01544|         'constructor_params': {
01545|             'model_name': 'x-ai/grok-4.1-fast',
01546|             'base_url': OPENROUTER_BASE_URL,
01547|             'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
01548|         }
01549|     },
01550|     # 'llama3.2': {
01551|     #     'class': ChatOllama,
01552|     #     'constructor_params': {'model': 'llama3.2:latest', 'base_url': OLLAMA_BASE_URL}
01553|     # },
01554|     # 'llama3.1': {
// 进度: 第120行/共300行
01555|     #     'class': ChatOllama,
01556|     #     'constructor_params': {'model': 'llama3.1:latest', 'base_url': OLLAMA_BASE_URL}
01557|     # },
01558|     # 'gemma3': {
01559|     #     'class': ChatOllama,
01560|     #     'constructor_params': {'model': 'gemma3:latest', 'base_url': OLLAMA_BASE_URL}
01561|     # },
01562|     # 'deepseek-r1': {
01563|     #     'class': ChatOllama,
01564|     #     'constructor_params': {'model': 'deepseek-r1:latest', 'base_url': OLLAMA_BASE_URL}
01565|     # },
01566| 
01567|     # Add more models here easily:
01568|     # 'mistral7b': {
01569|     #     'class': ChatOllama,
01570|     #     'constructor_params': {'model': 'mistral:7b', 'base_url': OLLAMA_BASE_URL}
01571|     # },
01572|     # 'gpt3.5': {
01573|     #      'class': ChatOpenAI,
01574|     #      'constructor_params': {'model_name': 'gpt-3.5-turbo', 'base_url': OLLAMA_BASE_URL}
// 进度: 第140行/共300行
01575|     # }
01576| }
01577| 
01578| 
01579| def _normalize_model_name(name: str) -> str:
01580|     return name.strip().lower()
01581| 
01582| 
01583| def _get_ollama_base_url() -> Optional[str]:
01584|     if not OLLAMA_BASE_URL:
01585|         return None
01586|     return OLLAMA_BASE_URL.rstrip("/") + "/"
01587| 
01588| 
01589| def fetch_ollama_models() -> List[str]:
01590|     """
01591|     Retrieve the list of locally available Ollama models by querying the Ollama HTTP API.
01592|     Returns an empty list if the API isn't reachable or the base URL is not defined.
01593|     """
01594|     base_url = _get_ollama_base_url()
// 进度: 第160行/共300行
01595|     if not base_url:
01596|         return []
01597| 
01598|     try:
01599|         resp = requests.get(urljoin(base_url, "api/tags"), timeout=3)
01600|         resp.raise_for_status()
01601|         models = resp.json().get("models", [])
01602|         available = []
01603|         for m in models:
01604|             name = m.get("name") or m.get("model")
01605|             if name:
01606|                 available.append(name)
01607|         return available
01608|     except (requests.RequestException, ValueError):
01609|         return []
01610| 
01611| 
01612| def get_model_choices() -> List[str]:
01613|     """
01614|     Combine the statically configured cloud models with the locally available Ollama models and custom models.
// 进度: 第180行/共300行
01615|     """
01616|     base_models = list(_llm_config_map.keys())
01617|     dynamic_models = fetch_ollama_models()
01618| 
01619|     # Import custom models
01620|     try:
01621|         from custom_models import get_custom_model_names
01622|         custom_models = get_custom_model_names()
01623|     except ImportError:
01624|         custom_models = []
01625| 
01626|     normalized = {_normalize_model_name(m): m for m in base_models}
01627| 
01628|     # Add Ollama models
01629|     for dm in dynamic_models:
01630|         key = _normalize_model_name(dm)
01631|         if key not in normalized:
01632|             normalized[key] = dm
01633| 
01634|     # Add custom models
// 进度: 第200行/共300行
01635|     for cm in custom_models:
01636|         key = _normalize_model_name(cm)
01637|         if key not in normalized:
01638|             normalized[key] = cm
01639| 
01640|     # Preserve the order: original base models first, then custom models, then dynamic ones in alphabetical order
01641|     ordered_dynamic = sorted(
01642|         [name for key, name in normalized.items() if name not in base_models and name not in custom_models],
01643|         key=_normalize_model_name,
01644|     )
01645|     return base_models + custom_models + ordered_dynamic
01646| 
01647| 
01648| def resolve_model_config(model_choice: str):
01649|     """
01650|     Resolve a model choice (case-insensitive) to the corresponding configuration.
01651|     Supports predefined remote models, locally installed Ollama models, and custom models.
01652|     """
01653|     model_choice_lower = _normalize_model_name(model_choice)
01654| 
// 进度: 第220行/共300行
01655|     # Check predefined models first
01656|     config = _llm_config_map.get(model_choice_lower)
01657|     if config:
01658|         return config
01659| 
01660|     # Check Ollama models
01661|     for ollama_model in fetch_ollama_models():
01662|         if _normalize_model_name(ollama_model) == model_choice_lower:
01663|             return {
01664|                 "class": ChatOllama,
01665|                 "constructor_params": {"model": ollama_model, "base_url": OLLAMA_BASE_URL},
01666|             }
01667| 
01668|     # Check custom models
01669|     try:
01670|         from custom_models import get_model_config, get_custom_model_names
01671|         for custom_model_name in get_custom_model_names():
01672|             if _normalize_model_name(custom_model_name) == model_choice_lower:
01673|                 model_config = get_model_config(custom_model_name)
01674|                 if model_config:
// 进度: 第240行/共300行
01675|                     model_type = model_config.get("type", "").lower()
01676|                     config_params = model_config.get("config", {})
01677| 
01678|                     # Handle different custom model types
01679|                     if model_type == "openai":
01680|                         return {
01681|                             "class": ChatOpenAI,
01682|                             "constructor_params": {
01683|                                 "model_name": config_params.get("model_name", custom_model_name),
01684|                                 "base_url": config_params.get("base_url"),
01685|                                 "api_key": config_params.get("api_key"),
01686|                             }
01687|                         }
01688|                     elif model_type == "azure openai":
01689|                         return {
01690|                             "class": ChatOpenAI,
01691|                             "constructor_params": {
01692|                                 "model_name": config_params.get("model_name", custom_model_name),
01693|                                 "azure_endpoint": config_params.get("base_url"),
01694|                                 "api_key": config_params.get("api_key"),
// 进度: 第260行/共300行
01695|                                 "api_version": "2024-02-01",
01696|                             }
01697|                         }
01698|                     elif model_type == "ollama":
01699|                         return {
01700|                             "class": ChatOllama,
01701|                             "constructor_params": {
01702|                                 "model": config_params.get("model_name", custom_model_name),
01703|                                 "base_url": config_params.get("base_url", OLLAMA_BASE_URL),
01704|                             }
01705|                         }
01706|                     elif model_type == "anthropic":
01707|                         return {
01708|                             "class": ChatAnthropic,
01709|                             "constructor_params": {
01710|                                 "model": config_params.get("model_name", custom_model_name),
01711|                                 "api_key": config_params.get("api_key"),
01712|                             }
01713|                         }
01714|                     elif model_type == "google":
// 进度: 第280行/共300行
01715|                         return {
01716|                             "class": ChatGoogleGenerativeAI,
01717|                             "constructor_params": {
01718|                                 "model": config_params.get("model_name", custom_model_name),
01719|                                 "google_api_key": config_params.get("api_key"),
01720|                             }
01721|                         }
01722|                     elif model_type in ["cohere", "mistral", "deepseek", "通义千问", "智谱ai", "百度文心一言", "讯飞星火", "moonshot", "01.ai"]:
01723|                         return {
01724|                             "class": ChatOpenAI,
01725|                             "constructor_params": {
01726|                                 "model_name": config_params.get("model_name", custom_model_name),
01727|                                 "base_url": config_params.get("base_url"),
01728|                                 "api_key": config_params.get("api_key"),
01729|                             }
01730|                         }
01731|     except ImportError:
01732|         pass
01733| 
01734|     return None
// 进度: 第300行/共300行
// ==========
// 文件结束: .\llm_utils.py
// 总行数: 300行
// 下一个文件: [等待添加]
// ==========


第1673页：.\ui.py（完整1174行）
01735| """
01736| IntelNexus - Web UI
01737| ==================
01738| Multi-source network intelligence search interface.
01739| Apple-inspired minimalist design.
01740| """
01741| 
01742| import base64
01743| import socket
01744| import streamlit as st
01745| from datetime import datetime
01746| from concurrent.futures import ThreadPoolExecutor
01747| from scrape import scrape_multiple
01748| 
01749| from report_export import export_report, get_export_formats
01750| from web_search import get_web_results
01751| from news_search import get_news_results
01752| from darkweb_search import get_darkweb_results, is_available as darkweb_available
01753| 
01754| from llm_utils import BufferedStreamingHandler, get_model_choices
// 进度: 第20行/共1174行
01755| from llm import get_llm, refine_query, filter_results, generate_summary, expand_query_for_search
01756| from custom_models import add_custom_model, get_custom_model_names, remove_custom_model
01757| 
01758| 
01759| LANG = {
01760|     "zh": {
01761|         "title": "IntelNexus",
01762|         "subtitle": "多源网络情报分析平台",
01763|         "search_placeholder": "输入搜索内容...",
01764|         "search_button": "搜索",
01765|         "search_mode": "搜索模式",
01766|         "settings": "设置",
01767|         "language": "语言",
01768|         "llm_model": "AI模型",
01769|         "threads": "线程数",
01770|         "sources": "数据来源",
01771|         "loading": "加载中...",
01772|         "refining": "优化查询中...",
01773|         "searching": "搜索中...",
01774|         "filtering": "筛选中...",
// 进度: 第40行/共1174行
01775|         "scraping": "抓取内容...",
01776|         "generating": "生成报告中...",
01777|         "refined_query": "优化后的查询",
01778|         "search_results": "搜索结果",
01779|         "filtered_results": "筛选结果",
01780|         "report_title": "情报报告",
01781|         "download": "下载报告",
01782|         "download_format": "下载格式",
01783|         "complete": "完成",
01784|         "darkweb_warning": "暗网搜索：基于公开索引（无需登录）",
01785|         "mode_all": "全部来源",
01786|         "mode_web": "网页搜索",
01787|         "mode_news": "新闻资讯",
01788|         "mode_darkweb": "暗网搜索",
01789|         "results_count": "条结果",
01790|         "zh": "中文",
01791|         "en": "English",
01792|         "add_custom_model": "添加自定义模型",
01793|         "model_name": "模型名称",
01794|         "model_type": "模型类型",
// 进度: 第60行/共1174行
01795|         "base_url": "Base URL (可选)",
01796|         "api_key": "API密钥",
01797|         "model_id": "模型ID",
01798|         "add_model": "添加模型",
01799|         "model_exists": "模型名称已存在或添加失败",
01800|         "fill_fields": "请填写所有必填字段",
01801|         "ok": "确定",
01802|         "deleted": "已删除",
01803|         "custom_models_list": "已添加的模型",
01804|         "model_add_success": "模型已添加",
01805|         "error": "错误",
01806|         "download_ready": "准备下载",
01807|         "download_failed": "下载失败",
01808|         "pdf_ready": "PDF已准备",
01809|         "word_ready": "Word已准备",
01810|         "md_ready": "Markdown已准备",
01811|         "ollama_base_url": "Ollama Base URL",
01812|         "delete": "删除",
01813|         "darkweb_settings": "暗网设置",
01814|         "tor_status": "Tor状态",
// 进度: 第80行/共1174行
01815|         "tor_running": "已运行",
01816|         "tor_not_running": "未运行",
01817|         "tor_port": "Tor端口",
01818|         "detect_tor": "检测Tor",
01819|         "advanced_mode": "高级模式",
01820|         "advanced_mode_desc": "启用Tor代理搜索（需要Tor运行）",
01821|         "breached_forum": "Breached论坛",
01822|         "breached_username": "用户名",
01823|         "breached_password": "密码",
01824|         "breached_register": "没有账号？点击注册",
01825|         "breached_saved": "已保存",
01826|         "tor_setup_guide": "Tor配置指引",
01827|         "tor_download": "下载Tor浏览器",
01828|         "default_mode": "默认模式（仅Ahmia，无需Tor）",
01829|         "breached_hint": "💡 使用自己的账号可访问更多内容",
01830|         "custom_onion_sites": "自定义暗网站点",
01831|         "site_name": "站点名称",
01832|         "site_url": "站点URL",
01833|         "site_need_auth": "需要认证",
01834|         "add_site": "添加站点",
// 进度: 第100行/共1174行
01835|         "added_sites": "已添加的站点",
01836|         "no_sites": "暂无自定义站点",
01837|         "site_saved": "站点已保存",
01838|         "site_deleted": "站点已删除",
01839|     },
01840|     "en": {
01841|         "title": "IntelNexus",
01842|         "subtitle": "Multi-Source Network Intelligence Platform",
01843|         "search_placeholder": "Enter search query...",
01844|         "search_button": "Search",
01845|         "search_mode": "Search Mode",
01846|         "settings": "Settings",
01847|         "language": "Language",
01848|         "llm_model": "AI Model",
01849|         "threads": "Threads",
01850|         "sources": "Data Sources",
01851|         "loading": "Loading...",
01852|         "refining": "Refining query...",
01853|         "searching": "Searching...",
01854|         "filtering": "Filtering...",
// 进度: 第120行/共1174行
01855|         "scraping": "Scraping content...",
01856|         "generating": "Generating report...",
01857|         "refined_query": "Refined Query",
01858|         "search_results": "Search Results",
01859|         "filtered_results": "Filtered Results",
01860|         "report_title": "Intelligence Report",
01861|         "download": "Download",
01862|         "download_format": "Format",
01863|         "complete": "Complete",
01864|         "darkweb_warning": "Dark web: Based on public indexes (no login required)",
01865|         "mode_all": "All Sources",
01866|         "mode_web": "Web Search",
01867|         "mode_news": "News",
01868|         "mode_darkweb": "Dark Web",
01869|         "results_count": "results",
01870|         "zh": "Chinese",
01871|         "en": "English",
01872|         "add_custom_model": "Add Custom Model",
01873|         "model_name": "Model Name",
01874|         "model_type": "Model Type",
// 进度: 第140行/共1174行
01875|         "base_url": "Base URL (optional)",
01876|         "api_key": "API Key",
01877|         "model_id": "Model ID",
01878|         "add_model": "Add Model",
01879|         "model_exists": "Model name already exists or failed to add",
01880|         "fill_fields": "Please fill all required fields",
01881|         "ok": "OK",
01882|         "deleted": "Deleted",
01883|         "custom_models_list": "Custom Models",
01884|         "model_add_success": "Model added",
01885|         "error": "Error",
01886|         "download_ready": "Ready to download",
01887|         "download_failed": "Download failed",
01888|         "pdf_ready": "PDF Ready",
01889|         "word_ready": "Word Ready",
01890|         "md_ready": "Markdown Ready",
01891|         "ollama_base_url": "Ollama Base URL",
01892|         "delete": "Delete",
01893|         "darkweb_settings": "Dark Web Settings",
01894|         "tor_status": "Tor Status",
// 进度: 第160行/共1174行
01895|         "tor_running": "Running",
01896|         "tor_not_running": "Not Running",
01897|         "tor_port": "Tor Port",
01898|         "detect_tor": "Detect Tor",
01899|         "advanced_mode": "Advanced Mode",
01900|         "advanced_mode_desc": "Enable Tor proxy search (requires Tor running)",
01901|         "breached_forum": "Breached Forum",
01902|         "breached_username": "Username",
01903|         "breached_password": "Password",
01904|         "breached_register": "No account? Click to register",
01905|         "breached_saved": "Saved",
01906|         "tor_setup_guide": "Tor Setup Guide",
01907|         "tor_download": "Download Tor Browser",
01908|         "default_mode": "Default mode (Ahmia only, no Tor needed)",
01909|         "breached_hint": "💡 Use your own account to access more content",
01910|         "custom_onion_sites": "Custom Onion Sites",
01911|         "site_name": "Site Name",
01912|         "site_url": "Site URL",
01913|         "site_need_auth": "Requires Auth",
01914|         "add_site": "Add Site",
// 进度: 第180行/共1174行
01915|         "added_sites": "Added Sites",
01916|         "no_sites": "No custom sites yet",
01917|         "site_saved": "Site saved",
01918|         "site_deleted": "Site deleted",
01919|     }
01920| }
01921| 
01922| SEARCH_MODES = {
01923|     "all": ["mode_all", "全部来源"],
01924|     "web": ["mode_web", "网页搜索"],
01925|     "news": ["mode_news", "新闻资讯"],
01926|     "darkweb": ["mode_darkweb", "暗网搜索"],
01927| }
01928| 
01929| BREACHED_URL = "http://breachedmw4otc2lhx7nqe4wyxfhpvy32ooz26opvqkmmrbg73c7ooad.onion"
01930| DEFAULT_TOR_PORT = 9150
01931| 
01932| def check_tor_status(port=DEFAULT_TOR_PORT):
01933|     """检测Tor代理端口是否开放"""
01934|     try:
// 进度: 第200行/共1174行
01935|         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
01936|         sock.settimeout(2)
01937|         result = sock.connect_ex(('127.0.0.1', port))
01938|         sock.close()
01939|         return result == 0
01940|     except:
01941|         return False
01942| 
01943| def get_tor_port():
01944|     """获取Tor代理端口"""
01945|     return st.session_state.get("tor_port", DEFAULT_TOR_PORT)
01946| 
01947| 
01948| def get_text(key):
01949|     lang_code = st.session_state.get("lang", "zh")
01950|     return LANG.get(lang_code, LANG["zh"]).get(key, key)
01951| 
01952| 
01953| @st.cache_data(ttl=200, show_spinner=False)
01954| def cached_search(mode, refined_query, threads, advanced_mode=False, tor_port=DEFAULT_TOR_PORT, ui_sites=None):
// 进度: 第220行/共1174行
01955|     results = []
01956| 
01957|     with ThreadPoolExecutor(max_workers=threads) as executor:
01958|         futures = []
01959| 
01960|         if mode in ["web", "all"]:
01961|             futures.append(executor.submit(get_web_results, refined_query, threads, 40))
01962| 
01963|         if mode in ["news", "all"]:
01964|             futures.append(executor.submit(get_news_results, refined_query, 30))
01965| 
01966|         if mode in ["darkweb", "all"]:
01967|             if darkweb_available():
01968|                 futures.append(executor.submit(get_darkweb_results, refined_query, threads, advanced_mode, tor_port, ui_sites))
01969|             else:
01970|                 print("警告: 暗网搜索已启用但Tor未连接或Ahmia不可用")
01971| 
01972|         for f in futures:
01973|             try:
01974|                 results.extend(f.result())
// 进度: 第240行/共1174行
01975|             except Exception as e:
01976|                 print(f"Search error: {e}")
01977| 
01978|     return results
01979| 
01980| 
01981| @st.cache_data(ttl=200, show_spinner=False)
01982| def cached_scrape(filtered, threads):
01983|     return scrape_multiple(filtered, max_workers=threads)
01984| 
01985| 
01986| st.set_page_config(
01987|     page_title="IntelNexus",
01988|     page_icon=None,
01989|     initial_sidebar_state="expanded",
01990| )
01991| 
01992| # Force Light theme
01993| st.markdown("""
01994| <style>
// 进度: 第260行/共1174行
01995|     /* Force Light Theme */
01996|     .stApp {
01997|         background-color: #FFFFFF !important;
01998|         color: #1E1E1E !important;
01999|     }
02000|     [data-testid="stSidebar"] {
02001|         background-color: #F5F5F5 !important;
02002|     }
02003|     div[data-testid="stMarkdownContainer"] {
02004|         color: #1E1E1E !important;
02005|     }
02006|     .stTextInput > div > div > input {
02007|         background-color: #FFFFFF !important;
02008|         color: #1E1E1E !important;
02009|     }
02010|     /* Remove dark theme gradient background */
02011|     header[data-testid="stHeader"] {
02012|         background-color: transparent !important;
02013|     }
02014|     .stDeployButton {
// 进度: 第280行/共1174行
02015|         display: none !important;
02016|     }
02017| </style>
02018| """, unsafe_allow_html=True)
02019| 
02020| if "lang" not in st.session_state:
02021|     st.session_state.lang = "zh"
02022| 
02023| if "query_cache" not in st.session_state:
02024|     st.session_state.query_cache = ""
02025| 
02026| st.markdown("""
02027| <style>
02028|     @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Text:wght@300;400;500;600&display=swap');
02029| 
02030|     :root {
02031|         --morandi-bg: #E8E4DF;
02032|         --morandi-sidebar: #DCD8D3;
02033|         --morandi-card: #F5F2EE;
02034|         --morandi-blue: #7B9CB5;
// 进度: 第300行/共1174行
02035|         --morandi-green: #8FA890;
02036|         --morandi-pink: #C4A4A4;
02037|         --morandi-peach: #D4A5A5;
02038|         --morandi-text: #5C5C5C;
02039|         --morandi-text-light: #8A8A8A;
02040|         --morandi-border: #C9C5C0;
02041|         --morandi-accent: #9CB5B0;
02042|     }
02043| 
02044|     #stDecoration {
02045|         display: none !important;
02046|     }
02047| 
02048|     * {
02049|         font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif !important;
02050|     }
02051| 
02052|     .stApp {
02053|         background: var(--morandi-bg);
02054|     }
// 进度: 第320行/共1174行
02055| 
02056|     div[data-testid="stSidebar"] {
02057|         background: var(--morandi-sidebar);
02058|         border-right: 1px solid var(--morandi-border);
02059|     }
02060| 
02061|     .sidebar-title {
02062|         font-size: 20px;
02063|         font-weight: 600;
02064|         color: var(--morandi-text);
02065|         padding: 20px 16px 10px;
02066|     }
02067| 
02068|     .sidebar-subtitle {
02069|         font-size: 13px;
02070|         color: var(--morandi-text-light);
02071|         padding: 0 16px 20px;
02072|     }
02073| 
02074|     .main-title {
// 进度: 第340行/共1174行
02075|         font-size: 40px;
02076|         font-weight: 600;
02077|         color: var(--morandi-text);
02078|         letter-spacing: -0.02em;
02079|     }
02080| 
02081|     .main-subtitle {
02082|         font-size: 19px;
02083|         font-weight: 400;
02084|         color: var(--morandi-text-light);
02085|         margin-top: 4px;
02086|     }
02087| 
02088|     .search-input input {
02089|         border-radius: 14px !important;
02090|         border: 1px solid var(--morandi-border) !important;
02091|         padding: 14px 18px !important;
02092|         font-size: 17px !important;
02093|         background: #FFFFFF !important;
02094|         color: var(--morandi-text) !important;
// 进度: 第360行/共1174行
02095|         transition: all 0.3s ease !important;
02096|     }
02097| 
02098|     .search-input input:focus {
02099|         border-color: var(--morandi-blue) !important;
02100|         box-shadow: 0 0 0 3px rgba(123, 156, 181, 0.15) !important;
02101|         outline: none !important;
02102|     }
02103| 
02104|     .search-input input::placeholder {
02105|         color: var(--morandi-text-light) !important;
02106|     }
02107| 
02108|     .search-button button {
02109|         border-radius: 14px !important;
02110|         background: var(--morandi-blue) !important;
02111|         border: none !important;
02112|         padding: 14px 28px !important;
02113|         font-size: 17px !important;
02114|         font-weight: 500 !important;
// 进度: 第380行/共1174行
02115|         color: #FFFFFF !important;
02116|         transition: all 0.3s ease !important;
02117|     }
02118| 
02119|     .search-button button:hover {
02120|         background: #6B8BA5 !important;
02121|         transform: translateY(-1px);
02122|     }
02123| 
02124|     .search-button button:active {
02125|         transform: scale(0.98) translateY(0);
02126|     }
02127| 
02128|     div[data-testid="stRadio"] > div {
02129|         gap: 8px;
02130|     }
02131| 
02132|     div[data-testid="stRadio"] label {
02133|         border-radius: 12px !important;
02134|         padding: 12px 16px !important;
// 进度: 第400行/共1174行
02135|         background: var(--morandi-sidebar) !important;
02136|         border: 1px solid transparent !important;
02137|         transition: all 0.2s ease !important;
02138|         color: var(--morandi-text) !important;
02139|     }
02140| 
02141|     div[data-testid="stRadio"] label:hover {
02142|         background: var(--morandi-sidebar) !important;
02143|     }
02144| 
02145|     div[data-testid="stRadio"] input:checked + div {
02146|         background: var(--morandi-sidebar) !important;
02147|         border-color: transparent !important;
02148|         color: var(--morandi-text) !important;
02149|     }
02150| 
02151|     div[data-testid="stSelectbox"] > div {
02152|         background: var(--morandi-sidebar) !important;
02153|         border: 1px solid var(--morandi-border) !important;
02154|         border-radius: 12px !important;
// 进度: 第420行/共1174行
02155|     }
02156| 
02157|     div[data-testid="stSelectbox"] > div:focus-within {
02158|         border-color: var(--morandi-border) !important;
02159|         box-shadow: none !important;
02160|     }
02161| 
02162|     .lang-switch {
02163|         display: flex;
02164|         gap: 8px;
02165|         padding: 12px 16px;
02166|     }
02167| 
02168|     .lang-btn {
02169|         padding: 8px 16px;
02170|         border-radius: 20px;
02171|         font-size: 13px;
02172|         cursor: pointer;
02173|         border: 1px solid var(--morandi-border);
02174|         background: var(--morandi-card);
// 进度: 第440行/共1174行
02175|         color: var(--morandi-text);
02176|         transition: all 0.2s;
02177|     }
02178| 
02179|     .lang-btn:hover {
02180|         background: #E5E1DC;
02181|     }
02182| 
02183|     .lang-btn.active {
02184|         background: var(--morandi-green);
02185|         color: #FFFFFF;
02186|         border-color: var(--morandi-green);
02187|     }
02188| 
02189|     .result-card {
02190|         background: var(--morandi-card);
02191|         border-radius: 18px;
02192|         padding: 24px;
02193|         margin: 16px 0;
02194|         box-shadow: 0 4px 16px rgba(0,0,0,0.06);
// 进度: 第460行/共1174行
02195|         border: 1px solid var(--morandi-border);
02196|     }
02197| 
02198|     .result-title {
02199|         font-size: 15px;
02200|         font-weight: 600;
02201|         color: var(--morandi-text);
02202|         margin-bottom: 8px;
02203|     }
02204| 
02205|     .result-stats {
02206|         display: flex;
02207|         gap: 16px;
02208|         margin-top: 16px;
02209|         padding-top: 16px;
02210|         border-top: 1px solid var(--morandi-border);
02211|     }
02212| 
02213|     .stat-item {
02214|         text-align: center;
// 进度: 第480行/共1174行
02215|     }
02216| 
02217|     .stat-value {
02218|         font-size: 24px;
02219|         font-weight: 600;
02220|         color: var(--morandi-text);
02221|     }
02222| 
02223|     .stat-label {
02224|         font-size: 12px;
02225|         color: var(--morandi-text-light);
02226|         margin-top: 4px;
02227|     }
02228| 
02229|     .report-section {
02230|         background: var(--morandi-card);
02231|         border-radius: 18px;
02232|         padding: 24px;
02233|         margin: 16px 0;
02234|         box-shadow: 0 4px 16px rgba(0,0,0,0.06);
// 进度: 第500行/共1174行
02235|         border: 1px solid var(--morandi-border);
02236|     }
02237| 
02238|     .report-title {
02239|         font-size: 22px;
02240|         font-weight: 600;
02241|         color: var(--morandi-text);
02242|         margin-bottom: 16px;
02243|         padding-bottom: 12px;
02244|         border-bottom: 1px solid var(--morandi-border);
02245|     }
02246| 
02247|     .download-btn {
02248|         display: inline-block;
02249|         padding: 12px 24px;
02250|         background: var(--morandi-green);
02251|         border-radius: 12px;
02252|         color: #FFFFFF;
02253|         text-decoration: none;
02254|         font-weight: 500;
// 进度: 第520行/共1174行
02255|         transition: all 0.3s;
02256|     }
02257| 
02258|     .download-btn:hover {
02259|         background: #7F9680;
02260|         transform: translateY(-1px);
02261|     }
02262| 
02263|     .section-header {
02264|         font-size: 13px;
02265|         font-weight: 600;
02266|         color: var(--morandi-text-light);
02267|         text-transform: uppercase;
02268|         letter-spacing: 0.5px;
02269|         margin-bottom: 12px;
02270|     }
02271| 
02272|     div.stButton > button {
02273|         border-radius: 12px;
02274|     }
// 进度: 第540行/共1174行
02275| 
02276|     div[data-testid="stSelectbox"] > div > div {
02277|         border-radius: 12px;
02278|     }
02279| 
02280|     div[data-testid="stSlider"] > div > div {
02281|         border-radius: 12px;
02282|     }
02283| 
02284|     .stSuccess {
02285|         background: var(--morandi-green);
02286|         color: #FFFFFF;
02287|         border-radius: 12px;
02288|     }
02289| 
02290|     .stSpinner > div > div {
02291|         border-top-color: var(--morandi-blue);
02292|     }
02293| 
02294|     div[data-testid="stMarkdownContainer"] p {
// 进度: 第560行/共1174行
02295|         color: var(--morandi-text);
02296|     }
02297| 
02298|     .stTextInput > div > div > input {
02299|         border-radius: 14px !important;
02300|     }
02301| 
02302|     header {
02303|         background: none !important;
02304|     }
02305| 
02306|     [data-testid="stHeaderContainer"] {
02307|         background: var(--morandi-bg) !important;
02308|     }
02309| 
02310|     div[data-testid="stHeaderContainer"]::before {
02311|         display: none !important;
02312|     }
02313| </style>
02314| """, unsafe_allow_html=True)
// 进度: 第580行/共1174行
02315| 
02316| 
02317| with st.sidebar:
02318|     st.markdown(f'<div class="sidebar-title">{get_text("title")}</div>', unsafe_allow_html=True)
02319|     st.markdown(f'<div class="sidebar-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
02320| 
02321|     st.markdown("---")
02322|     st.markdown(f'<div class="section-header">{get_text("search_mode")}</div>', unsafe_allow_html=True)
02323| 
02324|     mode_options = list(SEARCH_MODES.keys())
02325|     search_mode = st.radio(
02326|         "mode",
02327|         mode_options,
02328|         format_func=lambda x: get_text(SEARCH_MODES[x][0]),
02329|         label_visibility="collapsed",
02330|         index=0
02331|     )
02332| 
02333|     if search_mode == "darkweb" and not darkweb_available():
02334|         st.warning(get_text("darkweb_warning"))
// 进度: 第600行/共1174行
02335| 
02336|     # 暗网设置区域
02337|     if search_mode == "darkweb":
02338|         st.markdown("---")
02339|         with st.expander(f"🧅 {get_text('darkweb_settings')}", expanded=True):
02340|             # Tor状态检测
02341|             tor_port = st.number_input(
02342|                 get_text("tor_port"),
02343|                 min_value=1,
02344|                 max_value=65535,
02345|                 value=st.session_state.get("tor_port", DEFAULT_TOR_PORT),
02346|                 key="tor_port"
02347|             )
02348| 
02349|             # 检测Tor状态
02350|             tor_running = check_tor_status(tor_port)
02351|             if tor_running:
02352|                 st.success(f"🟢 {get_text('tor_running')}")
02353|             else:
02354|                 st.error(f"🔴 {get_text('tor_not_running')}")
// 进度: 第620行/共1174行
02355| 
02356|             col_tor1, col_tor2 = st.columns([1, 1])
02357|             with col_tor1:
02358|                 if st.button(get_text("detect_tor"), key="detect_tor_btn"):
02359|                     st.rerun()
02360| 
02361|             # 高级模式选项
02362|             advanced_mode = st.checkbox(
02363|                 get_text("advanced_mode"),
02364|                 value=st.session_state.get("advanced_mode", False),
02365|                 help=get_text("advanced_mode_desc"),
02366|                 key="advanced_mode"
02367|             )
02368| 
02369|             if not tor_running and advanced_mode:
02370|                 st.warning(f"⚠️ {get_text('tor_not_running')} - {get_text('default_mode')}")
02371| 
02372|             # Breached论坛配置
02373|             st.markdown("---")
02374|             st.markdown(f"**{get_text('breached_forum')}**")
// 进度: 第640行/共1174行
02375| 
02376|             # 注册链接 + 提示
02377|             st.markdown(f"""
02378|             <a href="{BREACHED_URL}" target="_blank" style="text-decoration: none;">
02379|                 <span style="color: #4A90D9;">🔗 {get_text('breached_register')}</span>
02380|             </a>
02381|             <br><br>
02382|             <span style="color: #6B7280; font-size: 0.9em;">{get_text('breached_hint')}</span>
02383|             """, unsafe_allow_html=True)
02384| 
02385|             col_breach1, col_breach2 = st.columns(2)
02386|             with col_breach1:
02387|                 breached_user = st.text_input(
02388|                     get_text("breached_username"),
02389|                     value=st.session_state.get("breached_username", ""),
02390|                     key="breached_user"
02391|                 )
02392|             with col_breach2:
02393|                 breached_pass = st.text_input(
02394|                     get_text("breached_password"),
// 进度: 第660行/共1174行
02395|                     value=st.session_state.get("breached_password", ""),
02396|                     type="password",
02397|                     key="breached_pass"
02398|                 )
02399| 
02400|             if breached_user and breached_pass:
02401|                 st.session_state.breached_username = breached_user
02402|                 st.session_state.breached_password = breached_pass
02403|                 st.success(f"✓ {get_text('breached_saved')}")
02404| 
02405|             # 自定义暗网站点配置
02406|             st.markdown("---")
02407|             st.markdown(f"**{get_text('custom_onion_sites')}**")
02408| 
02409|             # 初始化自定义站点列表
02410|             if "custom_onion_sites" not in st.session_state:
02411|                 st.session_state.custom_onion_sites = []
02412| 
02413|             # 添加新站点表单（使用container代替expander避免嵌套）
02414|             with st.container():
// 进度: 第680行/共1174行
02415|                 st.markdown(f"**{get_text('add_site')}**")
02416|                 col_site1, col_site2 = st.columns(2)
02417|                 with col_site1:
02418|                     new_site_name = st.text_input(
02419|                         get_text("site_name"),
02420|                         key="new_site_name",
02421|                         placeholder="My Site"
02422|                     )
02423|                     new_site_url = st.text_input(
02424|                         get_text("site_url"),
02425|                         key="new_site_url",
02426|                         placeholder="http://xxx.onion/search?q="
02427|                     )
02428|                 with col_site2:
02429|                     new_site_auth = st.checkbox(
02430|                         get_text("site_need_auth"),
02431|                         key="new_site_auth"
02432|                     )
02433|                     new_site_user = ""
02434|                     new_site_pass = ""
// 进度: 第700行/共1174行
02435|                     if new_site_auth:
02436|                         new_site_user = st.text_input(
02437|                             get_text("breached_username"),
02438|                             key="new_site_user"
02439|                         )
02440|                         new_site_pass = st.text_input(
02441|                             get_text("breached_password"),
02442|                             type="password",
02443|                             key="new_site_pass"
02444|                         )
02445| 
02446|                 if st.button(get_text("add_site"), key="add_site_btn"):
02447|                     if new_site_name and new_site_url:
02448|                         new_site = {
02449|                             "name": new_site_name,
02450|                             "url": new_site_url,
02451|                         }
02452|                         if new_site_auth and new_site_user and new_site_pass:
02453|                             new_site["auth"] = {
02454|                                 "type": "basic",
// 进度: 第720行/共1174行
02455|                                 "username": new_site_user,
02456|                                 "password": new_site_pass
02457|                             }
02458|                         # 保存到session
02459|                         st.session_state.custom_onion_sites.append(new_site)
02460|                         # 持久化保存到文件
02461|                         try:
02462|                             import json
02463|                             import os
02464|                             os.makedirs("data", exist_ok=True)
02465|                             sites_file = "data/custom_onion_sites.json"
02466|                             with open(sites_file, "w", encoding="utf-8") as f:
02467|                                 json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
02468|                         except Exception as e:
02469|                             print(f"保存站点失败: {e}")
02470|                         st.success(f"✓ {get_text('site_saved')}")
02471|                         st.rerun()
02472| 
02473|             # 显示已添加的站点
02474|             # 尝试从文件加载站点
// 进度: 第740行/共1174行
02475|             try:
02476|                 import json
02477|                 sites_file = "data/custom_onion_sites.json"
02478|                 if os.path.exists(sites_file):
02479|                     with open(sites_file, "r", encoding="utf-8") as f:
02480|                         loaded_sites = json.load(f)
02481|                         if loaded_sites and not st.session_state.custom_onion_sites:
02482|                             st.session_state.custom_onion_sites = loaded_sites
02483|             except:
02484|                 pass
02485| 
02486|             if st.session_state.custom_onion_sites:
02487|                 st.markdown(f"**{get_text('added_sites')}**")
02488|                 for i, site in enumerate(st.session_state.custom_onion_sites):
02489|                     col_site, col_del = st.columns([4, 1])
02490|                     with col_site:
02491|                         auth_info = " 🔒" if site.get("auth") else ""
02492|                         st.markdown(f"- {site.get('name', 'Unknown')}{auth_info}")
02493|                     with col_del:
02494|                         if st.button("🗑️", key=f"del_site_{i}"):
// 进度: 第760行/共1174行
02495|                             st.session_state.custom_onion_sites.pop(i)
02496|                             # 更新文件
02497|                             try:
02498|                                 import json
02499|                                 import os
02500|                                 sites_file = "data/custom_onion_sites.json"
02501|                                 with open(sites_file, "w", encoding="utf-8") as f:
02502|                                     json.dump(st.session_state.custom_onion_sites, f, ensure_ascii=False, indent=2)
02503|                             except:
02504|                                 pass
02505|                             st.rerun()
02506|             else:
02507|                 st.markdown(f"_{get_text('no_sites')}_")
02508| 
02509|     st.markdown("---")
02510|     st.markdown(f'<div class="section-header">{get_text("settings")}</div>', unsafe_allow_html=True)
02511| 
02512|     model_options = get_model_choices()
02513|     default_model = "qwen2.5:7b" if "qwen2.5:7b" in model_options else (model_options[0] if model_options else "gpt-4o")
02514|     model_index = model_options.index(default_model) if default_model in model_options else 0
// 进度: 第780行/共1174行
02515| 
02516|     model = st.selectbox(get_text("llm_model"), model_options, index=model_index)
02517|     threads = st.slider(get_text("threads"), 1, 16, 5)
02518| 
02519|     # 语言切换 - 在设置中
02520|     lang_options = {get_text("zh"): "zh", get_text("en"): "en"}
02521|     current_lang_display = get_text("zh") if st.session_state.lang == "zh" else get_text("en")
02522|     selected_lang = st.selectbox(get_text("language"), list(lang_options.keys()),
02523|                                   index=0 if st.session_state.lang == "zh" else 1,
02524|                                   key="lang_selector")
02525|     if lang_options.get(selected_lang) != st.session_state.lang:
02526|         st.session_state.lang = lang_options[selected_lang]
02527|         st.rerun()
02528| 
02529|     # 自定义模型管理
02530|     st.markdown("---")
02531|     with st.expander(get_text("add_custom_model")):
02532|         col_name, col_type = st.columns(2)
02533|         with col_name:
02534|             custom_model_name = st.text_input(
// 进度: 第800行/共1174行
02535|                 get_text("model_name"),
02536|                 key="custom_model_name"
02537|             )
02538|         with col_type:
02539|             model_type = st.selectbox(
02540|                 get_text("model_type"),
02541|                 [
02542|                     "OpenAI", "Azure OpenAI", "Anthropic", "Google", "Cohere",
02543|                     "Mistral", "DeepSeek", "Ollama", "通义千问", "智谱AI",
02544|                     "百度文心一言", "讯飞星火", "Moonshot", "01.AI"
02545|                 ],
02546|                 key="model_type_selector"
02547|             )
02548| 
02549|         if model_type == "OpenAI":
02550|             base_url = st.text_input(get_text("base_url"))
02551|             api_key = st.text_input(get_text("api_key"), type="password", key="openai_api_key")
02552|             model_id = st.text_input(get_text("model_id"))
02553|         elif model_type == "Anthropic":
02554|             api_key = st.text_input(get_text("api_key"), type="password", key="anthropic_api_key")
// 进度: 第820行/共1174行
02555|             model_id = st.text_input(get_text("model_id"))
02556|         elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
02557|             api_key = st.text_input(get_text("api_key"), type="password", key=f"{model_type.lower()}_api_key")
02558|             base_url = st.text_input(get_text("base_url"), key=f"{model_type.lower()}_base_url")
02559|             model_id = st.text_input(get_text("model_id"))
02560|         else:  # Ollama
02561|             base_url = st.text_input(get_text("ollama_base_url"), value="http://127.0.0.1:11434", key="ollama_base_url")
02562|             api_key = None
02563|             model_id = st.text_input(get_text("model_name"))
02564| 
02565|         if st.button(get_text("add_model")):
02566|             if custom_model_name and model_id:
02567|                 config = {"model_name": model_id}
02568|                 if model_type in ["OpenAI", "Azure OpenAI"]:
02569|                     if base_url:
02570|                         config["base_url"] = base_url
02571|                     if api_key:
02572|                         config["api_key"] = api_key
02573|                 elif model_type == "Anthropic":
02574|                     if api_key:
// 进度: 第840行/共1174行
02575|                         config["api_key"] = api_key
02576|                 elif model_type in ["Google", "Cohere", "Mistral", "DeepSeek", "通义千问", "智谱AI", "百度文心一言", "讯飞星火", "Moonshot", "01.AI"]:
02577|                     if api_key:
02578|                         config["api_key"] = api_key
02579|                     if base_url:
02580|                         config["base_url"] = base_url
02581|                 else:  # Ollama
02582|                     config["base_url"] = base_url
02583| 
02584|                 if add_custom_model(custom_model_name, model_type.lower(), config):
02585|                     st.success(get_text("model_add_success"))
02586|                     st.rerun()
02587|                 else:
02588|                     st.error(get_text("model_exists"))
02589|             else:
02590|                 st.error(get_text("fill_fields"))
02591| 
02592|     # 显示已添加的自定义模型
02593|     custom_models = get_custom_model_names()
02594|     if custom_models:
// 进度: 第860行/共1174行
02595|         with st.expander(get_text("custom_models_list")):
02596|             for custom_model in custom_models:
02597|                 col_model, col_delete = st.columns([3, 1])
02598|                 with col_model:
02599|                     st.write(custom_model)
02600|                 with col_delete:
02601|                     if st.button(get_text("delete"), key=f"delete_{custom_model}"):
02602|                         if remove_custom_model(custom_model):
02603|                             st.success(get_text("deleted"))
02604|                             st.rerun()
02605| 
02606|     st.markdown("---")
02607|     st.markdown(f'<div class="section-header">{get_text("download_format")}</div>', unsafe_allow_html=True)
02608| 
02609|     # 初始化下载格式
02610|     if "sidebar_download_format" not in st.session_state:
02611|         st.session_state.sidebar_download_format = "md"
02612| 
02613|     # 初始化下载状态（用于解决页面消失问题）
02614|     if "download_ready" not in st.session_state:
// 进度: 第880行/共1174行
02615|         st.session_state.download_ready = False
02616|     if "download_data" not in st.session_state:
02617|         st.session_state.download_data = None
02618|     if "download_filename" not in st.session_state:
02619|         st.session_state.download_filename = None
02620|     if "download_mime" not in st.session_state:
02621|         st.session_state.download_mime = None
02622| 
02623|     format_options = ["md", "pdf", "docx", "xlsx"]
02624|     format_labels = {
02625|         "md": "Markdown",
02626|         "pdf": "PDF",
02627|         "docx": "Word",
02628|         "xlsx": "Excel"
02629|     }
02630| 
02631|     sidebar_format = st.selectbox(
02632|         "选择下载格式",
02633|         format_options,
02634|         format_func=lambda x: format_labels[x],
// 进度: 第900行/共1174行
02635|         label_visibility="collapsed",
02636|         key="sidebar_format_select"
02637|     )
02638|     st.session_state.sidebar_download_format = sidebar_format
02639| 
02640|     st.markdown("---")
02641|     st.markdown(f'<div class="section-header">{get_text("sources")}</div>', unsafe_allow_html=True)
02642|     st.caption("Semantic Scholar, RSS, Reddit, Bing")
02643| 
02644| 
02645| col1, col2 = st.columns([8, 2])
02646| with col1:
02647|     st.markdown(f'<div class="main-title">{get_text("title")}</div>', unsafe_allow_html=True)
02648|     st.markdown(f'<div class="main-subtitle">{get_text("subtitle")}</div>', unsafe_allow_html=True)
02649| 
02650| with st.form("search_form", clear_on_submit=False):
02651|     col_input, col_button = st.columns([10, 1])
02652|     with col_input:
02653|         query = st.text_input(
02654|             "query",
// 进度: 第920行/共1174行
02655|             placeholder=get_text("search_placeholder"),
02656|             label_visibility="collapsed",
02657|             key="query_input"
02658|         )
02659|     with col_button:
02660|         run_button = st.form_submit_button(get_text("search_button"))
02661| 
02662| status_slot = st.empty()
02663| 
02664| # 搜索逻辑
02665| if run_button and query:
02666|     # 保存搜索词到session_state
02667|     st.session_state.query_cache = query
02668|     st.session_state.search_mode_cache = search_mode
02669|     st.session_state.threads_cache = threads
02670|     st.session_state.model_cache = model
02671| 
02672|     # 清空之前的搜索结果
02673|     for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
02674|         st.session_state.pop(k, None)
// 进度: 第940行/共1174行
02675| 
02676|     with status_slot.container():
02677|         with st.spinner(get_text("loading")):
02678|             llm = get_llm(model)
02679| 
02680|     with status_slot.container():
02681|         with st.spinner(get_text("refining")):
02682|             # refine_query现在返回查询列表（原始+翻译）
02683|             query_variants = refine_query(llm, query)
02684|             # 保存原始查询用于导出
02685|             st.session_state.refined = query
02686|             # 转换为搜索字符串
02687|             search_query = expand_query_for_search(query_variants)
02688| 
02689|     st.markdown(f"""
02690|     <div class="result-card">
02691|         <div class="section-header">{get_text("refined_query")}</div>
02692|         <div class="result-title">原始查询: {query}</div>
02693|         <div class="result-title" style="color: var(--morandi-blue);">多语言查询: {search_query}</div>
02694|     </div>
// 进度: 第960行/共1174行
02695|     """, unsafe_allow_html=True)
02696| 
02697|     with status_slot.container():
02698|         with st.spinner(get_text("searching")):
02699|             advanced_mode = st.session_state.get("advanced_mode", False)
02700|             tor_port = st.session_state.get("tor_port", DEFAULT_TOR_PORT)
02701|             ui_sites = st.session_state.get("custom_onion_sites", [])
02702|             st.session_state.results = cached_search(search_mode, search_query, threads, advanced_mode, tor_port, ui_sites)
02703| 
02704|     source_counts = {}
02705|     for r in st.session_state.results:
02706|         src = r.get("source", "Unknown")
02707|         source_counts[src] = source_counts.get(src, 0) + 1
02708| 
02709|     results_count = len(st.session_state.results)
02710| 
02711|     # 显示搜索源统计
02712|     source_info = " | ".join([f"{k}: {v}" for k, v in source_counts.items()])
02713|     st.markdown(f"""
02714|     <div class="result-card">
// 进度: 第980行/共1174行
02715|         <div class="result-stats">
02716|             <div class="stat-item">
02717|                 <div class="stat-value">{results_count}</div>
02718|                 <div class="stat-label">{get_text("results_count")}</div>
02719|             </div>
02720|         </div>
02721|         <div class="stat-label" style="margin-top: 10px;">数据来源: {source_info}</div>
02722|     </div>
02723|     """, unsafe_allow_html=True)
02724| 
02725|     # 保留所有搜索结果（不过滤）
02726|     st.session_state.filtered = st.session_state.results
02727| 
02728|     with status_slot.container():
02729|         with st.spinner(get_text("scraping")):
02730|             st.session_state.scraped = cached_scrape(st.session_state.filtered, threads)
02731|             # 调试日志
02732|             print(f"=== SCRAPING DEBUG ===")
02733|             print(f"Filtered results count: {len(st.session_state.filtered)}")
02734|             print(f"Scraped keys: {list(st.session_state.scraped.keys())[:5]}")
// 进度: 第1000行/共1174行
02735|             if st.session_state.scraped:
02736|                 first_content = list(st.session_state.scraped.values())[0]
02737|                 print(f"First content length: {len(first_content)}")
02738|                 print(f"First content preview: {first_content[:300]}")
02739| 
02740|     st.session_state.streamed_summary = ""
02741| 
02742|     def ui_emit(chunk):
02743|         st.session_state.streamed_summary += chunk
02744|         summary_slot.markdown(st.session_state.streamed_summary)
02745| 
02746|     st.markdown(f"""
02747|     <div class="report-section">
02748|         <div class="report-title">{get_text("report_title")}</div>
02749|     </div>
02750|     """, unsafe_allow_html=True)
02751|     summary_slot = st.empty()
02752| 
02753|     with status_slot.container():
02754|         with st.spinner(get_text("generating")):
// 进度: 第1020行/共1174行
02755|             stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
02756|             llm.callbacks = [stream_handler]
02757|             _ = generate_summary(llm, query, st.session_state.scraped, search_mode)
02758| 
02759|     now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
02760|     st.session_state.report_timestamp = now
02761| 
02762|     # 标记搜索已完成
02763|     st.session_state.search_completed = True
02764|     st.session_state.status_slot = "complete"
02765|     st.session_state.export_format_choice = "md"
02766| 
02767|     status_slot.success(get_text("complete"))
02768| 
02769| 
02770| # 显示搜索结果和下载区域（独立于run_button）
02771| if st.session_state.get("search_completed", False) and st.session_state.get("streamed_summary"):
02772|     st.markdown("<br>", unsafe_allow_html=True)
02773| 
02774|     # 获取sidebar中选择的下载格式
// 进度: 第1040行/共1174行
02775|     download_format = st.session_state.get('sidebar_download_format', 'md')
02776|     format_labels_display = {"md": "Markdown", "pdf": "PDF", "docx": "Word", "xlsx": "Excel"}
02777| 
02778|     st.info(f"下载格式: **{format_labels_display.get(download_format)}**")
02779| 
02780|     # 直接生成并下载，不使用rerun
02781|     if st.button(get_text("download"), use_container_width=True, key="download_btn"):
02782|         from pathlib import Path
02783| 
02784|         try:
02785|             filename = f"report_{st.session_state.report_timestamp}"
02786|             if download_format == 'pdf':
02787|                 from report_export import export_pdf
02788|                 pdf_path = export_pdf(st.session_state.streamed_summary, st.session_state.refined, filename)
02789|                 with open(pdf_path, 'rb') as f:
02790|                     pdf_data = f.read()
02791|                 st.download_button(
02792|                     label=get_text("pdf_ready"),
02793|                     data=pdf_data,
02794|                     file_name=f"{filename}.pdf",
// 进度: 第1060行/共1174行
02795|                     mime="application/pdf",
02796|                     key="pdf_download_now"
02797|                 )
02798|                 try:
02799|                     Path(pdf_path).unlink()
02800|                 except:
02801|                     pass
02802| 
02803|             elif download_format == 'docx':
02804|                 from report_export import export_word
02805|                 docx_path = export_word(st.session_state.streamed_summary, st.session_state.refined, filename)
02806|                 with open(docx_path, 'rb') as f:
02807|                     docx_data = f.read()
02808|                 st.download_button(
02809|                     label=get_text("word_ready"),
02810|                     data=docx_data,
02811|                     file_name=f"{filename}.docx",
02812|                     mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
02813|                     key="docx_download_now"
02814|                 )
// 进度: 第1080行/共1174行
02815|                 try:
02816|                     Path(docx_path).unlink()
02817|                 except:
02818|                     pass
02819| 
02820|             elif download_format == 'xlsx':
02821|                 from report_export import export_excel
02822|                 xlsx_path = export_excel(st.session_state.streamed_summary, st.session_state.refined, filename)
02823|                 with open(xlsx_path, 'rb') as f:
02824|                     xlsx_data = f.read()
02825|                 st.download_button(
02826|                     label="Excel已准备",
02827|                     data=xlsx_data,
02828|                     file_name=f"{filename}.xlsx",
02829|                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
02830|                     key="xlsx_download_now"
02831|                 )
02832|                 try:
02833|                     Path(xlsx_path).unlink()
02834|                 except:
// 进度: 第1100行/共1174行
02835|                     pass
02836| 
02837|             else:  # markdown
02838|                 st.download_button(
02839|                     label=get_text("md_ready"),
02840|                     data=st.session_state.streamed_summary,
02841|                     file_name=f"{filename}.md",
02842|                     mime="text/markdown",
02843|                     key="md_download_now"
02844|                 )
02845|         except Exception as e:
02846|             st.error(f"{get_text('error')}: {str(e)}")
02847| 
02848|     # 显示搜索结果实际内容
02849|     if st.session_state.get("filtered") and len(st.session_state.get("filtered", [])) > 0:
02850|         st.markdown("---")
02851| 
02852|         # 初始化分页状态
02853|         if "result_page" not in st.session_state:
02854|             st.session_state.result_page = 1
// 进度: 第1120行/共1174行
02855| 
02856|         all_results = st.session_state.filtered
02857|         total_results = len(all_results)
02858| 
02859|         # 每页显示数量
02860|         ITEMS_PER_PAGE = 40
02861|         total_pages = (total_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
02862| 
02863|         # 标题和分页控件
02864|         col1, col2 = st.columns([3, 1])
02865|         with col1:
02866|             st.markdown(f'<div class="report-title">📋 搜索结果详情 ({total_results}条)</div>', unsafe_allow_html=True)
02867|         with col2:
02868|             # 分页导航
02869|             page_cols = st.columns([1, 1, 1])
02870|             with page_cols[0]:
02871|                 if st.session_state.result_page > 1:
02872|                     if st.button("◀ 上一页", key="prev_page"):
02873|                         st.session_state.result_page -= 1
02874|                         st.rerun()
// 进度: 第1140行/共1174行
02875|             with page_cols[1]:
02876|                 st.markdown(f"**{st.session_state.result_page}/{total_pages}**")
02877|             with page_cols[2]:
02878|                 if st.session_state.result_page < total_pages:
02879|                     if st.button("下一页 ▶", key="next_page"):
02880|                         st.session_state.result_page += 1
02881|                         st.rerun()
02882| 
02883|         # 计算当前页显示范围
02884|         start_idx = (st.session_state.result_page - 1) * ITEMS_PER_PAGE
02885|         end_idx = min(start_idx + ITEMS_PER_PAGE, total_results)
02886|         page_results = all_results[start_idx:end_idx]
02887| 
02888|         # 按来源分组显示当前页
02889|         source_groups = {}
02890|         for item in page_results:
02891|             source = item.get("source", "Unknown")
02892|             if source not in source_groups:
02893|                 source_groups[source] = []
02894|             source_groups[source].append(item)
// 进度: 第1160行/共1174行
02895| 
02896|         for source, items in source_groups.items():
02897|             with st.expander(f"📌 {source} ({len(items)}条)", expanded=False):
02898|                 for i, item in enumerate(items):
02899|                     actual_idx = start_idx + i + 1
02900|                     st.markdown(f"**{actual_idx}. {item.get('title', '无标题')[:150]}**")
02901|                     if item.get('description'):
02902|                         st.markdown(f"📝 {item.get('description', '')[:500]}...")
02903|                     elif item.get('summary'):
02904|                         st.markdown(f"📝 {item.get('summary', '')[:500]}...")
02905|                     if item.get('link') or item.get('url'):
02906|                         link = item.get('link') or item.get('url')
02907|                         st.markdown(f"🔗 [查看原文]({link})")
02908|                     st.markdown("---")
// ==========
// 文件结束: .\ui.py
// 总行数: 1174行
// 下一个文件: [等待添加]
// ==========


第2911页：.\scrape.py（完整118行）
02909| import random
02910| import requests
02911| import threading
02912| from requests.adapters import HTTPAdapter
02913| from urllib3.util.retry import Retry
02914| from bs4 import BeautifulSoup
02915| from concurrent.futures import ThreadPoolExecutor, as_completed
02916| 
02917| import warnings
02918| warnings.filterwarnings("ignore")
02919| 
02920| # Define a list of rotating user agents.
02921| USER_AGENTS = [
02922|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
02923|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
02924|     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
02925|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
02926|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
02927|     "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
02928|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
// 进度: 第20行/共118行
02929|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
02930|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
02931| ]
02932| 
02933| def get_tor_session():
02934|     """
02935|     Creates a requests Session with Tor SOCKS proxy and automatic retries.
02936|     """
02937|     session = requests.Session()
02938|     retry = Retry(
02939|         total=3,
02940|         read=3,
02941|         connect=3,
02942|         backoff_factor=0.3,
02943|         status_forcelist=[500, 502, 503, 504]
02944|     )
02945|     adapter = HTTPAdapter(max_retries=retry)
02946|     session.mount("http://", adapter)
02947|     session.mount("https://", adapter)
02948| 
// 进度: 第40行/共118行
02949|     session.proxies = {
02950|         "http": "socks5h://127.0.0.1:9150",
02951|         "https": "socks5h://127.0.0.1:9150"
02952|     }
02953|     return session
02954| 
02955| def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
02956|     """
02957|     Scrapes a single URL using a robust Tor session.
02958|     Returns a tuple (url, scraped_text).
02959|     """
02960|     url = url_data['link']
02961| 
02962|     # 跳过PDF和其他不支持的格式
02963|     if url.lower().endswith('.pdf') or '.pdf?' in url.lower():
02964|         return (url, f"{url_data['title']} - [PDF文件，请直接下载查看]")
02965| 
02966|     use_tor = ".onion" in url
02967| 
02968|     headers = {
// 进度: 第60行/共118行
02969|         "User-Agent": random.choice(USER_AGENTS),
02970|         "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
02971|     }
02972| 
02973|     try:
02974|         if use_tor:
02975|             session = get_tor_session()
02976|             response = session.get(url, headers=headers, timeout=45)
02977|         else:
02978|             response = requests.get(url, headers=headers, timeout=30)
02979| 
02980|         if response.status_code == 200:
02981|             # 强制使用UTF-8解码，解决中文乱码问题
02982|             response.encoding = 'utf-8'
02983| 
02984|             soup = BeautifulSoup(response.text, "html.parser")
02985|             # Clean up text: remove scripts/styles
02986|             for script in soup(["script", "style"]):
02987|                 script.extract()
02988|             text = soup.get_text(separator=' ', strip=True)
// 进度: 第80行/共118行
02989|             # Normalize whitespace
02990|             text = ' '.join(text.split())
02991| 
02992|             # 如果抓取内容太短（少于100字符），说明可能失败了，返回标题
02993|             if len(text) < 100:
02994|                 scraped_text = url_data['title']
02995|             else:
02996|                 scraped_text = f"{url_data['title']} - {text}"
02997|         else:
02998|             scraped_text = url_data['title']
02999|     except Exception as e:
03000|         # Return title only on failure, so we don't lose the reference
03001|         scraped_text = url_data['title']
03002| 
03003|     return url, scraped_text
03004| 
03005| def scrape_multiple(urls_data, max_workers=5):
03006|     """
03007|     Scrapes multiple URLs concurrently using a thread pool.
03008|     """
// 进度: 第100行/共118行
03009|     results = {}
03010|     max_chars = 2000  # Increased limit slightly for better context
03011| 
03012|     with ThreadPoolExecutor(max_workers=max_workers) as executor:
03013|         future_to_url = {
03014|             executor.submit(scrape_single, url_data): url_data
03015|             for url_data in urls_data
03016|         }
03017|         for future in as_completed(future_to_url):
03018|             try:
03019|                 url, content = future.result()
03020|                 if len(content) > max_chars:
03021|                     content = content[:max_chars] + "...(truncated)"
03022|                 results[url] = content
03023|             except Exception:
03024|                 continue
03025| 
03026|     return results
// ==========
// 文件结束: .\scrape.py
// 总行数: 118行
// 下一个文件: [等待添加]
// ==========


第3040页：.\report_export.py（完整617行）
03027| """
03028| Report Export Module
03029| ===================
03030| Export intelligence reports to various formats (Markdown, PDF, Word).
03031| Supports Chinese and English with professional formatting.
03032| """
03033| 
03034| import os
03035| from datetime import datetime
03036| from typing import Dict, List, Optional
03037| import re
03038| 
03039| try:
03040|     from reportlab.lib.pagesizes import letter, A4
03041|     from reportlab.lib import colors
03042|     from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
03043|     from reportlab.lib.units import inch
03044|     from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
03045|     from reportlab.pdfgen import canvas
03046|     from reportlab.pdfbase import pdfmetrics
// 进度: 第20行/共617行
03047|     from reportlab.pdfbase.ttfonts import TTFont
03048|     REPORTLAB_AVAILABLE = True
03049| except ImportError:
03050|     REPORTLAB_AVAILABLE = False
03051| 
03052| try:
03053|     from fpdf import FPDF
03054| 
03055|     class PDFReport(FPDF):
03056|         def __init__(self, is_chinese=False):
03057|             super().__init__()
03058|             self.is_chinese = is_chinese
03059|             self.set_auto_page_break(auto=True, margin=15)
03060| 
03061|         def header(self):
03062|             self.set_font('Helvetica', 'B', 18)
03063|             self.cell(0, 15, 'IntelNexus Intelligence Report', 0, 1, 'C')
03064|             self.set_draw_color(100, 100, 100)
03065|             self.line(15, 20, 195, 20)
03066|             self.ln(8)
// 进度: 第40行/共617行
03067| 
03068|         def footer(self):
03069|             self.set_y(-15)
03070|             self.set_font('Helvetica', 'I', 9)
03071|             self.cell(0, 10, f'Page {self.page_no()}  |  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
03072| 
03073|     FPDF_AVAILABLE = True
03074| except ImportError:
03075|     FPDF_AVAILABLE = False
03076|     PDFReport = None
03077| 
03078| FPDF2_AVAILABLE = False
03079| try:
03080|     from fpdf import FPDF
03081| 
03082|     class FPDF2_CHINESE(FPDF):
03083|         def footer(self):
03084|             self.set_y(-15)
03085|             self.set_font("Helvetica", style="I", size=9)
03086|             self.cell(0, 10, f'Page {self.page_no()}  |  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
// 进度: 第60行/共617行
03087| 
03088|     FPDF2_AVAILABLE = True
03089| except ImportError:
03090|     pass
03091| 
03092| 
03093| 
03094| 
03095| try:
03096|     from docx import Document
03097|     from docx.shared import Inches, Pt, RGBColor
03098|     from docx.enum.text import WD_ALIGN_PARAGRAPH
03099| except ImportError:
03100|     Document = None
03101| 
03102| try:
03103|     from openpyxl import Workbook
03104|     from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
03105|     from openpyxl.utils import get_column_letter
03106|     OPENPYXL_AVAILABLE = True
// 进度: 第80行/共617行
03107| except ImportError:
03108|     Workbook = None
03109|     OPENPYXL_AVAILABLE = False
03110| 
03111| 
03112| def _format_content_for_pdf(content: str) -> str:
03113|     """Format content for better PDF rendering."""
03114|     # 移除markdown的某些格式符号，使其在PDF中更清晰
03115|     lines = content.split('\n')
03116|     formatted_lines = []
03117| 
03118|     for line in lines:
03119|         # 转换markdown标题
03120|         if line.startswith('# '):
03121|             formatted_lines.append('\n' + line.replace('# ', '■ ').upper())
03122|         elif line.startswith('## '):
03123|             formatted_lines.append('\n▸ ' + line.replace('## ', '').strip())
03124|         else:
03125|             formatted_lines.append(line)
03126| 
// 进度: 第100行/共617行
03127|     return '\n'.join(formatted_lines)
03128| 
03129| 
03130| def export_markdown(content: str, query: str, output_path: str) -> str:
03131|     """Export to Markdown format with enhanced structure."""
03132|     # 清理内容，移除所有特殊字符
03133|     content = _clean_content(content)
03134| 
03135|     with open(output_path, 'w', encoding='utf-8') as f:
03136|         f.write("# IntelNexus 智能情报报告\n\n")
03137|         f.write(f"## 报告信息\n\n")
03138|         f.write(f"- **查询内容**: {query}\n")
03139|         f.write(f"- **生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n")
03140|         f.write(f"- **报告类型**: 多源网络情报分析\n\n")
03141|         f.write("---\n\n")
03142|         f.write("## 分析结果\n\n")
03143|         f.write(content)
03144|         f.write("\n\n---\n\n")
03145|         f.write(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
03146|         f.write("*© 2026 IntelNexus Platform - 多源网络情报分析平台*\n")
// 进度: 第120行/共617行
03147|     return output_path
03148| 
03149| 
03150| def _clean_markdown_for_word(text: str) -> str:
03151|     """清理Markdown标记符号用于Word导出。"""
03152|     # 移除markdown标题标记
03153|     text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
03154|     # 处理粗体：**text** -> text
03155|     text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
03156|     text = re.sub(r'__(.+?)__', r'\1', text)
03157|     # 处理斜体
03158|     text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
03159|     text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', text)
03160|     # 处理代码块
03161|     text = re.sub(r'`([^`]+)`', r'\1', text)
03162|     text = re.sub(r'```[\s\S]*?```', '', text)
03163|     # 处理链接
03164|     text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1 (\2)', text)
03165|     return text
03166| 
// 进度: 第140行/共617行
03167| 
03168| def _clean_content(content: str) -> str:
03169|     """清理内容特殊字符，用于所有导出格式。"""
03170|     if not content:
03171|         return content
03172| 
03173|     # 逐个替换特殊字符
03174|     chars_to_remove = [
03175|         '■', '□', '▢', '▣', '▤', '▥', '▦', '▧', '▨', '▩', '▪', '▫', '▬', '▭', '▮', '▯',
03176|         '▰', '▱', '△', '▽', '▷', '◁', '◆', '◇', '○', '●', '◐', '◑', '◒', '◓', '◔', '◕',
03177|         '◖', '◗', '★', '☆', '☉', '♠', '♣', '♥', '♦', '♩', '♪', '♫', '⚐', '⚑', '⚡',
03178|         '⚪', '⚫', '⚬', '✓', '✗', '✘', '✔', '✖', '✚', '✽', '✿', '❀', '❖', '❤',
03179|     ]
03180|     for char in chars_to_remove:
03181|         content = content.replace(char, '')
03182| 
03183|     # 移除emoji范围
03184|     try:
03185|         emoji_pattern = re.compile("["
03186|             u"\U0001F600-\U0001F64F"
// 进度: 第160行/共617行
03187|             u"\U0001F300-\U0001F5FF"
03188|             u"\U0001F680-\U0001F6FF"
03189|             u"\U0001F1E0-\U0001F1FF"
03190|             "]+", flags=re.UNICODE)
03191|         content = emoji_pattern.sub('', content)
03192|     except:
03193|         pass
03194| 
03195|     return content
03196| 
03197| 
03198| def export_pdf(content: str, query: str, output_path: str) -> str:
03199|     """Export to PDF format with Chinese support using fpdf2."""
03200|     if not FPDF2_AVAILABLE:
03201|         raise ImportError("fpdf2 is not installed. Install with: pip install fpdf2")
03202| 
03203|     try:
03204|         clean_query = query[:100] if query else "[No query content]"
03205|     except:
03206|         clean_query = "[Query processing error]"
// 进度: 第180行/共617行
03207| 
03208|     output_dir = os.path.dirname(output_path)
03209|     if output_dir and not os.path.exists(output_dir):
03210|         os.makedirs(output_dir)
03211| 
03212|     if not output_path.endswith('.pdf'):
03213|         output_path += '.pdf'
03214| 
03215|     pdf = FPDF2_CHINESE(format='A4')
03216|     pdf.add_page()
03217|     pdf.set_auto_page_break(True, 15)
03218| 
03219|     font_paths = [
03220|         "C:/Windows/Fonts/simhei.ttf",
03221|         "C:/Windows/Fonts/simkai.ttf",
03222|         "C:/Windows/Fonts/simfang.ttf",
03223|     ]
03224| 
03225|     font_name = "helvetica"
03226|     for font_path in font_paths:
// 进度: 第200行/共617行
03227|         if os.path.exists(font_path):
03228|             try:
03229|                 pdf.add_font("Chinese", "", font_path, uni=True)
03230|                 pdf.add_font("Chinese", "B", font_path, uni=True)
03231|                 pdf.add_font("Chinese", "I", font_path, uni=True)
03232|                 font_name = "Chinese"
03233|                 break
03234|             except Exception as e:
03235|                 print(f"Font loading error: {e}")
03236|                 continue
03237| 
03238|     import warnings
03239|     warnings.filterwarnings("ignore", category=DeprecationWarning)
03240| 
03241|     pdf.set_font(font_name, style="B", size=16)
03242|     pdf.set_text_color(31, 71, 136)
03243|     pdf.cell(0, 15, "IntelNexus Intelligence Report", 0, 1, "C")
03244| 
03245|     pdf.set_draw_color(200, 200, 200)
03246|     pdf.line(15, 25, 195, 25)
// 进度: 第220行/共617行
03247|     pdf.ln(5)
03248| 
03249|     pdf.set_font(font_name, style="B", size=12)
03250|     pdf.set_text_color(50, 50, 50)
03251|     pdf.cell(0, 8, "Report Information", ln=True)
03252|     pdf.set_font(font_name, size=11)
03253| 
03254|     pdf.cell(40, 6, "Query: ", ln=False)
03255|     pdf.multi_cell(0, 6, clean_query if clean_query else "[No query]")
03256| 
03257|     pdf.cell(40, 6, "Generated: ", ln=False)
03258|     pdf.cell(0, 6, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ln=True)
03259| 
03260|     pdf.cell(40, 6, "Platform: ", ln=False)
03261|     pdf.cell(0, 6, "IntelNexus v1.0", ln=True)
03262| 
03263|     pdf.cell(40, 6, "Type: ", ln=False)
03264|     pdf.cell(0, 6, "Multi-Source Network Intelligence Analysis", ln=True)
03265| 
03266|     pdf.ln(5)
// 进度: 第240行/共617行
03267|     pdf.set_draw_color(200, 200, 200)
03268|     pdf.line(10, pdf.get_y(), 200, pdf.get_y())
03269|     pdf.ln(5)
03270| 
03271|     pdf.set_font(font_name, style="B", size=12)
03272|     pdf.set_text_color(31, 71, 136)
03273|     pdf.cell(0, 8, "Analysis Results", ln=True)
03274|     pdf.set_font(font_name, size=10)
03275|     pdf.set_text_color(50, 50, 50)
03276| 
03277|     max_length = 15000
03278|     if len(content) > max_length:
03279|         display_content = content[:max_length] + "\n\n[Content too long. Please check the full Markdown or Word report.]"
03280|     else:
03281|         display_content = content
03282| 
03283|     display_content = _clean_content(display_content)
03284|     display_content = _clean_markdown_for_word(display_content)
03285| 
03286|     lines = display_content.split('\n')
// 进度: 第260行/共617行
03287|     for line in lines:
03288|         line = line.strip()
03289|         if not line:
03290|             pdf.ln(2)
03291|             continue
03292| 
03293|         if line.startswith('# '):
03294|             pdf.ln(2)
03295|             pdf.set_font(font_name, style="B", size=13)
03296|             pdf.set_text_color(31, 71, 136)
03297|             pdf.cell(0, 8, line.replace('# ', '').strip(), ln=True)
03298|             pdf.set_font(font_name, size=10)
03299|             pdf.set_text_color(50, 50, 50)
03300|         elif line.startswith('## '):
03301|             pdf.ln(1)
03302|             pdf.set_font(font_name, style="B", size=12)
03303|             pdf.set_text_color(31, 71, 136)
03304|             pdf.cell(0, 7, line.replace('## ', '').strip(), ln=True)
03305|             pdf.set_font(font_name, size=10)
03306|             pdf.set_text_color(50, 50, 50)
// 进度: 第280行/共617行
03307|         elif line.startswith('### '):
03308|             pdf.set_font(font_name, style="B", size=11)
03309|             pdf.set_text_color(46, 90, 136)
03310|             pdf.cell(0, 6, line.replace('### ', '').strip(), ln=True)
03311|             pdf.set_font(font_name, size=10)
03312|             pdf.set_text_color(50, 50, 50)
03313|         else:
03314|             if pdf.get_y() > 250:
03315|                 pdf.add_page()
03316|                 pdf.set_font(font_name, size=10)
03317|                 pdf.set_text_color(50, 50, 50)
03318| 
03319|             pdf.cell(0, 6, line, ln=True)
03320| 
03321|     pdf.ln(10)
03322|     pdf.set_draw_color(200, 200, 200)
03323|     pdf.line(10, pdf.get_y(), 200, pdf.get_y())
03324|     pdf.ln(2)
03325|     pdf.set_font(font_name, style="I", size=8)
03326|     pdf.set_text_color(128, 128, 128)
// 进度: 第300行/共617行
03327|     pdf.cell(0, 5, f"© 2026 IntelNexus Platform | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 0, "C")
03328| 
03329|     pdf.output(output_path)
03330|     return output_path
03331| 
03332| 
03333| 
03334| def _get_chinese_font():
03335|     """获取系统中可用的中文字体"""
03336|     chinese_fonts = ['微软雅黑', 'SimHei', '黑体', 'Arial', 'Calibri']
03337|     available_fonts = []
03338|     try:
03339|         from docx.enum.style import WD_STYLE_TYPE
03340|         from docx.styles.styles import Styles
03341|     except:
03342|         pass
03343|     return chinese_fonts[0]
03344| 
03345| 
03346| def _add_paragraph_with_formatting(doc, text: str, style: str = None):
// 进度: 第320行/共617行
03347|     """Add a paragraph to document with markdown formatting support.
03348| 
03349|     Converts **text** to bold, *text* to italic, `code` to code formatting.
03350|     """
03351|     if not text.strip():
03352|         return
03353| 
03354|     font_name = _get_chinese_font()
03355| 
03356|     para = doc.add_paragraph(style=style)
03357| 
03358|     bold_pattern = r'\*\*(.+?)\*\*'
03359|     italic_pattern = r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)'
03360|     code_pattern = r'`([^`]+)`'
03361| 
03362|     combined = f'({bold_pattern}|{italic_pattern}|{code_pattern})'
03363| 
03364|     last_end = 0
03365|     for match in re.finditer(combined, text):
03366|         if match.start() > last_end:
// 进度: 第340行/共617行
03367|             run = para.add_run(text[last_end:match.start()])
03368|             run.font.name = font_name
03369|             run.font.size = Pt(11)
03370| 
03371|         if match.group(2):
03372|             run = para.add_run(match.group(2))
03373|             run.font.bold = True
03374|             run.font.name = font_name
03375|             run.font.size = Pt(11)
03376|         elif match.group(3):
03377|             run = para.add_run(match.group(3))
03378|             run.font.italic = True
03379|             run.font.name = font_name
03380|             run.font.size = Pt(11)
03381|         elif match.group(4):
03382|             run = para.add_run(match.group(4))
03383|             run.font.name = 'Courier New'
03384|             run.font.size = Pt(10)
03385|             run.font.color.rgb = RGBColor(128, 0, 0)
03386| 
// 进度: 第360行/共617行
03387|         last_end = match.end()
03388| 
03389|     if last_end < len(text):
03390|         run = para.add_run(text[last_end:])
03391|         run.font.name = font_name
03392|         run.font.size = Pt(11)
03393| 
03394| 
03395| def export_word(content: str, query: str, output_path: str) -> str:
03396|     """Export to Word format with markdown formatting rendering."""
03397|     if Document is None:
03398|         raise ImportError("python-docx is not installed. Install with: pip install python-docx")
03399| 
03400|     font_name = _get_chinese_font()
03401| 
03402|     doc = Document()
03403| 
03404|     style = doc.styles['Normal']
03405|     style.font.name = font_name
03406|     style.font.size = Pt(11)
// 进度: 第380行/共617行
03407| 
03408|     # 标题
03409|     title = doc.add_heading('IntelNexus 智能情报分析报告', 0)
03410|     title_format = title.paragraph_format
03411|     title_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
03412| 
03413|     # 报告信息
03414|     info_heading = doc.add_heading('报告信息', level=1)
03415| 
03416|     info_table = doc.add_table(rows=4, cols=2)
03417|     info_table.style = 'Light Grid Accent 1'
03418| 
03419|     info_data = [
03420|         ('查询内容', query if query else '[No query]'),
03421|         ('生成时间', datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')),
03422|         ('平台版本', 'IntelNexus v1.0'),
03423|         ('报告类型', '多源网络情报分析')
03424|     ]
03425| 
03426|     for i, (key, value) in enumerate(info_data):
// 进度: 第400行/共617行
03427|         cells = info_table.rows[i].cells
03428|         cells[0].text = key
03429|         cells[1].text = str(value)
03430|         # 设置格式
03431|         for paragraph in cells[0].paragraphs:
03432|             for run in paragraph.runs:
03433|                 run.font.bold = True
03434| 
03435|     doc.add_paragraph()  # 空行
03436| 
03437|     # 分析结果
03438|     result_heading = doc.add_heading('分析结果', level=1)
03439| 
03440|     # 清理内容，移除所有特殊字符
03441|     content = _clean_content(content)
03442| 
03443|     # 处理markdown格式的内容 - 正确渲染markdown格式
03444|     lines = content.split('\n')
03445|     for line in lines:
03446|         if not line.strip():
// 进度: 第420行/共617行
03447|             doc.add_paragraph()
03448|             continue
03449| 
03450|         # 处理标题
03451|         if line.startswith('# '):
03452|             title_text = line.replace('# ', '').strip()
03453|             heading = doc.add_heading(title_text, level=1)
03454|         elif line.startswith('## '):
03455|             title_text = line.replace('## ', '').strip()
03456|             heading = doc.add_heading(title_text, level=2)
03457|         elif line.startswith('### '):
03458|             title_text = line.replace('### ', '').strip()
03459|             heading = doc.add_heading(title_text, level=3)
03460|         # 处理列表
03461|         elif re.match(r'^\d+\.\s', line):
03462|             list_text = re.sub(r'^\d+\.\s', '', line).strip()
03463|             _add_paragraph_with_formatting(doc, list_text, 'List Number')
03464|         elif line.startswith('- '):
03465|             list_text = line[2:].strip()
03466|             _add_paragraph_with_formatting(doc, list_text, 'List Bullet')
// 进度: 第440行/共617行
03467|         elif line.startswith('* '):
03468|             list_text = line[2:].strip()
03469|             _add_paragraph_with_formatting(doc, list_text, 'List Bullet')
03470|         else:
03471|             # 清理可能的markdown标题标记（处理行内或意外的情况）
03472|             cleaned_line = _clean_markdown_for_word(line.strip())
03473|             if cleaned_line.strip():
03474|                 _add_paragraph_with_formatting(doc, cleaned_line)
03475| 
03476|     # 添加页脚
03477|     doc.add_paragraph()
03478|     footer_para = doc.add_paragraph()
03479|     footer_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
03480|     footer_run = footer_para.add_run(f"© 2026 IntelNexus Platform | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
03481|     footer_run.italic = True
03482|     footer_run.font.size = Pt(9)
03483|     footer_run.font.color.rgb = RGBColor(128, 128, 128)
03484| 
03485|     # 确保输出目录存在
03486|     output_dir = os.path.dirname(output_path)
// 进度: 第460行/共617行
03487|     if output_dir and not os.path.exists(output_dir):
03488|         os.makedirs(output_dir)
03489| 
03490|     doc.save(output_path)
03491|     return output_path
03492| 
03493| 
03494| 
03495| def export_report(content: str, query: str, output_path: str, format: str = 'md') -> str:
03496|     """Export report to specified format."""
03497|     if not output_path:
03498|         timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
03499|         output_path = f"report_{timestamp}"
03500| 
03501|     if format == 'pdf':
03502|         if not output_path.endswith('.pdf'):
03503|             output_path += '.pdf'
03504|         return export_pdf(content, query, output_path)
03505|     elif format == 'docx':
03506|         if not output_path.endswith('.docx'):
// 进度: 第480行/共617行
03507|             output_path += '.docx'
03508|         return export_word(content, query, output_path)
03509|     else:
03510|         if not output_path.endswith('.md'):
03511|             output_path += '.md'
03512|         return export_markdown(content, query, output_path)
03513| 
03514| 
03515| def get_export_formats() -> List[str]:
03516|     """Get list of available export formats."""
03517|     formats = ['md']
03518|     if FPDF2_AVAILABLE:
03519|         formats.append('pdf')
03520|     if Document:
03521|         formats.append('docx')
03522|     if OPENPYXL_AVAILABLE:
03523|         formats.append('xlsx')
03524|     return formats
03525| 
03526| 
// 进度: 第500行/共617行
03527| def export_excel(content: str, query: str, output_path: str) -> str:
03528|     """Export to Excel format with proper formatting."""
03529|     if Workbook is None:
03530|         raise ImportError("openpyxl is not installed. Install with: pip install openpyxl")
03531| 
03532|     wb = Workbook()
03533|     ws = wb.active
03534|     ws.title = "情报报告"
03535| 
03536|     # 定义样式
03537|     header_font = Font(name='微软雅黑', size=16, bold=True, color='FFFFFF')
03538|     header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
03539|     header_alignment = Alignment(horizontal='center', vertical='center')
03540| 
03541|     title_font = Font(name='微软雅黑', size=12, bold=True)
03542|     title_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
03543| 
03544|     normal_font = Font(name='微软雅黑', size=11)
03545|     wrap_alignment = Alignment(wrap_text=True, vertical='top')
03546| 
// 进度: 第520行/共617行
03547|     thin_border = Border(
03548|         left=Side(style='thin'),
03549|         right=Side(style='thin'),
03550|         top=Side(style='thin'),
03551|         bottom=Side(style='thin')
03552|     )
03553| 
03554|     # 标题行
03555|     ws.merge_cells('A1:B1')
03556|     ws['A1'] = 'IntelNexus 智能情报分析报告'
03557|     ws['A1'].font = header_font
03558|     ws['A1'].fill = header_fill
03559|     ws['A1'].alignment = header_alignment
03560|     ws.row_dimensions[1].height = 30
03561| 
03562|     # 报告信息
03563|     ws['A3'] = '查询内容'
03564|     ws['B3'] = query if query else '[无查询内容]'
03565|     ws['A4'] = '生成时间'
03566|     ws['B4'] = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
// 进度: 第540行/共617行
03567|     ws['A5'] = '平台版本'
03568|     ws['B5'] = 'IntelNexus v1.0'
03569|     ws['A6'] = '报告类型'
03570|     ws['B6'] = '多源网络情报分析'
03571| 
03572|     for row in range(3, 7):
03573|         ws[f'A{row}'].font = title_font
03574|         ws[f'A{row}'].fill = title_fill
03575|         ws[f'A{row}'].border = thin_border
03576|         ws[f'B{row}'].border = thin_border
03577|         ws[f'B{row}'].alignment = wrap_alignment
03578| 
03579|     # 分析结果标题
03580|     ws['A8'] = '分析结果'
03581|     ws['A8'].font = title_font
03582|     ws['A8'].fill = title_fill
03583|     ws.merge_cells('A8:B8')
03584|     ws['A8'].alignment = Alignment(horizontal='center', vertical='center')
03585|     ws['A8'].border = thin_border
03586|     ws['B8'].border = thin_border
// 进度: 第560行/共617行
03587|     ws.row_dimensions[8].height = 25
03588| 
03589|     # 解析内容并添加到 Excel
03590|     start_row = 9
03591|     current_row = start_row
03592| 
03593|     # 清理内容中的markdown标题标记
03594|     clean_content = _clean_markdown_for_word(content)
03595| 
03596|     # 按段落添加内容
03597|     paragraphs = clean_content.split('\n\n')
03598|     for para in paragraphs:
03599|         para = para.strip()
03600|         if not para:
03601|             continue
03602| 
03603|         # 检查是否是标题
03604|         is_title = False
03605|         if para.startswith('■ ') or para.startswith('▸ '):
03606|             is_title = True
// 进度: 第580行/共617行
03607|             para = para[2:].strip() if para.startswith('■ ') else para[2:].strip()
03608| 
03609|         ws[f'A{current_row}'] = para
03610|         ws.merge_cells(f'A{current_row}:B{current_row}')
03611| 
03612|         if is_title:
03613|             ws[f'A{current_row}'].font = Font(name='微软雅黑', size=11, bold=True, color='1F4E79')
03614|         else:
03615|             ws[f'A{current_row}'].font = normal_font
03616| 
03617|         ws[f'A{current_row}'].alignment = wrap_alignment
03618|         ws[f'A{current_row}'].border = thin_border
03619|         ws.row_dimensions[current_row].height = max(20, len(para) // 40 * 15 + 20)
03620| 
03621|         current_row += 1
03622| 
03623|     # 设置列宽
03624|     ws.column_dimensions['A'].width = 30
03625|     ws.column_dimensions['B'].width = 70
03626| 
// 进度: 第600行/共617行
03627|     # 添加页脚
03628|     footer_row = current_row + 2
03629|     ws.merge_cells(f'A{footer_row}:B{footer_row}')
03630|     ws[f'A{footer_row}'] = f"© 2026 IntelNexus Platform | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
03631|     ws[f'A{footer_row}'].font = Font(name='微软雅黑', size=9, italic=True, color='808080')
03632|     ws[f'A{footer_row}'].alignment = Alignment(horizontal='center')
03633| 
03634|     # 确保输出目录存在
03635|     output_dir = os.path.dirname(output_path)
03636|     if output_dir and not os.path.exists(output_dir):
03637|         os.makedirs(output_dir)
03638| 
03639|     if not output_path.endswith('.xlsx'):
03640|         output_path += '.xlsx'
03641| 
03642|     wb.save(output_path)
03643|     return output_path
// ==========
// 文件结束: .\report_export.py
// 总行数: 617行
// 下一个文件: [等待添加]
// ==========


第3693页：.\custom_models.py（完整113行）
03644| """
03645| Custom Models Management Module
03646| ==============================
03647| Allow users to add and manage custom LLM models.
03648| """
03649| 
03650| import json
03651| import os
03652| from typing import Dict, List, Optional
03653| from pathlib import Path
03654| 
03655| 
03656| CUSTOM_MODELS_FILE = "data/custom_models.json"
03657| 
03658| 
03659| def _ensure_custom_models_file():
03660|     """Ensure the custom models file exists."""
03661|     Path("data").mkdir(exist_ok=True)
03662|     if not os.path.exists(CUSTOM_MODELS_FILE):
03663|         with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
// 进度: 第20行/共113行
03664|             json.dump({"models": []}, f, ensure_ascii=False, indent=2)
03665| 
03666| 
03667| def get_custom_models() -> List[Dict[str, str]]:
03668|     """Get all custom models."""
03669|     _ensure_custom_models_file()
03670|     try:
03671|         with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
03672|             data = json.load(f)
03673|             return data.get("models", [])
03674|     except Exception as e:
03675|         print(f"Error reading custom models: {e}")
03676|         return []
03677| 
03678| 
03679| def add_custom_model(name: str, model_type: str, config: Dict) -> bool:
03680|     """
03681|     Add a new custom model.
03682| 
03683|     Args:
// 进度: 第40行/共113行
03684|         name: Model name (e.g., "my-gpt-4")
03685|         model_type: Type of model (e.g., "openai", "ollama", "anthropic")
03686|         config: Model configuration (API key, base URL, etc.)
03687| 
03688|     Returns:
03689|         True if successful, False otherwise
03690|     """
03691|     if not name or not model_type:
03692|         return False
03693| 
03694|     _ensure_custom_models_file()
03695| 
03696|     try:
03697|         with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
03698|             data = json.load(f)
03699| 
03700|         # Check if model already exists
03701|         existing_names = [m["name"] for m in data.get("models", [])]
03702|         if name in existing_names:
03703|             return False
// 进度: 第60行/共113行
03704| 
03705|         # Add new model
03706|         new_model = {
03707|             "name": name,
03708|             "type": model_type,
03709|             "config": config
03710|         }
03711|         data.get("models", []).append(new_model)
03712| 
03713|         with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
03714|             json.dump(data, f, ensure_ascii=False, indent=2)
03715| 
03716|         return True
03717|     except Exception as e:
03718|         print(f"Error adding custom model: {e}")
03719|         return False
03720| 
03721| 
03722| def remove_custom_model(name: str) -> bool:
03723|     """Remove a custom model by name."""
// 进度: 第80行/共113行
03724|     _ensure_custom_models_file()
03725| 
03726|     try:
03727|         with open(CUSTOM_MODELS_FILE, 'r', encoding='utf-8') as f:
03728|             data = json.load(f)
03729| 
03730|         original_count = len(data.get("models", []))
03731|         data["models"] = [m for m in data.get("models", []) if m["name"] != name]
03732| 
03733|         if len(data["models"]) < original_count:
03734|             with open(CUSTOM_MODELS_FILE, 'w', encoding='utf-8') as f:
03735|                 json.dump(data, f, ensure_ascii=False, indent=2)
03736|             return True
03737|         return False
03738|     except Exception as e:
03739|         print(f"Error removing custom model: {e}")
03740|         return False
03741| 
03742| 
03743| def get_custom_model_names() -> List[str]:
// 进度: 第100行/共113行
03744|     """Get a list of custom model names."""
03745|     return [m["name"] for m in get_custom_models()]
03746| 
03747| 
03748| def get_model_config(name: str) -> Optional[Dict]:
03749|     """Get the configuration for a custom model."""
03750|     for model in get_custom_models():
03751|         if model["name"] == name:
03752|             return {
03753|                 "type": model.get("type"),
03754|                 "config": model.get("config", {})
03755|             }
03756|     return None
// ==========
// 文件结束: .\custom_models.py
// 总行数: 113行
// 下一个文件: [等待添加]
// ==========


第3817页：.\search_history.py（完整130行）
03757| """
03758| Search History Module
03759| ====================
03760| Manage search history and saved reports.
03761| """
03762| 
03763| import os
03764| import json
03765| from datetime import datetime
03766| from typing import List, Dict, Optional
03767| from pathlib import Path
03768| 
03769| 
03770| class SearchHistory:
03771|     def __init__(self, storage_dir: str = "data"):
03772|         self.storage_dir = Path(storage_dir)
03773|         self.history_file = self.storage_dir / "search_history.json"
03774|         self.reports_dir = self.storage_dir / "reports"
03775|         self._ensure_dirs()
03776| 
// 进度: 第20行/共130行
03777|     def _ensure_dirs(self):
03778|         self.storage_dir.mkdir(exist_ok=True)
03779|         self.reports_dir.mkdir(exist_ok=True)
03780| 
03781|     def add_search(self, query: str, mode: str, results_count: int, model: str) -> Dict:
03782|         """Add a new search to history."""
03783|         entry = {
03784|             "id": self._generate_id(),
03785|             "query": query,
03786|             "mode": mode,
03787|             "results_count": results_count,
03788|             "model": model,
03789|             "timestamp": datetime.now().isoformat(),
03790|             "status": "completed"
03791|         }
03792| 
03793|         history = self.get_history()
03794|         history.insert(0, entry)
03795| 
03796|         if len(history) > 100:
// 进度: 第40行/共130行
03797|             history = history[:100]
03798| 
03799|         self._save_history(history)
03800|         return entry
03801| 
03802|     def get_history(self, limit: int = 20) -> List[Dict]:
03803|         """Get search history."""
03804|         if not self.history_file.exists():
03805|             return []
03806| 
03807|         try:
03808|             with open(self.history_file, 'r', encoding='utf-8') as f:
03809|                 return json.load(f)[:limit]
03810|         except:
03811|             return []
03812| 
03813|     def save_report(self, query: str, content: str, mode: str) -> str:
03814|         """Save a report to file."""
03815|         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
03816|         safe_query = "".join(c for c in query if c.isalnum() or c in " -_")[:30]
// 进度: 第60行/共130行
03817|         filename = f"{safe_query}_{timestamp}.md"
03818|         filepath = self.reports_dir / filename
03819| 
03820|         with open(filepath, 'w', encoding='utf-8') as f:
03821|             f.write(f"# Intelligence Report\n\n")
03822|             f.write(f"**Query**: {query}\n")
03823|             f.write(f"**Mode**: {mode}\n")
03824|             f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
03825|             f.write("---\n\n")
03826|             f.write(content)
03827| 
03828|         return str(filepath)
03829| 
03830|     def get_reports(self) -> List[Dict]:
03831|         """Get list of saved reports."""
03832|         reports = []
03833|         if not self.reports_dir.exists():
03834|             return reports
03835| 
03836|         for f in sorted(self.reports_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
// 进度: 第80行/共130行
03837|             stats = f.stat()
03838|             reports.append({
03839|                 "name": f.name,
03840|                 "path": str(f),
03841|                 "size": stats.st_size,
03842|                 "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
03843|             })
03844| 
03845|         return reports
03846| 
03847|     def load_report(self, filename: str) -> Optional[str]:
03848|         """Load a saved report."""
03849|         filepath = self.reports_dir / filename
03850|         if not filepath.exists():
03851|             return None
03852| 
03853|         try:
03854|             with open(filepath, 'r', encoding='utf-8') as f:
03855|                 return f.read()
03856|         except:
// 进度: 第100行/共130行
03857|             return None
03858| 
03859|     def delete_report(self, filename: str) -> bool:
03860|         """Delete a saved report."""
03861|         filepath = self.reports_dir / filename
03862|         if filepath.exists():
03863|             filepath.unlink()
03864|             return True
03865|         return False
03866| 
03867|     def clear_history(self):
03868|         """Clear search history."""
03869|         self._save_history([])
03870| 
03871|     def _generate_id(self) -> str:
03872|         return datetime.now().strftime("%Y%m%d%H%M%S%f")
03873| 
03874|     def _save_history(self, history: List[Dict]):
03875|         with open(self.history_file, 'w', encoding='utf-8') as f:
03876|             json.dump(history, f, ensure_ascii=False, indent=2)
// 进度: 第120行/共130行
03877| 
03878| 
03879| _history_instance = None
03880| 
03881| def get_history_manager() -> SearchHistory:
03882|     """Get global history manager instance."""
03883|     global _history_instance
03884|     if _history_instance is None:
03885|         _history_instance = SearchHistory()
03886|     return _history_instance
// ==========
// 文件结束: .\search_history.py
// 总行数: 130行
// 下一个文件: [等待添加]
// ==========

第14页：.\academic_search.py（完整270行）
03886| import os
03887| import arxiv
03888| import requests
03889| import re
03890| from typing import List, Dict, Optional
03891| from concurrent.futures import ThreadPoolExecutor, as_completed
03892| from bs4 import BeautifulSoup
03893| import random
03894| 
03895| try:
03896|     from semanticscholar import SemanticScholar
03897| except ImportError:
03898|     SemanticScholar = None
03899| 
03900| USER_AGENTS = [
03901|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
03902|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
03903|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
03904| ]
03905| 
// 进度: 第20行/共270行
03906| 
03907| class AcademicSearch:
03908|     def __init__(self, semantic_scholar_key: Optional[str] = None):
03909|         self.semantic_scholar_key = semantic_scholar_key
03910|         if SemanticScholar and semantic_scholar_key:
03911|             try:
03912|                 self.sch_client = SemanticScholar(api_key=semantic_scholar_key)
03913|             except:
03914|                 self.sch_client = None
03915|         else:
03916|             self.sch_client = None
03917| 
03918|     def search_arxiv(self, query: str, max_results: int = 10) -> List[Dict]:
03919|         results = []
03920|         try:
03921|             client = arxiv.Client()
03922|             search = arxiv.Search(
03923|                 query=query,
03924|                 max_results=max_results,
03925|                 sort_by=arxiv.SortCriterion.Relevance
// 进度: 第40行/共270行
03926|             )
03927|             for paper in client.results(search):
03928|                 results.append({
03929|                     "title": paper.title,
03930|                     "authors": [a.name for a in paper.authors],
03931|                     "summary": paper.summary[:500] if paper.summary else "",
03932|                     "published": str(paper.published.date()) if paper.published else "",
03933|                     "pdf_url": paper.pdf_url,
03934|                     "arxiv_id": paper.entry_id.split("/")[-1] if paper.entry_id else "",
03935|                     "categories": paper.categories if paper.categories else [],
03936|                     "source": "arXiv",
03937|                     "url": paper.entry_id if paper.entry_id else paper.pdf_url
03938|                 })
03939|         except Exception as e:
03940|             print(f"ArXiv search error: {e}")
03941|         return results
03942| 
03943|     def search_semantic_scholar(self, query: str, max_results: int = 10) -> List[Dict]:
03944|         results = []
03945|         if not self.sch_client:
// 进度: 第60行/共270行
03946|             return results
03947| 
03948|         try:
03949|             papers = self.sch_client.search_paper(query, limit=max_results)
03950|             for paper in papers:
03951|                 results.append({
03952|                     "title": paper.title,
03953|                     "authors": [a.name for a in paper.authors] if paper.authors else [],
03954|                     "summary": paper.abstract[:500] if paper.abstract else "",
03955|                     "published": str(paper.year) if paper.year else "",
03956|                     "pdf_url": paper.url or "",
03957|                     "citation_count": paper.citation_count or 0,
03958|                     "source": "Semantic Scholar",
03959|                     "url": paper.url or ""
03960|                 })
03961|         except Exception as e:
03962|             print(f"Semantic Scholar search error: {e}")
03963|         return results
03964| 
03965|     def search_pubmed(self, query: str, max_results: int = 10) -> List[Dict]:
// 进度: 第80行/共270行
03966|         results = []
03967|         try:
03968|             base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
03969|             params = {
03970|                 "db": "pubmed",
03971|                 "term": query,
03972|                 "retmax": max_results,
03973|                 "retmode": "json",
03974|                 "sort": "relevance"
03975|             }
03976|             headers = {"User-Agent": random.choice(USER_AGENTS)}
03977| 
03978|             response = requests.get(base_url, params=params, headers=headers, timeout=15)
03979|             if response.status_code == 200:
03980|                 data = response.json()
03981|                 ids = data.get("esearchresult", {}).get("idlist", [])
03982| 
03983|                 if ids:
03984|                     fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
03985|                     fetch_params = {
// 进度: 第100行/共270行
03986|                         "db": "pubmed",
03987|                         "id": ",".join(ids),
03988|                         "retmode": "json"
03989|                     }
03990|                     fetch_response = requests.get(fetch_url, params=fetch_params, headers=headers, timeout=15)
03991|                     if fetch_response.status_code == 200:
03992|                         summary_data = fetch_response.json()
03993|                         for pubmed_id in ids:
03994|                             try:
03995|                                 result = summary_data.get("result", {}).get(pubmed_id, {})
03996|                                 if result.get("uid"):
03997|                                     results.append({
03998|                                         "title": result.get("title", ""),
03999|                                         "authors": [a.get("name", "") for a in result.get("authors", [])],
04000|                                         "summary": result.get("summary", "")[:500],
04001|                                         "published": result.get("pubdate", ""),
04002|                                         "pdf_url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
04003|                                         "pubmed_id": pubmed_id,
04004|                                         "source": "PubMed",
04005|                                         "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
// 进度: 第120行/共270行
04006|                                     })
04007|                             except:
04008|                                 continue
04009|         except Exception as e:
04010|             print(f"PubMed search error: {e}")
04011|         return results
04012| 
04013|     def search_google_scholar(self, query: str, max_results: int = 10) -> List[Dict]:
04014|         results = []
04015|         try:
04016|             url = "https://scholar.google.com/scholar"
04017|             headers = {
04018|                 "User-Agent": random.choice(USER_AGENTS),
04019|                 "Accept": "text/html,application/xhtml+xml"
04020|             }
04021|             params = {"q": query, "num": min(max_results, 10), "hl": "en"}
04022| 
04023|             response = requests.get(url, params=params, headers=headers, timeout=15)
04024|             if response.status_code == 200:
04025|                 soup = BeautifulSoup(response.text, "html.parser")
// 进度: 第140行/共270行
04026| 
04027|                 for item in soup.select("div.gs_r")[:max_results]:
04028|                     try:
04029|                         title_elem = item.select_one("h3.gs_rt")
04030|                         title = title_elem.get_text(strip=True) if title_elem else ""
04031|                         title = re.sub(r'\[.*?\]', '', title)
04032| 
04033|                         link_elem = item.select_one("h3.gs_rt a")
04034|                         link = link_elem.get("href", "") if link_elem else ""
04035| 
04036|                         snippet = item.select_one("div.gs_rs")
04037|                         summary = snippet.get_text(strip=True) if snippet else ""
04038| 
04039|                         if title and link:
04040|                             results.append({
04041|                                 "title": title,
04042|                                 "authors": [],
04043|                                 "summary": summary[:500],
04044|                                 "published": "",
04045|                                 "pdf_url": "",
// 进度: 第160行/共270行
04046|                                 "source": "Google Scholar",
04047|                                 "url": link
04048|                             })
04049|                     except:
04050|                         continue
04051|         except Exception as e:
04052|             print(f"Google Scholar search error: {e}")
04053|         return results
04054| 
04055|     def search_ieee(self, query: str, max_results: int = 10) -> List[Dict]:
04056|         results = []
04057|         try:
04058|             url = "https://ieeexplore.ieee.org/rest/search"
04059|             headers = {
04060|                 "User-Agent": random.choice(USER_AGENTS),
04061|                 "Content-Type": "application/json",
04062|                 "Accept": "application/json"
04063|             }
04064|             payload = {
04065|                 "newsearch": True,
// 进度: 第180行/共270行
04066|                 "queryText": query,
04067|                 "matchPubs": True,
04068|                 "maxRecords": max_results,
04069|                 "returnFacets": ["ALL"]
04070|             }
04071| 
04072|             response = requests.post(url, json=payload, headers=headers, timeout=15)
04073|             if response.status_code == 200:
04074|                 data = response.json()
04075|                 records = data.get("records", [])
04076| 
04077|                 for record in records:
04078|                     try:
04079|                         results.append({
04080|                             "title": record.get("articleTitle", ""),
04081|                             "authors": [a.get("name", "") for a in record.get("authors", [])],
04082|                             "summary": record.get("abstract", "")[:500],
04083|                             "published": record.get("publicationDate", ""),
04084|                             "pdf_url": record.get("pdfUrl", ""),
04085|                             "ieee_id": record.get("articleNumber", ""),
// 进度: 第200行/共270行
04086|                             "source": "IEEE Xplore",
04087|                             "url": record.get("documentUrl", "")
04088|                         })
04089|                     except:
04090|                         continue
04091|         except Exception as e:
04092|             print(f"IEEE search error: {e}")
04093|         return results
04094| 
04095|     def search_doaj(self, query: str, max_results: int = 10) -> List[Dict]:
04096|         results = []
04097|         try:
04098|             url = "https://doaj.org/api/v2/search/articles"
04099|             params = {
04100|                 "query": query,
04101|                 "pageSize": max_results,
04102|                 "sort": "relevance"
04103|             }
04104|             headers = {"User-Agent": random.choice(USER_AGENTS)}
04105| 
// 进度: 第220行/共270行
04106|             response = requests.get(url, params=params, headers=headers, timeout=15)
04107|             if response.status_code == 200:
04108|                 data = response.json()
04109|                 articles = data.get("results", [])
04110| 
04111|                 for article in articles:
04112|                     try:
04113|                         results.append({
04114|                             "title": article.get("title", ""),
04115|                             "authors": [a.get("name", "") for a in article.get("authors", [])],
04116|                             "summary": article.get("abstract", "")[:500],
04117|                             "published": article.get("publishedDate", ""),
04118|                             "pdf_url": article.get("pdfUrl", ""),
04119|                             "doi": article.get("doi", ""),
04120|                             "source": "DOAJ",
04121|                             "url": article.get("url", "")
04122|                         })
04123|                     except:
04124|                         continue
04125|         except Exception as e:
// 进度: 第240行/共270行
04126|             print(f"DOAJ search error: {e}")
04127|         return results
04128| 
04129|     def search(self, query: str, max_results: int = 10) -> List[Dict]:
04130|         all_results = []
04131| 
04132|         with ThreadPoolExecutor(max_workers=5) as executor:
04133|             futures = [
04134|                 executor.submit(self.search_arxiv, query, max_results),
04135|                 executor.submit(self.search_semantic_scholar, query, max_results),
04136|                 executor.submit(self.search_pubmed, query, max_results),
04137|                 executor.submit(self.search_google_scholar, query, max_results),
04138|                 executor.submit(self.search_doaj, query, max_results),
04139|             ]
04140| 
04141|             for future in as_completed(futures):
04142|                 try:
04143|                     results = future.result()
04144|                     if results:
04145|                         all_results.extend(results)
// 进度: 第260行/共270行
04146|                 except Exception as e:
04147|                     print(f"Search error: {e}")
04148| 
04149|         all_results.sort(key=lambda x: x.get("published", ""), reverse=True)
04150|         return all_results[:max_results * 3]
04151| 
04152| 
04153| def get_academic_results(query: str, max_results: int = 10, api_key: Optional[str] = None) -> List[Dict]:
04154|     searcher = AcademicSearch(semantic_scholar_key=api_key)
04155|     return searcher.search(query, max_results)
// ==========
// 文件结束: .\academic_search.py
// 总行数: 270行
// 下一个文件: [等待添加]
// ==========


第303页：.\gui.py（完整314行）
04156| """
04157| IntelNexus GUI
04158| =============
04159| CustomTkinter-based GUI for IntelNexus.
04160| """
04161| 
04162| import os
04163| import sys
04164| import threading
04165| from datetime import datetime
04166| 
04167| import customtkinter as ctk
04168| from tkinter import filedialog
04169| 
04170| from llm import get_llm, refine_query, generate_summary
04171| from llm_utils import get_model_choices
04172| from web_search import get_web_results
04173| from news_search import get_news_results
04174| from darkweb_search import get_darkweb_results, is_available as darkweb_available
04175| from scrape import scrape_multiple
// 进度: 第20行/共314行
04176| from report_export import export_markdown
04177| 
04178| 
04179| ctk.set_appearance_mode("light")
04180| ctk.set_default_color_theme("blue")
04181| 
04182| SEARCH_MODES = {
04183|     "web": "网页搜索",
04184|     "news": "新闻资讯",
04185|     "darkweb": "暗网搜索",
04186|     "all": "全部来源"
04187| }
04188| 
04189| 
04190| class IntelNexusGUI(ctk.CTk):
04191|     def __init__(self):
04192|         super().__init__()
04193| 
04194|         self.title("IntelNexus - 多源网络情报分析平台")
04195|         self.geometry("1200x800")
// 进度: 第40行/共314行
04196| 
04197|         self.search_thread = None
04198|         self.stop_search = False
04199| 
04200|         self.setup_ui()
04201| 
04202|     def setup_ui(self):
04203|         self.grid_columnconfigure(1, weight=1)
04204|         self.grid_rowconfigure(0, weight=1)
04205| 
04206|         self.create_sidebar()
04207|         self.create_main_area()
04208| 
04209|     def create_sidebar(self):
04210|         self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
04211|         self.sidebar.grid(row=0, column=0, sticky="nsew")
04212|         self.sidebar.grid_rowconfigure(20, weight=1)
04213| 
04214|         title_label = ctk.CTkLabel(
04215|             self.sidebar,
// 进度: 第60行/共314行
04216|             text="IntelNexus",
04217|             font=ctk.CTkFont(size=24, weight="bold")
04218|         )
04219|         title_label.grid(row=0, column=0, padx=20, pady=(20, 10))
04220| 
04221|         subtitle = ctk.CTkLabel(
04222|             self.sidebar,
04223|             text="多源网络情报分析平台",
04224|             font=ctk.CTkFont(size=12)
04225|         )
04226|         subtitle.grid(row=1, column=0, padx=20, pady=(0, 20))
04227| 
04228|         mode_label = ctk.CTkLabel(self.sidebar, text="搜索模式", font=ctk.CTkFont(size=14, weight="bold"))
04229|         mode_label.grid(row=2, column=0, padx=20, pady=(10, 5))
04230| 
04231|         self.mode_var = ctk.StringVar(value="all")
04232|         for i, (mode, label) in enumerate(SEARCH_MODES.items()):
04233|             radio = ctk.CTkRadioButton(
04234|                 self.sidebar,
04235|                 text=label,
// 进度: 第80行/共314行
04236|                 variable=self.mode_var,
04237|                 value=mode
04238|             )
04239|             radio.grid(row=3 + i, column=0, padx=20, pady=5, sticky="w")
04240| 
04241|         model_label = ctk.CTkLabel(self.sidebar, text="AI模型", font=ctk.CTkFont(size=14, weight="bold"))
04242|         model_label.grid(row=8, column=0, padx=20, pady=(20, 5))
04243| 
04244|         model_choices = get_model_choices()
04245|         self.model_var = ctk.StringVar(value=model_choices[0] if model_choices else "qwen2.5:7b")
04246|         self.model_combo = ctk.CTkComboBox(
04247|             self.sidebar,
04248|             values=model_choices,
04249|             variable=self.model_var,
04250|             state="readonly"
04251|         )
04252|         self.model_combo.grid(row=9, column=0, padx=20, pady=5, sticky="ew")
04253| 
04254|         threads_label = ctk.CTkLabel(self.sidebar, text="线程数", font=ctk.CTkFont(size=14, weight="bold"))
04255|         threads_label.grid(row=10, column=0, padx=20, pady=(20, 5))
// 进度: 第100行/共314行
04256| 
04257|         self.threads_slider = ctk.CTkSlider(
04258|             self.sidebar,
04259|             from_=1,
04260|             to=16,
04261|             number_of_steps=15,
04262|             command=self.update_threads_label
04263|         )
04264|         self.threads_slider.set(5)
04265|         self.threads_slider.grid(row=11, column=0, padx=20, pady=5, sticky="ew")
04266| 
04267|         self.threads_label = ctk.CTkLabel(self.sidebar, text="5")
04268|         self.threads_label.grid(row=12, column=0, padx=20, pady=(0, 10))
04269| 
04270|         about_label = ctk.CTkLabel(
04271|             self.sidebar,
04272|             text="© 2024 IntelNexus\nAI驱动的网络情报平台",
04273|             font=ctk.CTkFont(size=10),
04274|             text_color="gray"
04275|         )
// 进度: 第120行/共314行
04276|         about_label.grid(row=21, column=0, padx=20, pady=10)
04277| 
04278|     def update_threads_label(self, value):
04279|         self.threads_label.configure(text=str(int(value)))
04280| 
04281|     def create_main_area(self):
04282|         self.main_frame = ctk.CTkFrame(self, corner_radius=0)
04283|         self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
04284| 
04285|         self.main_frame.grid_columnconfigure(0, weight=1)
04286|         self.main_frame.grid_rowconfigure(2, weight=1)
04287| 
04288|         header = ctk.CTkLabel(
04289|             self.main_frame,
04290|             text="搜索查询",
04291|             font=ctk.CTkFont(size=18, weight="bold")
04292|         )
04293|         header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
04294| 
04295|         input_frame = ctk.CTkFrame(self.main_frame)
// 进度: 第140行/共314行
04296|         input_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
04297|         input_frame.grid_columnconfigure(0, weight=1)
04298| 
04299|         self.query_entry = ctk.CTkEntry(
04300|             input_frame,
04301|             placeholder_text="输入搜索内容...",
04302|             height=40,
04303|             font=ctk.CTkFont(size=14)
04304|         )
04305|         self.query_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
04306| 
04307|         self.query_entry.bind("<Return>", lambda e: self.start_search())
04308| 
04309|         self.search_btn = ctk.CTkButton(
04310|             input_frame,
04311|             text="开始搜索",
04312|             height=40,
04313|             font=ctk.CTkFont(size=14, weight="bold"),
04314|             command=self.start_search
04315|         )
// 进度: 第160行/共314行
04316|         self.search_btn.grid(row=0, column=1)
04317| 
04318|         self.status_label = ctk.CTkLabel(
04319|             self.main_frame,
04320|             text="就绪",
04321|             font=ctk.CTkFont(size=12),
04322|             text_color="gray"
04323|         )
04324|         self.status_label.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")
04325| 
04326|         self.progress_bar = ctk.CTkProgressBar(self.main_frame)
04327|         self.progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
04328|         self.progress_bar.set(0)
04329| 
04330|         result_label = ctk.CTkLabel(
04331|             self.main_frame,
04332|             text="分析报告",
04333|             font=ctk.CTkFont(size=18, weight="bold")
04334|         )
04335|         result_label.grid(row=4, column=0, padx=20, pady=(20, 10), sticky="w")
// 进度: 第180行/共314行
04336| 
04337|         self.result_text = ctk.CTkTextbox(self.main_frame, font=ctk.CTkFont(size=12))
04338|         self.result_text.grid(row=5, column=0, sticky="nsew", padx=20, pady=10)
04339| 
04340|         btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
04341|         btn_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=10)
04342| 
04343|         self.save_btn = ctk.CTkButton(
04344|             btn_frame,
04345|             text="保存报告",
04346|             command=self.save_report,
04347|             state="disabled"
04348|         )
04349|         self.save_btn.pack(side="right")
04350| 
04351|     def start_search(self):
04352|         query = self.query_entry.get().strip()
04353|         if not query:
04354|             return
04355| 
// 进度: 第200行/共314行
04356|         self.search_btn.configure(state="disabled", text="搜索中...")
04357|         self.save_btn.configure(state="disabled")
04358|         self.result_text.delete("1.0", "end")
04359|         self.stop_search = False
04360| 
04361|         self.search_thread = threading.Thread(target=self.run_search, args=(query,))
04362|         self.search_thread.start()
04363| 
04364|     def run_search(self, query):
04365|         try:
04366|             self.update_status("初始化LLM...", 0.05)
04367|             model = self.model_var.get()
04368|             threads = int(self.threads_slider.get())
04369|             mode = self.mode_var.get()
04370| 
04371|             llm = get_llm(model)
04372| 
04373|             self.update_status("优化查询...", 0.1)
04374|             query_variants = refine_query(llm, query)
04375|             search_query = " | ".join(query_variants) if isinstance(query_variants, list) else query_variants
// 进度: 第220行/共314行
04376| 
04377|             self.update_status(f"搜索{SEARCH_MODES.get(mode, mode)}...", 0.2)
04378|             results = []
04379| 
04380|             with threading.ThreadPoolExecutor(max_workers=threads) as executor:
04381|                 futures = []
04382| 
04383|                 if mode in ["web", "all"]:
04384|                     futures.append(executor.submit(get_web_results, search_query, threads, 20))
04385| 
04386|                 if mode in ["news", "all"]:
04387|                     futures.append(executor.submit(get_news_results, search_query, 15))
04388| 
04389|                 if mode in ["darkweb", "all"] and darkweb_available():
04390|                     futures.append(executor.submit(get_darkweb_results, search_query, threads))
04391| 
04392|                 for f in futures:
04393|                     try:
04394|                         r = f.result()
04395|                         if r:
// 进度: 第240行/共314行
04396|                             results.extend(r)
04397|                     except Exception as e:
04398|                         print(f"Search error: {e}")
04399| 
04400|             self.update_status(f"找到 {len(results)} 条结果", 0.4)
04401| 
04402|             if not results:
04403|                 self.update_status("未找到结果", 0)
04404|                 self.search_complete()
04405|                 return
04406| 
04407|             self.update_status("抓取内容...", 0.6)
04408|             scraped = scrape_multiple(results, max_workers=threads)
04409| 
04410|             self.update_status("生成报告...", 0.8)
04411|             stream_handler = GUIStreamHandler(self.result_text)
04412|             llm.callbacks = [stream_handler]
04413| 
04414|             summary = generate_summary(llm, query, scraped)
04415| 
// 进度: 第260行/共314行
04416|             self.update_status("完成", 1.0)
04417|             self.search_complete()
04418| 
04419|         except Exception as e:
04420|             self.update_status(f"错误: {str(e)}", 0)
04421|             self.search_complete()
04422| 
04423|     def update_status(self, text, progress):
04424|         self.after(0, lambda: self.status_label.configure(text=text))
04425|         self.after(0, lambda: self.progress_bar.set(progress))
04426| 
04427|     def search_complete(self):
04428|         self.after(0, lambda: self.search_btn.configure(state="normal", text="开始搜索"))
04429|         self.after(0, lambda: self.save_btn.configure(state="normal"))
04430| 
04431|     def save_report(self):
04432|         content = self.result_text.get("1.0", "end").strip()
04433|         if not content:
04434|             return
04435| 
// 进度: 第280行/共314行
04436|         timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
04437|         filename = f"report_{timestamp}.md"
04438| 
04439|         filepath = filedialog.asksaveasfilename(
04440|             defaultextension=".md",
04441|             filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
04442|             initialfile=filename
04443|         )
04444| 
04445|         if filepath:
04446|             try:
04447|                 with open(filepath, "w", encoding="utf-8") as f:
04448|                     f.write(content)
04449|                 self.status_label.configure(text=f"已保存: {filepath}")
04450|             except Exception as e:
04451|                 self.status_label.configure(text=f"保存失败: {str(e)}")
04452| 
04453| 
04454| class GUIStreamHandler:
04455|     def __init__(self, text_widget):
// 进度: 第300行/共314行
04456|         self.text_widget = text_widget
04457| 
04458|     def on_llm_new_token(self, token, **kwargs):
04459|         self.text_widget.insert("end", token)
04460|         self.text_widget.see("end")
04461| 
04462| 
04463| def run_gui():
04464|     app = IntelNexusGUI()
04465|     app.mainloop()
04466| 
04467| 
04468| if __name__ == "__main__":
04469|     run_gui()
// ==========
// 文件结束: .\gui.py
// 总行数: 314行
// 下一个文件: [等待添加]
// ==========


第638页：.\keyword_extraction.py（完整182行）
04470| """
04471| Keyword Extraction Module
04472| ========================
04473| Extract and analyze keywords from search results and documents.
04474| """
04475| 
04476| import re
04477| from typing import List, Dict, Set, Tuple
04478| from collections import Counter
04479| import math
04480| 
04481| 
04482| class KeywordExtractor:
04483|     def __init__(self):
04484|         self.stopwords = self._load_stopwords()
04485| 
04486|     def _load_stopwords(self) -> Set[str]:
04487|         """Load common stopwords."""
04488|         return {
04489|             "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
// 进度: 第20行/共182行
04490|             "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
04491|             "be", "have", "has", "had", "do", "does", "did", "will", "would",
04492|             "could", "should", "may", "might", "must", "shall", "can", "need",
04493|             "this", "that", "these", "those", "i", "you", "he", "she", "it",
04494|             "we", "they", "what", "which", "who", "whom", "whose", "where",
04495|             "when", "why", "how", "all", "each", "every", "both", "few",
04496|             "more", "most", "other", "some", "such", "no", "nor", "not",
04497|             "only", "own", "same", "so", "than", "too", "very", "just",
04498|             "also", "now", "here", "there", "then", "once", "if", "because",
04499|             "until", "while", "about", "against", "between", "into", "through",
04500|             "during", "before", "after", "above", "below", "up", "down", "out",
04501|             "off", "over", "under", "again", "further", "any", "their", "them",
04502|             "his", "her", "its", "our", "your", "my", "said", "new", "one",
04503|             "two", "first", "last", "long", "little", "old", "great", "high",
04504|             "small", "large", "big", "early", "young", "important", "public",
04505|             "good", "bad", "best", "better", "well", "back", "still", "even",
04506|             "get", "got", "made", "make", "many", "much", "may", "take", "see",
04507|             "come", "only", "like", "way", "think", "even", "use", "used"
04508|         }
04509| 
// 进度: 第40行/共182行
04510|     def extract_keywords(self, text: str, top_n: int = 20) -> List[Dict]:
04511|         """Extract top keywords from text using TF-IDF-like scoring."""
04512|         words = self._preprocess(text)
04513| 
04514|         if not words:
04515|             return []
04516| 
04517|         word_freq = Counter(words)
04518|         total_words = len(words)
04519| 
04520|         word_scores = {}
04521|         for word, freq in word_freq.items():
04522|             if word in self.stopwords:
04523|                 continue
04524|             if len(word) < 3:
04525|                 continue
04526| 
04527|             tf = freq / total_words
04528| 
04529|             idf = math.log(1 + total_words / (freq + 1))
// 进度: 第60行/共182行
04530| 
04531|             word_scores[word] = tf * idf
04532| 
04533|         sorted_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
04534| 
04535|         return [
04536|             {"keyword": word, "score": round(score, 4), "frequency": word_freq[word]}
04537|             for word, score in sorted_words[:top_n]
04538|         ]
04539| 
04540|     def extract_phrases(self, text: str, top_n: int = 10) -> List[Dict]:
04541|         """Extract key phrases (2-4 words)."""
04542|         words = self._preprocess(text)
04543| 
04544|         phrases = []
04545|         for n in [2, 3, 4]:
04546|             for i in range(len(words) - n + 1):
04547|                 phrase = " ".join(words[i:i+n])
04548|                 phrases.append(phrase)
04549| 
// 进度: 第80行/共182行
04550|         if not phrases:
04551|             return []
04552| 
04553|         phrase_freq = Counter(phrases)
04554| 
04555|         filtered = {
04556|             p: f for p, f in phrase_freq.items()
04557|             if not any(sw in p.split() for sw in self.stopwords)
04558|         }
04559| 
04560|         sorted_phrases = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
04561| 
04562|         unique_phrases = []
04563|         seen = set()
04564|         for phrase, freq in sorted_phrases:
04565|             words_in_phrase = set(phrase.split())
04566|             is_subphrase = False
04567|             for seen_phrase in seen:
04568|                 if words_in_phrase.issubset(set(seen_phrase.split())):
04569|                     is_subphrase = True
// 进度: 第100行/共182行
04570|                     break
04571|             if not is_subphrase:
04572|                 unique_phrases.append({
04573|                     "phrase": phrase,
04574|                     "frequency": freq
04575|                 })
04576|                 seen.add(phrase)
04577|             if len(unique_phrases) >= top_n:
04578|                 break
04579| 
04580|         return unique_phrases
04581| 
04582|     def extract_entities(self, text: str) -> Dict:
04583|         """Extract named entities (simple pattern-based)."""
04584|         entities = {
04585|             "emails": re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text),
04586|             "urls": re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text),
04587|             "dates": re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text),
04588|             "years": re.findall(r'\b(19|20)\d{2}\b', text),
04589|             "numbers": re.findall(r'\b\d+(?:\.\d+)?(?:[kmb])?\b', text.lower()),
// 进度: 第120行/共182行
04590|         }
04591| 
04592|         return {k: list(set(v))[:20] for k, v in entities.items() if v}
04593| 
04594|     def analyze_content(self, content: Dict) -> Dict:
04595|         """Analyze content and extract all keywords, phrases, entities."""
04596|         text = ""
04597|         if isinstance(content, dict):
04598|             text = " ".join(str(v) for v in content.values() if v)
04599|         elif isinstance(content, list):
04600|             text = " ".join(str(item) for item in content if item)
04601|         else:
04602|             text = str(content)
04603| 
04604|         return {
04605|             "keywords": self.extract_keywords(text, 15),
04606|             "phrases": self.extract_phrases(text, 10),
04607|             "entities": self.extract_entities(text),
04608|             "stats": {
04609|                 "total_words": len(text.split()),
// 进度: 第140行/共182行
04610|                 "total_chars": len(text)
04611|             }
04612|         }
04613| 
04614|     def _preprocess(self, text: str) -> List[str]:
04615|         """Preprocess text for keyword extraction."""
04616|         text = text.lower()
04617| 
04618|         text = re.sub(r'http\S+|www\.\S+', '', text)
04619|         text = re.sub(r'\S+@\S+', '', text)
04620| 
04621|         text = re.sub(r'[^\w\s]', ' ', text)
04622| 
04623|         words = text.split()
04624| 
04625|         words = [w for w in words if w not in self.stopwords and len(w) >= 3]
04626| 
04627|         return words
04628| 
04629| 
// 进度: 第160行/共182行
04630| def extract_keywords(text: str, top_n: int = 20) -> List[Dict]:
04631|     """Quick keyword extraction function."""
04632|     extractor = KeywordExtractor()
04633|     return extractor.extract_keywords(text, top_n)
04634| 
04635| 
04636| def analyze_keywords(results: List[Dict]) -> Dict:
04637|     """Analyze keywords from search results."""
04638|     extractor = KeywordExtractor()
04639| 
04640|     all_content = ""
04641|     for result in results:
04642|         all_content += result.get("title", "") + " "
04643|         all_content += result.get("summary", "") + " "
04644|         all_content += result.get("description", "") + " "
04645|         all_content += result.get("content", "") + " "
04646| 
04647|     return {
04648|         "keywords": extractor.extract_keywords(all_content, 20),
04649|         "phrases": extractor.extract_phrases(all_content, 10),
// 进度: 第180行/共182行
04650|         "entities": extractor.extract_entities(all_content)
04651|     }
// ==========
// 文件结束: .\keyword_extraction.py
// 总行数: 182行
// 下一个文件: [等待添加]
// ==========


第835页：.\launcher.py（完整7行）
04652| import subprocess
04653| import sys
04654| import os
04655| 
04656| if __name__ == "__main__":
04657|     ui_path = os.path.join(os.getcwd(), "ui.py")
04658|     subprocess.run([sys.executable, "-m", "streamlit", "run", ui_path, "--server.port=8501", "--server.headless=true"])
// ==========
// 文件结束: .\launcher.py
// 总行数: 7行
// 下一个文件: [等待添加]
// ==========


第848页：.\multilang.py（完整168行）
04659| """
04660| Multi-Language Support Module
04661| ============================
04662| Support for multi-language search and translation.
04663| """
04664| 
04665| import re
04666| from typing import Dict, List, Optional, Tuple
04667| from collections import defaultdict
04668| 
04669| 
04670| LANGUAGE_CODES = {
04671|     "en": "English",
04672|     "zh": "Chinese",
04673|     "es": "Spanish",
04674|     "fr": "French",
04675|     "de": "German",
04676|     "ja": "Japanese",
04677|     "ko": "Korean",
04678|     "ru": "Russian",
// 进度: 第20行/共168行
04679|     "ar": "Arabic",
04680|     "pt": "Portuguese",
04681|     "it": "Italian",
04682|     "nl": "Dutch",
04683|     "pl": "Polish",
04684|     "tr": "Turkish",
04685|     "vi": "Vietnamese",
04686|     "th": "Thai",
04687|     "id": "Indonesian",
04688|     "hi": "Hindi",
04689| }
04690| 
04691| SEARCH_ENGINES_BY_LANG = {
04692|     "en": [
04693|         {"name": "Google", "url": "https://www.google.com/search?q={query}"},
04694|         {"name": "Bing", "url": "https://www.bing.com/search?q={query}"},
04695|     ],
04696|     "zh": [
04697|         {"name": "Baidu", "url": "https://www.baidu.com/s?wd={query}"},
04698|         {"name": "Bing Chinese", "url": "https://cn.bing.com/search?q={query}"},
// 进度: 第40行/共168行
04699|     ],
04700|     "es": [
04701|         {"name": "Google Spain", "url": "https://www.google.es/search?q={query}"},
04702|         {"name": "Bing Spain", "url": "https://www.bing.com/search?q={query}&setlang=es"},
04703|     ],
04704|     "ja": [
04705|         {"name": "Google Japan", "url": "https://www.google.co.jp/search?q={query}"},
04706|         {"name": "Yahoo Japan", "url": "https://search.yahoo.co.jp/search?p={query}"},
04707|     ],
04708| }
04709| 
04710| ACADEMIC_SOURCES = {
04711|     "en": ["arXiv", "Semantic Scholar", "Google Scholar"],
04712|     "zh": ["CNKI", "Wanfang", "Paper with Code"],
04713|     "ja": ["CiNii", "J-STAGE"],
04714| }
04715| 
04716| 
04717| class LanguageDetector:
04718|     def __init__(self):
// 进度: 第60行/共168行
04719|         self.chinese_chars = re.compile(r'[\u4e00-\u9fff]')
04720|         self.japanese_chars = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
04721|         self.korean_chars = re.compile(r'[\uac00-\ud7af]')
04722|         self.arabic_chars = re.compile(r'[\u0600-\u06ff]')
04723|         self.cyrillic_chars = re.compile(r'[\u0400-\u04ff]')
04724| 
04725|     def detect(self, text: str) -> Tuple[str, float]:
04726|         """Detect language of text."""
04727|         if not text:
04728|             return "en", 0.0
04729| 
04730|         text = text.lower()
04731| 
04732|         scores = defaultdict(int)
04733| 
04734|         if self.chinese_chars.search(text):
04735|             scores["zh"] += len(self.chinese_chars.findall(text)) * 2
04736| 
04737|         if self.japanese_chars.search(text):
04738|             scores["ja"] += len(self.japanese_chars.findall(text)) * 2
// 进度: 第80行/共168行
04739| 
04740|         if self.korean_chars.search(text):
04741|             scores["ko"] += len(self.korean_chars.findall(text)) * 2
04742| 
04743|         if self.arabic_chars.search(text):
04744|             scores["ar"] += len(self.arabic_chars.findall(text)) * 2
04745| 
04746|         english_words = len([w for w in text.split() if w in "the a is are was were be been have has had do does did"])
04747|         scores["en"] += english_words
04748| 
04749|         if not scores:
04750|             return "en", 0.5
04751| 
04752|         total = sum(scores.values())
04753|         detected_lang = max(scores, key=scores.get)
04754|         confidence = scores[detected_lang] / total if total > 0 else 0.5
04755| 
04756|         return detected_lang, min(confidence, 1.0)
04757| 
04758|     def get_language_name(self, code: str) -> str:
// 进度: 第100行/共168行
04759|         """Get language name from code."""
04760|         return LANGUAGE_CODES.get(code, code.upper())
04761| 
04762| 
04763| class MultiLanguageSearch:
04764|     def __init__(self):
04765|         self.detector = LanguageDetector()
04766| 
04767|     def detect_query_language(self, query: str) -> Dict:
04768|         """Detect the language of a search query."""
04769|         lang_code, confidence = self.detector.detect(query)
04770| 
04771|         return {
04772|             "code": lang_code,
04773|             "name": self.detector.get_language_name(lang_code),
04774|             "confidence": round(confidence, 2)
04775|         }
04776| 
04777|     def get_search_engines(self, language: str = "en") -> List[Dict]:
04778|         """Get search engines for specific language."""
// 进度: 第120行/共168行
04779|         return SEARCH_ENGINES_BY_LANG.get(language, SEARCH_ENGINES_BY_LANG["en"])
04780| 
04781|     def get_academic_sources(self, language: str = "en") -> List[str]:
04782|         """Get academic sources for specific language."""
04783|         return ACADEMIC_SOURCES.get(language, ACADEMIC_SOURCES["en"])
04784| 
04785|     def suggest_translations(self, query: str, target_langs: List[str] = None) -> Dict:
04786|         """Suggest query translations for other languages."""
04787|         if target_langs is None:
04788|             target_langs = ["en", "zh", "es", "fr", "de", "ja"]
04789| 
04790|         current_lang, _ = self.detector.detect(query)
04791| 
04792|         suggestions = {}
04793|         for lang in target_langs:
04794|             if lang != current_lang:
04795|                 suggestions[lang] = {
04796|                     "code": lang,
04797|                     "name": self.detector.get_language_name(lang),
04798|                     "note": f"Translation to {self.detector.get_language_name(lang)} recommended"
// 进度: 第140行/共168行
04799|                 }
04800| 
04801|         return {
04802|             "original": {
04803|                 "query": query,
04804|                 "language": current_lang,
04805|                 "name": self.detector.get_language_name(current_lang)
04806|             },
04807|             "alternatives": suggestions
04808|         }
04809| 
04810|     def get_supported_languages(self) -> List[Dict]:
04811|         """Get list of supported languages."""
04812|         return [
04813|             {"code": code, "name": name}
04814|             for code, name in LANGUAGE_CODES.items()
04815|         ]
04816| 
04817| 
04818| def detect_language(text: str) -> Tuple[str, float]:
// 进度: 第160行/共168行
04819|     """Quick language detection."""
04820|     detector = LanguageDetector()
04821|     return detector.detect(text)
04822| 
04823| 
04824| def get_language_name(code: str) -> str:
04825|     """Get language name from code."""
04826|     return LANGUAGE_CODES.get(code, code.upper())
// ==========
// 文件结束: .\multilang.py
// 总行数: 168行
// 下一个文件: [等待添加]
// ==========


第1030页：.\run.py（完整48行）
04827| import os
04828| import sys
04829| import logging
04830| 
04831| logging.basicConfig(level=logging.DEBUG, filename='streamlit_debug.log', filemode='w')
04832| 
04833| def main():
04834|     logging.info("=" * 50)
04835|     logging.info("IntelNexus Starting")
04836|     logging.info(f"Frozen: {getattr(sys, 'frozen', False)}")
04837|     logging.info(f"sys.executable: {sys.executable}")
04838|     logging.info(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
04839|     logging.info(f"sys.argv: {sys.argv}")
04840|     logging.info("=" * 50)
04841| 
04842|     ui_path = os.path.join(sys._MEIPASS, 'ui.py') if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.py")
04843| 
04844|     logging.info(f"UI path: {ui_path}")
04845|     logging.info(f"UI exists: {os.path.exists(ui_path)}")
04846| 
// 进度: 第20行/共48行
04847|     if getattr(sys, 'frozen', False):
04848|         sys.path.insert(0, sys._MEIPASS)
04849|         logging.info(f"Added to sys.path: {sys._MEIPASS}")
04850| 
04851|     logging.info("Importing streamlit...")
04852|     try:
04853|         from streamlit.web import cli as stcli
04854|         logging.info("Streamlit imported successfully")
04855| 
04856|         sys.argv = [
04857|             "streamlit", "run", ui_path,
04858|             "--server.port=8501",
04859|             "--server.headless=true",
04860|             "--server.autoOpenBrowser=true",
04861|             "--global.developmentMode=false"
04862|         ]
04863|         logging.info(f"streamlit argv: {sys.argv}")
04864| 
04865|         logging.info("Calling stcli.main()...")
04866|         stcli.main()
// 进度: 第40行/共48行
04867|     except Exception as e:
04868|         logging.error(f"Error: {e}")
04869|         import traceback
04870|         logging.error(traceback.format_exc())
04871|         input("Error occurred. Press Enter to exit...")
04872| 
04873| if __name__ == "__main__":
04874|     main()
// ==========
// 文件结束: .\run.py
// 总行数: 48行
// 下一个文件: [等待添加]
// ==========


第1086页：.\run_nuitka.py（完整13行）
04875| import os
04876| import sys
04877| import subprocess
04878| 
04879| if __name__ == "__main__":
04880|     ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.py")
04881|     subprocess.run([
04882|         sys.executable, "-m", "streamlit", "run", ui_path,
04883|         "--server.port=8501",
04884|         "--server.headless=true",
04885|         "--server.enableCors=false",
04886|         "--server.enableXsrfProtection=false"
04887|     ])
// ==========
// 文件结束: .\run_nuitka.py
// 总行数: 13行
// 下一个文件: [等待添加]
// ==========


第1105页：.\setup_cx.py（完整34行）
04888| from cx_Freeze import setup, Executable
04889| import os
04890| 
04891| build_options = {
04892|     "packages": [
04893|         "streamlit",
04894|         "streamlit.web.cli",
04895|         "streamlit.runtime",
04896|         "click",
04897|         "altair",
04898|         "pandas",
04899|         "numpy",
04900|     ],
04901|     "excludes": [],
04902|     "include_files": [
04903|         "ui.py",
04904|     ],
04905| }
04906| 
04907| executables = [
// 进度: 第20行/共34行
04908|     Executable(
04909|         "run_nuitka.py",
04910|         base="console",
04911|         target_name="IntelNexus.exe",
04912|     )
04913| ]
04914| 
04915| setup(
04916|     name="IntelNexus",
04917|     version="1.0",
04918|     description="AI-Powered Multi-Source Network Intelligence Platform",
04919|     options={"build_exe": build_options},
04920|     executables=executables,
04921| )
// ==========
// 文件结束: .\setup_cx.py
// 总行数: 34行
// 下一个文件: [等待添加]
// ==========


第1146页：.\social_search.py（完整309行）
04922| import os
04923| import requests
04924| import random
04925| from typing import List, Dict, Optional
04926| from concurrent.futures import ThreadPoolExecutor, as_completed
04927| from bs4 import BeautifulSoup
04928| 
04929| try:
04930|     import tweepy
04931| except ImportError:
04932|     tweepy = None
04933| 
04934| try:
04935|     import praw
04936| except ImportError:
04937|     praw = None
04938| 
04939| USER_AGENTS = [
04940|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
04941|     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
// 进度: 第20行/共309行
04942|     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
04943| ]
04944| 
04945| 
04946| class SocialSearch:
04947|     def __init__(self, twitter_token: Optional[str] = None, reddit_client: Optional[object] = None):
04948|         self.twitter_token = twitter_token
04949|         self.reddit_client = reddit_client
04950| 
04951|         if tweepy and twitter_token:
04952|             try:
04953|                 self.twitter_client = tweepy.Client(bearer_token=twitter_token)
04954|             except Exception as e:
04955|                 print(f"Twitter client init error: {e}")
04956|                 self.twitter_client = None
04957|         else:
04958|             self.twitter_client = None
04959| 
04960|     def search_twitter(self, query: str, max_results: int = 10) -> List[Dict]:
04961|         results = []
// 进度: 第40行/共309行
04962| 
04963|         if not self.twitter_client:
04964|             return results
04965| 
04966|         try:
04967|             tweets = self.twitter_client.search_recent_tweets(
04968|                 query=query,
04969|                 max_results=min(max_results, 100),
04970|                 tweet_fields=["created_at", "author_id", "public_metrics"]
04971|             )
04972| 
04973|             if tweets.data:
04974|                 for tweet in tweets.data:
04975|                     results.append({
04976|                         "title": tweet.text[:200],
04977|                         "content": tweet.text,
04978|                         "author_id": str(tweet.author_id) if tweet.author_id else "",
04979|                         "created_at": str(tweet.created_at) if tweet.created_at else "",
04980|                         "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
04981|                         "retweets": tweet.public_metrics.get("retweet_count", 0) if tweet.public_metrics else 0,
// 进度: 第60行/共309行
04982|                         "source": "Twitter/X"
04983|                     })
04984|         except Exception as e:
04985|             print(f"Twitter search error: {e}")
04986| 
04987|         return results
04988| 
04989|     def search_reddit(self, query: str, max_results: int = 10) -> List[Dict]:
04990|         results = []
04991| 
04992|         if not self.reddit_client:
04993|             return results
04994| 
04995|         try:
04996|             subreddits = ["all", "technology", "science", "news", "worldnews"]
04997| 
04998|             for subreddit_name in subreddits[:2]:
04999|                 try:
05000|                     subreddit = self.reddit_client.subreddit(subreddit_name)
05001|                     posts = subreddit.search(query, limit=max_results)
// 进度: 第80行/共309行
05002| 
05003|                     for post in posts:
05004|                         results.append({
05005|                             "title": post.title,
05006|                             "content": post.selftext[:500] if post.selftext else "",
05007|                             "author": str(post.author) if post.author else "",
05008|                             "score": post.score,
05009|                             "num_comments": post.num_comments,
05010|                             "created_utc": str(post.created_utc),
05011|                             "url": post.url,
05012|                             "source": f"Reddit r/{subreddit_name}"
05013|                         })
05014|                 except Exception as e:
05015|                     print(f"Reddit search error in {subreddit_name}: {e}")
05016|         except Exception as e:
05017|             print(f"Reddit search error: {e}")
05018| 
05019|         return results
05020| 
05021|     def search_reddit_public(self, query: str, max_results: int = 10) -> List[Dict]:
// 进度: 第100行/共309行
05022|         results = []
05023| 
05024|         try:
05025|             url = f"https://www.reddit.com/search.json?q={requests.utils.quote(query)}&limit={max_results}&sort=relevance"
05026|             headers = {
05027|                 "User-Agent": random.choice(USER_AGENTS),
05028|                 "Accept": "application/json"
05029|             }
05030|             response = requests.get(url, headers=headers, timeout=15)
05031| 
05032|             if response.status_code == 200:
05033|                 data = response.json()
05034|                 children = data.get("data", {}).get("children", [])
05035| 
05036|                 for child in children:
05037|                     post = child.get("data", {})
05038|                     if post.get("is_video") or post.get("nsfw"):
05039|                         continue
05040|                     results.append({
05041|                         "title": post.get("title", ""),
// 进度: 第120行/共309行
05042|                         "content": post.get("selftext", "")[:500],
05043|                         "author": post.get("author", ""),
05044|                         "score": post.get("score", 0),
05045|                         "num_comments": post.get("num_comments", 0),
05046|                         "created_utc": post.get("created_utc", ""),
05047|                         "url": f"https://reddit.com{post.get('permalink', '')}",
05048|                         "source": "Reddit"
05049|                     })
05050|         except Exception as e:
05051|             print(f"Reddit public search error: {e}")
05052| 
05053|         return results
05054| 
05055|     def search_hackernews(self, query: str, max_results: int = 10) -> List[Dict]:
05056|         results = []
05057| 
05058|         try:
05059|             url = f"https://hn.algolia.com/api/v1/search"
05060|             params = {"query": query, "tags": "story", "hitsPerPage": max_results}
05061|             headers = {"User-Agent": random.choice(USER_AGENTS)}
// 进度: 第140行/共309行
05062| 
05063|             response = requests.get(url, params=params, headers=headers, timeout=15)
05064| 
05065|             if response.status_code == 200:
05066|                 data = response.json()
05067|                 hits = data.get("hits", [])
05068| 
05069|                 for hit in hits:
05070|                     results.append({
05071|                         "title": hit.get("title", ""),
05072|                         "content": hit.get("story_text", "")[:500] if hit.get("story_text") else "",
05073|                         "author": hit.get("author", ""),
05074|                         "score": hit.get("points", 0),
05075|                         "num_comments": hit.get("num_comments", 0),
05076|                         "created_utc": hit.get("created_at", ""),
05077|                         "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
05078|                         "source": "Hacker News"
05079|                     })
05080|         except Exception as e:
05081|             print(f"Hacker News search error: {e}")
// 进度: 第160行/共309行
05082| 
05083|         return results
05084| 
05085|     def search_stackoverflow(self, query: str, max_results: int = 10) -> List[Dict]:
05086|         results = []
05087| 
05088|         try:
05089|             url = "https://api.stackexchange.com/2.3/search/advanced"
05090|             params = {
05091|                 "order": "desc",
05092|                 "sort": "relevance",
05093|                 "q": query,
05094|                 "site": "stackoverflow",
05095|                 "pagesize": max_results
05096|             }
05097|             headers = {"User-Agent": random.choice(USER_AGENTS)}
05098| 
05099|             response = requests.get(url, params=params, headers=headers, timeout=15)
05100| 
05101|             if response.status_code == 200:
// 进度: 第180行/共309行
05102|                 data = response.json()
05103|                 items = data.get("items", [])
05104| 
05105|                 for item in items:
05106|                     results.append({
05107|                         "title": item.get("title", ""),
05108|                         "content": item.get("body_markdown", "")[:500] if item.get("body_markdown") else "",
05109|                         "author": item.get("owner", {}).get("display_name", ""),
05110|                         "score": item.get("score", 0),
05111|                         "num_comments": item.get("answer_count", 0),
05112|                         "created_utc": item.get("creation_date", ""),
05113|                         "url": item.get("link", ""),
05114|                         "source": "Stack Overflow"
05115|                     })
05116|         except Exception as e:
05117|             print(f"Stack Overflow search error: {e}")
05118| 
05119|         return results
05120| 
05121|     def search_zhihu(self, query: str, max_results: int = 10) -> List[Dict]:
// 进度: 第200行/共309行
05122|         results = []
05123| 
05124|         try:
05125|             url = f"https://www.zhihu.com/api/v4/search_v3"
05126|             params = {
05127|                 "q": query,
05128|                 "type": "topic",
05129|                 "limit": max_results,
05130|                 "offset": 0
05131|             }
05132|             headers = {
05133|                 "User-Agent": random.choice(USER_AGENTS),
05134|                 "Referer": "https://www.zhihu.com"
05135|             }
05136| 
05137|             response = requests.get(url, params=params, headers=headers, timeout=15)
05138| 
05139|             if response.status_code == 200:
05140|                 data = response.json()
05141|                 items = data.get("data", [])
// 进度: 第220行/共309行
05142| 
05143|                 for item in items:
05144|                     results.append({
05145|                         "title": item.get("highlight", {}).get("title", item.get("name", "")),
05146|                         "content": item.get("excerpt", "")[:500] if item.get("excerpt") else "",
05147|                         "author": "",
05148|                         "score": item.get("follower_count", 0),
05149|                         "num_comments": item.get("discussion_count", 0),
05150|                         "created_utc": "",
05151|                         "url": f"https://www.zhihu.com/topic/{item.get('id', '')}",
05152|                         "source": "知乎"
05153|                     })
05154|         except Exception as e:
05155|             print(f"Zhihu search error: {e}")
05156| 
05157|         return results
05158| 
05159|     def search_weibo(self, query: str, max_results: int = 10) -> List[Dict]:
05160|         results = []
05161| 
// 进度: 第240行/共309行
05162|         try:
05163|             url = "https://m.weibo.cn/api/container/getIndex"
05164|             params = {
05165|                 "containerid": f"100103type=1&q={requests.utils.quote(query)}",
05166|                 "page": 1
05167|             }
05168|             headers = {
05169|                 "User-Agent": random.choice(USER_AGENTS),
05170|                 "Referer": "https://m.weibo.cn"
05171|             }
05172| 
05173|             response = requests.get(url, params=params, headers=headers, timeout=15)
05174| 
05175|             if response.status_code == 200:
05176|                 data = response.json()
05177|                 cards = data.get("data", {}).get("cards", [])
05178| 
05179|                 for card in cards:
05180|                     if card.get("card_type") == 9:
05181|                         mblog = card.get("mblog", {})
// 进度: 第260行/共309行
05182|                         results.append({
05183|                             "title": mblog.get("text", "")[:200],
05184|                             "content": mblog.get("text", ""),
05185|                             "author": mblog.get("user", {}).get("screen_name", ""),
05186|                             "score": mblog.get("attitudes_count", 0),
05187|                             "num_comments": mblog.get("comments_count", 0),
05188|                             "created_utc": mblog.get("created_at", ""),
05189|                             "url": f"https://weibo.com/detail/{mblog.get('id', '')}",
05190|                             "source": "微博"
05191|                         })
05192|         except Exception as e:
05193|             print(f"Weibo search error: {e}")
05194| 
05195|         return results
05196| 
05197|     def search(self, query: str, max_results: int = 10) -> List[Dict]:
05198|         all_results = []
05199| 
05200|         with ThreadPoolExecutor(max_workers=6) as executor:
05201|             futures = []
// 进度: 第280行/共309行
05202| 
05203|             if self.twitter_client:
05204|                 futures.append(executor.submit(self.search_twitter, query, max_results))
05205| 
05206|             if self.reddit_client:
05207|                 futures.append(executor.submit(self.search_reddit, query, max_results))
05208|             else:
05209|                 futures.append(executor.submit(self.search_reddit_public, query, max_results))
05210| 
05211|             futures.append(executor.submit(self.search_hackernews, query, max_results))
05212|             futures.append(executor.submit(self.search_stackoverflow, query, max_results))
05213|             futures.append(executor.submit(self.search_zhihu, query, max_results))
05214|             futures.append(executor.submit(self.search_weibo, query, max_results))
05215| 
05216|             for future in as_completed(futures):
05217|                 try:
05218|                     results = future.result()
05219|                     if results:
05220|                         all_results.extend(results)
05221|                 except Exception as e:
// 进度: 第300行/共309行
05222|                     print(f"Search error: {e}")
05223| 
05224|         all_results.sort(key=lambda x: x.get("score", 0) + x.get("likes", 0), reverse=True)
05225|         return all_results[:max_results * 3]
05226| 
05227| 
05228| def get_social_results(query: str, max_results: int = 10, twitter_token: Optional[str] = None) -> List[Dict]:
05229|     searcher = SocialSearch(twitter_token=twitter_token)
05230|     return searcher.search(query, max_results)
// ==========
// 文件结束: .\social_search.py
// 总行数: 309行
// 下一个文件: [等待添加]
// ==========


第1476页：.\trend_analysis.py（完整192行）
05231| """
05232| Trend Analysis Module
05233| ====================
05234| Analyze research trends and topics from search results.
05235| """
05236| 
05237| import re
05238| from typing import List, Dict, Optional
05239| from collections import Counter
05240| from datetime import datetime, timedelta
05241| import json
05242| import os
05243| 
05244| 
05245| TRENDING_KEYWORDS = {
05246|     "ai": ["machine learning", "deep learning", "neural network", "GPT", "LLM", "transformer", "AI"],
05247|     "tech": ["quantum", "blockchain", "web3", "metaverse", "AR", "VR"],
05248|     "science": ["climate", "CRISPR", "fusion", "space", "astronomy"],
05249|     "security": ["cybersecurity", "privacy", "encryption", "zero-day"],
05250| }
// 进度: 第20行/共192行
05251| 
05252| 
05253| class TrendAnalyzer:
05254|     def __init__(self):
05255|         self.trend_data_file = "data/trends.json"
05256| 
05257|     def analyze_results(self, results: List[Dict]) -> Dict:
05258|         """Analyze search results for trends."""
05259|         if not results:
05260|             return {"error": "No results to analyze"}
05261| 
05262|         keywords = self._extract_keywords(results)
05263|         sources = self._analyze_sources(results)
05264|         topics = self._identify_topics(results)
05265|         timeline = self._estimate_timeline(results)
05266| 
05267|         return {
05268|             "keywords": keywords,
05269|             "sources": sources,
05270|             "topics": topics,
// 进度: 第40行/共192行
05271|             "timeline": timeline,
05272|             "total_results": len(results)
05273|         }
05274| 
05275|     def _extract_keywords(self, results: List[Dict]) -> List[Dict]:
05276|         """Extract and count keywords from results."""
05277|         all_text = ""
05278| 
05279|         for result in results:
05280|             all_text += result.get("title", "") + " "
05281|             all_text += result.get("summary", "") + " "
05282|             all_text += result.get("description", "") + " "
05283|             all_text += result.get("content", "") + " "
05284| 
05285|         words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
05286| 
05287|         stopwords = {
05288|             "this", "that", "with", "from", "have", "been", "will", "were",
05289|             "they", "their", "what", "about", "which", "when", "make", "like",
05290|             "time", "just", "know", "take", "people", "into", "year", "your",
// 进度: 第60行/共192行
05291|             "good", "some", "could", "them", "see", "other", "than", "then",
05292|             "now", "look", "only", "come", "its", "over", "think", "also"
05293|         }
05294| 
05295|         words = [w for w in words if w not in stopwords]
05296|         word_counts = Counter(words)
05297| 
05298|         top_keywords = [
05299|             {"keyword": word, "count": count}
05300|             for word, count in word_counts.most_common(15)
05301|         ]
05302| 
05303|         return top_keywords
05304| 
05305|     def _analyze_sources(self, results: List[Dict]) -> Dict:
05306|         """Analyze distribution of sources."""
05307|         source_counts = Counter()
05308| 
05309|         for result in results:
05310|             source = result.get("source", "Unknown")
// 进度: 第80行/共192行
05311|             source_counts[source] += 1
05312| 
05313|         return {
05314|             "distribution": dict(source_counts),
05315|             "total_sources": len(source_counts)
05316|         }
05317| 
05318|     def _identify_topics(self, results: List[Dict]) -> List[Dict]:
05319|         """Identify main topics from results."""
05320|         text = ""
05321|         for result in results:
05322|             text += result.get("title", "") + " "
05323| 
05324|         text_lower = text.lower()
05325| 
05326|         topics = []
05327|         for category, keywords in TRENDING_KEYWORDS.items():
05328|             matched = []
05329|             for keyword in keywords:
05330|                 if keyword.lower() in text_lower:
// 进度: 第100行/共192行
05331|                     matched.append(keyword)
05332|             if matched:
05333|                 topics.append({
05334|                     "category": category,
05335|                     "keywords": matched,
05336|                     "relevance": len(matched) / len(keywords)
05337|                 })
05338| 
05339|         topics.sort(key=lambda x: x["relevance"], reverse=True)
05340|         return topics[:5]
05341| 
05342|     def _estimate_timeline(self, results: List[Dict]) -> Dict:
05343|         """Estimate timeline of results."""
05344|         dates = []
05345| 
05346|         for result in results:
05347|             published = result.get("published") or result.get("published_at") or ""
05348|             if published:
05349|                 try:
05350|                     if "T" in published:
// 进度: 第120行/共192行
05351|                         date = published.split("T")[0]
05352|                     else:
05353|                         date = published[:10]
05354|                     dates.append(date)
05355|                 except:
05356|                     pass
05357| 
05358|         if not dates:
05359|             return {"range": "Unknown", "recent": 0}
05360| 
05361|         dates.sort()
05362| 
05363|         now = datetime.now()
05364|         recent_count = 0
05365|         for date in dates:
05366|             try:
05367|                 d = datetime.strptime(date[:10], "%Y-%m-%d")
05368|                 if (now - d).days < 30:
05369|                     recent_count += 1
05370|             except:
// 进度: 第140行/共192行
05371|                 pass
05372| 
05373|         return {
05374|             "earliest": dates[0] if dates else None,
05375|             "latest": dates[-1] if dates else None,
05376|             "recent_30_days": recent_count,
05377|             "total_dated": len(dates)
05378|         }
05379| 
05380|     def get_trending(self) -> Dict:
05381|         """Get overall trending data."""
05382|         if not os.path.exists(self.trend_data_file):
05383|             return {"trending_keywords": [], "recent_searches": []}
05384| 
05385|         try:
05386|             with open(self.trend_data_file, 'r') as f:
05387|                 return json.load(f)
05388|         except:
05389|             return {"trending_keywords": [], "recent_searches": []}
05390| 
// 进度: 第160行/共192行
05391|     def save_trend(self, query: str, keywords: List[str]):
05392|         """Save trend data."""
05393|         data = self.get_trending()
05394| 
05395|         if "trending_keywords" not in data:
05396|             data["trending_keywords"] = []
05397|         if "recent_searches" not in data:
05398|             data["recent_searches"] = []
05399| 
05400|         for kw in keywords[:5]:
05401|             data["trending_keywords"].append({
05402|                 "keyword": kw,
05403|                 "timestamp": datetime.now().isoformat()
05404|             })
05405| 
05406|         data["recent_searches"].insert(0, {
05407|             "query": query,
05408|             "timestamp": datetime.now().isoformat()
05409|         })
05410| 
// 进度: 第180行/共192行
05411|         data["trending_keywords"] = data["trending_keywords"][-100:]
05412|         data["recent_searches"] = data["recent_searches"][:50]
05413| 
05414|         os.makedirs("data", exist_ok=True)
05415|         with open(self.trend_data_file, 'w') as f:
05416|             json.dump(data, f, indent=2)
05417| 
05418| 
05419| def analyze_trends(results: List[Dict]) -> Dict:
05420|     """Quick trend analysis function."""
05421|     analyzer = TrendAnalyzer()
05422|     return analyzer.analyze_results(results)
// ==========
// 文件结束: .\trend_analysis.py
// 总行数: 192行
// 下一个文件: [等待添加]
// ==========
