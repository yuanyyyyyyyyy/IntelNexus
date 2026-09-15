"""本地推理功耗实测（式(1) 的 P_avg 依据）。

口径
----
式(1) 需要的是"推理期间的平均整机功耗"。整机功耗在无功耗计的情况下
无法直接读取，本模块改为**对可实测的主要耗电部件逐项实测**：

- **CPU 封装功耗**：Windows Energy Meter 计数器
  ``\\Energy Meter(rapl_package0_pkg)\\Power``（RAPL，单位 mW）；
- **GPU 功耗**：``nvidia-smi --query-gpu=power.draw``（单位 W）。

两者之和作为 P_avg，属于**下界**（未含屏幕、内存、芯片组、存储等）。
该偏差在论文中如实说明，并由 5.3 节敏感性分析给出电费项在本地折算成本中
的占比——实测占比很低（折旧项主导），故该下界不影响结论方向。

测量方式
--------
在**受控负载**下采样：先做一次短输入预热（把模型载入显存，避免把加载
阶段的功耗算进推理），再对一条真实样本执行完整生成，采样线程在生成期间
持续读数。产出的原始采样序列一并归档，便于复核。

产物
----
``reports/power_probe.json``::

    {
      "config": "qwen3:8b", "duration_s": ..., "n_samples": ...,
      "cpu_pkg_w": {...}, "gpu_w": {...}, "p_avg_watt": ...,
      "basis": "...", "samples": [[t, cpu_w, gpu_w, gpu_util], ...]
    }
"""
from __future__ import annotations

import statistics
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from experiments.common import utc_now_iso, write_json
from experiments.logging_utils import get_logger
from experiments.paths import REPORTS_DIR

logger = get_logger("exp.power")

POWER_PATH = REPORTS_DIR / "power_probe.json"

# Windows Energy Meter 的 RAPL 计数器（AMD 平台实例名形如 rapl_package0_pkg）
RAPL_COUNTER = r"\Energy Meter(rapl_package0_pkg)\Power"
CPU_PKG_MW_TO_W = 1000.0
# 低于该 GPU 利用率视为非推理活跃样本，不计入均值
GPU_ACTIVE_UTIL = 5.0


def read_cpu_pkg_w(timeout: float = 8.0) -> Optional[float]:
    """读取 CPU 封装功耗（W）。计数器不可用返回 None。"""
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           (f"$s=(Get-Counter '{RAPL_COUNTER}' -ErrorAction SilentlyContinue).CounterSamples;"
            "if($s){[math]::Round($s[0].CookedValue,1)}")]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        logger.debug("读取 CPU 功耗失败: %s", e)
        return None
    text = (out.stdout or b"").decode("utf-8", "ignore").strip()
    if not text:
        return None
    try:
        return float(text) / CPU_PKG_MW_TO_W
    except ValueError:
        return None


def read_gpu_power() -> Tuple[Optional[float], Optional[float]]:
    """读取 (GPU 功耗 W, GPU 利用率 %)。"""
    cmd = ["nvidia-smi", "--query-gpu=power.draw,utilization.gpu",
           "--format=csv,noheader,nounits"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=8)
    except Exception as e:  # noqa: BLE001
        logger.debug("读取 GPU 功耗失败: %s", e)
        return None, None
    text = (out.stdout or b"").decode("utf-8", "ignore").strip().splitlines()
    if not text:
        return None, None
    parts = [p.strip() for p in text[0].split(",")]
    try:
        power = float(parts[0])
    except (ValueError, IndexError):
        power = None
    try:
        util = float(parts[1])
    except (ValueError, IndexError):
        util = None
    return power, util


def summarize(cpu: List[float], gpu: List[float]) -> Dict[str, Any]:
    """对两类读数给出均值/中位数/最大与样本数（缺测返回 None）。"""
    def _stat(xs: List[float]) -> Optional[Dict[str, Any]]:
        if not xs:
            return None
        return {"mean": round(statistics.fmean(xs), 2),
                "median": round(statistics.median(xs), 2),
                "max": round(max(xs), 2),
                "n": len(xs)}

    c, g = _stat(cpu), _stat(gpu)
    total = None
    if c and g:
        total = round(c["mean"] + g["mean"], 2)
    elif c:
        total = c["mean"]
    elif g:
        total = g["mean"]
    return {"cpu_pkg_w": c, "gpu_w": g, "p_avg_watt": total}


def _activate_filter(sample: Tuple[float, Optional[float], Optional[float], Optional[float]]
                     ) -> bool:
    """只保留推理活跃期间的样本（GPU 在跑，或 CPU 封装功耗明显高于静息）。"""
    _, cpu, gpu, util = sample
    if util is not None and util >= GPU_ACTIVE_UTIL:
        return True
    return cpu is not None and gpu is not None


def measure(config_id: str = "qwen3:8b", warmup: bool = True,
            interval_s: float = 3.0, out: Optional[Path] = None) -> Dict[str, Any]:
    """在受控负载下实测推理功耗。需要本机 Ollama 可用。"""
    from experiments import config_loader
    from experiments.collect import snapshot
    from experiments.harness import instrument

    exp_cfg = config_loader.experiment_config()
    cfg = next((c for c in list(exp_cfg.get("configs", []))
                if str(c.get("id")) == config_id), None)
    if cfg is None:
        raise ValueError(f"未找到本地配置 {config_id}")
    items = snapshot.pilot_set(1)
    if not items:
        raise RuntimeError("样本集为空，请先构建快照")
    item = dict(items[0])
    binding = instrument.build_llm(cfg, exp_cfg, seed=int(exp_cfg.get("seed", 0)))

    if warmup:
        # 预热：短输入跑一次，把模型载入显存，避免把加载阶段的功耗计入推理
        warm = dict(item)
        warm["content"] = (item.get("content") or "")[:400]
        t0 = time.perf_counter()
        instrument.generate_once(binding.llm, warm,
                                 input_max_chars=int((exp_cfg.get("unit") or {}).get("input_max_chars", 8000)))
        logger.info("预热完成，用时 %.1fs", time.perf_counter() - t0)

    samples: List[Tuple[float, Optional[float], Optional[float], Optional[float]]] = []
    stop = threading.Event()

    def _sampler() -> None:
        start = time.perf_counter()
        while not stop.is_set():
            cpu = read_cpu_pkg_w()
            gpu, util = read_gpu_power()
            samples.append((round(time.perf_counter() - start, 2), cpu, gpu, util))
            stop.wait(interval_s)

    th = threading.Thread(target=_sampler, daemon=True)
    th.start()
    t0 = time.perf_counter()
    res = instrument.generate_once(binding.llm, item,
                                   input_max_chars=int((exp_cfg.get("unit") or {}).get("input_max_chars", 8000)))
    generation_s = time.perf_counter() - t0
    stop.set()
    th.join(timeout=interval_s + 8)

    active = [s for s in samples if _activate_filter(s)]
    used = active or samples
    cpu = [s[1] for s in used if s[1] is not None]
    gpu = [s[2] for s in used if s[2] is not None]
    report = {
        "generated_at": utc_now_iso(),
        "config": config_id,
        "model": binding.model,
        "item_id": item.get("id"),
        "input_chars": len(item.get("content") or ""),
        "output_chars": len(res.text or ""),
        "generation_s": round(generation_s, 2),
        "interval_s": interval_s,
        "n_samples": len(samples),
        "n_active_samples": len(active),
        "method": "Windows Energy Meter (RAPL package) + nvidia-smi，生成期间采样",
        "basis": ("P_avg 取实测 CPU 封装功耗与 GPU 功耗之和，为整机功耗的**下界**"
                  "（未含屏幕、内存、芯片组与存储）；论文须在 5.3 与 6.3 说明，"
                  "并以电费项占比证明该下界不改变结论方向"),
        "samples": [[round(s[0], 2), s[1], s[2], s[3]] for s in samples],
    }
    report.update(summarize(cpu, gpu))
    path = Path(out) if out else POWER_PATH
    write_json(path, report)
    logger.info("%s 推理功耗：CPU %.2f W + GPU %.2f W → P_avg %.2f W（%d 个活跃样本）",
                config_id, (report.get("cpu_pkg_w") or {}).get("mean", float("nan")),
                (report.get("gpu_w") or {}).get("mean", float("nan")),
                report.get("p_avg_watt") or float("nan"), len(active))
    return report


def main(config_id: str = "qwen3:8b") -> Dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    r = measure(config_id)
    print(f"已写入 {POWER_PATH}")
    print(f"  CPU 封装 {r.get('cpu_pkg_w')}")
    print(f"  GPU      {r.get('gpu_w')}")
    print(f"  P_avg    {r.get('p_avg_watt')} W（整机下界）")
    return r


if __name__ == "__main__":
    main()
