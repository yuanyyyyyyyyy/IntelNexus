"""启动 Tor 并等待引导完成。

设计要点（每一条都踩过坑）：
1. 用 DETACHED_PROCESS 启动：Tor 必须完全脱离父进程控制台，否则关闭 bat 窗口
   会让 Tor 收到控制台关闭事件而退出。
2. 不用 bat 的 findstr 轮询日志：`100%` 里的 `%` 会被 cmd 当变量前缀，导致
   findstr 参数被破坏后转去读 stdin 直接挂死；且 findstr 按 ANSI 读 UTF-8 日志会匹配失败。
3. 不用 `start "Tor" /min ...` 起窗口：在无桌面会话下 start 会阻塞。
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

# 本脚本位于 scripts/，仓库根是 scripts/ 的父目录
ROOT = Path(__file__).resolve().parent.parent
TOR_EXE = Path(r"D:\Tool\Technology\Tor Browser\Browser\TorBrowser\Tor\tor.exe")
TORRC = ROOT / "data" / "tor_runtime" / "torrc"
TORLOG = ROOT / "data" / "tor_runtime" / "tor.log"
PT = ROOT / "tools" / "tor" / "tor" / "pluggable_transports" / "lyrebird.exe"
PORT = 2080
TIMEOUT = 180


def port_open(port: int = PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def read_log() -> str:
    try:
        return TORLOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    if port_open():
        print(f"[OK] Tor 已在运行：127.0.0.1:{PORT}")
        return 0

    for label, path in (("tor.exe", TOR_EXE), ("lyrebird.exe", PT)):
        if not path.exists():
            print(f"[!!] 未找到 {label}：{path}")
            return 1

    TORLOG.parent.mkdir(parents=True, exist_ok=True)
    if TORLOG.exists():
        TORLOG.unlink()

    print("[..] 正在启动 Tor（obfs4 桥接，经 Clash 出海）...")
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [str(TOR_EXE), "-f", str(TORRC)],
        cwd=str(TOR_EXE.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )

    start = time.time()
    warned = False
    while time.time() - start < TIMEOUT:
        log = read_log()
        if "Bootstrapped 100%" in log:
            print(f"[OK] Tor 引导完成（{time.time() - start:.0f}s），"
                  f"SocksPort=127.0.0.1:{PORT}")
            print("     提示：第一条 .onion 访问要建链，可能等 60 秒以上；之后会快很多")
            return 0
        if not warned and "Problem bootstrapping" in log:
            print("[..] 桥接连接不稳定，正在重试（常见于节点被限速）...")
            warned = True
        if proc.poll() is not None:
            print(f"[!!] Tor 进程已退出（code={proc.returncode}）")
            for ln in [x for x in log.splitlines() if "warn" in x.lower()][-3:]:
                print(f"     {ln}")
            return 1
        time.sleep(1)

    print(f"[!!] {TIMEOUT} 秒内未完成引导，日志：{TORLOG}")
    print("     常见原因：Clash 未启动（7890），或当前节点封锁 Tor 流量——换个节点重试")
    return 1


if __name__ == "__main__":
    sys.exit(main())
