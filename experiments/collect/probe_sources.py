"""信源探测：确认「能不能采、采出来长什么样、参考摘要是否与正文同源」。

这一步决定表1 实际能列哪些信源。输出 ``reports/source_probe.json``，
并逐源打印：HTTP 状态、抓到的条数、样例字段名、参考摘要长度、
详情页抓取是否可行（决定该源能否进入质量评测集）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from experiments import config_loader
from experiments.collect.compliant_fetcher import build_fetcher
from experiments.collect.parsers import extract_main_text, parse_api_json, parse_rss
from experiments.common import write_json
from experiments.logging_utils import get_logger
from experiments.paths import REPORTS_DIR

logger = get_logger("exp.probe_sources")


def _build_url(spec: Dict[str, Any], limit: int, page: int = 1) -> tuple[str, Dict[str, object]]:
    url = str(spec.get("url"))
    params: Dict[str, object] = {}
    tpl = spec.get("params_template")
    if tpl:
        params_str = str(tpl).format(limit=limit, offset=0, page=page)
        for kv in params_str.split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k] = v
    return url, params


def probe_one(spec: Dict[str, Any], fetcher, limit: int) -> Dict[str, Any]:
    url, params = _build_url(spec, limit)
    res = fetcher.get(url, params=params or None)
    info: Dict[str, Any] = {
        "id": spec.get("id"),
        "name": spec.get("name"),
        "category": spec.get("category"),
        "url": url,
        "ok": res.ok,
        "http_status": res.status,
        "error": res.error,
        "robots_allowed": res.robots_allowed,
        "robots_source": res.robots_source,
        "n_items": 0,
        "sample": None,
        "detail_fetch": None,
        "suggestion": None,
    }
    if not res.ok:
        info["suggestion"] = "不可达，表1 不列此源"
        return info

    entries: List[Dict[str, Any]] = []
    if spec.get("kind") == "rss":
        entries = parse_rss(res.text)
        info["n_items"] = len(entries)
        if entries:
            e = entries[0]
            info["sample"] = {
                "title": (e.get("title") or "")[:80],
                "link": (e.get("link") or "")[:120],
                "summary_len": len(e.get("summary") or ""),
                "published": e.get("published"),
            }
            # 详情页抓取可行性：决定该源能否"正文与参考摘要不同源"
            if e.get("link"):
                d = fetcher.get(str(e["link"]))
                info["detail_fetch"] = {
                    "ok": d.ok,
                    "status": d.status,
                    "robots_allowed": d.robots_allowed,
                    "text_len": len(extract_main_text(d.text)) if d.ok else 0,
                }
    else:
        try:
            data = json.loads(res.text)
        except Exception as e:  # noqa: BLE001
            info["error"] = f"JSON 解析失败: {type(e).__name__}"
            info["suggestion"] = "响应非 JSON，需调整 kind 或 items_path"
            return info
        entries = parse_api_json(data, spec)
        info["n_items"] = len(entries)
        if entries:
            e = entries[0]
            info["sample"] = {
                "native_id": (e.get("native_id") or "")[:60],
                "title": (e.get("title") or "")[:80],
                "summary_len": len(e.get("summary") or ""),
                "published": e.get("published"),
                "top_level_keys": list((e.get("raw") or {}).keys())[:12],
            }

    if info["n_items"] == 0:
        info["suggestion"] = "抓到 0 条，需核对 items_path / id_field / summary_field"
    return info


def main(limit: int = 3, out: str | None = None) -> Dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = config_loader.sources_config()
    fetcher = build_fetcher(cfg)
    results = []
    for spec in cfg.get("sources", []):
        if spec.get("enabled") is False:
            continue
        logger.info("探测信源: %s", spec.get("id"))
        try:
            results.append(probe_one(spec, fetcher, limit))
        except Exception as e:  # noqa: BLE001
            results.append({"id": spec.get("id"), "ok": False, "error": f"{type(e).__name__}: {e}"})

    print("=" * 78)
    print(f"{'信源':<22}{'状态':<8}{'条数':<6}{'摘要长':<8}{'详情页':<10}说明")
    print("-" * 78)
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        sample = r.get("sample") or {}
        detail = r.get("detail_fetch") or {}
        detail_txt = "-" if not detail else ("可用" if detail.get("ok") and detail.get("text_len", 0) > 200 else "不可用")
        print(f"{str(r.get('id')):<22}{status:<8}{r.get('n_items', 0):<6}"
              f"{sample.get('summary_len', '-')!s:<8}{detail_txt:<10}{r.get('suggestion') or r.get('error') or ''}")
    print("=" * 78)
    path = write_json(out or (REPORTS_DIR / "source_probe.json"), {"probed_at": results and True, "results": results})
    print(f"已写入: {path}")
    return {"results": results}
