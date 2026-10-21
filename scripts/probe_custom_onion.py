"""自定义 onion 源接入预检（演示日工具，R17b）。

拿到访客的 .onion 源 URL 后先跑本脚本，60-150 秒内判定「能否直接在
自定义站点面板接入」，避免演示现场才发现查询形态不匹配。

用法:
    python scripts/probe_custom_onion.py <url> [--basic user:pass]
        [--cookie k=v ...] [--port 2080] [--query ransomware] [--timeout 75]

判定逻辑：
1. Tor SOCKS 可达性；
2. base_url 经 Tor 的可达性（超时可到 75s——新站首链 60-75s 属常态）；
3. 用与 search_custom_onion_site 完全相同的代码路径跑真实搜索
   （请求侧超时固定 30s，新站首搜大概率超时，脚本自动做一次预热重试）；
4. 按结果与 CUSTOM_SITE_LAST_ERRORS 给出「可直接接入 / 需适配」结论。

URL 写法（与应用内添加面板一致）：
- 模板形态（推荐）：http://站点.onion/search?q={query}   —— 兼容 ?q=/?query=
- 无占位符：       http://站点.onion                      —— 按 ?search= 追加
"""
import argparse
import socket
import sys
import time

sys.path.insert(0, ".")

import requests


def _title_of(html: str) -> str:
    low = html.lower()
    i = low.find("<title>")
    j = low.find("</title>")
    return html[i + 7:j].strip() if 0 <= i < j else "(无标题)"


def main() -> int:
    ap = argparse.ArgumentParser(description="自定义 onion 源接入预检")
    ap.add_argument("url", help="站点 URL，可含 {query} 占位符")
    ap.add_argument("--basic", default=None, help="Basic 认证 user:pass")
    ap.add_argument("--cookie", action="append", default=[], help="Cookie k=v，可多次")
    ap.add_argument("--port", type=int, default=None, help="Tor SOCKS 端口（默认 TOR_PROXY_PORT/2080）")
    ap.add_argument("--query", default="ransomware", help="试搜关键词")
    ap.add_argument("--timeout", type=int, default=75, help="可达性探测超时秒数")
    args = ap.parse_args()

    from intelnexus.core.search_constants import get_tor_proxy_port
    port = args.port or get_tor_proxy_port() or 2080

    print(f"[0] Tor SOCKS 127.0.0.1:{port} ...", end=" ")
    try:
        socket.create_connection(("127.0.0.1", port), timeout=3).close()
        print("可达")
    except Exception as e:
        print(f"不可达（{type(e).__name__}）—— 先运行 scripts/start_tor.bat")
        return 2

    proxies = {"http": f"socks5h://127.0.0.1:{port}", "https": f"socks5h://127.0.0.1:{port}"}
    headers = {"User-Agent": "Mozilla/5.0 (intelnexus-probe)"}
    auth = None
    if args.basic:
        user, _, pwd = args.basic.partition(":")
        auth = {"type": "basic", "username": user, "password": pwd}
    elif args.cookie:
        auth = {"type": "cookie",
                "cookies": dict(kv.split("=", 1) for kv in args.cookie)}

    print(f"[1] base_url 可达性（超时 {args.timeout}s；新站首链 60-75s 属常态）...")
    t0 = time.time()
    try:
        resp = requests.get(args.url.replace("{query}", args.query), proxies=proxies,
                            headers=headers, timeout=args.timeout,
                            auth=tuple(args.basic.split(":", 1)) if args.basic else None)
        dt = time.time() - t0
        print(f"    HTTP {resp.status_code}，{dt:.1f}s，{len(resp.text)} chars，标题: {_title_of(resp.text)[:60]}")
    except Exception as e:
        print(f"    不可达: {type(e).__name__}: {e}")
        print("判定: ✗ 站点经 Tor 不可达 —— 先解决地址/网络/Tor 出海，再谈接入")
        return 1

    print(f"[2] 端到端试搜（与应用同代码路径，查询词 {args.query!r}；"
          "请求侧超时 30s，首搜超时会自动预热重试一次）...")
    from intelnexus.search_app import darkweb as dw

    site = {"name": "probe", "url": args.url}
    if auth:
        site["auth"] = auth

    results = dw.search_custom_onion_site(site, args.query, tor_port=port)
    if not results:
        print("    首搜 0 条（新站首链预热中，属预期）——重试一次...")
        results = dw.search_custom_onion_site(site, args.query, tor_port=port)

    err = dw.CUSTOM_SITE_LAST_ERRORS.get("probe")
    if results:
        print(f"    命中 {len(results)} 条，示例:")
        for r in results[:3]:
            print(f"      - {r['title'][:50]}  {r['link'][:70]}")
        print("判定: ✓ 可直接接入 —— 在「暗网搜索 → 自定义暗网站点」面板按同 URL 添加即可")
        print("      （记得：演示前重启 Tor；若现场首搜 0 条，再搜一次即恢复）")
        return 0

    print(f"    归因: {err or '未知'}")
    if err and "不支持 ?search=" in err and "{query}" not in args.url:
        print("判定: ✗ 需适配 —— 站点不支持 ?search= 形态。"
              "找到站内搜索 URL（把一次真实搜索的地址栏 URL 抄下来，查询词换成 {query}）"
              "后用模板形态重跑本脚本。")
    elif err and "请求失败" in err:
        print("判定: △ 站点可达但 30s 请求超时 —— 新站建链慢，重跑本脚本；"
              "若稳定超时则站点响应过慢，演示时需提前预热。")
    else:
        print("判定: ✗ 需适配 —— 见上方归因（HTTP 非 200 / 解析 0 条 / 认证失败）。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
