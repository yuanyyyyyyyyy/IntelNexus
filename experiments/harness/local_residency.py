"""本地显存驻留体检：判断 7–8B 模型能否全 GPU 驻留，并给出规模判定。

背景（实测）：本机 RTX 4050 Laptop 显存 6 141 MiB，`ollama ps` 显示
`qwen3:8b 6.6 GB 36%/64% CPU/GPU` —— 约 1/3 的层回落到 CPU，生成仅 8.3 tok/s、
单条 170–226 s。上下文从 8192 降到 4096 后仍为 30%/70%，说明是显存总量不足，
不是 KV cache 配置问题。

本模块按固定规则给出结论（写死在代码里，避免事后解释）：

- ``gpu_share >= 0.95`` 且单条耗时 ≤ 90 s → ``full-ok``
- 否则 → ``degrade-required``（并给出候选处置）
- 无法测量 → ``unknown``
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from experiments.common import run_command, utc_now_iso, write_json
from experiments.harness import instrument
from experiments.logging_utils import get_logger
from experiments.paths import REPORTS_DIR

logger = get_logger("exp.residency")

GPU_SHARE_OK = 0.95
LATENCY_OK_S = 90.0
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)%\s*(CPU|GPU)", re.I)
# 成对写法：两个百分数后跟一组标签，例如 "30%/70% CPU/GPU"
_PAIR_RE = re.compile(
    r"(\d+(?:\.\d+)?)%\s*/\s*(\d+(?:\.\d+)?)%\s*(CPU|GPU)\s*/\s*(CPU|GPU)", re.I)
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|MB)", re.I)


def parse_processor(raw: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """解析 ollama ps 的 PROCESSOR 字段，返回 (cpu_share, gpu_share)。

    支持两种写法：
    - 成对：``30%/70% CPU/GPU``（两个百分数按标签顺序对应）
    - 单个：``100% GPU`` / ``100% CPU``
    缺失或无法识别返回 (None, None)。
    """
    if not raw:
        return None, None
    text = str(raw)

    pair = _PAIR_RE.search(text)
    if pair:
        a = float(pair.group(1)) / 100.0
        b = float(pair.group(2)) / 100.0
        l1, l2 = pair.group(3).upper(), pair.group(4).upper()
        cpu = a if l1 == "CPU" else b
        gpu = b if l2 == "GPU" else a
        return cpu, gpu

    single = _PCT_RE.search(text)
    if single:
        v = float(single.group(1)) / 100.0
        if single.group(2).upper() == "GPU":
            return max(0.0, 1.0 - v), v
        return v, max(0.0, 1.0 - v)
    return None, None


def parse_ollama_ps(raw: str, model: str) -> Dict[str, Any]:
    """从 `ollama ps` 输出中取出指定模型的 SIZE / PROCESSOR / CONTEXT。"""
    info: Dict[str, Any] = {"raw_line": None, "size_gb": None, "size_raw": None,
                            "processor_raw": None, "gpu_share": None,
                            "context": None, "found": False}
    for line in (raw or "").splitlines():
        if not line.strip() or line.lower().startswith("name"):
            continue
        if model.split(":")[0] not in line:
            continue
        info["found"] = True
        info["raw_line"] = " ".join(line.split())
        m = _SIZE_RE.search(line)
        if m:
            val, unit = float(m.group(1)), m.group(2).upper()
            info["size_raw"] = f"{val} {unit}"
            info["size_gb"] = round(val / 1024, 2) if unit == "MB" else val
        pm = re.search(
            r"(\d+(?:\.\d+)?%\s*/\s*\d+(?:\.\d+)?%\s*CPU/GPU"
            r"|\d+(?:\.\d+)?%\s*/\s*\d+(?:\.\d+)?%\s*GPU/CPU"
            r"|\d+(?:\.\d+)?%\s*(?:CPU|GPU))", line, re.I)
        if pm:
            info["processor_raw"] = pm.group(1)
            _, gpu = parse_processor(pm.group(1))
            info["gpu_share"] = gpu
        cm = re.search(r"\b(\d{3,6})\b\s*\d+\s*minutes?", line)
        if cm:
            info["context"] = int(cm.group(1))
        break
    return info


def verdict(gpu_share: Optional[float], item_latency_s: Optional[float]) -> str:
    """按固定阈值判定能否直接跑 full。"""
    if gpu_share is None or item_latency_s is None:
        return "unknown"
    if gpu_share >= GPU_SHARE_OK and item_latency_s <= LATENCY_OK_S:
        return "full-ok"
    return "degrade-required"


@dataclass
class ResidencyTrial:
    num_ctx: int
    n_items: int
    item_latency_s: Optional[float]
    size_gb: Optional[float]
    processor_raw: Optional[str]
    gpu_share: Optional[float]
    verdict: str
    error: Optional[str] = None


def _ollama_ps(model: str) -> Dict[str, Any]:
    res = run_command(["ollama", "ps"], timeout=20)
    if not res["ok"]:
        return {"found": False, "error": res["stderr"] or "ollama ps 失败"}
    return parse_ollama_ps(res["stdout"], model)


def check_model(config_id: str = "qwen3:8b", ctx_variants: Optional[List[int]] = None,
                n_items: int = 2) -> Dict[str, Any]:
    """对指定本地配置按多个上下文长度体检，返回判定与建议。"""
    from experiments import config_loader
    from experiments.collect import snapshot

    exp_cfg = config_loader.experiment_config()
    cfg = next((c for c in (exp_cfg.get("configs") or []) if str(c.get("id")) == config_id), None)
    if cfg is None:
        raise ValueError(f"未找到本地配置 {config_id}")
    model = str(cfg.get("model"))
    variants = ctx_variants or [int((exp_cfg.get("ollama", {}) or {}).get("options", {}).get("num_ctx", 4096)),
                              2048]
    items = snapshot.pilot_set(n_items) or snapshot.smoke_set(n_items)

    trials: List[ResidencyTrial] = []
    for ctx in variants:
        logger.info("体检 num_ctx=%d（%d 条）", ctx, len(items))
        try:
            binding = instrument.build_llm(cfg, exp_cfg, seed=int(exp_cfg.get("seed", 0)),
                                           request_overrides={"num_ctx": int(ctx)})
        except Exception as e:  # noqa: BLE001
            trials.append(ResidencyTrial(ctx, 0, None, None, None, None, "unknown",
                                         error=f"{type(e).__name__}: {e}"))
            continue
        lats: List[float] = []
        err: Optional[str] = None
        for it in items:
            res = instrument.generate_once(binding.llm, it, usage=binding.usage,
                                           input_max_chars=(exp_cfg.get("unit", {}) or {}).get("input_max_chars"))
            if res.error:
                err = res.error
            lats.append(res.latency_s)
        ps_info = _ollama_ps(model)
        avg = round(sum(lats) / len(lats), 2) if lats else None
        trials.append(ResidencyTrial(
            num_ctx=int(ctx), n_items=len(lats), item_latency_s=avg,
            size_gb=ps_info.get("size_gb"), processor_raw=ps_info.get("processor_raw"),
            gpu_share=ps_info.get("gpu_share"),
            verdict=verdict(ps_info.get("gpu_share"), avg), error=err,
        ))
        logger.info("  num_ctx=%d → %.1fs/条，%s，判定 %s", ctx, avg or 0,
                    ps_info.get("processor_raw"), trials[-1].verdict)

    best = min((t for t in trials if t.item_latency_s), key=lambda t: t.item_latency_s, default=None)
    final = best.verdict if best else "unknown"
    recommendations: List[str] = []
    if final != "full-ok":
        recommendations = [
            "关闭占用显存的程序（浏览器/微信等）后重跑本命令，争取全 GPU 驻留",
            "拉取更小的本地模型（如 ollama pull qwen3:4b）以获得全 GPU 驻留",
            "缩减 full 规模（如 60–100 条 × 3 次）并记入 PROTOCOL 偏差",
        ]
    report = {
        "generated_at": utc_now_iso(), "config": config_id, "model": model,
        "trials": [asdict(t) for t in trials],
        "thresholds": {"gpu_share_ok": GPU_SHARE_OK, "latency_ok_s": LATENCY_OK_S},
        "verdict": final,
        "recommendations": recommendations,
    }
    write_json(REPORTS_DIR / "local_residency.json", report)
    print("=" * 72)
    print(f"{'num_ctx':<10}{'单条耗时/s':<12}{'SIZE':<10}{'PROCESSOR':<20}{'判定'}")
    print("-" * 72)
    for t in trials:
        print(f"{t.num_ctx:<10}{str(t.item_latency_s):<12}{str(t.size_gb):<10}"
              f"{str(t.processor_raw):<20}{t.verdict}")
    print("=" * 72)
    print(f"结论：{final}")
    for r in recommendations:
        print(f"  - {r}")
    print(f"已写入: {REPORTS_DIR / 'local_residency.json'}")
    return report


if __name__ == "__main__":
    check_model()
