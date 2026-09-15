"""环境探测（R7 / 表2 配置列的实测来源）。

产出 ``experiments/reports/env_report.json``，回答四个问题：
1. 本地能不能跑 7-8B 模型（GPU 型号与显存、Ollama 版本与已装模型）；
2. 云端端点通不通、有哪些模型可选（旗舰档 / 轻量档按提示词挑选）；
3. 隐私测量工具有没有（pktmon / tshark / mitmproxy）；
4. 信源可不可达（决定表1 实际能列哪些信源）。

纪律：探测失败如实记录 ``ok=false`` 与原因，绝不猜测硬件或模型版本。
"""
from __future__ import annotations

import json
import os
import platform
import sys
from typing import Any, Dict, List, Optional

from experiments import config_loader
from experiments.common import (
    PLACEHOLDER,
    git_commit,
    git_dirty,
    has_command,
    has_module,
    mask_secret,
    run_command,
    utc_now_iso,
    write_json,
)
from experiments.logging_utils import get_logger
from experiments.paths import ENV_REPORT

logger = get_logger("exp.env_probe")

# 需要探测的可选依赖（缺失时相关指标保留 not-yet-measured）
OPTIONAL_MODULES = [
    "yaml", "scipy", "psutil", "pynvml", "numpy", "jieba",
    "bert_score", "rouge_score", "matplotlib", "sklearn",
    "langchain_ollama", "langchain_openai",
]


# --------------------------------------------------------------------- 平台
def probe_platform() -> Dict[str, Any]:
    cpu = platform.processor() or PLACEHOLDER
    mem_total_mb = None
    if has_module("psutil"):
        try:
            import psutil

            mem_total_mb = round(psutil.virtual_memory().total / (1024 ** 2), 1)
            cpu = cpu or platform.machine()
        except Exception as e:  # noqa: BLE001
            logger.debug("psutil 读取内存失败: %s", e)
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "os": f"{platform.system()} {platform.release()}",
        "os_detail": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu,
        "cpu_count": os.cpu_count(),
        "memory_total_mb": mem_total_mb,
    }


# --------------------------------------------------------------------- GPU
def probe_gpu() -> Dict[str, Any]:
    """优先 nvidia-smi（CSV），缺失时回退 pynvml，都没有则如实标注不可用。"""
    result: Dict[str, Any] = {
        "available": False,
        "source": None,
        "devices": [],
        "driver_version": None,
        "note": None,
    }
    smi = run_command(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        timeout=20,
    )
    if smi["ok"] and smi["stdout"]:
        devices = []
        for line in smi["stdout"].splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                mem_raw = (parts[1] if len(parts) > 1 else "") or ""
                mem_mb = None
                digits = "".join(ch for ch in mem_raw if ch.isdigit())
                if digits:
                    mem_mb = int(digits)
                devices.append(
                    {
                        "name": parts[0],
                        "memory_total": mem_raw or None,
                        "memory_total_mb": mem_mb,
                        "driver_version": parts[2] if len(parts) > 2 else None,
                    }
                )
        if devices:
            result.update(
                available=True,
                source="nvidia-smi",
                devices=devices,
                driver_version=devices[0].get("driver_version"),
            )
            mem = devices[0].get("memory_total_mb")
            if isinstance(mem, int) and mem < 8000:
                result["note"] = (
                    f"显存 {mem} MB（<8 GB）：7–8B 模型需量化且上下文须收紧，"
                    "建议 num_ctx ≤8192，并在论文中记录该约束"
                )
            return result
        result["note"] = "nvidia-smi 返回空，可能无 NVIDIA 设备"
    else:
        result["note"] = smi["stderr"] or "nvidia-smi 不可用"

    if has_module("pynvml"):
        try:
            import pynvml

            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            devices = []
            for i in range(count):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(h)
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                devices.append(
                    {
                        "name": name.decode() if isinstance(name, bytes) else str(name),
                        "memory_total": f"{round(mem.total / (1024 ** 2))} MiB",
                        "driver_version": None,
                    }
                )
            pynvml.nvmlShutdown()
            if devices:
                result.update(available=True, source="pynvml", devices=devices)
        except Exception as e:  # noqa: BLE001
            result["note"] = f"pynvml 探测失败: {type(e).__name__}: {e}"
    elif not result["available"]:
        result["note"] = (result["note"] or "") + "；pynvml 未安装"
    return result


# --------------------------------------------------------------------- Ollama
def probe_ollama(cfg: Dict[str, Any]) -> Dict[str, Any]:
    ollama_cfg = (cfg or {}).get("ollama", {}) or {}
    base_url = os.getenv(ollama_cfg.get("base_url_env", "OLLAMA_BASE_URL")) or ollama_cfg.get(
        "default_base_url", "http://127.0.0.1:11434"
    )
    out: Dict[str, Any] = {
        "cli_installed": has_command("ollama"),
        "version": None,
        "base_url": base_url,
        "reachable": False,
        "models": [],
        "error": None,
    }
    ver = run_command(["ollama", "--version"], timeout=20)
    if ver["ok"]:
        # `ollama --version` 在服务未启动时会在版本行前后打印告警，需按行提取版本号
        out["version"] = _parse_ollama_version(ver["stdout"])
        out["version_raw"] = ver["stdout"]

    try:
        import requests

        # 本地服务直连，不继承代理（与 intelnexus/core/llm/utils.py:_NO_PROXY 一致）
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=10,
                         proxies={"http": None, "https": None})
        r.raise_for_status()
        data = r.json() or {}
        models = []
        for m in data.get("models", []) or []:
            models.append(
                {
                    "name": m.get("name") or m.get("model"),
                    "digest": (m.get("digest") or "")[:19] or None,
                    "size_gb": round((m.get("size") or 0) / (1024 ** 3), 2) if m.get("size") else None,
                    "parameter_size": (m.get("details") or {}).get("parameter_size"),
                    "family": (m.get("details") or {}).get("family"),
                }
            )
        out.update(reachable=True, models=models)
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _parse_ollama_version(raw: str) -> Optional[str]:
    """从 `ollama --version` 输出中提取版本号。

    服务未启动时输出形如::

        Warning: could not connect to a running Ollama instance
        Warning: client version is 0.17.7

    因此逐行匹配版本号，取第一个命中。
    """
    import re

    for line in (raw or "").splitlines():
        m = re.search(r"(\d+\.\d+\.\d+(?:[-.\w]+)?)", line)
        if m:
            return m.group(1)
    return None


def local_models_ready(ollama_report: Dict[str, Any], wanted: List[str]) -> Dict[str, Any]:
    """检查配置矩阵里的本地模型是否已在本机可用。"""
    have = {m.get("name") for m in ollama_report.get("models", [])}
    missing = [w for w in wanted if w not in have]
    return {"wanted": wanted, "available": [w for w in wanted if w in have], "missing": missing}


# --------------------------------------------------------------------- 云端
def pick_model(model_ids: List[str], hints: List[str]) -> Optional[str]:
    """按提示词优先级从 /v1/models 返回的模型 id 中挑选。

    先做完全相等匹配，再做子串包含匹配；都失败返回 None（由调用方保留占位）。
    """
    ids = [str(i) for i in model_ids if i]
    for hint in hints or []:
        for mid in ids:
            if mid == hint:
                return mid
    for hint in hints or []:
        for mid in ids:
            if hint in mid:
                return mid
    return None


def _probe_endpoint(base_url: str, api_key: Optional[str], timeout: int = 20) -> Dict[str, Any]:
    """探测 OpenAI 兼容端点的连通性与模型清单。密钥不外泄。"""
    out: Dict[str, Any] = {
        "configured": bool(api_key),
        "key_status": mask_secret(api_key),
        "base_url": base_url,
        "reachable": False,
        "latency_ms": None,
        "models": [],
        "error": None,
    }
    if not api_key:
        out["error"] = "环境变量未提供 API key"
        return out
    try:
        import requests

        headers = {"Authorization": f"Bearer {api_key}"}
        r = requests.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=timeout,
                         proxies={"http": None, "https": None})
        out["latency_ms"] = int(r.elapsed.total_seconds() * 1000)
        out["http_status"] = r.status_code
        r.raise_for_status()
        data = r.json() or {}
        out["models"] = sorted({str(m.get("id")) for m in (data.get("data") or []) if m.get("id")})
        out["reachable"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def probe_cloud(cfg: Dict[str, Any]) -> Dict[str, Any]:
    providers = ((cfg or {}).get("cloud", {}) or {}).get("providers", []) or []
    report: Dict[str, Any] = {}
    for p in providers:
        name = p.get("name")
        key = os.getenv(p.get("env_key", ""), "")
        base_url = p.get("base_url")
        logger.info("探测云端端点: %s (%s)", name, base_url)
        info = _probe_endpoint(base_url, key)
        info["flagship_hint"] = p.get("flagship_hint", [])
        info["light_hint"] = p.get("light_hint", [])
        # 环境变量可显式指定模型（优先于自动挑选）
        override_hi = os.getenv(f"EXP_{str(name).upper()}_FLAGSHIP_MODEL")
        override_lo = os.getenv(f"EXP_{str(name).upper()}_LIGHT_MODEL")
        info["selected"] = {
            "flagship": override_hi or pick_model(info.get("models", []), p.get("flagship_hint", [])),
            "light": override_lo or pick_model(info.get("models", []), p.get("light_hint", [])),
        }
        if not info["models"] and info["reachable"] is False:
            info["note"] = "端点不可达或未返回模型清单，模型名以控制台实际可用为准"
        report[name] = info
    return report


# --------------------------------------------------------------------- 抓包能力
def probe_capture(cfg: Dict[str, Any]) -> Dict[str, Any]:
    order = ((cfg or {}).get("privacy", {}) or {}).get("capture_order", ["pktmon", "tshark", "mitmproxy"])
    found = {name: has_command(name) for name in order}
    # scapy 作为纯 Python 备选（需 Npcap 驱动）
    found["scapy"] = has_module("scapy")
    selected = next((n for n in order if found.get(n)), None)
    return {
        "available": found,
        "selected": selected,
        "requires_admin": selected in ("pktmon", "tshark"),
        "note": None
        if selected
        else "未发现可用的抓包工具，表6 出域字节数将保留 not-yet-measured",
    }


# --------------------------------------------------------------------- 信源
def probe_sources(urls: Optional[List[Dict[str, Any]]] = None, timeout: float = 12.0) -> List[Dict[str, Any]]:
    """逐个探测信源可达性。只把实际可达的源写进表1。"""
    if urls is None:
        try:
            urls = config_loader.sources_config().get("sources", [])
        except Exception as e:  # noqa: BLE001
            logger.warning("读取 sources.yaml 失败: %s", e)
            return []
    results = []
    try:
        import requests
    except ImportError:
        return [{"id": s.get("id"), "url": s.get("url"), "ok": False, "error": "requests 未安装"} for s in urls]

    ua = "IntelNexusResearchBot/1.0 (academic)"
    for s in urls:
        # 与 collect/probe_sources.py 保持一致：已停用的信源不探测、不进表1
        if s.get("enabled") is False:
            continue
        item: Dict[str, Any] = {
            "id": s.get("id"),
            "name": s.get("name"),
            "category": s.get("category"),
            "url": s.get("url"),
            "ok": False,
            "http_status": None,
            "latency_ms": None,
            "error": None,
        }
        try:
            r = requests.get(
                s.get("url"),
                headers={"User-Agent": ua},
                timeout=timeout,
                allow_redirects=True,
            )
            item.update(http_status=r.status_code, latency_ms=int(r.elapsed.total_seconds() * 1000), ok=r.status_code < 400)
        except Exception as e:  # noqa: BLE001
            item["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        results.append(item)
        logger.info("信源 %s -> %s (%s ms)", item["id"], "OK" if item["ok"] else "FAIL", item["latency_ms"])
    return results


# --------------------------------------------------------------------- 依赖
def probe_dependencies() -> Dict[str, bool]:
    return {m: has_module(m) for m in OPTIONAL_MODULES}


# --------------------------------------------------------------------- 汇总
def build_report(with_network: bool = True) -> Dict[str, Any]:
    try:
        cfg = config_loader.experiment_config()
    except Exception as e:  # noqa: BLE001
        logger.warning("读取 experiment.yaml 失败: %s", e)
        cfg = {}

    report: Dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "git_commit": git_commit(),
        "git_dirty": git_dirty(),
        "config_sha256": None,
        "platform": probe_platform(),
        "gpu": probe_gpu(),
        "ollama": probe_ollama(cfg),
        "cloud": {},
        "capture": probe_capture(cfg),
        "dependencies": probe_dependencies(),
        "sources": [],
        "blocking_issues": [],
    }
    local_ids = [c.get("model") for c in (cfg.get("configs") or []) if c.get("backend") == "ollama"]
    report["local_models"] = local_models_ready(report["ollama"], [m for m in local_ids if m])

    if with_network:
        report["cloud"] = probe_cloud(cfg)
        report["sources"] = probe_sources()

    # 阻塞项判定：缺什么就报什么，便于逐项解决
    issues: List[str] = []
    if not report["gpu"]["available"]:
        issues.append("未检测到 NVIDIA GPU：本地组只能 CPU 推理，须在论文局限中如实说明")
    if not report["ollama"]["reachable"]:
        issues.append("Ollama 服务不可达：本地组全部指标保持 not-yet-measured")
    if report["local_models"].get("missing"):
        issues.append("本地模型未拉取: " + ", ".join(report["local_models"]["missing"]))
    if with_network:
        qwen = report["cloud"].get("qwen", {})
        if not qwen.get("reachable"):
            issues.append("云端 qwen 端点不可达：表3/4/5 云端组保持 not-yet-measured")
        elif not qwen.get("selected", {}).get("flagship") or not qwen.get("selected", {}).get("light"):
            issues.append("云端旗舰档或轻量档模型未能自动选定，请用 EXP_QWEN_*_MODEL 显式指定")
        if not report["capture"]["selected"]:
            issues.append("无可用抓包工具：表6 出域字节数保持 not-yet-measured")
        reachable_sources = [s for s in report["sources"] if s.get("ok")]
        if not reachable_sources:
            issues.append("无可达信源：表1 与数据集构建无法进行")
    if not report["dependencies"].get("scipy"):
        issues.append("缺少 scipy：表7 的 Wilcoxon 检验无法计算")
    report["blocking_issues"] = issues
    return report


def print_summary(report: Dict[str, Any]) -> None:
    p = report["platform"]
    print("=" * 72)
    print("环境探测报告")
    print("=" * 72)
    print(f"时间(UTC) : {report['generated_at']}")
    print(f"git       : {report['git_commit']}  dirty={report['git_dirty']}")
    print(f"Python    : {p['python']}  ({p['os']})")
    print(f"CPU       : {p['cpu']} x{p['cpu_count']}   内存 {p['memory_total_mb']} MB")

    gpu = report["gpu"]
    if gpu["available"]:
        for d in gpu["devices"]:
            print(f"GPU       : {d.get('name')}  显存 {d.get('memory_total')}  驱动 {d.get('driver_version')}")
    else:
        print(f"GPU       : 不可用（{gpu.get('note')}）")

    ol = report["ollama"]
    print(f"Ollama    : cli={ol['cli_installed']} ver={ol['version']} 可达={ol['reachable']} ({ol['base_url']})")
    for m in ol["models"]:
        print(f"            - {m.get('name')}  {m.get('parameter_size')}  {m.get('size_gb')} GB")
    lm = report.get("local_models") or {}
    if lm.get("missing"):
        print(f"            缺失本地模型: {', '.join(lm['missing'])}")

    for name, info in (report.get("cloud") or {}).items():
        print(f"云端[{name}] : 可达={info.get('reachable')} 延迟={info.get('latency_ms')}ms "
              f"模型数={len(info.get('models') or [])} 选定={info.get('selected')}")
        if info.get("error"):
            print(f"            error: {info['error'][:120]}")

    cap = report["capture"]
    print(f"抓包工具  : {cap['selected']}  可用={cap['available']}")

    srcs = report.get("sources") or []
    if srcs:
        print("信源      :")
        for s in srcs:
            flag = "OK " if s.get("ok") else "FAIL"
            print(f"   [{flag}] {s.get('id'):24s} {s.get('http_status')} {s.get('latency_ms')}ms {s.get('error') or ''}")

    miss = [k for k, v in report["dependencies"].items() if not v]
    if miss:
        print(f"缺失依赖  : {', '.join(miss)}")

    if report["blocking_issues"]:
        print("-" * 72)
        print("阻塞项：")
        for i in report["blocking_issues"]:
            print(f"  ! {i}")
    print("=" * 72)


def main(out: Optional[str] = None, with_network: bool = True) -> Dict[str, Any]:
    from experiments.paths import REPORTS_DIR

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report(with_network=with_network)
    path = write_json(ENV_REPORT if out is None else out, report)
    print_summary(report)
    print(f"已写入: {path}")
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="环境探测")
    ap.add_argument("--out", default=None, help="输出路径（默认 experiments/reports/env_report.json）")
    ap.add_argument("--no-network", action="store_true", help="跳过云端端点与信源探测")
    args = ap.parse_args()
    main(out=args.out, with_network=not args.no_network)
