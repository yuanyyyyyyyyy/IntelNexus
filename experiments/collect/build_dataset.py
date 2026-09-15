"""构建固定数据集快照（R1 / 表1）。

只采一次，落盘为快照；后续 smoke/pilot/full/replication 全部只读同一快照，
杜绝"不同阶段数据不同"造成的口径漂移。

产物（默认 experiments/data/snapshot/）::

    items.jsonl          统一条目
    dataset_stats.json   表1 与 R1 归档所需的统计
    dedup_log.jsonl      每条被丢弃的重复项及原因
    collection_log.jsonl 每次 HTTP 请求（URL/状态/时间/robots 判定）
    manifest.sha256      全量文件哈希清单
    raw/<source>.json    原始响应（可离线复核）

纪律：抓不到的源不写进表1；摘要缺失或过短的条目直接跳过并记录原因；
不因"凑够 200 条"而降低标准。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from experiments import config_loader
from experiments.collect.compliant_fetcher import build_fetcher
from experiments.collect.parsers import extract_main_text, normalize, parse_api_json, parse_rss
from experiments.common import (
    git_commit,
    sha256_file,
    utc_now_iso,
    write_json,
)
from experiments.logging_utils import get_logger
from experiments.paths import SNAPSHOT_DIR

logger = get_logger("exp.collect")

MAX_DETAIL_CHARS = 20000


def _to_date(value: Optional[str]) -> Optional[str]:
    """把各种发布时间格式归一化为 YYYY-MM-DD；无法解析返回 None。"""
    if not value:
        return None
    s = str(value).strip()
    try:
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
    except Exception:  # noqa: BLE001
        pass
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).date().isoformat()
    except Exception:  # noqa: BLE001
        return None


def _request(fetcher, url: str, params: Optional[Dict[str, object]], log: List[Dict[str, Any]]):
    res = fetcher.get(url, params=params)
    log.append(
        {
            "url": url,
            "params": params or {},
            "status": res.status,
            "ok": res.ok,
            "elapsed_ms": res.elapsed_ms,
            "robots_allowed": res.robots_allowed,
            "robots_source": res.robots_source,
            "error": res.error,
            "at": utc_now_iso(),
        }
    )
    return res


def _collect_nvd(spec: Dict[str, Any], fetcher, limit: int, log: List[Dict[str, Any]],
                 raw_dir: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Counter, Dict[str, str]]:
    """采集 NVD，并返回 CVE 编号 -> 描述全文的映射（供跨源配对使用）。"""
    entries: List[Dict[str, Any]] = []
    url = str(spec.get("url"))
    fetched = 0
    page_size = min(int(limit), 2000)
    # 默认排序是 CVE 编号升序（会从 1999 年的条目开始），对论文无意义。
    # 若配置了 window_days，则限定最近 N 天发布的条目，使时间跨度可解释。
    base_params: Dict[str, object] = {}
    window = spec.get("window_days")
    if window:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=int(window))
        base_params["pubStartDate"] = start.strftime("%Y-%m-%dT%H:%M:%S.000")
        base_params["pubEndDate"] = end.strftime("%Y-%m-%dT%H:%M:%S.000")
    # 默认排序会返回窗口内最早的条目，时间跨度只有一两天；
    # 配置 start_indexes 时在窗口内多点取样，使表1 的时间跨度可解释。
    offsets = [int(x) for x in (spec.get("start_indexes") or [])] or [0]
    per_offset = max(1, int(limit) // len(offsets))
    for i, off in enumerate(offsets):
        take = min(per_offset, int(limit) - fetched)
        if take <= 0:
            break
        params = dict(base_params)
        params.update({"resultsPerPage": take, "startIndex": off})
        res = _request(fetcher, url, params, log)
        if not res.ok:
            logger.warning("NVD startIndex=%d 采集失败（%s），跳过该取样点", off, res.error)
            continue
        (raw_dir / f"nvd_cve_api_o{off}.json").write_text(res.text, encoding="utf-8")
        try:
            batch = parse_api_json(json.loads(res.text), spec)
        except Exception as e:  # noqa: BLE001
            logger.warning("NVD startIndex=%d 解析失败: %s", off, e)
            continue
        entries.extend(batch)
        fetched += len(batch)
    cve_map: Dict[str, str] = {}
    for e in entries:
        native = str(e.get("native_id") or "")
        if native and e.get("content_inline"):
            cve_map[native] = e["content_inline"]
    return entries, [], Counter(), cve_map


def _collect_api(spec: Dict[str, Any], fetcher, limit: int, log: List[Dict[str, Any]],
                 raw_dir: Path) -> List[Dict[str, Any]]:
    """分页采集 JSON API（如 GitHub 限制 per_page ≤ 100，需翻页）。"""
    url = str(spec.get("url"))
    tpl = spec.get("params_template")
    if not tpl:
        res = _request(fetcher, url, None, log)
        if not res.ok:
            logger.error("%s 采集失败: %s", spec.get("id"), res.error)
            return []
        (raw_dir / f"{spec.get('id')}.json").write_text(res.text, encoding="utf-8")
        try:
            entries = parse_api_json(json.loads(res.text), spec)
        except Exception as e:  # noqa: BLE001
            logger.error("%s 解析失败: %s", spec.get("id"), e)
            return []
        return entries[: int(limit)] if limit else entries

    entries: List[Dict[str, Any]] = []
    max_per_page = int(spec.get("max_per_page", 100))
    fetched, page = 0, 1
    while fetched < int(limit):
        per_page = min(max_per_page, int(limit) - fetched)
        params: Dict[str, object] = {}
        for kv in str(tpl).format(limit=per_page, offset=fetched, page=page).split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k] = v
        res = _request(fetcher, url, params, log)
        if not res.ok:
            logger.error("%s 第 %d 页采集失败: %s", spec.get("id"), page, res.error)
            break
        (raw_dir / f"{spec.get('id')}_p{page}.json").write_text(res.text, encoding="utf-8")
        try:
            batch = parse_api_json(json.loads(res.text), spec)
        except Exception as e:  # noqa: BLE001
            logger.error("%s 第 %d 页解析失败: %s", spec.get("id"), page, e)
            break
        if not batch:
            break
        entries.extend(batch)
        fetched += len(batch)
        page += 1
        if len(batch) < per_page:
            break
    return entries


def _collect_rss(spec: Dict[str, Any], fetcher, limit: int, log: List[Dict[str, Any]],
                 raw_dir: Path) -> List[Dict[str, Any]]:
    res = _request(fetcher, str(spec.get("url")), None, log)
    if not res.ok:
        logger.error("%s 采集失败: %s", spec.get("id"), res.error)
        return []
    (raw_dir / f"{spec.get('id')}.xml").write_text(res.text, encoding="utf-8")
    entries = parse_rss(res.text)
    return entries[: int(limit)] if limit else entries


def _detail_cached(link: str, fetcher, log: List[Dict[str, Any]], raw_dir: Path) -> Optional[str]:
    """详情页正文抓取，带磁盘缓存。

    缓存既加快重跑，也避免对同一站点重复请求（采集礼节）。
    """
    from experiments.common import sha256_text

    cache_dir = raw_dir / "detail"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = sha256_text(link)[:20]
    cache_file = cache_dir / f"{key}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    res = _request(fetcher, link, None, log)
    if not res.ok:
        logger.debug("详情页抓取失败 %s: %s", link, res.error)
        return None
    text = extract_main_text(res.text, MAX_DETAIL_CHARS)
    if text:
        cache_file.write_text(text, encoding="utf-8")
    return text


def _resolve_content(spec: Dict[str, Any], entry: Dict[str, Any], fetcher,
                     cve_map: Dict[str, str], log: List[Dict[str, Any]],
                     raw_dir: Path) -> Tuple[str, str, Optional[str]]:
    """返回 (content, content_from, skip_reason)。"""
    mode = str(spec.get("content_from") or "inline")
    if mode == "nvd_crossref":
        native = str(entry.get("native_id") or "")
        text = cve_map.get(native, "")
        if len(text) < 80:
            return "", "nvd_crossref", "no-nvd-match"
        return text, "nvd_crossref", None
    if mode == "field":
        text = entry.get("content_inline") or ""
        if len(text) < 80:
            return "", "field", "content-too-short"
        return text, "field", None
    if mode == "detail":
        link = str(entry.get("link") or "")
        if not link:
            return "", "detail", "no-link"
        text = _detail_cached(link, fetcher, log, raw_dir)
        if text is None:
            return "", "detail", "detail-unavailable"
        if len(text) < 80:
            return "", "detail", "detail-too-short"
        return text, "detail", None
    # inline：正文即摘要字段（仅用于构成与时延测量，不进入质量评测）
    text = entry.get("content_inline") or entry.get("summary") or ""
    if len(text) < 80:
        return "", "inline", "content-too-short"
    return text, "inline", None


def build(limit_per_source: int = 300, out_dir: Optional[Path] = None,
          dataset_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    snap_dir = Path(out_dir) if out_dir else SNAPSHOT_DIR
    raw_dir = snap_dir / "raw"
    snap_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    cfg = config_loader.sources_config()
    exp_cfg = dataset_cfg if dataset_cfg is not None else {}
    try:
        exp_cfg = exp_cfg or config_loader.experiment_config().get("dataset", {})
    except Exception:  # noqa: BLE001
        exp_cfg = exp_cfg or {}

    fetcher = build_fetcher(cfg)
    log: List[Dict[str, Any]] = []
    cve_map: Dict[str, str] = {}

    all_items: List[Dict[str, Any]] = []
    dedup_log: List[Dict[str, Any]] = []
    per_source: List[Dict[str, Any]] = []
    seen_hash: Dict[str, str] = {}
    seen_url: Dict[str, str] = {}

    for spec in cfg.get("sources", []):
        if spec.get("enabled") is False:
            continue
        sid = str(spec.get("id"))
        logger.info("采集 %s (%s)", sid, spec.get("name"))
        skipped: Counter = Counter()
        collected = 0

        if sid == "nvd_cve_api":
            entries, _, _, cve_map = _collect_nvd(spec, fetcher, limit_per_source, log, raw_dir)
        elif spec.get("kind") == "rss":
            entries = _collect_rss(spec, fetcher, limit_per_source, log, raw_dir)
        else:
            entries = _collect_api(spec, fetcher, limit_per_source, log, raw_dir)

        collected = len(entries)
        kept = 0
        dates: List[str] = []
        for e in entries:
            content, content_from, reason = _resolve_content(spec, e, fetcher, cve_map, log, raw_dir)
            if reason:
                skipped[reason] += 1
                continue
            item = normalize(spec, e, content, content_from)
            if item is None:
                skipped["normalize-failed"] += 1
                continue
            h = item["content_sha256"]
            if h in seen_hash:
                dedup_log.append({"id": item["id"], "reason": "duplicate-content", "same_as": seen_hash[h]})
                skipped["duplicate-content"] += 1
                continue
            u = (item.get("url") or "").strip()
            # 空 URL 不参与判重（无逐条详情页的信源不能靠 URL 去重）
            if u and u in seen_url:
                dedup_log.append({"id": item["id"], "reason": "duplicate-url", "same_as": seen_url[u]})
                skipped["duplicate-url"] += 1
                continue
            seen_hash[h] = item["id"]
            if u:
                seen_url[u] = item["id"]
            d = _to_date(item.get("published_at"))
            if d:
                dates.append(d)
            all_items.append(item)
            kept += 1

        per_source.append(
            {
                "id": sid,
                "name": spec.get("name"),
                "category": spec.get("category"),
                "url": spec.get("url"),
                "collected": collected,
                "kept": kept,
                "quality_eligible": bool(spec.get("quality_eligible", False)),
                "skipped": dict(skipped),
                "date_min": min(dates) if dates else None,
                "date_max": max(dates) if dates else None,
            }
        )
        logger.info("  %s: 采集 %d 保留 %d 跳过 %s", sid, collected, kept, dict(skipped))

    # ---- 落盘 ----
    items_path = snap_dir / "items.jsonl"
    with open(items_path, "w", encoding="utf-8") as f:
        for it in all_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    with open(snap_dir / "dedup_log.jsonl", "w", encoding="utf-8") as f:
        for r in dedup_log:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(snap_dir / "collection_log.jsonl", "w", encoding="utf-8") as f:
        for r in log:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 表1：按信源类别聚合
    cat_rows: Dict[str, Dict[str, Any]] = {}
    for s in per_source:
        cat = s.get("category") or "未分类"
        row = cat_rows.setdefault(
            cat, {"category": cat, "sources": [], "collected": 0, "kept": 0,
                  "date_min": None, "date_max": None, "quality_eligible": 0}
        )
        row["sources"].append(s.get("name"))
        row["collected"] += s.get("collected", 0)
        row["kept"] += s.get("kept", 0)
        row["quality_eligible"] += sum(
            1 for it in all_items if it.get("source_id") == s["id"] and it.get("quality_eligible")
        )
        for bound, agg in (("date_min", min), ("date_max", max)):
            v = s.get(bound)
            if v:
                row[bound] = agg(x for x in [row[bound], v] if x)

    table1 = []
    for cat, row in cat_rows.items():
        span = "—"
        if row["date_min"] and row["date_max"]:
            span = row["date_min"] if row["date_min"] == row["date_max"] else f"{row['date_min']}~{row['date_max']}"
        table1.append(
            {
                "category": cat,
                "representative": " / ".join(row["sources"][:2]),
                "raw_count": row["collected"],
                "span": span,
                "dedup_count": row["kept"],
                "quality_eligible": row["quality_eligible"],
            }
        )

    stats = {
        "generated_at": utc_now_iso(),
        "git_commit": git_commit(),
        "limit_per_source": limit_per_source,
        "sources": per_source,
        "table1": table1,
        "totals": {
            "collected": sum(s["collected"] for s in per_source),
            "kept": len(all_items),
            "dedup_removed": len(dedup_log),
            "quality_eligible": sum(1 for it in all_items if it.get("quality_eligible")),
        },
        "requests": len(log),
        "min_total_required": int((exp_cfg or {}).get("min_total_required", 200)),
    }
    stats["meets_min_total"] = stats["totals"]["kept"] >= stats["min_total_required"]
    write_json(snap_dir / "dataset_stats.json", stats)

    # 哈希清单
    files = [items_path] + sorted(p for p in snap_dir.rglob("*") if p.is_file() and p.name != "manifest.sha256")
    with open(snap_dir / "manifest.sha256", "w", encoding="utf-8") as f:
        for p in files:
            f.write(f"{sha256_file(p)}  {p.relative_to(snap_dir).as_posix()}\n")

    print("=" * 72)
    print(f"条目合计 {stats['totals']['kept']}（去重移除 {stats['totals']['dedup_removed']}），"
          f"其中可用于质量评测 {stats['totals']['quality_eligible']}")
    for r in table1:
        print(f"  {r['category']:<10} {r['representative'][:34]:<36} 原始 {r['raw_count']:<5} "
              f"去重后 {r['dedup_count']:<5} 跨度 {r['span']}")
    if not stats["meets_min_total"]:
        print(f"  ! 未达到最小样本量 {stats['min_total_required']}，请扩大 limit 或启用更多信源")
    print(f"已写入: {snap_dir}")
    print("=" * 72)
    return stats


def main(limit: int = 300, out: Optional[str] = None) -> Dict[str, Any]:
    return build(limit_per_source=limit, out_dir=Path(out) if out else None)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="构建固定数据集快照")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    main(limit=a.limit, out=a.out)
