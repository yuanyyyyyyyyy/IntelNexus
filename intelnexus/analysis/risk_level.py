"""威胁证据驱动的风险等级
==========================

风险等级必须与「信息质量」彻底解耦。

历史缺陷：风险等级曾由来源平均可信度反推（``avg_score < 0.4 → 高``、
``< 0.6 → 中``），语义被彻底扭曲 —— 它表达的其实是「这批资料质量差」，
呈现给读者的却是「目标有中等风险」；更糟的是形成反向激励：资料越权威，
风险等级反而越低。

现在的判定只接受**客观威胁证据**：

+---------+---------------------------------------------------------------+
| 等级    | 触发条件（任一）                                                |
+=========+===============================================================+
| 高      | CISA KEV 命中 / 公开利用命中 / CVE 命中 ≥3 / 威胁情报源命中 ≥3  |
| 中      | CVE 命中 ≥1 / 威胁情报源命中 ≥1 / 跨源冲突严重度 ≥0.5           |
| 低      | 仅存在低强度冲突（0 < 严重度 < 0.5）                            |
| 证据不足| 无任何上述信号                                                  |
+---------+---------------------------------------------------------------+

「证据不足」是一等公民：没有证据就是没有结论，绝不用「中」来填充空白。
"""

import re
from typing import Dict, Iterable, List, Optional, Tuple

LEVEL_INSUFFICIENT = "证据不足"
LEVEL_LOW = "低"
LEVEL_MEDIUM = "中"
LEVEL_HIGH = "高"

#: 等级由弱到强，供历史事件比较风险变化方向
_RISK_ORDER = [LEVEL_INSUFFICIENT, LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH]

#: 威胁情报/漏洞/暗网类来源（命中即视为威胁证据）。
#: 刻意不含 FreeBuf/安全客/先知社区/SecRSS 等安全媒体 —— 它们是「报道安全
#: 事件的新闻源」，检索命中 3 篇新闻不等于存在 3 个独立威胁证据。
THREAT_INTEL_SOURCES = {
    "NVD", "CISA_KEV", "CNVD", "CNNVD", "ExploitDB", "AlienVault_OTX",
    "OTX", "AlienVault", "ThreatIntel",
}

#: 暗网类来源（单独归入威胁证据，但不与漏洞库混算）
DARKWEB_SOURCES = {"Ahmia", "OnionLink", "TorDex", "Darkweb", "DarkWeb"}

#: 已知被利用漏洞（KEV）专用来源
KEV_SOURCES = {"CISA_KEV"}

#: 公开利用代码来源
EXPLOIT_SOURCES = {"ExploitDB"}

_CVE_PATTERN = re.compile(r'\bCVE-\d{4}-\d{4,7}\b', re.IGNORECASE)
_CNNVD_PATTERN = re.compile(r'\b(?:CNNVD|CNVD)-\d{6}-\d{4,7}\b', re.IGNORECASE)

#: CVE 命中数与等级阈值
CVE_HITS_FOR_HIGH = 3
TI_HITS_FOR_HIGH = 3
CONFLICT_SEVERITY_FOR_MEDIUM = 0.5


def risk_level_rank(level: Optional[str]) -> int:
    """等级序号（越大越危险）；未知等级与「证据不足」同为最低档。"""
    try:
        return _RISK_ORDER.index(level)
    except (ValueError, TypeError):
        return 0


def compute_risk_level(evidence: Optional[Dict]) -> Tuple[str, str]:
    """根据客观威胁证据计算风险等级。

    Args:
        evidence: 由 :func:`collect_risk_evidence` 产出的证据字典。
            只读取威胁信号字段；``avg_score`` / ``credibility`` 等可信度
            字段一律忽略（曾因引入这些字段导致语义错标）。

    Returns:
        ``(level, reason)``。无威胁信号时返回 ``("证据不足", ...)``。
    """
    evidence = evidence or {}

    def _int(key: str) -> int:
        try:
            return int(evidence.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    def _float(key: str) -> float:
        try:
            return float(evidence.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    kev = _int("kev_hits")
    cve = _int("cve_hits")
    exploit = _int("exploit_hits")
    ti = _int("ti_source_hits")
    conflict = _float("conflict_max_severity")

    if kev > 0:
        return LEVEL_HIGH, f"CISA KEV 已知被利用漏洞命中 {kev} 条"
    if exploit > 0:
        return LEVEL_HIGH, f"公开利用代码命中 {exploit} 条"
    if cve >= CVE_HITS_FOR_HIGH:
        return LEVEL_HIGH, f"CVE/CNVD 命中 {cve} 条（≥{CVE_HITS_FOR_HIGH}）"
    if ti >= TI_HITS_FOR_HIGH:
        return LEVEL_HIGH, f"威胁情报类来源命中 {ti} 条（≥{TI_HITS_FOR_HIGH}）"

    if cve > 0:
        return LEVEL_MEDIUM, f"CVE/CNVD 命中 {cve} 条"
    if ti > 0:
        return LEVEL_MEDIUM, f"威胁情报类来源命中 {ti} 条"
    if conflict >= CONFLICT_SEVERITY_FOR_MEDIUM:
        return LEVEL_MEDIUM, f"跨源冲突最高严重度 {conflict:.0%}"

    if conflict > 0:
        return LEVEL_LOW, f"仅存在低强度跨源冲突（严重度 {conflict:.0%}）"

    return LEVEL_INSUFFICIENT, "未采集到漏洞/威胁情报/冲突等客观威胁证据，不做风险定级"


def _result_text(result: Dict) -> str:
    return " ".join(
        str(result.get(k) or "") for k in ("title", "description", "snippet", "summary")
    )


def _source_name(result: Dict) -> str:
    return str(result.get("source") or result.get("source_name") or "")


def collect_risk_evidence(results: Optional[Iterable[Dict]],
                          conflicts: Optional[List[Dict]] = None) -> Dict:
    """从检索结果与跨源冲突中汇总威胁证据。

    Args:
        results: 搜索结果列表
        conflicts: ``ConflictDetector.detect`` 产出的冲突列表

    Returns:
        ``{"kev_hits", "cve_hits", "exploit_hits", "ti_source_hits",
        "conflict_max_severity", "threat_sources"}``
    """
    kev = 0
    exploit = 0
    cve_ids: set = set()
    ti_sources: set = set()
    threat_sources: Dict[str, int] = {}

    for r in results or []:
        name = _source_name(r)
        if name in KEV_SOURCES:
            kev += 1
        if name in EXPLOIT_SOURCES:
            exploit += 1
        if name in THREAT_INTEL_SOURCES:
            ti_sources.add(name)
        elif name in DARKWEB_SOURCES:
            ti_sources.add(name)
            threat_sources[name] = threat_sources.get(name, 0) + 1

        # CVE 按 ID 去重：同一编号被多篇报道转载不等于多个独立漏洞
        text = _result_text(r)
        for m in _CVE_PATTERN.findall(text) + _CNNVD_PATTERN.findall(text):
            cve_ids.add(m.upper())

    cve = len(cve_ids)
    ti = len(ti_sources)

    conflict_max = 0.0
    for c in conflicts or []:
        try:
            conflict_max = max(conflict_max, float(c.get("severity") or 0.0))
        except (TypeError, ValueError):
            continue

    return {
        "kev_hits": kev,
        "cve_hits": cve,
        "exploit_hits": exploit,
        "ti_source_hits": ti,
        "conflict_max_severity": round(conflict_max, 3),
        "threat_sources": threat_sources,
    }
