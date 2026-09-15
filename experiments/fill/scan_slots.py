"""扫描稿件中的 not-yet-measured 占位，生成稳定 slot 清单。

slot_id 格式：``<文件名>:<行号>:<第几个>``。行号与序号在文件不变时稳定，
因此 mapping 一旦绑定，重跑不会错位。

对表格中的占位额外记录：表号、行标签（首列）、列标签（表头对应列），
这样 gen_mapping 可以按"表+行+列"自动生成绑定，无需逐个数第几个占位。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.common import PLACEHOLDER, write_json
from experiments.paths import DEFAULT_CONTENT_DIR, SLOTS

# 内容文件的指令前缀是 "::"（如 ::tblcap / ::tbl），兼容写成 ":::" 的情况
TBL_CAP_RE = re.compile(r"^:::?tblcap\s+表\s*(\d+)")
TBL_MARKERS = ("::tbl", ":::tbl")
CONTEXT_LEN = 60


def _context(line: str, pos: int) -> str:
    start = max(0, pos - CONTEXT_LEN)
    end = min(len(line), pos + len(PLACEHOLDER) + CONTEXT_LEN)
    return line[start:end]


def scan_file(path: Path) -> List[Dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    slots: List[Dict[str, Any]] = []
    table_no: Optional[int] = None
    header: List[str] = []
    in_table = False

    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        m = TBL_CAP_RE.match(line.strip())
        if m:
            table_no = int(m.group(1))
            header = []
            in_table = False
            # 表注本身也携带实测数值（如"表3　质量对比（均值±标准差，n=…）"），
            # 早期版本直接 continue 会把它整行漏掉，导致表注的 n 永远填不上
            if PLACEHOLDER in line:
                for k in range(line.count(PLACEHOLDER)):
                    slots.append({
                        "slot_id": f"{path.name}:{idx}:{k + 1}",
                        "file": path.name,
                        "line": idx,
                        "nth": k + 1,
                        "table": table_no,
                        "row": None,
                        "column": None,
                        "kind": "tblcap",
                        "context": _context(line, line.find(PLACEHOLDER) + k),
                    })
            continue
        if line.strip() in TBL_MARKERS:
            in_table = True
            header = []
            continue
        if in_table and not line.strip().startswith("|"):
            in_table = False
        if in_table and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not header:
                header = cells
                continue
            row_label = cells[0] if cells else ""
            for ci, cell in enumerate(cells):
                for k in range(cell.count(PLACEHOLDER)):
                    slots.append({
                        "slot_id": f"{path.name}:{idx}:{len(slots) + 1}",
                        "file": path.name,
                        "line": idx,
                        "nth": len(slots) + 1,
                        "table": table_no,
                        "row": row_label,
                        "column": header[ci] if ci < len(header) else None,
                        "kind": "table",
                        "context": _context(line, 0),
                    })
            continue

        if PLACEHOLDER in line:
            for k in range(line.count(PLACEHOLDER)):
                slots.append({
                    "slot_id": f"{path.name}:{idx}:{k + 1}",
                    "file": path.name,
                    "line": idx,
                    "nth": k + 1,
                    "table": None,
                    "row": None,
                    "column": None,
                    "kind": "body",
                    "context": _context(line, line.find(PLACEHOLDER) + k),
                })
    return slots


def scan(content_dir: Optional[Path] = None, out: Optional[Path] = None) -> Dict[str, Any]:
    d = Path(content_dir) if content_dir else DEFAULT_CONTENT_DIR
    if not d.exists():
        raise FileNotFoundError(f"稿件目录不存在: {d}")
    slots: List[Dict[str, Any]] = []
    for p in sorted(d.glob("*.md")):
        s = scan_file(p)
        slots.extend(s)
        print(f"  {p.name:<22} {len(s)} 处占位")
    by_table: Dict[str, int] = {}
    for s in slots:
        if s.get("kind") == "tblcap":
            key = "表注"
        elif s.get("table"):
            key = f"表{s['table']}"
        else:
            key = "正文"
        by_table[key] = by_table.get(key, 0) + 1
    result = {
        "content_dir": str(d),
        "scanned_files": sorted(p.name for p in d.glob("*.md")),
        "total": len(slots),
        "by_table": by_table,
        "slots": slots,
    }
    write_json(out or SLOTS, result)
    print(f"合计 {len(slots)} 处占位：{by_table}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--content-dir", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    scan(Path(a.content_dir) if a.content_dir else None, Path(a.out) if a.out else None)
