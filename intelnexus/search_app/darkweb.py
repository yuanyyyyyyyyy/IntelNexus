"""
Dark Web Search Module
====================
This module supports:
1. Public dark web search engines (Ahmia, OnionLink)
2. Custom .onion sites with optional authentication

Enable via .env: ENABLE_DARKWEB=true
"""

import os
import socket

import base64
import requests
import random
import json
from urllib.parse import parse_qs, quote, unquote, urlparse
from bs4 import BeautifulSoup

from intelnexus.core.logger import get_logger
from intelnexus.core.search_constants import USER_AGENTS

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


def fetch_with_auth(url, auth=None, tor_port=None):
    """使用认证访问暗网站点"""
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    session = requests.Session()
    session.headers.update(headers)

    # 设置代理
    port = tor_port or get_tor_proxy_port()
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
    except Exception as e:
        logger.warning(f"自定义 onion 站点访问失败 {url[:80]}: {type(e).__name__}: {e}")
        return None


def search_custom_onion_site(site_config, query, tor_port=None):
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

        response = fetch_with_auth(search_url, auth, tor_port=tor_port)

        if response is not None and response.status_code != 200:
            logger.warning(f"自定义 onion 站点 {name} 返回 HTTP {response.status_code}: {base_url[:80]}")

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

# Reference list of known .onion search engines (for documentation / future expansion).
# Currently active engines used in search: Ahmia (public), OnionLink & TorDex (Tor required).
# To add more engines, uncomment and wire them into get_darkweb_results().
# _DARKWEB_ENGINE_REFERENCE = [
#     {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}"},
#     {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}"},
#     {"name": "Amnesia", "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}"},
#     {"name": "Kaizer", "url": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}"},
#     {"name": "Tornado", "url": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}"},
#     {"name": "TorNet", "url": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}"},
#     {"name": "Tor66", "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}"},
# ]

# Import from shared to avoid duplication
from intelnexus.core.search_constants import get_tor_proxy_port  # noqa: E402


def fetch_ahmia_results(query):
    """从Ahmia获取暗网搜索结果（无需Tor，明网直连/系统代理均可）。

    Ahmia 2026 改版后 /search/?q= 返回 JS 壳页（站方自述未部署非 JS 版），
    需先从壳页提取反爬隐藏 token（如 f119ab=156abb）二次请求才返回服务端
    渲染结果。token 名值动态提取，站方轮换字段名时无需改代码；壳页直接
    含结果时省去二次请求。
    """
    results = []
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        session = requests.Session()

        response = session.get(
            f"https://ahmia.fi/search/?q={quote(query)}",
            headers=headers, timeout=12)
        if response.status_code != 200:
            logger.warning(f"Ahmia 壳页返回 HTTP {response.status_code}")
            return results

        # 壳页无结果时提取 token 二次请求
        if "<h4" not in response.text:
            soup = BeautifulSoup(response.text, "html.parser")
            form = soup.find("form", id="searchForm") or soup
            hidden = form.find("input", {"type": "hidden"})
            if hidden and hidden.get("name") and hidden.get("value"):
                response = session.get(
                    "https://ahmia.fi/search/",
                    params={"q": query, hidden["name"]: hidden["value"]},
                    headers=headers, timeout=15)
                if response.status_code != 200:
                    logger.warning(f"Ahmia 结果页返回 HTTP {response.status_code}")
                    return results

        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.select("h4 a[href]"):
            try:
                href = str(a.get("href", ""))
                title = a.get_text(strip=True)
                if not title or len(title) <= 2:
                    continue
                if "redirect_url=" in href:
                    # 结果链接是站方跳转包装，真实 onion 地址在 redirect_url 参数里
                    qs = parse_qs(urlparse(href).query)
                    link = unquote(qs.get("redirect_url", [""])[0])
                elif ".onion" in href.lower():
                    link = href if href.startswith("http") else f"https://ahmia.fi{href}"
                else:
                    continue
                if ".onion" not in link.lower():
                    continue
                # 摘要跟随 h4 后的 <p>，供相关性评分与可信度评估使用（缺失不阻塞）
                description = ""
                try:
                    p = a.find_parent("h4").find_next_sibling("p")
                    if p is not None:
                        description = p.get_text(strip=True)[:300]
                except Exception:
                    pass
                results.append({
                    "title": title[:100] or "暗网资源",
                    "link": link,
                    "description": description,
                    "source": "Ahmia"
                })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Ahmia 检索失败: {type(e).__name__}: {e}")

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
    except Exception as e:
        logger.warning(f"OnionLink 检索失败: {type(e).__name__}: {e}")

    return results


def fetch_tordex_search(query, tor_port=None):
    """从TorDex搜索获取结果"""
    results = []
    try:
        url = f"https://tordexu72joez4ofvtvk6hxdlh3cvt7qexvzuwcyhyhj5f5xt22b5gfqd.onion/search?q={quote(query)}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        port = tor_port or get_tor_proxy_port()
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
    except Exception as e:
        logger.warning(f"TorDex 检索失败: {type(e).__name__}: {e}")

    return results


def is_available():
    """检查暗网搜索是否可用"""
    if not ENABLE_DARKWEB:
        return False
    return True


def tor_reachable(port=None, timeout=1.0):
    """探测本地 Tor SOCKS 代理端口是否可连（仅 TCP 握手，不发 SOCKS 请求）。

    用于把「Tor 没开导致的空结果」与「确实没有暗网结果」区分开：
    前者应作为错误信号进健康面板，后者是正常业务空结果。
    """
    try:
        port = int(port or get_tor_proxy_port())
    except (TypeError, ValueError):
        port = 9150
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


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
                search_results = fetch_tordex_search(query, tor_port=tor_port)
                if search_results:
                    results.extend(search_results)
            except Exception:
                pass

        # 3. 自定义暗网站点（支持认证）
        custom_sites = get_custom_onion_sites(ui_sites)
        for site in custom_sites:
            try:
                site_results = search_custom_onion_site(site, query, tor_port=tor_port)
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
