"""BERTScore 接入层测试：逐条缓存、基座探测、降级纪律。

缓存的存在理由很具体：1800 条配对在 CPU 上要跑几十分钟，而 `aggregate`
每跑一次都会重算。没有缓存，任何一次重跑（补 token 校准、换金标、补人工
评分表）都要再等一遍。

纪律：依赖/模型不可用时必须抛 `MetricUnavailable` 整列留占位，
**不得**改用近似实现或静默降级。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.metrics import bertscore, bertscore_cache


# ------------------------------------------------------------------ 缓存键
def test_cache_key_is_stable_for_same_inputs():
    a = bertscore_cache.cache_key("m", "候选文本", "参考摘要")
    b = bertscore_cache.cache_key("m", "候选文本", "参考摘要")
    assert a == b and len(a) == 64          # sha256 十六进制


def test_cache_key_is_model_scoped():
    """换基座不能复用旧分数，否则不同基座的结果会串味。"""
    a = bertscore_cache.cache_key("model-a", "c", "r")
    b = bertscore_cache.cache_key("model-b", "c", "r")
    assert a != b


def test_cache_key_separates_candidate_and_reference():
    """不能因为拼接歧义把 (ab,c) 与 (a,bc) 当成同一条。"""
    a = bertscore_cache.cache_key("m", "ab", "c")
    b = bertscore_cache.cache_key("m", "a", "bc")
    assert a != b


# ------------------------------------------------------------------ 载入
def test_load_cache_returns_empty_when_file_missing(tmp_path: Path):
    assert bertscore_cache.load_cache(tmp_path / "nope.jsonl") == {}


def test_load_cache_skips_corrupt_lines(tmp_path: Path):
    p = tmp_path / "c.jsonl"
    good = bertscore_cache.cache_key("m", "c", "r")
    p.write_text(
        json.dumps({"key": good, "f1": 0.5}) + "\n"
        + "{ 这不是合法 JSON }\n"
        + json.dumps({"key": "k2"}) + "\n",      # 缺 f1
        encoding="utf-8")
    cache = bertscore_cache.load_cache(p)
    assert cache == {good: 0.5}


# ------------------------------------------------------------------ 查缓存 + 补算
def _fake_scorer(calls: list):
    def _fn(cands, refs):
        calls.append(list(cands))
        return [0.5 + i * 0.1 for i in range(len(cands))]
    return _fn


def test_score_with_cache_computes_then_hits(tmp_path: Path):
    cache_path = tmp_path / "c.jsonl"
    calls: list = []
    cands = ["c1", "c2"]
    refs = ["r1", "r2"]

    vals, stats = bertscore_cache.score_with_cache(
        cands, refs, model="m", score_fn=_fake_scorer(calls), cache_path=cache_path)
    assert vals == pytest.approx([0.5, 0.6])
    assert stats == {"hit": 0, "computed": 2}
    assert len(calls) == 1                      # 只调了一次批处理

    # 第二次：全部命中，绝不能再调打分函数
    calls.clear()
    vals2, stats2 = bertscore_cache.score_with_cache(
        cands, refs, model="m", score_fn=_fake_scorer(calls), cache_path=cache_path)
    assert vals2 == pytest.approx(vals)
    assert stats2 == {"hit": 2, "computed": 0}
    assert calls == []


def test_score_with_cache_recomputes_only_misses(tmp_path: Path):
    cache_path = tmp_path / "c.jsonl"
    calls: list = []
    bertscore_cache.score_with_cache(["c1"], ["r1"], model="m",
                                     score_fn=_fake_scorer(calls), cache_path=cache_path)
    calls.clear()
    vals, stats = bertscore_cache.score_with_cache(
        ["c1", "c2"], ["r1", "r2"], model="m",
        score_fn=_fake_scorer(calls), cache_path=cache_path)
    assert stats == {"hit": 1, "computed": 1}
    assert calls == [["c2"]]                    # 只把未命中的送去算
    assert len(vals) == 2


def test_score_with_cache_keeps_none_for_empty_pairs(tmp_path: Path):
    """空候选/空参考没有 F1，返回 None，且不该进缓存。"""
    calls: list = []
    vals, stats = bertscore_cache.score_with_cache(
        ["", "c1"], ["r1", ""], model="m",
        score_fn=_fake_scorer(calls), cache_path=tmp_path / "c.jsonl")
    assert vals == [None, None]
    assert stats == {"hit": 0, "computed": 0}
    assert calls == []


def test_score_with_cache_separates_independent_result_slots(tmp_path: Path):
    """两个位置可能引用相同的文本，但必须各自得到值。"""
    vals, _ = bertscore_cache.score_with_cache(
        ["same", "same"], ["ref", "ref"], model="m",
        score_fn=_fake_scorer([]), cache_path=tmp_path / "c.jsonl")
    assert vals == pytest.approx([0.5, 0.5])


def test_score_with_cache_chunks_large_batches(tmp_path: Path):
    """1800 条要分块算：一次巨型调用既无进度也无可中断点。"""
    sizes: list = []

    def _fn(cands, refs):
        sizes.append(len(cands))
        return [0.1] * len(cands)

    cands = [f"c{i}" for i in range(5)]
    refs = [f"r{i}" for i in range(5)]
    vals, stats = bertscore_cache.score_with_cache(
        cands, refs, model="m", score_fn=_fn,
        cache_path=tmp_path / "c.jsonl", chunk_size=2)
    assert sizes == [2, 2, 1]
    assert stats == {"hit": 0, "computed": 5}
    assert vals == pytest.approx([0.1] * 5)


def test_score_with_cache_persists_each_chunk_before_next(tmp_path: Path):
    """中断续算的前提：每块算完就落盘，第二块失败时第一块的成果不能丢。"""
    cache_path = tmp_path / "c.jsonl"
    calls = {"n": 0}

    def _flaky(cands, refs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("模拟中断")
        return [0.7] * len(cands)

    cands = [f"c{i}" for i in range(4)]
    refs = [f"r{i}" for i in range(4)]
    with pytest.raises(RuntimeError):
        bertscore_cache.score_with_cache(cands, refs, model="m", score_fn=_flaky,
                                         cache_path=cache_path, chunk_size=2)
    saved = bertscore_cache.load_cache(cache_path)
    assert len(saved) == 2                       # 第一块的 2 条已落盘

    # 重跑：第一块命中，只需补第二块
    vals, stats = bertscore_cache.score_with_cache(
        cands, refs, model="m",
        score_fn=lambda c, r: [0.7] * len(c), cache_path=cache_path, chunk_size=2)
    assert stats == {"hit": 2, "computed": 2}
    assert vals == pytest.approx([0.7] * 4)


# ------------------------------------------------------------------ 基座探测与降级
def test_ensure_tokenizer_limits_sets_max_length_when_missing(tmp_path: Path):
    """实测缺陷：缺 model_max_length → Rust 分词器 enable_truncation 整型溢出。"""
    d = tmp_path / "model"
    d.mkdir()
    (d / "tokenizer_config.json").write_text('{"do_lower_case": false}', encoding="utf-8")
    bertscore._ensure_tokenizer_limits(d)
    cfg = json.loads((d / "tokenizer_config.json").read_text(encoding="utf-8"))
    assert cfg["model_max_length"] == bertscore.MAX_TOKENS


def test_ensure_tokenizer_limits_repairs_absurd_value(tmp_path: Path):
    d = tmp_path / "model"
    d.mkdir()
    (d / "tokenizer_config.json").write_text(
        json.dumps({"model_max_length": int(1e30)}), encoding="utf-8")
    bertscore._ensure_tokenizer_limits(d)
    cfg = json.loads((d / "tokenizer_config.json").read_text(encoding="utf-8"))
    assert cfg["model_max_length"] == bertscore.MAX_TOKENS


def test_ensure_tokenizer_limits_is_idempotent(tmp_path: Path):
    d = tmp_path / "model"
    d.mkdir()
    (d / "tokenizer_config.json").write_text(
        json.dumps({"model_max_length": 512, "do_lower_case": False}), encoding="utf-8")
    before = (d / "tokenizer_config.json").read_text(encoding="utf-8")
    bertscore._ensure_tokenizer_limits(d)
    assert (d / "tokenizer_config.json").read_text(encoding="utf-8") == before


def test_available_reports_not_ready_without_local_model(tmp_path, monkeypatch):
    """未固定落盘时必须给明确指引，且不得联网下载。"""
    monkeypatch.setattr(bertscore, "model_dir", lambda local_dir=None: tmp_path / "empty")
    info = bertscore.available()
    assert info["ready"] is False
    assert "bertscore-fetch" in (info["hint"] or "")


def test_score_raises_metric_unavailable_without_local_model(tmp_path, monkeypatch):
    monkeypatch.setattr(bertscore, "model_dir", lambda local_dir=None: tmp_path / "empty")
    with pytest.raises(bertscore.MetricUnavailable):
        bertscore.score(["c"], ["r"])


def test_score_returns_none_when_all_pairs_empty():
    """全空输入无需加载模型即返回全 None。"""
    assert bertscore.score(["", ""], ["", ""]) == [None, None]


# ------------------------------------------------------------------ 缓存清理
def test_prune_keeps_only_current_model(tmp_path: Path):
    """口径变更（换基座/改 idf）后旧键永远命中不了，留着只会让人以为算过两遍。"""
    p = tmp_path / "c.jsonl"
    bertscore_cache.append_cache(p, [("k1", 0.1, "m-old"), ("k2", 0.2, "m-new")])
    dropped = bertscore_cache.prune(p, keep_model="m-new")
    assert dropped == 1
    assert set(bertscore_cache.load_cache(p)) == {"k2"}
    assert bertscore_cache.stats(p)["by_model"] == {"m-new": 1}


def test_prune_keeps_corrupt_lines_out_but_reports_count(tmp_path: Path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"key":"k1","f1":0.1,"model":"m-new"}\nnot-json\n', encoding="utf-8")
    assert bertscore_cache.prune(p, keep_model="m-new") == 1
    assert set(bertscore_cache.load_cache(p)) == {"k1"}


def test_cache_model_id_includes_idf_and_weight_fingerprint():
    """缓存键必须能区分「同一基座名但权重不同」与「idf 开关不同」，
    否则换了基座或改了口径仍复用旧分数，且不会有任何提示。"""
    ident = bertscore.cache_model_id()
    assert "bert-base-multilingual-cased" in ident
    assert "idf=" in ident
    if bertscore.model_info():                    # 基座已落盘时应有指纹
        assert "nofp" not in ident
    else:
        assert "nofp" in ident


def test_cache_model_id_changes_with_weight_fingerprint(monkeypatch):
    base = {"files": {"model.safetensors": {"sha256": "aaaa" * 16}}}
    monkeypatch.setattr(bertscore, "model_info", lambda: base)
    first = bertscore.cache_model_id()
    monkeypatch.setattr(bertscore, "model_info",
                        lambda: {"files": {"model.safetensors": {"sha256": "bbbb" * 16}}})
    assert bertscore.cache_model_id() != first


def test_cache_model_id_is_stable_for_same_inputs(monkeypatch):
    monkeypatch.setattr(bertscore, "model_info",
                        lambda: {"files": {"model.safetensors": {"sha256": "cccc" * 16}}})
    assert bertscore.cache_model_id() == bertscore.cache_model_id()


@pytest.mark.slow
def test_score_runs_on_local_base():
    """真实打分冒烟：基座未落盘时跳过（离线环境不该因此失败）。"""
    if not bertscore.available().get("ready"):
        pytest.skip("基座未落盘，跳过真实打分")
    vals = bertscore.score(
        ["CVE-2026-12345 是一处远程代码执行漏洞，建议尽快升级。"],
        ["CVE-2026-12345 is a remote code execution vulnerability. Patch immediately."])
    assert len(vals) == 1 and 0.0 < float(vals[0]) <= 1.0
