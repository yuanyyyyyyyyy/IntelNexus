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

import base64
import requests
import random
import json
from urllib.parse import quote
from bs4 import BeautifulSoup

from src.logger import get_logger
from src.search import USER_AGENTS

logger = get_logger(__name__)

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
        except Exception:
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
    except Exception:
        pass
    
    # 3. 合并UI传递的站点
    if ui_sites:
        for us in ui_sites:
            if us not in sites:
                sites.append(us)
    
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
    except Exception:
        return None


def search_custom_onion_site(site_config, query):
    """搜索自定义暗网站点"""
    results = []
    try:
        base_url = site_config.get("url", "")
        auth = site_config.get("auth")
        name = site_config.get("name", "Custom")

        # Decode base64-encoded password if present
        if auth and isinstance(auth.get("password"), str):
            try:
                auth = dict(auth)
                auth["password"] = base64.b64decode(auth["password"].encode("utf-8")).decode("utf-8")
            except Exception:
                pass

        # 尝试访问站点并搜索
        search_url = f"{base_url}?search={quote(query)}"
        
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
                except Exception:
                    continue
    except Exception:
        pass
    
    return results

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

# Import from src.search to avoid duplication
from src.search import get_tor_proxy_port  # noqa: E402


def fetch_ahmia_results(query):
    """从Ahmia获取暗网搜索结果（无需Tor）"""
    results = []
    try:
        url = f"https://ahmia.fi/search/?q={quote(query)}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=12)
        
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
                except Exception:
                    continue
    except Exception:
        pass
    
    return results


def fetch_onionlink_search(query):
    """从onionlink搜索获取结果（无需Tor）"""
    results = []
    try:
        url = f"https://onionlink.net/?s={quote(query)}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=12)
        
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
                except Exception:
                    continue
    except Exception:
        pass
    
    return results


def fetch_tordex_search(query):
    """从TorDex搜索获取结果（无需Tor）"""
    results = []
    try:
        url = f"https://tordexu72joez4ofvtvk6hxdlh3cvt7qexvzuwcyhyhj5f5xt22b5gfqd.onion/search?q={quote(query)}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        port = get_tor_proxy_port()
        response = requests.get(url, headers=headers, timeout=12, proxies={
            "http": f"socks5h://127.0.0.1:{port}",
            "https": f"socks5h://127.0.0.1:{port}"
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
                except Exception:
                    continue
    except Exception:
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
        except Exception:
            pass
        
        # 2. 高级模式：使用Tor代理搜索
        if advanced_mode:
            # OnionLink搜索（需要Tor）
            try:
                search_results = fetch_onionlink_search(query)
                if search_results:
                    results.extend(search_results)
            except Exception:
                pass
            
            # TorDex搜索（需要Tor）
            try:
                search_results = fetch_tordex_search(query)
                if search_results:
                    results.extend(search_results)
            except Exception:
                pass
        
        # 3. 自定义暗网站点（支持认证）
        custom_sites = get_custom_onion_sites(ui_sites)
        for site in custom_sites:
            try:
                site_results = search_custom_onion_site(site, query)
                if site_results:
                    results.extend(site_results)
            except Exception:
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
