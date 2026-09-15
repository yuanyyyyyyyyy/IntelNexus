import random
import re
import ipaddress
from html import unescape
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
# get_cached 保留导入：既有调用方与测试按名 patch 它，读取统一走 get_cached_entry
from intelnexus.core.settings.cache import get_cached, get_cached_entry, set_cached  # noqa: F401

from intelnexus.core.logger import get_logger
from intelnexus.core.search import USER_AGENTS, get_http_proxies, get_session, get_shared_tor_session

try:
    import trafilatura
except ImportError:
    trafilatura = None  # 未安装时静默降级为整页文本

logger = get_logger(__name__)

# 反爬验证码页特征：URL 特征（百度 wappass / captcha 路径）+ 文本特征兜底。
# 验证码页通常返回 HTTP 200 且带最终 URL（跟随重定向后），若不识别，
# 验证码文本会被当正文进入评分/实体/证据链路，验证码 URL 会被当作真实地址回写
_CAPTCHA_URL_HOSTS = ('wappass.', 'captcha.')
_CAPTCHA_TEXT_MARKERS = ('安全验证', '请输入验证码', '拖动滑块', '滑块验证', '完成拼图')


def _is_captcha_response(final_url: str, text: str) -> bool:
    """判断抓取到的页面是否为反爬验证码页。"""
    try:
        parsed = urlparse(final_url or '')
        host = (parsed.netloc or '').lower()
        path = (parsed.path or '').lower()
    except Exception:
        return False
    if any(h in host for h in _CAPTCHA_URL_HOSTS) or 'captcha' in path:
        return True
    head = (text or '')[:500]
    return sum(1 for m in _CAPTCHA_TEXT_MARKERS if m in head) >= 2


def _extract_main_text(html_text: str) -> str:
    """用 trafilatura 提取正文主内容（去导航/广告/侧栏/相关推荐）。

    返回空串表示未提取到（开关关闭/库缺失/失败/内容过短），调用方应
    降级为整页文本。整页文本会混入广告与页面框架文案，污染实体图谱
    和舆情输入，主内容提取是这些噪声的源头治理。
    """
    from config import ENABLE_MAIN_CONTENT_EXTRACTION
    if not ENABLE_MAIN_CONTENT_EXTRACTION or trafilatura is None or not html_text:
        return ""
    try:
        extracted = trafilatura.extract(
            html_text,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
    except Exception as e:
        logger.debug(f"正文提取失败（降级整页文本）: {type(e).__name__}")
        return ""
    return (extracted or "").strip() if extracted and len(extracted) >= 100 else ""


# 服务端未跟随重定向时（百度部分出口返回 200 + 脚本/meta 跳转），真实地址
# 只能从已下载的 HTML 里取；再发请求探测会翻倍耗时且触发风控，故离线解析。
_META_REFRESH_RE = re.compile(
    r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]*content=["\'][^"\']*?url=([^"\'>]+)',
    re.IGNORECASE)
_JS_REDIRECT_RE = re.compile(
    r'(?:window\.)?location(?:\.href)?\s*=\s*["\']([^"\']+)["\']'
    r'|location\.replace\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE)


def _is_wrapper_url(url: str) -> bool:
    """是否为搜索引擎跳转包装域（名单复用 core.search.web，延迟导入避循环）。"""
    try:
        from intelnexus.core.search.web import is_wrapper_url
        return is_wrapper_url(url)
    except Exception:
        return False


def _resolve_wrapper_target(final_url: str, html: str, limit: int = 20000) -> str:
    """从页面 HTML 解析跳转目标（meta refresh / JS location 赋值）。

    仅在最终 URL 仍落在搜索引擎包装域时调用；返回空串表示未解析到可用目标。
    解析出的目标同样要过 SSRF 校验——页面可伪造跳转把抓取引向内网。
    """
    if not html:
        return ""
    head = html[:limit]
    candidates = []
    m = _META_REFRESH_RE.search(head)
    if m:
        candidates.append(unescape(m.group(1).strip()))
    m = _JS_REDIRECT_RE.search(head)
    if m:
        candidates.append(unescape((m.group(1) or m.group(2) or "").strip()))

    for cand in candidates:
        if not cand:
            continue
        try:
            target = urljoin(final_url, cand) if not cand.startswith("http") else cand
        except Exception:
            continue
        if target.startswith("http") and is_safe_scrape_target(target):
            return target
    return ""


def is_safe_scrape_target(url: str) -> bool:
    """抓取目标防护（SSRF 第一层）：仅允许 http(s)，拒绝内网/环回地址。

    与 sources.py 的用户源校验独立——搜索结果 URL 同样可能指向内网
    （恶意页面投放 http://169.254.169.254/ 类地址诱导抓取）。
    DNS 解析后的 Rebinding 防护超出本层职责，此处只做语法与字面 IP 判定。
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower().strip(".")
        if not host:
            return False
        # 字面量 IPv4/IPv6 直接判定；域名做常见内网名后缀拦截
        if ":" in host:  # IPv6 字面量
            return not ipaddress.ip_address(host.strip("[]")).is_private \
                and not ipaddress.ip_address(host.strip("[]")).is_loopback
        try:
            ip = ipaddress.ip_address(host)
            return not ip.is_private and not ip.is_loopback and not ip.is_link_local
        except ValueError:
            pass
        if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
            return False
        return True
    except Exception:
        return False


def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL using a robust Tor session.
    Returns a tuple (url, scraped_text).
    """
    # 兼容 link/url 双键：registry 归一化输出 url 键，darkweb 等旧路径输出 link 键
    url = url_data.get('link') or url_data.get('url') or ''
    if not url:
        return '', ''
    if not is_safe_scrape_target(url):
        logger.warning(f"跳过不安全抓取目标: {url[:120]}")
        return url, ''

    entry = get_cached_entry(url)
    if entry is not None:
        cached = entry.get("content")
        if cached is not None:
            # 命中缓存时同样回填真实地址：包装链接的真实地址只在抓取时解析得到，
            # 不回写的话二次检索会重新变成 url=... 的壳，去重与证据溯源全部失效。
            resolved = entry.get("resolved_url")
            if resolved:
                url_data['resolved_url'] = resolved
            return (url, cached)

    if url.lower().endswith('.pdf') or '.pdf?' in url.lower():
        return (url, f"{url_data['title']} - [PDF文件，请直接下载查看]")

    use_tor = ".onion" in url

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        if use_tor:
            # 复用共享 Tor Session 单例（带连接池与重试）
            session = get_shared_tor_session()
            response = session.get(url, headers=headers, timeout=45)
        else:
            # 复用共享 HTTP Session（连接池 + 自动重试）
            session = get_session(get_http_proxies())
            response = session.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(response.text, "html.parser")
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            text = ' '.join(text.split())

            # 反爬验证码页（如百度 wappass 验证码）返回 200：丢弃正文走 title
            # 降级，且不回写 resolved_url，避免验证码 URL/文本污染下游链路
            # （验证码检测用整页文本，保持检测面完整）
            if _is_captcha_response(response.url or url, text):
                logger.debug(f"检测到反爬验证码页，丢弃正文: {url[:120]}")
                return url, url_data['title']

            # 正文主内容提取：去导航/广告/侧栏，失败保持整页文本（现状行为）
            main_text = _extract_main_text(response.text)
            if main_text:
                text = main_text

            # 包装 URL（如 baidu.com/link?url=）无法离线解码，抓取时跟随
            # 重定向后把真实地址回写到结果条目，供去重/评分/证据库使用。
            # 最终 URL 仍在包装域时（服务端返回脚本/meta 跳转），再从已下载
            # 的 HTML 离线解析一次，避免为解析地址额外发请求。
            try:
                final_url = response.url or url
                resolved = final_url if final_url != url else ""
                if not resolved or _is_wrapper_url(final_url):
                    resolved = _resolve_wrapper_target(final_url, response.text)
                if resolved and resolved != url and is_safe_scrape_target(resolved):
                    url_data['resolved_url'] = resolved
            except Exception:
                logger.debug(f"真实地址解析失败（不影响正文）: {url[:120]}")

            if len(text) < 100:
                scraped_text = url_data['title']
            else:
                scraped_text = f"{url_data['title']} - {text}"
        else:
            scraped_text = url_data['title']
    except Exception as e:
        scraped_text = url_data['title']

    return url, scraped_text

def scrape_multiple(urls_data, max_workers=5, resolved_map=None):
    """
    Scrapes multiple URLs concurrently using a thread pool.

    Args:
        urls_data: 结果条目列表（dict，含 url/link 与 title）。
        max_workers: 并发线程数。
        resolved_map: 可选输出字典，收集 {原始(包装)URL: 真实地址}，供调用方
            同步换键（结果条目与抓取字典的键必须一致，否则可信度评估会错位）。

    Returns:
        {URL: 抓取内容}；解析出真实地址时键为真实地址。
    """
    results = {}
    max_chars = 3000

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single, url_data): url_data
            for url_data in urls_data
        }
        for future in as_completed(future_to_url):
            url_data = future_to_url[future]
            try:
                url, content = future.result()
                if not url:
                    continue
                if len(content) > max_chars:
                    content = content[:max_chars] + "...(truncated)"
                resolved = url_data.get('resolved_url') if isinstance(url_data, dict) else None
                final_url = resolved or url
                results[final_url] = content
                if resolved and isinstance(resolved_map, dict):
                    resolved_map[url] = resolved
                # 缓存键仍是原始 URL：下次抓取请求的是包装链接，真实地址随条目回写
                set_cached(url, content, resolved_url=resolved)
            except Exception:
                continue

    return results
