"""BERTScore 逐条结果缓存。

存在理由很具体：full 阶段有 1800 条配对，在 CPU 上要跑几十分钟，而
``aggregate`` 每跑一次都会重算 BERTScore。没有缓存，任何一次重跑
（补 token 校准、换金标、补人工评分表）都要再等一遍全量时间。

设计要点：

- **键含模型名**：换基座不会串味（`sha256(model \\x00 candidate \\x00 reference)`）。
- **只算未命中项**：一次批处理调用，不逐条调用，避免把开销放大。
- **空文本不参与**：候选或参考为空时该位置没有 F1，返回 ``None`` 且不写缓存。
- **坏行不致命**：缓存是派生产物，任何损坏行跳过即可，不能中断汇总。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from experiments.common import sha256_text
from experiments.logging_utils import get_logger

logger = get_logger("exp.bertscore_cache")

SEPARATOR = "\x00"


def cache_key(model: str, candidate: str, reference: str) -> str:
    """逐条结果的稳定键。

    用 ``\\x00`` 分隔各字段再哈希：若直接拼接，``("ab", "c")`` 与 ``("a", "bc")``
    会得到同一个键，把不同配对的分数混在一起。
    """
    return sha256_text(SEPARATOR.join([str(model), str(candidate), str(reference)]))


def load_cache(path: Path | str) -> Dict[str, float]:
    """载入缓存（键 → F1）。文件不存在或某行损坏时跳过，不抛异常。"""
    p = Path(path)
    out: Dict[str, float] = {}
    if not p.exists():
        return out
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                key = rec["key"]
                val = rec["f1"]
            except Exception:  # noqa: BLE001 - 派生缓存，坏行直接跳过
                continue
            if isinstance(key, str) and isinstance(val, (int, float)):
                out[key] = float(val)
    return out


def append_cache(path: Path | str, rows: Sequence[Tuple[str, float, str]]) -> None:
    """增量追加 (key, f1, model) 到缓存文件。"""
    if not rows:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for key, f1, model in rows:
            f.write(json.dumps({"key": key, "f1": float(f1), "model": model},
                               ensure_ascii=False) + "\n")


def score_with_cache(candidates: Sequence[str], references: Sequence[str],
                     model: str,
                     score_fn: Callable[[List[str], List[str]], List[Optional[float]]],
                     cache_path: Path | str,
                     chunk_size: Optional[int] = None) -> Tuple[List[Optional[float]], Dict[str, int]]:
    """先查缓存、只补算未命中项。

    Args:
        chunk_size: 每批送算的条数。给定则**分块计算并逐块落盘**：
            全量 1800 条在 CPU 上要几十分钟，分块既有进度日志，也保证了
            "中断后重跑只补剩余部分"；``None`` 表示一次性送算。

    Returns:
        (逐条 F1（与输入等长，空文本处为 None）, {"hit": n, "computed": m})
        其中 ``computed`` 计的是**位置数**（去重后实际送算的配对可能更少）。
    """
    if len(candidates) != len(references):
        raise ValueError("candidates 与 references 长度不一致")

    cache = load_cache(cache_path)
    vals: List[Optional[float]] = [None] * len(candidates)

    # 1) 先扫命中，并收集未命中的唯一配对（同一配对出现多次只算一次）
    miss_keys: Dict[str, str] = {}          # key -> 首次出现的 candidate
    miss_refs: Dict[str, str] = {}
    hit = computed = 0
    for i, (c, r) in enumerate(zip(candidates, references)):
        if not c or not r:
            continue                        # 空文本没有 F1，不缓存
        key = cache_key(model, c, r)
        if key in cache:
            vals[i] = cache[key]
            hit += 1
            continue
        computed += 1
        miss_keys.setdefault(key, c)
        miss_refs.setdefault(key, r)

    if not miss_keys:
        logger.info("BERTScore 缓存全命中：%d 条", hit)
        return vals, {"hit": hit, "computed": computed}

    logger.info("BERTScore 缓存：命中 %d，待算 %d（唯一配对 %d）",
                hit, computed, len(miss_keys))
    keys = list(miss_keys.keys())
    total = len(keys)

    def _run(part: List[str], done: int) -> None:
        """算一批并立刻落盘：中断时已完成的批次不会白算。"""
        fresh = score_fn([miss_keys[k] for k in part], [miss_refs[k] for k in part])
        if len(fresh) != len(part):
            raise ValueError(f"打分函数返回条数不符：期望 {len(part)}，实得 {len(fresh)}")
        rows: List[Tuple[str, float, str]] = []
        for key, value in zip(part, fresh):
            if value is None:
                continue
            cache[key] = float(value)
            rows.append((key, float(value), model))
        append_cache(cache_path, rows)
        logger.info("BERTScore 进度 %d/%d", done, total)

    if chunk_size and chunk_size > 0:
        for start in range(0, total, int(chunk_size)):
            part = keys[start:start + int(chunk_size)]
            _run(part, min(start + int(chunk_size), total))
    else:
        _run(keys, total)

    for i, (c, r) in enumerate(zip(candidates, references)):
        if vals[i] is not None or not c or not r:
            continue
        vals[i] = cache.get(cache_key(model, c, r))
    return vals, {"hit": hit, "computed": computed}


def prune(path: Path | str, keep_model: str) -> int:
    """只保留 ``keep_model`` 的缓存行，返回删除的行数。

    口径变更（换基座、改 idf）后旧键永远命中不了，留着只会让人误以为算过两遍，
    也会让 ``stats`` 里出现两个模型名。坏行一并清掉。
    """
    p = Path(path)
    if not p.exists():
        return 0
    kept: List[str] = []
    removed = 0
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                rec = json.loads(s)
                if str(rec.get("model")) == str(keep_model):
                    kept.append(s)
                    continue
            except Exception:  # noqa: BLE001 - 坏行直接计入删除
                pass
            removed += 1
    if removed:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        tmp.replace(p)
    return removed


def stats(path: Path | str) -> Dict[str, Any]:
    """缓存文件的行数与模型分布（供 CLI 与论文归档展示）。"""
    p = Path(path)
    models: Dict[str, int] = {}
    n = 0
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                n += 1
                models[str(rec.get("model"))] = models.get(str(rec.get("model")), 0) + 1
    return {"entries": n, "by_model": models, "path": str(p)}
