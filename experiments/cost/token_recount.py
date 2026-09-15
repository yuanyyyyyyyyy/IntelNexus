"""云端 token 用量重算（表5 云端计费的事实源）。

背景
----
full 阶段的云端 600 条记录 ``tokens_in`` / ``tokens_out`` 为空：
LangChain 的 ``ChatOpenAI`` 在 ``streaming=True`` 下默认不回传 ``usage``
（需 ``stream_usage=True``），而实验为保留生产默认参数未开启它
（详见 PROTOCOL.md 偏差记录）。结果是表5 的"输入/输出 token 计费"
两列没有实测支撑。

处置
----
**不重新调用 API、不改动任何已完成的生成**，而是对"实际发生过的请求与
响应文本"用**官方分词器**重算，并对输入侧区分两种来源：

- ``tokens_in`` 优先取**该次运行自己记录的提示词**（``prompt_tokens``：
  2026-09-15 起由埋点在 ``on_chat_model_start`` 抓到实际发出的提示词、
  用 Qwen 分词器计数），``usage_source="recount_own_prompt"``。这是唯一与
  该次请求真正对应的值。
- 旧记录没有提示词留痕，回退为"本地 ``qwen3:8b`` 同一样本 ``prompt_eval_count``
  的重复间中位数"，``usage_source="recount_proxy"``。**这是跨调用代理，口径不可比**：
  ``prompt_eval_count`` 是**一条样本内各次调用之和**，而 ``generate_summary``
  在输出板块不足时会改用简化 prompt 重试（本地小模型常触发），于是代理值
  往往是"首次 + 重试"两次之和，而云端那一次可能只发 1 次请求（同调用校准
  6/6 次均为 ``calls=1``）。实测复算：``1820 + 559 = 2379``，与旧记录 2397
  相差 **0.751%**，恰等于独立实测的边界计数偏差。次要成分是提示词自身长度
  也会变化（见 :func:`proxy_spread`）。故代理值只用于定界：其不确定区间由
  ``token-calib`` 的跨调用观测定界（``calibration_cross_call``），并由
  ``cost/cost_model.input_token_band`` 变成表5 表注可引用的数字。
- ``tokens_out``：对云端**已存盘的生成文本**用 Qwen 分词器计数；该口径经
  API 实测**完全一致（偏差 0%）**。

**计数口径本身已实测准确**：``token-calib`` 做的是**同一次调用内**的比较
（同一次调用既读 API 回报的 usage，又对该次调用真正发出的提示词计数），
云端两档 6 次调用的输入偏差 ≤0.383%、输出偏差 0.000%；本地后端同调用对照
（``same_call_agreement``）最大偏差 0.751%。因此历史的 32.237% **不是**
计数误差，而是"各次调用之和"与"单次调用值"相比的口径错误；该结果已重标注
保留在 ``calibration_cross_call``，**不得当作计数误差引用**。

产物
----
``reports/token_recount.json``（含 ``tokenizer`` / ``basis`` / ``calibration`` /
``calibration_cross_call`` / ``configs``）。原始 ``records.jsonl`` 一律不改写。
"""
from __future__ import annotations

import statistics
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from experiments.common import read_json, read_jsonl, utc_now_iso, write_json
from experiments.logging_utils import get_logger
from experiments.paths import REPORTS_DIR, RUNS_DIR

logger = get_logger("exp.recount")

RECOUNT_PATH = REPORTS_DIR / "token_recount.json"
TOKENIZER_DIR = REPORTS_DIR.parent / "data" / "qwen_tokenizer"
TOKENIZER_MODEL = "Qwen/Qwen3-8B"
DEFAULT_MIRROR = "https://hf-mirror.com"

# 提示词 token 的回退基准来源：旧云端记录无提示词留痕时，借用本地同一样本计数
BASIS_CONFIG = "qwen3:8b"

# 输入 token 的来源标签（写进记录的 usage_source，供回填与 verify 显示真实来源）
SRC_RECOUNT_OWN = "recount_own_prompt"    # 该次运行自己记录的提示词（可信）
SRC_RECOUNT_PROXY = "recount_proxy"       # 跨调用代理值（旧记录，须以区间披露）

# 历史（跨调用）校准的定性说明：不得被误读为分词器口径误差
CROSS_CALL_NOTE = (
    "跨调用比较：把「本地当次运行记录的 prompt_eval_count 合计」与「另一次云调用的 "
    "API usage（单次）」相比，二者口径不可比——本地小模型常因输出板块不足而改用"
    "简化 prompt 重试，一条样本因此发 2 次请求，其 tokens_in 是各次之和，"
    "而云端那一次可能只发 1 次。实测复算：1820（首次）+ 559（重试）= 2379，"
    "与旧记录 2397 相差 0.751%，恰等于独立实测的计数偏差，说明该 32.237% "
    "源于调用次数口径差，而非提示词漂移或分词器误差；计数口径本身已由"
    "同调用校准验证（云端 ≤0.383% / 本地 ≤0.751%）。次要成分是提示词自身"
    "长度也会变化（见 proxy_spread）。该比值仅用于为输入侧定界（见 input_token_band）。"
)

_TOKENIZER = None


# ------------------------------------------------------------------ 分词器
def tokenizer_path() -> Path:
    return TOKENIZER_DIR / "tokenizer.json"


def ensure_tokenizer(mirror: str = DEFAULT_MIRROR) -> Path:
    """确保 Qwen 分词器本体在本地（缺失时从镜像下载一次并落盘）。"""
    path = tokenizer_path()
    if path.exists() and path.stat().st_size > 100_000:
        return path
    TOKENIZER_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{mirror.rstrip('/')}/{TOKENIZER_MODEL}/resolve/main/tokenizer.json"
    logger.info("下载 Qwen 分词器: %s", url)
    with urllib.request.urlopen(url, timeout=180) as resp:  # noqa: S310 - 固定 https 镜像
        data = resp.read()
    if len(data) < 100_000:
        raise RuntimeError(f"分词器下载异常（仅 {len(data)} 字节）: {url}")
    path.write_bytes(data)
    logger.info("分词器已保存: %s（%d 字节）", path, len(data))
    return path


def tokenizer_ready() -> bool:
    """分词器本体是否已在本地（判断本身**不触发下载**）。"""
    path = tokenizer_path()
    return path.exists() and path.stat().st_size > 100_000


def _tokenizer(ensure: bool = True):
    global _TOKENIZER
    if _TOKENIZER is None:
        if not ensure and not tokenizer_ready():
            return None
        if ensure:
            ensure_tokenizer()
        from tokenizers import Tokenizer  # type: ignore

        _TOKENIZER = Tokenizer.from_file(str(tokenizer_path()))
    return _TOKENIZER


def tokenizer_info() -> Dict[str, Any]:
    p = tokenizer_path()
    info: Dict[str, Any] = {"model": TOKENIZER_MODEL, "file": str(p)}
    if p.exists():
        info["bytes"] = p.stat().st_size
        try:
            info["vocab_size"] = _tokenizer().get_vocab_size()
        except Exception:  # noqa: BLE001
            pass
    return info


def count_tokens(text: Optional[str], ensure: bool = True) -> Optional[int]:
    """用 Qwen 分词器计 token 数；失败返回 None（调用方保留占位）。

    ``ensure=False`` 专供实验运行期埋点：分词器本体缺失时直接返回 None，
    **不联网下载、不打断生成**——计数依赖不该影响实验能否跑完。
    """
    if not text:
        return None
    try:
        # 装载也在 try 内：分词器文件存在但损坏、或 tokenizers 未安装时，
        # 同样必须是"返回 None"而不是把调用方打挂
        tk = _tokenizer(ensure=ensure)
        if tk is None:
            return None
        return len(tk.encode(text, add_special_tokens=False).ids)
    except Exception as e:  # noqa: BLE001
        logger.warning("分词失败: %s", e)
        return None


# ------------------------------------------------------------------ 构建
def _proxy_buckets() -> Dict[str, List[int]]:
    """本地 ``BASIS_CONFIG`` 各样本的提示词 token 观测（中位数与极差共用）。"""
    buckets: Dict[str, List[int]] = {}
    for mpath in sorted(RUNS_DIR.glob("*/manifest.json")):
        try:
            m = read_json(mpath)
        except Exception:  # noqa: BLE001
            continue
        if str(m.get("config")) != BASIS_CONFIG:
            continue
        for r in read_jsonl(mpath.parent / "records.jsonl"):
            if r.get("error") or r.get("tokens_in") is None:
                continue
            buckets.setdefault(str(r.get("sample_id")), []).append(int(r["tokens_in"]))
    return buckets


def local_prompt_tokens() -> Dict[str, int]:
    """**跨调用代理**：本地 ``qwen3:8b`` 同一样本提示词 token 合计的重复间中位数。

    只用于旧云端记录的回退，且**口径不可比**：``tokens_in`` 是**一条样本内
    各次调用之和**（本地小模型常触发简化 prompt 重试，见 :func:`proxy_spread`），
    而云端那一次可能只发 1 次请求。实测复算（``1820 + 559 = 2379`` vs 旧记录
    2397，差 0.751%）说明该口径差正是历史 32.237% 的来源，不是分词器误差。

    使用者必须标明 ``usage_source=recount_proxy`` 并以区间披露；新记录一律用
    自己留痕的提示词（``prompt_tokens`` / ``recount_own_prompt``）。
    """
    return {k: int(statistics.median(v)) for k, v in _proxy_buckets().items() if v}


def proxy_spread(sample_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """代理口径的可靠性证据：同一样本提示词 token 之和的重复间极差。

    极差主要由**该重复是否触发简化 prompt 重试**造成（重试会再加一次输入，
    实测约 560–600 token），次要成分是提示词自身长度变化。极差 > 0 即说明
    代理值必然偏离其中某一次调用，这是"输入侧只能给区间"的**直接证据**。
    """
    buckets = _proxy_buckets()
    wanted = set(str(s) for s in (sample_ids or []))
    rows = []
    for sid, vals in buckets.items():
        if wanted and sid not in wanted:
            continue
        rows.append({"sample_id": sid, "n": len(vals), "min": min(vals), "max": max(vals),
                     "median": int(statistics.median(vals)), "spread": max(vals) - min(vals)})
    spreads = [r["spread"] for r in rows]
    return {
        "config": BASIS_CONFIG,
        "samples": len(rows),
        "samples_with_spread": sum(1 for s in spreads if s > 0),
        "max_spread": max(spreads) if spreads else 0,
        "median_spread": int(statistics.median(spreads)) if spreads else 0,
        "rows": sorted(rows, key=lambda r: (-r["spread"], r["sample_id"])),
    }


def same_call_agreement() -> Dict[str, Any]:
    """本地后端的**同调用口径**实测一致性：埋点计数 vs 服务端 ``prompt_eval_count``。

    取**同一条记录**上的两个量（同一次生成、同一批请求），比较
    ``prompt_tokens_sum``（我方对实际发出提示词的分词计数，各次之和）与
    ``tokens_in``（Ollama 服务端累计的 ``prompt_eval_count``）。二者一致即说明
    计数方法本身准确，云端 32% 的差异只能归因于**提示词内容变化**，而不是口径。

    预期服务端略高：Ollama 会把模型自带的 chat 模板特殊 token 计入
    ``prompt_eval_count``，而我方只数模板渲染后的文本。该对照**不需要任何
    云端调用**（纯本地运行数据）。
    """
    rows: List[Dict[str, Any]] = []
    for mpath in sorted(RUNS_DIR.glob("*/manifest.json")):
        try:
            m = read_json(mpath)
        except Exception:  # noqa: BLE001
            continue
        if str(m.get("backend")) != "ollama":
            continue
        for r in read_jsonl(mpath.parent / "records.jsonl"):
            mine, server = r.get("prompt_tokens_sum"), r.get("tokens_in")
            if r.get("error") or not mine or not server:
                continue
            rows.append({
                "run_id": str(m.get("run_id")), "config": str(m.get("config")),
                "stage": m.get("stage"), "sample_id": str(r.get("sample_id")),
                "repeat": r.get("repeat"), "prompt_calls": r.get("prompt_calls"),
                "our_tokens": int(mine), "server_tokens": int(server),
                "dev_pct": round((int(mine) - int(server)) / int(server) * 100, 3),
            })
    devs = [abs(r["dev_pct"]) for r in rows]
    return {
        "available": bool(rows),
        "n_records": len(rows),
        "max_abs_dev_pct": max(devs) if devs else None,
        "median_abs_dev_pct": round(statistics.median(devs), 3) if devs else None,
        "note": ("同一次生成内的口径对照：我方计数（prompt_tokens_sum）vs 服务端 "
                 "prompt_eval_count。服务端额外计入模型自带 chat 模板的特殊 token，"
                 "故小幅差异属预期；出现数倍差异才说明口径有问题"),
        "rows": rows,
    }


def relabel_legacy_calibration(previous: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """把历史（跨调用）校准结果重标注，避免被误读为分词器计数误差。

    历史 ``calibration`` 段把"本地当次运行记录的 prompt_eval_count"与"另一次云调用的
    API usage"相比，属跨调用比较；该比较**口径不可比**（前者是各次调用之和），
    ``comparison_type`` 与机制说明必须写清，并附同样本提示词极差作为证据。

    已重标注过的记录会被**原地刷新**说明文本与证据（观测行保留）：核查结论若有
    更新，重建产物即可同步，不会因为幂等短路而留下旧文案。
    """
    previous = previous or {}
    existing = previous.get("calibration_cross_call")
    calib = previous.get("calibration")
    if isinstance(calib, dict) and calib.get("comparison_type") == "same-call":
        calib = None          # 同调用校准不是跨调用留档的来源
    if not isinstance(existing, dict) and not isinstance(calib, dict):
        return None
    out = dict(existing if isinstance(existing, dict) else calib)
    out["comparison_type"] = "cross-call"
    out["confound"] = CROSS_CALL_NOTE
    sample_ids = [str(r.get("sample_id")) for v in (out.get("configs") or {}).values()
                  for r in (v or {}).get("rows") or [] if r.get("sample_id")]
    spread = proxy_spread(sample_ids) if sample_ids else None
    if spread and spread.get("samples"):
        out["proxy_spread_evidence"] = {
            "note": "同样本提示词 token 合计在本组观测内的极差：代理值不可靠的直接证据",
            "samples": spread["samples"],
            "samples_with_spread": spread["samples_with_spread"],
            "max_spread": spread["max_spread"],
            "rows": spread["rows"],
        }
    return out


def _same_call_calibration(previous: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    calib = (previous or {}).get("calibration")
    if isinstance(calib, dict) and calib.get("comparison_type") == "same-call":
        return calib
    return None


def build(force: bool = False) -> Dict[str, Any]:
    """重算全部云端记录的 token 用量并落盘。已存在且非 force 时直接读取。

    输入侧**优先用记录自己的提示词留痕**（``prompt_tokens``），缺失才回退跨调用
    代理值；每条都带来源标签，使 verify 能区分"哪一格可信、哪一格只是区间中心"。
    """
    if RECOUNT_PATH.exists() and not force:
        data = read_json(RECOUNT_PATH)
        if (data or {}).get("configs"):
            logger.info("已存在重算结果，直接使用: %s", RECOUNT_PATH)
            return data

    proxy = local_prompt_tokens()
    if not proxy:
        logger.warning("未找到 %s 的 prompt token 代理基准：仅能填有提示词留痕的记录", BASIS_CONFIG)

    configs: Dict[str, Any] = {}
    stats = {"runs": 0, "records": 0, "tin_missing": 0, "tout_missing": 0,
             "tin_own_prompt": 0, "tin_proxy": 0}
    for mpath in sorted(RUNS_DIR.glob("*/manifest.json")):
        try:
            m = read_json(mpath)
        except Exception:  # noqa: BLE001
            continue
        if str(m.get("backend")) != "openai_compatible":
            continue
        rdir = mpath.parent
        run_id = str(m.get("run_id"))
        per_run: Dict[str, Any] = {}
        for r in read_jsonl(rdir / "records.jsonl"):
            if r.get("error"):
                continue
            sid = str(r.get("sample_id"))
            rep = str(r.get("repeat"))
            # 计费口径是各次调用输入之和（重试会发两次请求），故优先用 sum
            own = r.get("prompt_tokens_sum") or r.get("prompt_tokens")
            if own:
                tin, tin_src = int(own), SRC_RECOUNT_OWN
                stats["tin_own_prompt"] += 1
            else:
                proxy_val = proxy.get(sid)
                tin = int(proxy_val) if proxy_val else None
                tin_src = SRC_RECOUNT_PROXY if tin else None
                if tin:
                    stats["tin_proxy"] += 1
            tout = None
            out_rel = r.get("output_path")
            if out_rel and (rdir / out_rel).exists():
                tout = count_tokens((rdir / out_rel).read_text(encoding="utf-8"))
            if tin is None:
                stats["tin_missing"] += 1
            if tout is None:
                stats["tout_missing"] += 1
            if tin is None and tout is None:
                continue
            per_run.setdefault(sid, {})[rep] = {"tokens_in": tin, "tokens_out": tout,
                                                "tokens_in_source": tin_src}
            stats["records"] += 1
        if per_run:
            configs[run_id] = per_run
            stats["runs"] += 1

    previous = read_json(RECOUNT_PATH) if RECOUNT_PATH.exists() else {}
    data: Dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "usage_source": "recount",
        "basis_config": BASIS_CONFIG,
        "tokenizer": tokenizer_info(),
        "basis": {
            "input_tokens": (
                f"优先：该次运行自己的提示词留痕 prompt_tokens（usage_source={SRC_RECOUNT_OWN}）；"
                f"回退：{BASIS_CONFIG} 的 prompt_eval_count 合计的重复间中位数"
                f"（usage_source={SRC_RECOUNT_PROXY}，跨调用代理，口径不可比）"),
            "output_tokens": "对云端已存盘的生成文本用 Qwen 分词器计数（add_special_tokens=False）",
            "disclaimer": (
                "重算值取代未采集的 API usage。**计数口径已实测准确**：同调用内云端输入偏差 ≤0.383%、"
                "输出 0.000%，本地后端 ≤0.751%（见 calibration 与 same_call_agreement）。"
                "输入侧若为代理值，其偏差来自**调用次数口径差**（本地记录的 tokens_in 是一条样本内"
                "各次调用之和，含简化 prompt 重试；云端那一次常为单次），不确定区间见 "
                "calibration_cross_call 与 reports/cost_sensitivity.json 的 input_token_band，论文须并报"),
        },
        "proxy_spread": proxy_spread(),
        "same_call_agreement": same_call_agreement(),
        "calibration": _same_call_calibration(previous),
        "calibration_cross_call": relabel_legacy_calibration(previous),
        "stats": stats,
        "configs": configs,
    }
    write_json(RECOUNT_PATH, data)
    logger.info("token 重算完成：%d 个 run / %d 条记录（输入来自留痕 %d、代理 %d；缺输入 %d，缺输出 %d）",
                stats["runs"], stats["records"], stats["tin_own_prompt"], stats["tin_proxy"],
                stats["tin_missing"], stats["tout_missing"])
    return data


def load() -> Dict[str, Any]:
    if not RECOUNT_PATH.exists():
        return {}
    return read_json(RECOUNT_PATH) or {}


def overlay(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """把重算值叠加到内存中的记录（**不写回**原始 records.jsonl）。

    只填 ``tokens_in is None`` 且未失败的云端记录，并按来源标注
    ``usage_source``：``recount_own_prompt``（该次请求自己的提示词留痕，可信）
    或 ``recount_proxy``（跨调用代理，须以区间披露）。回填与 verify 据此
    区分"哪一格可信、哪一格只是区间中心"。
    """
    data = load()
    if not (data or {}).get("configs"):
        return {"applied": 0, "runs": 0, "available": False}
    applied, touched_runs = 0, 0
    by_source: Dict[str, int] = {}
    for m in runs:
        if str(m.get("backend")) != "openai_compatible":
            continue
        per_run = (data.get("configs") or {}).get(str(m.get("run_id"))) or {}
        if not per_run:
            continue
        touched = 0
        for r in (m.get("_records") or []):
            if r.get("error") or r.get("tokens_in") is not None:
                continue
            cell = (per_run.get(str(r.get("sample_id"))) or {}).get(str(r.get("repeat")))
            if not cell:
                continue
            src = str(cell.get("tokens_in_source") or SRC_RECOUNT_OWN)
            r["tokens_in"] = cell.get("tokens_in")
            r["tokens_out"] = cell.get("tokens_out")
            r["usage_source"] = src
            by_source[src] = by_source.get(src, 0) + 1
            applied += 1
            touched += 1
        if touched:
            touched_runs += 1
    if applied:
        logger.info("云端 token 重算已叠加：%d 条 / %d 个 run（来源 %s）",
                    applied, touched_runs, by_source)
    return {"applied": applied, "runs": touched_runs, "available": True,
            "by_source": by_source,
            "tokenizer": (data.get("tokenizer") or {}).get("model")}


# ------------------------------------------------------------------ 校准
def calibrate(n: int = 3, configs: Optional[List[str]] = None) -> Dict[str, Any]:
    """用真实 API 用量校准**同一次调用内**的分词器口径（需云端密钥）。

    对每个云端配置取 ``n`` 条样本，以 ``stream_usage=True`` 调用；同一次调用
    既读 API 回报的 usage，又对该次调用**真正发出的提示词**（埋点从
    ``on_chat_model_start`` 抓到的原文）用同一分词器计数。二者之差才是
    分词器口径偏差，写入 ``reports/token_recount.json`` 的 ``calibration`` 段
    （``comparison_type="same-call"``）。

    注意与历史版本的区别：旧版把"本地当次运行记录的 prompt_eval_count **合计**"
    与"本次 API usage（**单次**）"相比（跨调用）。本地小模型常因输出板块不足而
    改用简化 prompt 重试，一条样本发 2 次请求，其合计与单次值不可比——实测复算
    ``1820 + 559 = 2379`` 对旧记录 2397 只差 0.751%，恰等于独立实测的计数偏差。
    该结果只保留在 ``calibration_cross_call`` 作输入侧定界依据，不得当作口径误差。
    """
    from experiments import config_loader
    from experiments.collect import snapshot
    from experiments.harness import instrument

    exp_cfg = config_loader.experiment_config()
    items = snapshot.pilot_set(int(n))
    out: Dict[str, Any] = {"measured_at": utc_now_iso(), "comparison_type": "same-call",
                           "n_items": len(items), "configs": {}}

    for cfg in exp_cfg.get("configs", []):
        cid = str(cfg.get("id"))
        if cfg.get("backend") != "openai_compatible":
            continue
        if configs and cid not in configs:
            continue
        binding = instrument.build_llm(cfg, exp_cfg, seed=int(exp_cfg.get("seed", 0)),
                                       request_overrides={"stream_usage": True})
        rows: List[Dict[str, Any]] = []
        for it in items:
            res = instrument.generate_once(binding.llm, it, usage=binding.usage)
            api_in, api_out = res.usage.get("tokens_in"), res.usage.get("tokens_out")
            # 同调用口径：本次请求自己留痕的提示词计数（不是别次运行的代理值）
            same_in = res.usage.get("prompt_tokens")
            same_out = count_tokens(res.text) if res.text else None
            rows.append({
                "sample_id": str(it.get("id")), "error": res.error,
                "api_tokens_in": api_in, "prompt_tokens_in": same_in,
                "api_tokens_out": api_out, "recount_tokens_out": same_out,
                "dev_in_pct": _dev(api_in, same_in), "dev_out_pct": _dev(api_out, same_out),
                "prompt_calls": res.usage.get("prompt_calls"),
                "prompt_render": res.usage.get("prompt_render"),
                "prompt_chars": res.usage.get("prompt_chars"),
                "usage_source": res.usage.get("usage_source"),
            })
        devs = [abs(r[k]) for r in rows for k in ("dev_in_pct", "dev_out_pct")
                if isinstance(r.get(k), (int, float))]
        out["configs"][cid] = {
            "model": binding.model,
            "usage_source": next((r.get("usage_source") for r in rows
                                  if r.get("usage_source") not in (None, "none")), None),
            "max_abs_dev_pct": round(max(devs), 3) if devs else None,
            "rows": rows,
        }
        logger.info("%s 同调用口径校准最大偏差 %s%%", cid, out["configs"][cid]["max_abs_dev_pct"])

    data = load() or {"configs": {}}
    data["calibration_cross_call"] = relabel_legacy_calibration(data) or data.get("calibration_cross_call")
    data["calibration"] = out
    data.setdefault("usage_source", "recount")
    data["generated_at"] = data.get("generated_at") or utc_now_iso()
    write_json(RECOUNT_PATH, data)
    return out


def _dev(api: Optional[float], rec: Optional[float]) -> Optional[float]:
    if api in (None, 0) or rec is None:
        return None
    return round((float(rec) - float(api)) / float(api) * 100.0, 3)


def main(force: bool = True) -> Dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    data = build(force=force)
    print(f"已写入 {RECOUNT_PATH}")
    print(f"  分词器: {(data.get('tokenizer') or {}).get('model')}")
    print(f"  覆盖: {data.get('stats')}")
    spread = data.get("proxy_spread") or {}
    if spread:
        print(f"  代理可靠性: {spread.get('samples_with_spread')}/{spread.get('samples')} 个样本"
              f"的提示词在重复间变化（最大极差 {spread.get('max_spread')} token）"
              f"→ 输入侧只能给区间")
    agree = data.get("same_call_agreement") or {}
    if agree.get("available"):
        print(f"  同调用口径对照（本地 {agree.get('n_records')} 条）: 我方计数 vs 服务端"
              f" prompt_eval_count 最大偏差 {agree.get('max_abs_dev_pct')}%"
              f"（中位 {agree.get('median_abs_dev_pct')}%）")
    else:
        print("  ! 尚无同调用口径对照（跑一次本地 smoke 即可，无需云端调用）")
    calib = data.get("calibration") or {}
    if calib:
        print(f"  同调用口径校准（comparison_type={calib.get('comparison_type')}）:")
        for cfg, v in (calib.get("configs") or {}).items():
            print(f"    {cfg}: 最大绝对偏差 {v.get('max_abs_dev_pct')}%")
    else:
        print("  ! 尚无同调用口径校准（可运行 token-calib）；论文须说明该限制")
    cross = data.get("calibration_cross_call") or {}
    devs = [v.get("max_abs_dev_pct") for v in (cross.get("configs") or {}).values()
            if isinstance(v.get("max_abs_dev_pct"), (int, float))]
    if devs:
        print(f"  [留档] 跨调用最大观测偏差 {max(devs)}%"
              f"（调用次数口径差所致：本地含简化 prompt 重试=各次之和，云端常为单次；"
              f"**不是**计数误差，仅用于输入侧定界）")
    return data


if __name__ == "__main__":
    main()
