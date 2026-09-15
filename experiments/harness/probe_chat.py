"""云端连通性探针：用最小请求定位超时原因（不消耗大量 token）。

在跑批前先问四个问题：
1. 端点通不通（HTTP 级）；
2. 首字节延迟多少（判断是网络/代理问题还是生成慢）；
3. 短 prompt 能否在超时内完成；
4. 用与正式实验相同的输入长度，单条需要多久（判断是否需要限制输出长度）。

用法::

    python -m experiments.cli probe-chat                 # 两档各跑最小请求
    python -m experiments.cli probe-chat --full-input    # 额外用真实输入长度测一次
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from experiments import config_loader
from experiments.common import utc_now_iso, write_json
from experiments.harness import instrument
from experiments.logging_utils import get_logger
from experiments.paths import REPORTS_DIR

logger = get_logger("exp.probe_chat")

SHORT_PROMPT = "用一句话说明什么是 CVE。"


def _available_models(exp_cfg: Dict[str, Any], provider_name: str) -> List[str]:
    from experiments.paths import ENV_REPORT

    from experiments.common import read_json

    if not ENV_REPORT.exists():
        return []
    report = read_json(ENV_REPORT) or {}
    info = (report.get("cloud") or {}).get(provider_name) or {}
    return list(info.get("models") or [])


def probe_one(provider_name: str, model: str, exp_cfg: Dict[str, Any],
              prompt: str = SHORT_PROMPT, timeout: Optional[int] = None,
              max_tokens: Optional[int] = None, stream: bool = False) -> Dict[str, Any]:
    """对单个模型发一次最小请求，返回耗时与结果摘要。

    ``stream=True`` 时额外测量**首块到达时间（TTFT）**与**最大静默间隔**：
    推理型模型（如 qwen3-max）在思考阶段可能长时间不返回分块，
    若静默间隔接近 ``request_timeout``，即解释了流式路径下的读超时。
    """
    cloud_cfg = exp_cfg.get("cloud", {}) or {}
    providers = cloud_cfg.get("providers", []) or []
    provider = next((p for p in providers if p.get("name") == provider_name), {})
    api_key = os.getenv(str(provider.get("env_key") or ""), "")
    out: Dict[str, Any] = {
        "provider": provider_name, "model": model, "prompt_chars": len(prompt),
        "configured": bool(api_key), "ok": False, "stream": bool(stream),
        "elapsed_s": None, "ttft_s": None, "silence_max_s": None, "chunks": 0,
        "tokens_out": None, "error": None, "answer_chars": 0,
    }
    if not api_key:
        out["error"] = f"未设置环境变量 {provider.get('env_key')}"
        return out

    try:
        from openai import OpenAI
    except Exception as e:  # noqa: BLE001
        out["error"] = f"openai SDK 不可用: {e}"
        return out

    eff_timeout = float(timeout or cloud_cfg.get("request_timeout") or 120)
    out["timeout_used"] = eff_timeout
    start = time.perf_counter()
    try:
        client = OpenAI(api_key=api_key, base_url=provider.get("base_url"), timeout=eff_timeout)
        kwargs: Dict[str, Any] = {}
        if max_tokens:
            kwargs["max_tokens"] = int(max_tokens)

        if not stream:
            resp = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], **kwargs)
            elapsed = time.perf_counter() - start
            text = (resp.choices[0].message.content or "") if resp.choices else ""
            usage = getattr(resp, "usage", None)
            out.update(ok=True, elapsed_s=round(elapsed, 2), ttft_s=round(elapsed, 2),
                       answer_chars=len(text), chunks=1,
                       tokens_out=getattr(usage, "completion_tokens", None),
                       tokens_in=getattr(usage, "prompt_tokens", None))
        else:
            chunks = 0
            chars = 0
            first_at: Optional[float] = None
            last_at: Optional[float] = None
            max_gap = 0.0
            for chunk in client.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": prompt}],
                    stream=True, **kwargs):
                now = time.perf_counter()
                if first_at is None:
                    first_at = now
                elif last_at is not None:
                    max_gap = max(max_gap, now - last_at)
                last_at = now
                chunks += 1
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    # 推理型模型可能把思考过程放在 reasoning_content
                    chars += len(getattr(delta, "content", None) or "")
                    chars += len(getattr(delta, "reasoning_content", None) or "")
            elapsed = time.perf_counter() - start
            out.update(ok=True, elapsed_s=round(elapsed, 2),
                       ttft_s=round(first_at - start, 2) if first_at else None,
                       silence_max_s=round(max_gap, 2), chunks=chunks, answer_chars=chars)
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        out["elapsed_s"] = round(time.perf_counter() - start, 2)
    return out


def run(full_input: bool = False, timeout: Optional[int] = None,
        max_tokens: Optional[int] = None, model: Optional[str] = None,
        stream: bool = False) -> Dict[str, Any]:
    """跑探针。``stream=True`` 时对流式与非流式各测一遍并对比 TTFT 与静默间隔。"""
    exp_cfg = config_loader.experiment_config()
    cloud_cfg = exp_cfg.get("cloud", {}) or {}
    results: List[Dict[str, Any]] = []

    tiers = [("flagship", model)] if model else [("flagship", None), ("light", None)]
    for tier, forced in tiers:
        provider_name = "qwen"
        models = _available_models(exp_cfg, provider_name)
        name = forced
        if not name:
            from experiments.harness.env_probe import pick_model

            provider = next((p for p in (cloud_cfg.get("providers") or [])
                             if p.get("name") == provider_name), {})
            name = pick_model(models, provider.get(f"{tier}_hint", []))
        if not name:
            results.append({"tier": tier, "ok": False, "error": "未能确定模型名"})
            continue

        label = f"{tier}" + ("-stream" if stream else "")
        r = probe_one(provider_name, name, exp_cfg, SHORT_PROMPT, timeout, max_tokens, stream=stream)
        r["tier"] = label
        results.append(r)
        logger.info("探针[%s] %s -> %s（%.2fs, TTFT=%s）", label, name,
                    "OK" if r["ok"] else "FAIL", r["elapsed_s"] or 0, r.get("ttft_s"))

        if full_input and r["ok"]:
            from experiments.collect import snapshot

            items = snapshot.pilot_set(1)
            if items:
                long_prompt = items[0].get("content", "")[:20000]
                r2 = probe_one(provider_name, name, exp_cfg, long_prompt, timeout, max_tokens,
                               stream=stream)
                r2["tier"] = f"{label}-full-input"
                results.append(r2)
                logger.info("探针[%s] 输入 %d 字符 -> %s（%.2fs, TTFT=%s, 最大静默 %ss）", label,
                            len(long_prompt), "OK" if r2["ok"] else "FAIL",
                            r2["elapsed_s"] or 0, r2.get("ttft_s"), r2.get("silence_max_s"))

    report = {"probed_at": utc_now_iso(), "results": results, "stream": bool(stream),
              "timeout_used": timeout or cloud_cfg.get("request_timeout") or 120,
              "max_tokens_used": max_tokens or cloud_cfg.get("max_tokens")}
    out_name = "probe_chat_stream.json" if stream else "probe_chat.json"
    write_json(REPORTS_DIR / out_name, report)

    print("=" * 96)
    print(f"{'档位':<28}{'模型':<16}{'结果':<7}{'耗时/s':<9}{'TTFT/s':<9}{'静默/s':<9}{'字符':<8}错误")
    print("-" * 96)
    for r in results:
        print(f"{str(r.get('tier')):<28}{str(r.get('model')):<16}"
              f"{'OK' if r.get('ok') else 'FAIL':<7}{str(r.get('elapsed_s')):<9}"
              f"{str(r.get('ttft_s')):<9}{str(r.get('silence_max_s')):<9}"
              f"{str(r.get('answer_chars')):<8}{r.get('error') or ''}")
    print("=" * 96)
    print(f"已写入: {REPORTS_DIR / out_name}")
    _conclude(report)
    return report


def _conclude(report: Dict[str, Any]) -> None:
    """按取证结果给出唯一处置建议（避免事后解释）。"""
    to = float(report.get("timeout_used") or 120)
    flagged = 0
    for r in report.get("results") or []:
        if not r.get("ok"):
            continue
        sil = r.get("silence_max_s")
        if sil is not None and sil > to * 0.6:
            flagged += 1
            print(f"  ! {r.get('tier')}：最大静默 {sil}s 已接近超时 {to}s —— "
                  f"建议设 cloud.streaming=false（推理型模型流式静默触发读超时）")
        elif r.get("elapsed_s") and r["elapsed_s"] > to * 0.8:
            flagged += 1
            print(f"  ! {r.get('tier')}：总耗时 {r['elapsed_s']}s 接近超时 {to}s —— "
                  f"建议提高 cloud.request_timeout 或限制 cloud.max_tokens")
    if not flagged:
        print("  取证完成：TTFT/静默/总耗时均远离超时阈值，无需调整 streaming 或超时。")


if __name__ == "__main__":
    run()
