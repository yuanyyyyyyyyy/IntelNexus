"""批处理执行器：配置 × 样本 × 重复 → 原始记录 + run_manifest。

一个 run = 某个配置的一次完整重复（跑完样本集）。每次 run 产生::

    runs/<run_id>/manifest.json   运行级元信息（可追溯七要素）
    runs/<run_id>/records.jsonl   逐条记录（时延、token、错误）
    runs/<run_id>/outputs/*.md    原始生成文本（不入库）

纪律：
- 时延测量串行执行（并发会污染 P50/P95）；
- 任何一条失败都记录原因，不静默跳过，不重跑到"好看"为止；
- 失败率过高则中止该配置，交由人判断（禁止自动降样本量）。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from experiments import config_loader
from experiments.collect import snapshot
from experiments.common import (
    append_jsonl,
    git_commit,
    git_dirty,
    make_run_id,
    sha256_file,
    slug,
    utc_now_iso,
    write_json,
)
from experiments.harness import instrument, resource_monitor
from experiments.harness.baselines import run_baseline
from experiments.logging_utils import get_logger
from experiments.paths import RUNS_DIR

logger = get_logger("exp.runner")

ABORT_FAILURE_RATE = 0.5


@dataclass
class RunRecord:
    run_id: str
    config: str
    backend: str
    sample_id: str
    repeat: int
    latency_s: float
    # 提示词留痕：本条**最后一次** LLM 调用实际发出的提示词（旧记录无此字段）。
    # 用途：云端未回传 usage 时，事后可确认"那一次请求的提示词有多长"，
    # 不必再借用别次运行的值当代理（见 PROTOCOL.md 偏差记录 2026-09-15）。
    prompt_chars: Optional[int] = None
    prompt_sha256: Optional[str] = None
    prompt_tokens: Optional[int] = None      # 最后一次调用的提示词 token
    prompt_tokens_sum: Optional[int] = None  # 本条各次调用之和（与计费/服务端口径可比）
    prompt_calls: int = 0                    # >1 表示走了"简化 prompt 重试"
    prompt_render: Optional[str] = None      # chat_messages | text
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    usage_source: str = "none"
    peak_gpu_mb: Optional[float] = None
    peak_rss_mb: Optional[float] = None
    seed: Optional[int] = None
    seed_supported: bool = False
    model_version: Optional[str] = None
    output_chars: int = 0
    error: Optional[str] = None
    error_kind: Optional[str] = None   # timeout | generic | exception
    output_path: Optional[str] = None


def _script_fingerprint() -> Dict[str, Any]:
    """脚本版本存证：取本模块与埋点模块的哈希。"""
    here = Path(__file__).resolve().parent
    files = {
        "harness/runner.py": str(sha256_file(here / "runner.py"))[:16],
        "harness/instrument.py": str(sha256_file(here / "instrument.py"))[:16],
    }
    return files


def _sample_set(stage: str, exp_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    ds = exp_cfg.get("dataset", {}) or {}
    if stage == "smoke":
        return snapshot.smoke_set(int(ds.get("smoke_size", 2)))
    if stage == "pilot":
        return snapshot.pilot_set(int(ds.get("pilot_size", 30)))
    if stage == "full":
        return snapshot.full_set(int(ds.get("full_size", 200)))
    raise ValueError(f"未知阶段: {stage}（可选 smoke/pilot/full）")


def _baseline_run(cfg: Dict[str, Any], items: List[Dict[str, Any]], repeat: int,
                  baselines_cfg: Dict[str, Any], stage: str) -> Dict[str, Any]:
    run_id = make_run_id(cfg["id"], repeat)
    rdir = RUNS_DIR / run_id
    (rdir / "outputs").mkdir(parents=True, exist_ok=True)
    kind = str(cfg.get("kind"))
    params = (baselines_cfg or {}).get(kind, {}) or {}

    started = utc_now_iso()
    t0 = time.perf_counter()
    records: List[RunRecord] = []
    with resource_monitor.ResourceMonitor(interval_s=0.2) as mon:
        for it in items:
            s = time.perf_counter()
            try:
                text = run_baseline(kind, it.get("content", ""), params)
                err = None
            except Exception as e:  # noqa: BLE001
                text, err = "", f"{type(e).__name__}: {str(e)[:200]}"
            latency = time.perf_counter() - s
            out_path = rdir / "outputs" / f"{slug(it.get('id', 'x'), 60)}.md"
            if text:
                out_path.write_text(text, encoding="utf-8")
            rec = RunRecord(
                run_id=run_id, config=str(cfg["id"]), backend="baseline",
                sample_id=str(it.get("id")), repeat=repeat, latency_s=round(latency, 4),
                seed=None, seed_supported=True, model_version=f"baseline-{kind}",
                output_chars=len(text), error=err,
                output_path=str(out_path.relative_to(rdir)) if text else None,
            )
            records.append(rec)
    peaks = mon.stop()
    elapsed = time.perf_counter() - t0
    for r in records:
        r.peak_gpu_mb = peaks.get("peak_gpu_mb")
        r.peak_rss_mb = peaks.get("peak_rss_mb")
        append_jsonl(rdir / "records.jsonl", asdict(r))

    write_json(rdir / "manifest.json", {
        "run_id": run_id, "stage": stage, "config": str(cfg["id"]), "backend": "baseline",
        "baseline_kind": kind, "baseline_params": params,
        "repeat": repeat, "n_items": len(items),
        "started_at": started, "finished_at": utc_now_iso(),
        "elapsed_s": round(elapsed, 3),
        "throughput_per_min": round(len(items) / elapsed * 60, 2) if elapsed > 0 else None,
        "resource_peaks": peaks,
        "git_commit": git_commit(), "git_dirty": git_dirty(),
        "script_sha256": _script_fingerprint(),
        "dataset_sha256": snapshot.load().manifest_sha256,
        "failures": sum(1 for r in records if r.error),
        "valid_records": sum(1 for r in records if not r.error),
        "failed_records": sum(1 for r in records if r.error),
        "error_kinds": _error_kinds(records),
    })
    return {"run_id": run_id, "n": len(records), "failures": sum(1 for r in records if r.error)}


def _llm_run(cfg: Dict[str, Any], items: List[Dict[str, Any]], repeat: int,
             exp_cfg: Dict[str, Any], stage: str, seed: int) -> Dict[str, Any]:
    binding = instrument.build_llm(cfg, exp_cfg, seed=seed)
    run_id = make_run_id(cfg["id"], repeat)
    rdir = RUNS_DIR / run_id
    (rdir / "outputs").mkdir(parents=True, exist_ok=True)

    started = utc_now_iso()
    t0 = time.perf_counter()
    records: List[RunRecord] = []
    failures = 0
    with resource_monitor.ResourceMonitor(interval_s=0.5, gpu=(cfg.get("backend") == "ollama")) as mon:
        for i, it in enumerate(items, 1):
            unit_cfg = exp_cfg.get("unit", {}) or {}
            # 输入长度上限对所有后端统一生效（与论文表2 的截断说明一致）
            res = instrument.generate_once(
                binding.llm, it, search_mode=str(unit_cfg.get("search_mode", "all")),
                usage=binding.usage,
                input_max_chars=unit_cfg.get("input_max_chars"),
            )
            out_path = rdir / "outputs" / f"{slug(it.get('id', 'x'), 60)}.md"
            # 失败条目不落盘输出：避免错误文本被后续 aggregate 当作摘要评分
            wrote = False
            if res.text and not res.error:
                out_path.write_text(res.text, encoding="utf-8")
                wrote = True
            if res.error:
                failures += 1
            rec = RunRecord(
                run_id=run_id, config=str(cfg["id"]), backend=str(cfg.get("backend")),
                sample_id=str(it.get("id")), repeat=repeat, latency_s=round(res.latency_s, 4),
                tokens_in=res.usage.get("tokens_in"), tokens_out=res.usage.get("tokens_out"),
                usage_source=res.usage.get("usage_source", "none"),
                prompt_chars=res.usage.get("prompt_chars"),
                prompt_sha256=res.usage.get("prompt_sha256"),
                prompt_tokens=res.usage.get("prompt_tokens"),
                prompt_tokens_sum=res.usage.get("prompt_tokens_sum"),
                prompt_calls=int(res.usage.get("prompt_calls") or 0),
                prompt_render=res.usage.get("prompt_render"),
                seed=seed, seed_supported=binding.seed_supported,
                model_version=res.usage.get("model_version") or binding.model,
                output_chars=len(res.text) if not res.error else 0,
                error=res.error, error_kind=res.error_kind,
                output_path=str(out_path.relative_to(rdir)) if wrote else None,
            )
            records.append(rec)
            append_jsonl(rdir / "records.jsonl", asdict(rec))
            if i % 10 == 0 or i == len(items):
                logger.info("  %s 第 %d/%d 条，累计 %.1fs，失败 %d",
                            cfg["id"], i, len(items), time.perf_counter() - t0, failures)
            if records and failures / len(records) > ABORT_FAILURE_RATE:
                logger.error("失败率超过 %.0f%%，中止配置 %s", ABORT_FAILURE_RATE * 100, cfg["id"])
                break
    peaks = mon.stop()
    elapsed = time.perf_counter() - t0

    write_json(rdir / "manifest.json", {
        "run_id": run_id, "stage": stage, "config": str(cfg["id"]),
        "backend": str(cfg.get("backend")), "model": binding.model,
        "model_version_reported": next((r.model_version for r in records if r.model_version), None),
        "provider": binding.extra.get("provider"), "base_url": binding.extra.get("base_url"),
        "repeat": repeat, "n_items": len(items),
        "seed": seed, "seed_supported": binding.seed_supported,
        "llm_params": instrument.common_llm_params(),
        "dropped_params": binding.dropped_params,
        "extra_params": binding.extra,
        "started_at": started, "finished_at": utc_now_iso(),
        "elapsed_s": round(elapsed, 3),
        "throughput_per_min": round(len(records) / elapsed * 60, 2) if elapsed > 0 else None,
        "resource_peaks": peaks,
        "usage_source": next((r.usage_source for r in records if r.usage_source != "none"), "none"),
        "prompt_trace": _prompt_trace_summary(records),
        "git_commit": git_commit(), "git_dirty": git_dirty(),
        "script_sha256": _script_fingerprint(),
        "dataset_sha256": snapshot.load().manifest_sha256,
        "failures": failures,
        "valid_records": len(records) - failures,
        "failed_records": failures,
        "error_kinds": _error_kinds(records),
        "param_overrides": _param_overrides(exp_cfg, cfg),
    })
    return {"run_id": run_id, "n": len(records), "failures": failures,
            "usage_source": next((r.usage_source for r in records if r.usage_source != "none"), "none")}


def _prompt_trace_summary(records: List[RunRecord]) -> Dict[str, Any]:
    """提示词留痕覆盖情况，供事后核查"同一样本的提示词是否真的变了"。

    关键指标是 ``samples_with_multiple_texts``：同一 ``sample_id`` 在本 run 内
    出现过 >1 种提示词哈希的次数。这正是历史记录只能"借用别次运行的值"的原因
    （``generate_summary`` 的提示词含可信度 / 知识图谱 / 冲突 / 知识库等运行期
    上下文，实测同样本在不同调用间可差数千 token）。

    注意 ``distinct_texts`` 只是全部哈希的去重数，在"每条样本一个提示词"的
    正常情形下就约等于样本数，**不能**用它判断提示词是否稳定。
    """
    traced = [r for r in records if r.prompt_chars is not None]
    by_sample: Dict[str, set] = {}
    for r in traced:
        if r.prompt_sha256:
            by_sample.setdefault(r.sample_id, set()).add(r.prompt_sha256)
    try:
        from experiments.cost.token_recount import TOKENIZER_MODEL, tokenizer_ready

        ready = tokenizer_ready()
    except Exception:  # noqa: BLE001
        TOKENIZER_MODEL, ready = None, False
    return {
        "traced_records": len(traced),
        "untraced_records": len(records) - len(traced),
        "render": next((r.prompt_render for r in traced if r.prompt_render), None),
        "tokenizer": TOKENIZER_MODEL if ready else None,
        "tokenizer_ready": ready,
        "distinct_texts": len({r.prompt_sha256 for r in traced if r.prompt_sha256}),
        "samples_with_multiple_texts": sum(1 for v in by_sample.values() if len(v) > 1),
        "retried_records": sum(1 for r in records if r.prompt_calls > 1),
        "prompt_tokens_min": min((r.prompt_tokens for r in traced if r.prompt_tokens), default=None),
        "prompt_tokens_max": max((r.prompt_tokens for r in traced if r.prompt_tokens), default=None),
    }


def _error_kinds(records: List[RunRecord]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in records:
        if r.error_kind:
            out[r.error_kind] = out.get(r.error_kind, 0) + 1
    return out


def _param_overrides(exp_cfg: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """记录对主程序默认参数的任何覆盖（论文须如实说明，不得悄悄改参数）。"""
    overrides: Dict[str, Any] = {}
    # 统一的输入长度上限：对全部后端生效，覆盖生产中的小模型 25000 截断
    unit_cfg = (exp_cfg.get("unit", {}) or {})
    if unit_cfg.get("input_max_chars"):
        overrides["input_max_chars"] = unit_cfg["input_max_chars"]
    cloud_cfg = (exp_cfg.get("cloud", {}) or {})
    for key in ("streaming", "request_timeout", "max_tokens"):
        # streaming=False 属显式覆盖，必须留痕（不能用 truthy 判断）
        if cloud_cfg.get(key) is not None:
            overrides[key] = cloud_cfg[key]
    return overrides


def run_stage(stage: str = "smoke", configs: Optional[List[str]] = None,
              repeats: Optional[int] = None, sample_n: Optional[int] = None,
              dry_run: bool = False) -> Dict[str, Any]:
    exp_cfg = config_loader.experiment_config()
    items = _sample_set(stage, exp_cfg)
    if sample_n:
        items = items[: int(sample_n)]
    if not items:
        raise RuntimeError("样本集为空，请先运行 collect 构建快照")

    seed = int(exp_cfg.get("seed", 0))
    # 各阶段重复次数：优先 experiment.yaml 的 repeats_by_stage，
    # 与之缺失时回退 PROTOCOL.md 的约定（smoke/pilot=2，full=5）
    stage_repeats = (exp_cfg.get("repeats_by_stage") or {}) or {"smoke": 2, "pilot": 2, "full": 5}
    n_repeats = int(repeats if repeats is not None else stage_repeats.get(stage, exp_cfg.get("repeats", 5)))
    all_cfgs = list(exp_cfg.get("configs", [])) + list(exp_cfg.get("sensitivity", []) or [])
    selected = [c for c in all_cfgs if not configs or str(c["id"]) in configs]
    if not selected:
        raise RuntimeError(f"没有匹配的配置: {configs}")

    logger.info("阶段 %s：样本 %d 条，配置 %d 个，重复 %d 次", stage, len(items), len(selected), n_repeats)
    if dry_run:
        for c in selected:
            try:
                b = instrument.build_llm(c, exp_cfg, seed=seed) if c.get("backend") != "baseline" else None
                logger.info("[dry-run] %s 可用（model=%s, seed_supported=%s）",
                            c["id"], getattr(b, "model", "baseline"),
                            getattr(b, "seed_supported", True))
            except Exception as e:  # noqa: BLE001
                logger.error("[dry-run] %s 不可用: %s", c["id"], e)
        return {"stage": stage, "dry_run": True, "n_items": len(items), "configs": [c["id"] for c in selected]}

    results: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for cfg in selected:
        logger.info("开始配置 %s", cfg["id"])
        for rep in range(1, n_repeats + 1):
            try:
                if cfg.get("backend") == "baseline":
                    r = _baseline_run(cfg, items, rep, exp_cfg.get("baselines", {}) or {}, stage)
                else:
                    r = _llm_run(cfg, items, rep, exp_cfg, stage, seed)
            except RuntimeError as e:
                # 缺密钥等不可恢复问题：跳过该配置，不终止整轮
                logger.error("跳过配置 %s：%s", cfg["id"], e)
                skipped.append({"config": str(cfg["id"]), "reason": str(e)})
                break
            r["config"] = str(cfg["id"])
            r["repeat"] = rep
            results.append(r)
            logger.info("  %s 第 %d 次：%d 条，失败 %d，run_id=%s",
                        cfg["id"], rep, r["n"], r["failures"], r["run_id"])

    total_fail = sum(r["failures"] for r in results)
    summary = {
        "stage": stage, "generated_at": utc_now_iso(), "git_commit": git_commit(),
        "n_items": len(items), "n_repeats": n_repeats, "seed": seed,
        "total_records": sum(r["n"] for r in results),
        "total_failures": total_fail,
        "skipped_configs": skipped,
        "runs": results,
    }
    write_json(RUNS_DIR / f"summary_{stage}_{time.strftime('%Y%m%dT%H%M%S')}.json", summary)
    print("=" * 72)
    print(f"阶段 {stage} 完成：{summary['total_records']} 条记录，失败 {total_fail}")
    for r in results:
        print(f"  {r['config']:<18} rep{r['repeat']}  {r['run_id']}  失败 {r['failures']}")
    print("=" * 72)
    return summary


def main(stage: str = "smoke", configs: Optional[List[str]] = None, repeats: Optional[int] = None,
         sample_n: Optional[int] = None, dry_run: bool = False) -> Dict[str, Any]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return run_stage(stage=stage, configs=configs, repeats=repeats, sample_n=sample_n, dry_run=dry_run)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="执行实验阶段")
    ap.add_argument("stage", nargs="?", default="smoke", choices=["smoke", "pilot", "full"])
    ap.add_argument("--configs", default=None, help="逗号分隔的配置 id")
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--sample-n", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.stage, a.configs.split(",") if a.configs else None, a.repeats, a.sample_n, a.dry_run)
