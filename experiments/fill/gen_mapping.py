"""按表结构自动生成 slot → 指标的绑定骨架（mapping.yaml）。

自动绑定覆盖：表1（数据集）、表2（环境）、表3（质量）、表4（效能）、
表5（成本）、表6（隐私）、表7（统计）。
正文中的占位无法从表格结构推断，保持未绑定并列出，由作者按语义绑定。

产出的 mapping.yaml 可手工编辑；``apply`` 只读它，不自行猜测。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments.common import read_json, write_json
from experiments.paths import AGGREGATE, REPORTS_DIR

MAPPING_PATH = REPORTS_DIR / "mapping.yaml"

# 本地组的实际配置 id（由 aggregate.json 的 groups 解析），表6 的"本地"行需要它
_LOCAL_CFG: Optional[str] = None


def _resolve_local_config() -> Optional[str]:
    """从 aggregate.json 解析本地组的配置 id（如 qwen3:8b）。"""
    if not AGGREGATE.exists():
        return None
    agg = read_json(AGGREGATE) or {}
    for cfg, group in (agg.get("groups") or {}).items():
        if group == "local":
            return str(cfg)
    return None

# 表3/表4 行标签 → 配置 id
ROW_TO_CONFIG = {
    "qwen2.5:7b（本地）": "qwen2.5:7b",
    "qwen3:8b（本地）": "qwen3:8b",
    "qwen3:4b（本地）": "qwen3:4b",
    "llama3:8b（本地）": "llama3:8b",
    "mistral:7b（本地）": "mistral:7b",
    "云端旗舰档": "cloud_flagship",
    "云端轻量档": "cloud_light",
    "基线：关键词规则": "baseline_keyword",
    "基线：TextRank": "baseline_textrank",
    "基线：TF-IDF 聚类+首句": "baseline_tfidf",
    "本地（按配置合计）": "local",
    "本地（排除首次拉取）": "local",
}

# 表3 列 → 指标
T3_COL = {"ROUGE-L": "rouge_l", "BERTScore": "bertscore", "实体 F1": "entity_f1", "人工评分": "human"}
# 表4 列 → 指标
T4_COL = {
    "P50 时延/s": ("latency_p50", "float", 2),
    "P95 时延/s": ("latency_p95", "float", 2),
    "吞吐/（条·min−1）": ("throughput_per_min", "mean_sd", 2),
    "显存或内存峰值": ("peak_gpu_mb", "int", 0),
}
# 表1 列 → dataset_stats 字段
T1_COL = {"代表信源": "representative", "条数": "raw_count", "时间跨度": "span", "去重后条数": "dedup_count"}
# 表7 列 → 比较结果字段
T7_COL = {"统计量": ("statistic", "float", 1), "Cliff's delta": ("cliffs_delta", "float", 3),
          "Holm 校正后显著性": ("p_adj", "holm", 0)}


def _entry(source: str, path: List[str], fmt: str, digits: Optional[int] = None,
           note: str = "") -> Dict[str, Any]:
    e: Dict[str, Any] = {"source": source, "path": path, "fmt": fmt}
    if digits is not None:
        e["digits"] = digits
    if note:
        e["note"] = note
    return e


def _const(text: str) -> Dict[str, Any]:
    return {"source": "const", "value": text, "fmt": "str"}


def generate(slots: Dict[str, Any]) -> Dict[str, Any]:
    global _LOCAL_CFG
    _LOCAL_CFG = _resolve_local_config()
    mapping: Dict[str, Dict[str, Any]] = {}
    t7_index = 0

    for s in slots.get("slots", []):
        table = s.get("table")
        row = (s.get("row") or "").strip()
        col = (s.get("column") or "").strip()
        sid = s["slot_id"]

        # ---------------- 表注 ----------------
        # 表注（如"n=…"）不属于表格单元格，按语义规则绑定
        if s.get("kind") == "tblcap":
            _bind_body(s, mapping)
            continue

        # ---------------- 表1 数据集 ----------------
        if table == 1:
            field = T1_COL.get(col)
            if not field:
                continue
            if row == "合计":
                if field == "span":
                    mapping[sid] = _entry("dataset", ["overall_span"], "str")
                elif field == "raw_count":
                    mapping[sid] = _entry("dataset", ["totals", "collected"], "int")
                else:
                    mapping[sid] = _entry("dataset", ["totals", "kept"], "int")
            else:
                mapping[sid] = _entry("dataset", ["table1_by_category", row, field],
                                      "str" if field in ("representative", "span") else "int")
            continue

        # ---------------- 表2 环境 ----------------
        if table == 2:
            if row == "本地模型":
                mapping[sid] = _entry("env", ["local_hardware_context"], "str")
            elif row == "云端模型":
                if col in ("配置", "参数量/版本"):
                    mapping[sid] = _entry("env", ["cloud", "qwen", "selected",
                                                  "flagship" if "旗舰" in _row_ctx(slots, sid) else "light"], "str")
                else:
                    mapping[sid] = _const("云端托管（由服务商提供）")
            else:
                mapping[sid] = _const("—")
            continue

        # ---------------- 表3 质量 ----------------
        if table == 3:
            cfg = ROW_TO_CONFIG.get(row)
            metric = T3_COL.get(col)
            if cfg and metric:
                mapping[sid] = _entry("aggregate", ["configs", cfg, metric], "mean_sd", 3)
            continue

        # ---------------- 表4 效能 ----------------
        if table == 4:
            cfg = ROW_TO_CONFIG.get(row)
            spec = T4_COL.get(col)
            if cfg and spec:
                metric, fmt, digits = spec
                mapping[sid] = _entry("aggregate", ["configs", cfg, metric], fmt, digits)
            continue

        # ---------------- 表5 成本 ----------------
        if table == 5:
            cfg = ROW_TO_CONFIG.get(row)
            if not cfg:
                continue
            if cfg == "local":
                if col == "能耗与折旧折算":
                    mapping[sid] = _entry("aggregate", ["local_cost_summary", "cost_local"], "money", 6)
                elif col == "单次简报成本/元":
                    mapping[sid] = _entry("aggregate", ["local_cost_summary", "cost_per_item"], "money", 6)
            else:
                if col == "输入 token 计费":
                    mapping[sid] = _entry("aggregate", ["configs", cfg, "cost_token_in"], "money", 6)
                elif col == "输出 token 计费":
                    mapping[sid] = _entry("aggregate", ["configs", cfg, "cost_token_out"], "money", 6)
                elif col == "单次简报成本/元":
                    mapping[sid] = _entry("aggregate", ["configs", cfg, "cost_per_item_mean"], "money", 6)
            continue

        # ---------------- 表6 隐私 ----------------
        if table == 6:
            # "本地（排除首次拉取）"这类行标签不是配置 id：必须解析成实际的
            # 本地配置 id（如 qwen3:8b），否则 privacy.json 查不到而留占位
            cfg = _LOCAL_CFG if row.startswith("本地") else ROW_TO_CONFIG.get(row)
            if col.startswith("出域字节数"):
                # 列头为"/单次"，取按条归一化的值（总量另存在 bytes_total，便于复核）
                mapping[sid] = _entry("privacy", [cfg or row, "bytes_per_item"], "bytes")
            elif col == "外联目的地数":
                # 剔除回环地址后计数：本地组只访问 127.0.0.1，不构成出域
                mapping[sid] = _entry("privacy", [cfg or row, "external_destination_count"], "int")
            elif col == "本地明文残留条目数":
                mapping[sid] = _entry("scan", ["total_hits"], "int")
            continue

        # ---------------- 表7 统计 ----------------
        if table == 7:
            spec = T7_COL.get(col)
            if spec:
                field, fmt, digits = spec
                mapping[sid] = _entry("aggregate", ["comparisons", str(t7_index), field], fmt, digits)
            if col == "Holm 校正后显著性":
                t7_index += 1
            continue

        # ---------------- 正文：按语义关键词绑定 ----------------
        _bind_body(s, mapping)

    out = {
        "generated_from": slots.get("content_dir"),
        "total_slots": slots.get("total"),
        "bound": len(mapping),
        "unbound": int(slots.get("total", 0)) - len(mapping),
        "slots": mapping,
    }
    write_json(MAPPING_PATH, out)
    print(f"已生成 {MAPPING_PATH}：绑定 {out['bound']} / {out['total_slots']}，未绑定 {out['unbound']}")
    return out


# 正文占位的语义规则：(文件名包含, 上下文包含, source, path, fmt, digits)
BODY_RULES = [
    ("04_expdesign", "实验硬件环境为", "env", ["local_hardware_context"], "str", None),
    ("04_expdesign", "操作系统与驱动版本为", "env", ["os_driver"], "str", None),
    ("04_expdesign", "Ollama 运行时版本为", "env", ["ollama_version"], "str", None),
    ("04_expdesign", "Python 与主要依赖库版本为", "env", ["python_version"], "str", None),
    ("04_expdesign", "条公开安全公告", "dataset", ["totals", "kept"], "int", None),
    ("04_expdesign", "个 7B～8B 量级模型", "const3", [], "str", None),
    ("04_expdesign", "个商用 API", "const2", [], "str", None),
    ("05_results", "n=", "aggregate", ["n_quality_items"], "int", None),
]

# 同句多占位时按出现顺序绑定：(文件名包含, 触发词, [(nth, source, path, fmt, digits)])
# 式(1) 的说明句里 P_avg、p_e、D 三个占位相距不足 60 字符，上下文互相包含，
# 无法靠关键词区分；它们在该行内的出现顺序是固定的，故按 nth 绑定。
ORDER_RULES = [
    ("04_expdesign", "式（1）中", [
        (1, "pricing", ["local", "P_avg_watt"], "float", 1),
        (2, "pricing", ["local", "p_e_yuan_per_kwh"], "float", 2),
        (3, "pricing", ["local", "D_utilization"], "float", 2),
    ]),
]


def _bind_body(slot: Dict[str, Any], mapping: Dict[str, Any]) -> None:
    """正文与表注占位：只对能明确判定的位置自动绑定，其余留给人工。

    表注（如"表3　质量对比（均值±标准差，n=…）"）同样携带实测数值，
    故与正文共用同一套语义规则。
    """
    if slot.get("kind") not in ("body", "tblcap"):
        return
    fname = str(slot.get("file") or "")
    ctx = f"{slot.get('context') or ''}"
    sid = slot["slot_id"]

    # 同一句里有多个占位时（如式(1) 说明句同时出现 P_avg、p_e、D），
    # 按上下文关键词无法区分——因为三个占位的上下文互相重叠。此时按
    # 占位在该行内的出现顺序（nth）绑定。
    for fpat, needle, entries in ORDER_RULES:
        if fpat in fname and needle in ctx:
            nth = int(slot.get("nth") or 0)
            for n, source, path, fmt, digits in entries:
                if n == nth:
                    mapping[sid] = _entry(source, path, fmt, digits)
                    return

    for fpat, needle, source, path, fmt, digits in BODY_RULES:
        if fpat in fname and needle in ctx:
            if source.startswith("const"):
                mapping[sid] = _const(source.replace("const", ""))
            else:
                mapping[sid] = _entry(source, path, fmt, digits)
            return


def _row_ctx(slots: Dict[str, Any], slot_id: str) -> str:
    """取槽位所在行的上下文，用于区分云端两档。"""
    for s in slots.get("slots", []):
        if s["slot_id"] == slot_id:
            return f"{s.get('row') or ''}{s.get('context') or ''}"
    return ""


def load_mapping(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path else MAPPING_PATH
    if not p.exists():
        raise FileNotFoundError(f"未找到 {p}，请先运行 scan-slots 与 gen-mapping")
    return read_json(p)


if __name__ == "__main__":
    slots = read_json(REPORTS_DIR / "slots.json")
    generate(slots)
