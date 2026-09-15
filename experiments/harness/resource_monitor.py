"""资源采样：显存峰值与内存峰值（表4 最后一列）。

显存用 nvidia-smi 轮询（与项目环境一致，无需额外驱动绑定），
失败或无 GPU 时回退 psutil 的进程 RSS。采样在后台线程进行，
采样间隔默认 0.5 s，兼顾精度与开销。
"""
from __future__ import annotations

import subprocess
import threading
import time
from typing import Any, Dict, Optional

from experiments.common import has_command, has_module
from experiments.logging_utils import get_logger

logger = get_logger("exp.resource")


def _gpu_used_mb() -> Optional[float]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return None
        vals = []
        for line in (out.stdout or "").strip().splitlines():
            line = line.strip()
            if line:
                try:
                    vals.append(float(line.split(",")[0]))
                except ValueError:
                    continue
        return sum(vals) if vals else None
    except Exception:  # noqa: BLE001
        return None


def _rss_mb() -> Optional[float]:
    if not has_module("psutil"):
        return None
    try:
        import os

        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 ** 2)
    except Exception:  # noqa: BLE001
        return None


class ResourceMonitor:
    """后台采样显存/内存峰值。

    用法::

        m = ResourceMonitor()
        m.start()
        ... 执行生成 ...
        peak = m.stop()   # {"peak_gpu_mb": ..., "peak_rss_mb": ...}
    """

    def __init__(self, interval_s: float = 0.5, gpu: bool = True) -> None:
        self.interval_s = float(interval_s)
        self.use_gpu = bool(gpu) and has_command("nvidia-smi")
        self.peak_gpu_mb: Optional[float] = None
        self.peak_rss_mb: Optional[float] = None
        self.samples = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self.use_gpu:
                g = _gpu_used_mb()
                if g is not None:
                    self.peak_gpu_mb = g if self.peak_gpu_mb is None else max(self.peak_gpu_mb, g)
            r = _rss_mb()
            if r is not None:
                self.peak_rss_mb = r if self.peak_rss_mb is None else max(self.peak_rss_mb, r)
            self.samples += 1
            self._stop.wait(self.interval_s)

    def start(self) -> "ResourceMonitor":
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def stop(self) -> Dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_s * 2 + 1)
            self._thread = None
        return {
            "peak_gpu_mb": self.peak_gpu_mb,
            "peak_rss_mb": self.peak_rss_mb,
            "samples": self.samples,
            "gpu_sampled": self.use_gpu,
        }

    def __enter__(self) -> "ResourceMonitor":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def measure_once(fn, interval_s: float = 0.2):
    """便捷函数：执行 fn 并同时采样，返回 (结果, 峰值字典)。"""
    m = ResourceMonitor(interval_s=interval_s).start()
    t0 = time.perf_counter()
    try:
        result = fn()
    finally:
        peaks = m.stop()
    peaks["wall_s"] = time.perf_counter() - t0
    return result, peaks
