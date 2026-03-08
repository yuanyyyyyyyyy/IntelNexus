"""
Dark Web Search Module (OPTIONAL)
=================================
This module requires Tor to be running (SOCKS5 proxy on 127.0.0.1:9150)
Enable via .env: ENABLE_DARKWEB=true

WARNING: This module is for educational and authorized research purposes only.
"""

import os
import requests
import random
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import warnings
warnings.filterwarnings("ignore")

ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
]

DARKWEB_SEARCH_ENGINES = [
    "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}",
    "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}",
    "http://darkhuntyla64h75a3re5e2l3367lqn7ltmdzpgmr6b4nbz3q2iaxrid.onion/search?q={query}",
    "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}",
    "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}",
    "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}",
    "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}",
    "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}",
]

def get_tor_session():
    session = requests.Session()
    retry = Retry(total=3, read=3, connect=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.proxies = {"http": "socks5h://127.0.0.1:9150", "https": "socks5h://127.0.0.1:9150"}
    return session

def fetch_darkweb_results(endpoint, query):
    url = endpoint.format(query=query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = get_tor_session()
    
    try:
        response = session.get(url, headers=headers, timeout=40)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            for a in soup.find_all('a'):
                try:
                    href = a['href']
                    title = a.get_text(strip=True)
                    link = re.findall(r'https?:\/\/[a-z0-9\.]+\.onion.*', href)
                    if len(link) != 0:
                        if "search" not in link[0] and len(title) > 3:
                            links.append({"title": title, "link": link[0]})
                except:
                    continue
            return links
    except:
        pass
    return []

def is_available():
    return ENABLE_DARKWEB

def get_darkweb_results(refined_query, max_workers=5):
    if not ENABLE_DARKWEB:
        return []
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_darkweb_results, endpoint, refined_query)
                   for endpoint in DARKWEB_SEARCH_ENGINES]
        for future in as_completed(futures):
            result_urls = future.result()
            results.extend(result_urls)

    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link", "").rstrip('/')
        if link not in seen_links:
            seen_links.add(link)
            unique_results.append(res)
            
    return unique_results
