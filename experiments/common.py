"""实验管线通用工具：哈希、统计、格式化、运行标识、JSON 读写。

所有涉及"数值输出"的函数在输入缺失时返回 ``PLACEHOLDER``，
绝不返回 0、空串或估算值，以免被误当作实测结果写入稿件。
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import string
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from experiments.paths import ROOT

PLACEHOLDER = "not-yet-measured"


# --------------------------------------------------------------------- 时间
def utc_now_iso() -> str:
    """UTC 时间戳（ISO 8601，秒级精度，带 Z）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# --------------------------------------------------------------------- 哈希
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dict(data: Dict[str, Any]) -> str:
    """对字典做稳定序列化后取哈希（用于配置与脚本版本存证）。"""
    return sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str))


def git_commit(root: Optional[Path] = None) -> str:
    """当前 git commit；不可用返回 unavailable（不得编造）。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root or ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return (out.stdout or "").strip() or "unavailable"
    except Exception:
        return "unavailable"


def git_dirty(root: Optional[Path] = None) -> Optional[bool]:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root or ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode != 0:
            return None
        return bool((out.stdout or "").strip())
    except Exception:
        return None


# --------------------------------------------------------------------- 标识
def slug(text: str, maxlen: int = 40) -> str:
    """把配置名转成可安全用于文件名的片段。"""
    safe = "".join(c if (c.isalnum() or c in "._-") else "-" for c in str(text))
    return safe.strip("-")[:maxlen] or "unnamed"


def make_run_id(config: str, repeat: int) -> str:
    """run_id = UTC时间戳-配置-重复序号-8位随机串。

    随机串用于避免同一秒内的并发运行撞名；不承载任何语义。
    """
    rand = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"{utc_now_compact()}-{slug(config)}-r{int(repeat)}-{rand}"


# --------------------------------------------------------------------- 统计
def mean(values: Sequence[float]) -> Optional[float]:
    xs = [float(v) for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def stdev(values: Sequence[float]) -> Optional[float]:
    """样本标准差（ddof=1）；n<2 时为 0.0（如实反映无法估计方差）。"""
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    """线性插值分位数；空输入返回 None。"""
    xs = sorted(float(v) for v in values if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (float(p) / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return xs[int(k)]
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def mean_sd(values: Sequence[float]) -> Dict[str, Optional[float]]:
    return {"mean": mean(values), "sd": stdev(values), "n": len([v for v in values if v is not None])}


# --------------------------------------------------------------------- 格式化
def fmt_number(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return PLACEHOLDER
    return f"{float(value):.{int(digits)}f}"


def fmt_mean_sd(m: Optional[float], s: Optional[float], digits: int = 3) -> str:
    """论文表格用的 均值±标准差。任一缺失则整格保留占位。"""
    if m is None or s is None:
        return PLACEHOLDER
    return f"{float(m):.{int(digits)}f}±{float(s):.{int(digits)}f}"


def fmt_int(value: Optional[float]) -> str:
    if value is None:
        return PLACEHOLDER
    return f"{int(round(float(value)))}"


def fmt_pct(value: Optional[float], digits: int = 1) -> str:
    if value is None:
        return PLACEHOLDER
    return f"{float(value) * 100:.{int(digits)}f}%"


def pct_change(base: Optional[float], new: Optional[float]) -> Optional[float]:
    """相对变化比例（new/base - 1）；基数为 0 或缺失时返回 None。"""
    if base is None or new is None or base == 0:
        return None
    return float(new) / float(base) - 1.0


# --------------------------------------------------------------------- IO
def write_json(path: Path | str, data: Any, indent: int = 2) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, default=str)
    return path


def read_json(path: Path | str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_jsonl(path: Path | str, record: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path: Path | str) -> List[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# --------------------------------------------------------------------- 依赖探测
def has_module(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def has_command(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def run_command(cmd: Sequence[str], timeout: float = 15.0) -> Dict[str, Any]:
    """执行外部命令，返回 {ok, stdout, stderr, returncode, elapsed_s}。

    不抛异常：探测类命令的失败是正常结果，由调用方决定如何降级。
    """
    start = time.perf_counter()
    try:
        out = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "ok": out.returncode == 0,
            "stdout": (out.stdout or "").strip(),
            "stderr": (out.stderr or "").strip(),
            "returncode": out.returncode,
            "elapsed_s": round(time.perf_counter() - start, 3),
        }
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "command not found", "returncode": None,
                "elapsed_s": round(time.perf_counter() - start, 3)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"timeout after {timeout}s", "returncode": None,
                "elapsed_s": round(time.perf_counter() - start, 3)}
    except Exception as e:  # noqa: BLE001 - 探测命令需吞掉一切异常
        return {"ok": False, "stdout": "", "stderr": f"{type(e).__name__}: {e}", "returncode": None,
                "elapsed_s": round(time.perf_counter() - start, 3)}


def mask_secret(value: Optional[str]) -> str:
    """只回显密钥是否存在与其长度，绝不输出密钥内容。"""
    if not value:
        return "not-configured"
    return f"configured(len={len(value)})"
