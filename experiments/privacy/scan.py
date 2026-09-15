"""本地明文残留扫描（表6 第三列）。

对日志、缓存、临时文件等目录扫描敏感片段，统计"命中条目数"：
- 安全实体类：CVE/GHSA 编号、公告标题片段；
- 标识类：IPv4、邮箱、疑似密钥串。

只统计命中数量与所在目录，**不落盘任何命中内容**（扫描产物本身不应成为新的泄漏源）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.common import write_json
from experiments.logging_utils import get_logger
from experiments.paths import REPORTS_DIR

logger = get_logger("exp.scan")

PATTERNS: Dict[str, str] = {
    "cve": r"\bCVE-\d{4}-\d{4,7}\b",
    "ghsa": r"\bGHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\b",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "secret_like": r"\b(sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{16,})\b",
}

SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".woff", ".woff2", ".ttf",
               ".zip", ".gz", ".pdf", ".xlsx", ".docx", ".pkl", ".bin"}
MAX_FILE_BYTES = 8 * 1024 * 1024


def scan_dir(root: Path, patterns: Optional[Dict[str, str]] = None,
             max_files: int = 20000) -> Dict[str, Any]:
    """扫描目录，返回 {命中条目数, 按类型, 按目录, 扫描文件数}。"""
    root = Path(root)
    pats = {k: re.compile(v, re.I) for k, v in (patterns or PATTERNS).items()}
    hits = 0
    by_type: Dict[str, int] = {k: 0 for k in pats}
    scanned = 0
    files_with_hits: List[str] = []
    if not root.exists():
        return {"root": str(root), "exists": False, "hits": 0, "by_type": by_type, "files": 0}

    for p in root.rglob("*"):
        if scanned >= max_files:
            break
        if not p.is_file() or p.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        scanned += 1
        file_hits = 0
        for name, rx in pats.items():
            n = len(rx.findall(text))
            if n:
                by_type[name] += n
                file_hits += n
        if file_hits:
            hits += file_hits
            files_with_hits.append(str(p.relative_to(root)))
    return {"root": str(root), "exists": True, "hits": hits, "by_type": by_type,
            "files_scanned": scanned, "files_with_hits": len(files_with_hits),
            "sample_files": files_with_hits[:5]}


def scan_targets(targets: List[str], base: Path) -> Dict[str, Any]:
    """扫描配置中的多个目录，汇总明文残留条目数。"""
    total = 0
    per_target = []
    by_type: Dict[str, int] = {}
    for t in targets:
        path = Path(t)
        if not path.is_absolute():
            path = base / t
        res = scan_dir(path)
        per_target.append(res)
        total += int(res.get("hits") or 0)
        for k, v in (res.get("by_type") or {}).items():
            by_type[k] = by_type.get(k, 0) + v
    out = {"scanned_at": None, "total_hits": total, "by_type": by_type, "targets": per_target}
    write_json(REPORTS_DIR / "privacy_scan.json", out)
    logger.info("明文残留扫描：命中 %d 条，覆盖 %d 个目录", total, len(per_target))
    return out
