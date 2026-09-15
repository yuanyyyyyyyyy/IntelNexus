"""安全实体识别 P/R/F1（表3 实体 F1 列）。

实体类型：CVE 编号、产品名、版本号、攻击类型。
金标 = 规则抽取 + 人工校对（校对表为可选 CSV，未提供时以规则抽取结果为金标，
并在产物中标记 ``gold_source``，避免把规则结果冒充人工金标）。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
VERSION_RE = re.compile(r"\b\d+(?:\.\d+){1,3}\b")
GHSA_RE = re.compile(r"\bGHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\b", re.I)

ATTACK_TYPES = [
    "远程代码执行", "任意代码执行", "代码执行", "权限提升", "提权", "拒绝服务",
    "信息泄露", "缓冲区溢出", "跨站脚本", "SQL 注入", "SQL注入", "命令注入",
    "路径遍历", "反序列化", "绕过", "越界读写", "内存破坏", "拒绝服务攻击",
    "remote code execution", "privilege escalation", "denial of service",
    "information disclosure", "sql injection", "cross-site scripting",
    "path traversal", "deserialization", "buffer overflow",
]

# 常见产品/厂商名（用于产品名实体；词典固定，保证可复现）
PRODUCTS = [
    "Apache", "OpenSSL", "Linux", "Windows", "Chrome", "Firefox", "Thunderbird",
    "Ubuntu", "Debian", "Gentoo", "Red Hat", "SUSE", "macOS", "iOS", "Android",
    "Nginx", "Tomcat", "Spring", "Django", "Flask", "WordPress", "Drupal",
    "Jenkins", "GitLab", "GitHub", "Docker", "Kubernetes", "Redis", "MySQL",
    "PostgreSQL", "MongoDB", "Elasticsearch", "Java", "Python", "Node.js",
    "Adobe", "Cisco", "Microsoft", "Oracle", "IBM", "VMware", "Fortinet",
    "ZITADEL", "Grafana", "TensorFlow", "PHP", "Ruby", "Perl", "Go", "Rust",
]


def extract_entities(text: str) -> Set[Tuple[str, str]]:
    """抽取实体集合 {(类型, 归一化值)}。"""
    if not text:
        return set()
    ents: Set[Tuple[str, str]] = set()
    for m in CVE_RE.findall(text):
        ents.add(("cve", m.upper()))
    for m in GHSA_RE.findall(text):
        ents.add(("cve", m.upper()))
    for m in VERSION_RE.findall(text):
        if len(m) > 1:
            ents.add(("version", m))
    low = text.lower()
    for a in ATTACK_TYPES:
        if a.lower() in low:
            ents.add(("attack", a.lower()))
    for p in PRODUCTS:
        if re.search(rf"\b{re.escape(p)}\b", text, re.I):
            ents.add(("product", p.lower()))
    return ents


def prf(pred: Iterable[Tuple[str, str]], gold: Iterable[Tuple[str, str]]) -> Optional[Dict[str, float]]:
    """按实体集合算 P/R/F1；金标为空时返回 None（不得记为 0）。"""
    p, g = set(pred), set(gold)
    if not g:
        return None
    if not p:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    tp = len(p & g)
    precision = tp / len(p)
    recall = tp / len(g)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def load_gold_csv(path: Path) -> Dict[str, Set[Tuple[str, str]]]:
    """加载人工校对金标：CSV 列 = sample_id,entity_type,entity_value。"""
    gold: Dict[str, Set[Tuple[str, str]]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid = str(row.get("sample_id") or "").strip()
            t = str(row.get("entity_type") or "").strip()
            v = str(row.get("entity_value") or "").strip()
            if sid and t and v:
                gold.setdefault(sid, set()).add((t, v.lower()))
    return gold


def gold_from_reference(reference: str) -> Set[Tuple[str, str]]:
    """以参考摘要的规则抽取结果作为金标（未人工校对时的默认）。"""
    return extract_entities(reference or "")


def build_gold(item: Dict[str, str], mode: str = "union") -> Set[Tuple[str, str]]:
    """构建实体金标。

    Args:
        mode:
            - ``union``（默认，主口径）：参考摘要 ∪ 输入正文。
              可用样本显著更多（本数据集 64/170 → 约 170/170），
              衡量"生成摘要覆盖了多少原始关键实体"。
            - ``ref_only``（敏感性口径）：仅参考摘要中的实体，
              更聚焦但有效样本少（金标为空的样本按纪律跳过，不记 0）。
    """
    ref = extract_entities(item.get("official_summary") or "")
    if mode == "ref_only":
        return ref
    return ref | extract_entities(item.get("content") or "")


def export_gold_template(items: List[Dict[str, str]], out_path: Path) -> Path:
    """导出待人工校对的金标模板 CSV。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "entity_type", "entity_value", "action", "note"])
        for it in items:
            for t, v in sorted(gold_from_reference(it.get("reference", ""))):
                w.writerow([it.get("sample_id", ""), t, v, "keep", ""])
    return out_path
