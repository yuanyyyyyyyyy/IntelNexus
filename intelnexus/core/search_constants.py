"""Shared search constants and helpers.

Lives outside the core.search package on purpose: darkweb (imported by the
search source registry) needs USER_AGENTS / get_tor_proxy_port without
triggering core.search.__init__ and its registry -> sources -> darkweb cycle.
"""
import os
from datetime import datetime, timedelta

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def get_tor_proxy_port():
    """获取Tor代理端口（与 darkweb.py 保持一致）"""
    custom_port = os.getenv("TOR_PROXY_PORT")
    if custom_port:
        try:
            return int(custom_port)
        except Exception:
            pass
    return 9150


# ========== 安全领域同义词词典 ==========
SYNONYM_DICT = {
    # 漏洞相关
    "vulnerability": ["漏洞", "弱点", "安全缺陷"],
    "漏洞": ["vulnerability", "弱点", "安全缺陷"],
    "cve": ["漏洞编号", "安全公告"],
    "漏洞编号": ["cve"],
    "0day": ["零日漏洞", "零日", "zero-day", "zero day"],
    "零日漏洞": ["0day", "零日", "zero-day", "zero day"],
    "rce": ["远程代码执行", "remote code execution"],
    "远程代码执行": ["rce", "remote code execution"],
    "xss": ["跨站脚本", "cross-site scripting"],
    "跨站脚本": ["xss", "cross-site scripting"],
    "sqli": ["sql注入", "sql injection"],
    "sql注入": ["sqli", "sql injection"],
    "lfi": ["本地文件包含", "local file inclusion"],
    "本地文件包含": ["lfi", "local file inclusion"],
    "rfi": ["远程文件包含", "remote file inclusion"],
    "远程文件包含": ["rfi", "remote file inclusion"],
    "ssrf": ["服务器端请求伪造", "server-side request forgery"],
    "服务器端请求伪造": ["ssrf", "server-side request forgery"],
    "csrf": ["跨站请求伪造", "cross-site request forgery"],
    "跨站请求伪造": ["csrf", "cross-site request forgery"],
    "提权": ["权限提升", "privilege escalation", "privilege escalation"],
    "权限提升": ["提权", "privilege escalation"],
    "代码注入": ["code injection"],
    "反序列化漏洞": ["deserialization vulnerability", "insecure deserialization"],
    "内存溢出": ["buffer overflow", "heap overflow", "stack overflow"],
    "缓冲区溢出": ["buffer overflow", "heap overflow", "stack overflow"],

    # 攻击相关
    "exploit": ["利用", "攻击代码", "漏洞利用"],
    "利用": ["exploit", "攻击代码", "漏洞利用"],
    "攻击代码": ["exploit", "利用", "漏洞利用"],
    "apt": ["高级持续威胁", "advanced persistent threat"],
    "高级持续威胁": ["apt", "advanced persistent threat"],
    "勒索软件": ["ransomware", "勒索病毒"],
    "ransomware": ["勒索软件", "勒索病毒"],
    "钓鱼攻击": ["phishing", "phishing attack"],
    "phishing": ["钓鱼攻击", "phishing attack"],
    "ddos": ["分布式拒绝服务", "distributed denial of service"],
    "分布式拒绝服务": ["ddos", "distributed denial of service"],
    "供应链攻击": ["supply chain attack", "supply chain compromise"],
    "supply chain attack": ["供应链攻击"],
    "零信任": ["zero trust"],
    "zero trust": ["零信任"],

    # 数据泄露相关
    "breach": ["泄露", "数据泄露", "安全事件"],
    "泄露": ["breach", "数据泄露", "安全事件"],
    "数据泄露": ["data breach", "data leak", "breach"],
    "data breach": ["数据泄露", "data leak", "breach"],
    "data leak": ["数据泄露", "data breach", "breach"],

    # AI 相关
    "llm": ["大语言模型", "large language model", "大模型"],
    "大语言模型": ["llm", "large language model", "大模型"],
    "大模型": ["llm", "大语言模型", "large language model"],
    "ai安全": ["ai security", "artificial intelligence security"],
    "ai security": ["ai安全", "artificial intelligence security"],
    "模型投毒": ["model poisoning", "data poisoning"],
    "数据投毒": ["data poisoning", "model poisoning"],
    "提示注入": ["prompt injection", "prompt hacking"],
    "prompt injection": ["提示注入", "prompt hacking"],
    "对抗样本": ["adversarial example", "adversarial attack"],
    "adversarial example": ["对抗样本", "adversarial attack"],

    # 合规相关
    "gdpr": ["通用数据保护条例", "general data protection regulation"],
    "通用数据保护条例": ["gdpr", "general data protection regulation"],
    "等保": ["网络安全等级保护", "classified protection of cybersecurity"],
    "网络安全等级保护": ["等保", "classified protection of cybersecurity"],
    "数据安全法": ["data security law", "dsl"],
    "个人信息保护法": ["personal information protection law", "pipl"],
    "网络安全法": ["cybersecurity law", "csl"],

    # 厂商相关
    "奇安信": ["qianxin", "qianxin security"],
    "深信服": ["sangfor", "sangfor security"],
    "绿盟科技": ["nsfocus", "nsfocus security"],
    "启明星辰": ["venustech", "venustech security"],
    "安恒信息": ["dbappsecurity", "dbappsecurity security"],
    "天融信": ["topsec", "topsec security"],
    "安天": ["antiy", "antiy security"],
    "360": ["qihoo 360", "360 security"],
}


def expand_synonyms(query: str) -> list:
    """
    对查询中的关键词进行同义词扩展。

    Args:
        query: 原始查询字符串

    Returns:
        扩展后的查询列表（包含原始查询和同义词扩展）
    """
    import re

    tokens = re.split(r"[\s,，。、;；]+", query)
    expanded = [query]

    for token in tokens:
        token_lower = token.lower()
        if token_lower in SYNONYM_DICT:
            synonyms = SYNONYM_DICT[token_lower]
            # 用同义词替换原词生成新查询
            for syn in synonyms[:2]:  # 最多取2个同义词
                new_query = query.replace(token, syn, 1)
                if new_query != query and new_query not in expanded:
                    expanded.append(new_query)

    return expanded[:3]  # 最多返回3个扩展查询


def get_freshness_score(published_at: str) -> float:
    """
    根据发布时间计算时效性评分。

    Args:
        published_at: 发布时间字符串（ISO格式或YYYY-MM-DD格式）

    Returns:
        时效性评分（0.0 ~ 0.2）
    """
    if not published_at or published_at in ("Unknown date", "Unknown-Date", ""):
        return 0.0

    try:
        # 尝试解析ISO格式
        if "T" in published_at:
            pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        else:
            # 尝试解析YYYY-MM-DD格式
            pub_date = datetime.strptime(published_at[:10], "%Y-%m-%d")

        now = datetime.now()
        delta = now - pub_date

        if delta <= timedelta(days=1):
            return 0.2  # 24小时内
        elif delta <= timedelta(days=7):
            return 0.1  # 7天内
        elif delta <= timedelta(days=30):
            return 0.05  # 30天内
        else:
            return 0.0
    except Exception:
        return 0.0
