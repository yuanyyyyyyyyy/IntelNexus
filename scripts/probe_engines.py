"""暗网引擎存活探测（P2「引擎健康探测」工具，R10f/R11c 版）。

用法：
    .venv\\Scripts\\python.exe scripts\\probe_engines.py            # 标准：快慢双段超时
    .venv\\Scripts\\python.exe scripts\\probe_engines.py --quick    # 快扫：单段 12s

要点（两次踩坑换来的）：
1. .onion 首次建链实测 20-75 秒——单段 20s 超时会把活站误判为死站
   （2026-10-20 因此误判 OnionLand/Tor66 已死，随后接入成为新引擎）。
   故标准模式用「快 15s → 慢 70s」两段式：真死站 15s 内快速失败，
   慢建站第二段给足耐心。
2. 错误分类：`General SOCKS server failure (0x01)` = Tor 明确建链失败
   （站点大概率真死）；Connect/ReadTimeout = 建链慢，站点可能存活。
3. 连续多个 .onion 站超时 = Tor 电路整体老化的信号，此时建议重启 Tor
   （scripts\\restart_tor.bat），而不是逐个拉黑引擎。

Tor 需已运行（scripts\\start_tor.bat）。
"""
import sys
import time

import requests

TOR_PORT = 2080
QUERY = "ransomware"
PROXIES = {"http": f"socks5h://127.0.0.1:{TOR_PORT}", "https": f"socks5h://127.0.0.1:{TOR_PORT}"}

# (名称, URL, 是否经 Tor)；.onion 引擎必须走 socks5h
ENGINES = [
    ("Ahmia(明网)", "https://ahmia.fi/search/?q=" + QUERY, False),
    ("OnionLand", "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q=" + QUERY, True),
    ("Torgle", "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query=" + QUERY, True),
    ("Amnesia", "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query=" + QUERY, True),
    ("Kaizer", "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q=" + QUERY, True),
    ("Tornado", "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q=" + QUERY, True),
    ("TorNet", "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q=" + QUERY, True),
    ("Tor66", "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q=" + QUERY, True),
    ("DDG-onion", "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/html/?q=" + QUERY, True),
]

_ONION_TIMEOUT_SIGNATURES = ("general socks server failure", "timed out", "timeout", "10060", "10054")


def _probe_once(url: str, timeout: float):
    t = time.time()
    r = requests.get(url, timeout=timeout, proxies=PROXIES,
                     headers={"User-Agent": "Mozilla/5.0"})
    return r, time.time() - t


def probe_onion(name: str, url: str) -> str:
    """快慢双段探测：快段 15s 快速筛掉真死站，慢段 70s 给慢建站耐心。"""
    try:
        r, dt = _probe_once(url, 15)
        n = r.text.count(".onion")
        return f"ALIVE HTTP {r.status_code} onion-links={n} {dt:.1f}s"
    except Exception as fast_err:
        fast_sig = str(fast_err).lower()
        if not any(sig in fast_sig for sig in _ONION_TIMEOUT_SIGNATURES):
            # 非超时类错误（如连接被拒）重试意义不大，但仍给一次慢段确认
            pass
    try:
        r, dt = _probe_once(url, 70)
        n = r.text.count(".onion")
        return f"ALIVE(slow) HTTP {r.status_code} onion-links={n} {dt:.1f}s"
    except Exception as slow_err:
        s = str(slow_err)
        if "general socks server failure" in s.lower() or "0x01" in s:
            return f"DEAD Tor建链失败(0x01)——站点大概率已死 {time.time() % 100:.0f}"
        return f"DEAD? 超时/重置——可能存活，建议稍后复测或重启Tor"

def main() -> int:
    quick = "--quick" in sys.argv
    alive, slow_sites, onion_timeouts = [], [], 0
    print("=" * 60)
    print(f"暗网引擎存活探测（Tor SOCKS {TOR_PORT}，"
          f"{'快扫 12s' if quick else '快慢双段 15s/70s'}）")
    print("=" * 60)
    for name, url, via_tor in ENGINES:
        t = time.time()
        try:
            if quick:
                r = requests.get(url, timeout=12, proxies=PROXIES if via_tor else None,
                                 headers={"User-Agent": "Mozilla/5.0"})
                n = r.text.count(".onion")
                dt = time.time() - t
                if r.status_code == 200 and n > 0:
                    verdict = f"ALIVE HTTP {r.status_code} onion-links={n} {dt:.1f}s"
                    alive.append(name)
                else:
                    verdict = f"HTTP {r.status_code} {dt:.1f}s"
                print(f"{name}: {verdict}")
                continue
            if not via_tor:
                r, dt = _probe_once(url, 12)
                n = r.text.count(".onion")
                if r.status_code == 200 and n > 0:
                    verdict = f"ALIVE HTTP {r.status_code} onion-links={n} {dt:.1f}s"
                    alive.append(name)
                else:
                    verdict = f"HTTP {r.status_code} {dt:.1f}s"
                print(f"{name}: {verdict}")
                continue
            verdict = probe_onion(name, url)
            if verdict.startswith("ALIVE"):
                alive.append(name)
            if "可能存活" in verdict or "ALIVE(slow)" in verdict:
                slow_sites.append(name)
            if "超时" in verdict:
                onion_timeouts += 1
            print(f"{name}: {verdict} ({time.time() - t:.1f}s)")
        except Exception as e:
            print(f"{name}: ERROR {type(e).__name__} {str(e)[:60]}")
    print("-" * 60)
    print(f"存活引擎：{', '.join(alive) if alive else '无'}")
    if slow_sites:
        print(f"慢建链站点（存活但首次建链慢，演示前预热）：{', '.join(slow_sites)}")
    if onion_timeouts >= 3:
        print("⚠️ 多个 .onion 站超时——Tor 电路整体老化，建议重启：scripts\\restart_tor.bat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
