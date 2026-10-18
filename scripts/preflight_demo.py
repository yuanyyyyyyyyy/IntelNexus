"""演示前自检：一键确认暗网演示链路是否就绪。

本脚本位于 scripts/，仓库根是 scripts/ 的父目录。运行时会把仓库根插入
sys.path，因此 `--full` 分支里的 `from intelnexus...` 导入才可用。

用法（推荐用同目录的 check_demo.bat，它会切到仓库根再调用本脚本）：
    .venv\\Scripts\\python.exe scripts\\preflight_demo.py          # 快速检查
    .venv\\Scripts\\python.exe scripts\\preflight_demo.py --full   # 含 .onion 访问与端到端搜索

检查项：
    1. Clash 混合端口 7890（Tor 的 obfs4 桥接要经它出海）
    2. Tor SOCKS 2080（本地监听）
    3. Tor 出口身份（带重试：电路刚建立时首次连接常被中断）
    4. Ahmia 可达性 + 结果解析
    5. [--full] .onion 访问（演示真正的核心能力）
    6. [--full] 端到端暗网搜索
"""
import socket
import sys
import time
from pathlib import Path

# scripts/ 的父目录即仓库根，插入 sys.path 以便 --full 分支导入 intelnexus
PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

CLASH_PORT = 7890
TOR_PORT = 2080
TOR_PROXIES = {
    "http": f"socks5h://127.0.0.1:{TOR_PORT}",
    "https": f"socks5h://127.0.0.1:{TOR_PORT}",
}
# 用实测可用的 .onion（Tor Project 官方那个地址已失效）
ONION_TEST = "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/"


def _tcp_ok(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _line(ok: bool, label: str, detail: str = "") -> bool:
    mark = "[ OK ]" if ok else "[FAIL]"
    print(f"{mark} {label}" + (f"  — {detail}" if detail else ""))
    return ok


def _tor_get(url: str, timeout: int = 30, attempts: int = 3):
    """经 Tor 请求，失败自动重试。

    Tor 电路刚建立时，首次 TLS 握手常被中断（SSLEOFError / ConnectionAborted），
    重试一次通常就正常。这不是故障，但只试一次会误报。
    """
    import requests
    last = None
    for i in range(attempts):
        t = time.time()
        try:
            return requests.get(url, proxies=TOR_PROXIES, timeout=timeout), None, time.time() - t
        except Exception as e:
            last = e
            if i < attempts - 1:
                time.sleep(2)
    return None, last, 0.0


def _hint(err) -> str:
    s = str(err)
    if "SSLEOF" in s or "aborted" in s or "EOF occurred" in s:
        return "电路刚建立时首次握手被中断，属正常抖动；重跑本自检通常就过"
    if "timed out" in s.lower():
        return "超时：检查 Clash 节点是否可用"
    return s[:100]


def main() -> int:
    full = "--full" in sys.argv
    print("=" * 58)
    print("暗网演示链路自检")
    print("=" * 58)

    results = []

    clash_ok = _tcp_ok("127.0.0.1", CLASH_PORT)
    results.append(_line(clash_ok, f"Clash 混合端口 {CLASH_PORT}",
                         "" if clash_ok else "未监听：请先启动蜂窝云/Clash"))

    tor_ok = _tcp_ok("127.0.0.1", TOR_PORT)
    results.append(_line(tor_ok, f"Tor SOCKS 端口 {TOR_PORT}",
                         "" if tor_ok else "未监听：请先运行 start_tor.bat"))

    if tor_ok:
        resp, err, dt = _tor_get("https://check.torproject.org/api/ip")
        if resp is not None:
            data = resp.json()
            results.append(_line(bool(data.get("IsTor")), "Tor 出口身份",
                                 f"IsTor={data.get('IsTor')} IP={data.get('IP')} {dt:.1f}s"))
        else:
            results.append(_line(False, "Tor 出口身份", _hint(err)))
    else:
        results.append(_line(False, "Tor 出口身份", "跳过（端口未监听）"))

    try:
        import requests
        t = time.time()
        r = requests.get("https://ahmia.fi/search/?q=ransomware", timeout=20,
                         headers={"User-Agent": "Mozilla/5.0"})
        results.append(_line(r.status_code == 200, "Ahmia 可达性",
                             f"HTTP {r.status_code} {len(r.text)}B {time.time() - t:.1f}s"))
    except Exception as e:
        results.append(_line(False, "Ahmia 可达性", f"{type(e).__name__}: {e}"))

    if full and tor_ok:
        # .onion 建链慢（实测 20s+），且是否可达取决于目标站点本身，
        # 因此只作参考信息，不计入通过/失败——真正的能力由端到端搜索验证。
        resp, err, dt = _tor_get(ONION_TEST, timeout=70, attempts=1)
        if resp is not None:
            print(f"[ OK ] .onion 访问  — HTTP {resp.status_code} "
                  f"{len(resp.text)}B {dt:.1f}s")
        else:
            print("[ -- ] .onion 访问  — 未成功（不影响演示：主路径走 Ahmia）")
            print("       目标站点可能临时不可达，或首次建链超时；换个地址即可")

    if full:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from intelnexus.core.search.registry import get_registry
            from intelnexus.ui.results_detail import _is_onion_item
            reg = get_registry(darkweb_advanced=True, tor_port=TOR_PORT)
            t = time.time()
            res = reg.collect("darkweb", "ransomware", max_results=20, global_timeout=120)
            onion = sum(1 for x in res if _is_onion_item(x))
            results.append(_line(len(res) > 0, "端到端暗网搜索",
                                 f"{len(res)} 条 / {onion} 条 .onion {time.time() - t:.1f}s"))
        except Exception as e:
            results.append(_line(False, "端到端暗网搜索", f"{type(e).__name__}: {e}"))

    print("-" * 58)
    passed = sum(1 for x in results if x)
    total = len(results)
    if passed == total:
        print(f"全部通过（{passed}/{total}）——可以开始演示")
        print("提醒：正式演示前先搜 2-3 个词预热，第一条 .onion 要建链")
        return 0
    print(f"有 {total - passed} 项未通过（{passed}/{total}）——按上面的提示修复")
    return 1


if __name__ == "__main__":
    sys.exit(main())
