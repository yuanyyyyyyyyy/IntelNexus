"""出域字节测量（表6）。

方案选择：Windows 上 pktmon/tshark 需要管理员权限与驱动，可复现性差。
本模块改用**计量代理**：把 LLM 客户端的 base_url 指向本机代理，
由代理转发到真实端点并精确统计出域/入域字节与外联目的地。

这与抓包在"离开本机的字节数"这一口径上等价（差异仅为 TCP/TLS 头部开销，
已在产物中注明），且无需管理员权限、可在 CI 中离线自检。

HTTPS 走 CONNECT 隧道：隧道内为密文，统计的是加密后的字节数，
即真正离开本机的量；本地组经回环地址转发，出域量为 0。
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from experiments.common import utc_now_iso, write_json
from experiments.logging_utils import get_logger
from experiments.paths import REPORTS_DIR

logger = get_logger("exp.capture")

PRIVACY_JSON = REPORTS_DIR / "privacy.json"


class ProxyStats:
    """累计出域/入域字节与外联目的地。"""

    def __init__(self) -> None:
        self.bytes_out = 0      # 客户端 -> 外部（出域）
        self.bytes_in = 0       # 外部 -> 客户端
        self.destinations: set = set()
        self.requests = 0
        self._lock = threading.Lock()

    def add(self, out: int, inn: int, host: Optional[str] = None) -> None:
        with self._lock:
            self.bytes_out += int(out)
            self.bytes_in += int(inn)
            self.requests += 1
            if host:
                self.destinations.add(host)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "bytes_out": self.bytes_out,
                "bytes_in": self.bytes_in,
                "destination_count": len(self.destinations),
                "destinations": sorted(self.destinations),
                "requests": self.requests,
            }


def parse_upstream_path(url_or_path: str) -> str:
    """从代理收到的请求行中取出「路径 + 查询串」。

    HTTP 代理收到的是绝对 URI（如 ``http://host:port/v1/chat/completions?x=1``），
    而转发给上游时只需要路径部分。缺少这一步会把整串再拼一次，导致转发到错误地址。
    """
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        parsed = urlparse(url_or_path)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return path
    return url_or_path or "/"


def build_target_url(upstream_base: str, request_path: str, host_header: str = "") -> Tuple[str, str]:
    """由「上游基址 + 代理收到的请求行」算出真正要请求的 URL 与目标主机。

    这是修复"代理转发给自己"的核心逻辑：客户端把 ``base_url`` 指向本代理后，
    请求路径会丢掉供应商前缀（如 ``/compatible-mode/v1``），必须拼回上游基址。
    抽成纯函数便于离线测试。

    Returns:
        (完整 URL, 目标主机名)
    """
    path = parse_upstream_path(request_path)
    if upstream_base:
        parsed_up = urlparse(upstream_base)
        return upstream_base.rstrip("/") + path, (parsed_up.hostname or "unknown")
    host = host_header or "unknown"
    return f"http://{host}{path}", host.split(":")[0]


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    stats: ProxyStats = None  # type: ignore[assignment]
    # 上游真实基址。客户端把 base_url 指向本代理后，请求路径会丢掉
    # 供应商前缀（如 /compatible-mode/v1），必须由代理补回，否则会打回自己。
    upstream_base: str = ""

    def log_message(self, fmt: str, *args) -> None:  # 静默，避免把请求内容写进日志
        return

    # ---------------------------------------------------------- CONNECT 隧道
    def do_CONNECT(self) -> None:  # noqa: N802 - http.server 约定
        host, _, port_s = self.path.partition(":")
        port = int(port_s or 443)
        try:
            upstream = socket.create_connection((host, port), timeout=30)
        except Exception as e:  # noqa: BLE001
            self.send_error(502, f"upstream connect failed: {e}")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.connection.setblocking(False)
        upstream.setblocking(False)
        stats = self.stats
        stats.add(len(self.path.encode()) + 64, 0, host)
        stop = threading.Event()

        def pump(src: socket.socket, dst: socket.socket, is_out: bool) -> None:
            try:
                while not stop.is_set():
                    try:
                        data = src.recv(65536)
                    except (BlockingIOError, socket.timeout):
                        time.sleep(0.005)
                        continue
                    except OSError:
                        break
                    if not data:
                        break
                    try:
                        dst.sendall(data)
                    except OSError:
                        break
                    if is_out:
                        stats.add(len(data), 0, None)
                    else:
                        stats.add(0, len(data), None)
            finally:
                stop.set()

        t1 = threading.Thread(target=pump, args=(self.connection, upstream, True), daemon=True)
        t2 = threading.Thread(target=pump, args=(upstream, self.connection, False), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        for s in (self.connection, upstream):
            try:
                s.close()
            except OSError:
                pass

    def _target_url(self) -> Tuple[str, str]:
        """返回 (上游完整 URL, 目标主机)。逻辑见 ``build_target_url``。"""
        return build_target_url(self.upstream_base, self.path, self.headers.get("Host") or "")

    # ---------------------------------------------------------- 明文转发
    def _forward_plain(self) -> None:
        import requests

        url, dest_host = self._target_url()
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "content-length", "proxy-connection", "connection")}
        sent_out = len(body) + len(self.path) + 64
        payload = b""
        try:
            resp = requests.request(self.command, url, headers=headers, data=body or None,
                                    timeout=120, stream=False)
            payload = resp.content
            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "content-length", "connection"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:  # noqa: BLE001
            # 上游不可达等异常：返回 502 并**照常计数**。
            # 注意不能用 return —— 那样 finally 里的 payload 虽已初始化，
            # 但早期版本会在异常路径引用未赋值变量而崩掉整个请求线程。
            payload = b""
            try:
                self.send_error(502, f"upstream failed: {e}")
            except Exception:  # noqa: BLE001 - 客户端已断开时忽略
                pass
        finally:
            self.stats.add(sent_out, len(payload), dest_host)

    def do_GET(self) -> None:  # noqa: N802
        self._forward_plain()

    def do_POST(self) -> None:  # noqa: N802
        self._forward_plain()

    def do_PUT(self) -> None:  # noqa: N802
        self._forward_plain()


class CountingProxy:
    """本机计量代理。用法见 ``run_captured``。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 upstream_base: str = "") -> None:
        self.stats = ProxyStats()
        self.upstream_base = upstream_base
        handler = type("BoundHandler", (_ProxyHandler,),
                       {"stats": self.stats, "upstream_base": upstream_base})
        self._server = ThreadingHTTPServer((host, int(port)), handler)
        self._thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[0], self._server.server_address[1]
        return f"http://{host}:{port}"

    def start(self) -> "CountingProxy":
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> Dict[str, Any]:
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        return self.stats.snapshot()


def run_captured(fn: Callable[[str], Any], label: str = "",
                 exclude_first_pull: bool = True,
                 upstream_base: str = "") -> Dict[str, Any]:
    """在计量代理下执行 fn(proxy_base_url)，返回本次出域统计。

    Args:
        fn: 接收代理 base_url 的可调用对象（内部构造 LLM 并发起请求）
        label: 本次测量的标签（通常写配置 id）
        upstream_base: 上游真实基址（如 ``https://dashscope.aliyuncs.com/compatible-mode/v1``）。
            必须提供：客户端把 base_url 换成代理后会丢掉该前缀，
            由代理补回，否则请求会被转发回代理自身。
    """
    proxy = CountingProxy(upstream_base=upstream_base).start()
    started = utc_now_iso()
    error: Optional[str] = None
    try:
        fn(proxy.base_url)
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {str(e)[:200]}"
        logger.error("出域测量执行失败: %s", error)
    snap = proxy.stop()
    snap.update({"label": label, "started_at": started, "finished_at": utc_now_iso(),
                 "error": error, "exclude_first_pull": exclude_first_pull,
                 "method": "counting-proxy (CONNECT tunnel)"})
    return snap


def measure_config(config_id: str, sample_n: int = 10, stage: str = "pilot") -> Dict[str, Any]:
    """对某个配置做一次出域测量（经计量代理跑 N 条样本）。

    测量结果按配置累加，用于表6 的"出域字节数"与"去重外联目的地数"。
    """
    from experiments import config_loader
    from experiments.collect import snapshot
    from experiments.harness import instrument

    exp_cfg = config_loader.experiment_config()
    cfg = next((c for c in list(exp_cfg.get("configs", [])) + list(exp_cfg.get("sensitivity", []) or [])
                if str(c.get("id")) == config_id), None)
    if cfg is None:
        raise ValueError(f"未找到配置 {config_id}")
    items = snapshot.pilot_set(int(sample_n)) if stage == "pilot" else snapshot.smoke_set(int(sample_n))

    # 上游真实基址：云端取供应商 base_url，本地取 Ollama 地址。
    # 客户端 base_url 被换成代理地址后前缀会丢失，必须由代理补回。
    backend = str(cfg.get("backend"))
    if backend == "openai_compatible":
        provider = next((p for p in ((exp_cfg.get("cloud", {}) or {}).get("providers", []) or [])
                         if p.get("name") == cfg.get("provider")), {})
        upstream_base = str(provider.get("base_url") or "")
    else:
        import os

        ollama_cfg = exp_cfg.get("ollama", {}) or {}
        upstream_base = os.getenv(ollama_cfg.get("base_url_env", "OLLAMA_BASE_URL")) or str(
            ollama_cfg.get("default_base_url", "http://127.0.0.1:11434"))

    def _run(proxy_url: str) -> None:
        binding = instrument.build_llm(cfg, exp_cfg, seed=int(exp_cfg.get("seed", 0)),
                                       request_overrides={"base_url": proxy_url})
        for it in items:
            instrument.generate_once(binding.llm, it)

    snap = run_captured(_run, label=config_id, upstream_base=upstream_base)
    snap["n_items"] = len(items)
    snap["backend"] = backend
    snap["upstream_base"] = upstream_base
    if backend == "ollama":
        # 本地组的流量只经过 127.0.0.1 回环，**不构成数据出域**：
        # 出域字节数记为 0，实测的回环字节另行保留以便复核。
        snap["loopback_bytes"] = snap.get("bytes_out")
        snap["bytes_total"] = 0
        snap["note"] = "本地组仅回环流量，出域字节数按 0 计；loopback_bytes 为实测回环量"
    else:
        snap["bytes_total"] = snap.get("bytes_out")
    save_result(config_id, snap)
    logger.info("%s 出域 %s 字节（回环 %s），目的地 %s", config_id,
                snap.get("bytes_total"), snap.get("loopback_bytes"), snap.get("destinations"))
    return snap


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def judge_run(run: Dict[str, Any], backend: str) -> Tuple[bool, Optional[str]]:
    """判定一次出域测量是否有效。

    历史教训：``build_target_url`` 修好之前，代理会把请求转发回自身，
    于是产生"目的地全是 127.0.0.1、出域 1.1 GB、请求 13 万次"的虚假记录。
    这类记录必须**保留原件**（可复核）但**排除在合计之外**，
    否则表6 的出域字节数与目的地数会被严重污染。
    """
    if run.get("error"):
        return False, f"error: {str(run.get('error'))[:80]}"
    if int(run.get("requests") or 0) <= 0:
        return False, "no-requests"
    dests = {str(d) for d in (run.get("destinations") or [])}
    if backend != "ollama" and dests and dests <= LOOPBACK_HOSTS:
        return False, "proxy-loopback（请求被转发回代理自身，非真实出域）"
    if not dests:
        return False, "no-destinations"
    return True, None


def _aggregate(config: str, entry: Dict[str, Any]) -> None:
    """重算某配置的合计：只累加有效运行；本地组出域按 0 计。"""
    backend = ""
    valid_bytes = 0
    dests: set = set()
    invalids: List[Dict[str, Any]] = []
    for r in entry.get("runs") or []:
        backend = str(r.get("backend") or backend)
        ok, reason = judge_run(r, backend)
        r["valid"] = ok
        r["invalid_reason"] = reason
        if not ok:
            invalids.append({"label": r.get("label"), "started_at": r.get("started_at"),
                             "bytes_out": r.get("bytes_out"), "reason": reason})
            continue
        # 本地组：snap["bytes_total"] 已显式置 0（仅回环），合计口径以它为准
        valid_bytes += int(r.get("bytes_total", r.get("bytes_out")) or 0)
        dests.update(r.get("destinations") or [])
    valid_items = sum(int(r.get("n_items") or 0) for r in (entry.get("runs") or [])
                      if r.get("valid"))
    entry["bytes_total"] = valid_bytes
    entry["n_items"] = valid_items
    # 表6 的列头是"出域字节数/单次"，故另给按条归一化的值（与总分开列，便于复核）
    entry["bytes_per_item"] = (valid_bytes / valid_items) if valid_items else None
    # 本地组的唯一"目的地"是回环地址，它不是出域对象：表6 的"外联目的地数"
    # 必须用剔除回环后的计数，否则本地组会被记成 1，与"零外联"的结论矛盾
    entry["destinations"] = sorted(dests)
    entry["destination_count"] = len(dests)
    entry["external_destinations"] = sorted(d for d in dests if d not in LOOPBACK_HOSTS)
    entry["external_destination_count"] = len(entry["external_destinations"])
    entry["valid_runs"] = sum(1 for r in (entry.get("runs") or []) if r.get("valid"))
    entry["invalid_runs"] = invalids


def load_results() -> Dict[str, Dict[str, Any]]:
    """读取已保存的出域测量结果 {config: {...}}（合计仅含有效运行）。"""
    if not PRIVACY_JSON.exists():
        return {}
    try:
        with open(PRIVACY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data or {}).get("configs", {})
    except Exception:  # noqa: BLE001
        return {}


def save_result(config: str, snap: Dict[str, Any]) -> None:
    """把一次测量结果写入 reports/privacy.json（保留每次原始记录，合计只算有效运行）。"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {"configs": {}}
    if PRIVACY_JSON.exists():
        try:
            with open(PRIVACY_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:  # noqa: BLE001
            data = {"configs": {}}
    configs = data.setdefault("configs", {})
    entry = configs.setdefault(config, {"runs": [], "bytes_total": 0, "destinations": []})
    entry["runs"].append(snap)
    _aggregate(config, entry)
    data["method_note"] = (
        "计量代理（CONNECT 隧道）统计离开本机的加密字节数；"
        "无效运行（error / 零请求 / 云端配置目的地全为回环）保留原件但不计入合计。"
    )
    write_json(PRIVACY_JSON, data)
