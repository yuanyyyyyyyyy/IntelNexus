"""显存驻留体检的解析与判定（离线）。"""
from __future__ import annotations

from experiments.harness.local_residency import parse_ollama_ps, parse_processor, verdict


def test_parse_processor_cpu_first_order():
    cpu, gpu = parse_processor("30%/70% CPU/GPU")
    assert cpu == 0.30
    assert gpu == 0.70


def test_parse_processor_gpu_only():
    cpu, gpu = parse_processor("100% GPU")
    assert cpu == 0.0
    assert gpu == 1.0


def test_parse_processor_cpu_only():
    cpu, gpu = parse_processor("100% CPU")
    assert cpu == 1.0
    assert gpu == 0.0


def test_parse_processor_missing_returns_none():
    assert parse_processor(None) == (None, None)
    assert parse_processor("unknown") == (None, None)


def test_verdict_full_ok_requires_high_gpu_share_and_fast():
    assert verdict(0.98, 60.0) == "full-ok"


def test_verdict_degrade_when_cpu_offload():
    assert verdict(0.70, 60.0) == "degrade-required"


def test_verdict_degrade_when_slow_even_if_on_gpu():
    assert verdict(1.0, 200.0) == "degrade-required"


def test_verdict_unknown_without_measurement():
    assert verdict(None, None) == "unknown"
    assert verdict(0.99, None) == "unknown"


def test_parse_ollama_ps_extracts_size_and_processor():
    raw = "\n".join([
        "NAME        ID              SIZE      PROCESSOR          CONTEXT    UNTIL",
        "qwen3:8b    500a1f067a9f    6.0 GB    30%/70% CPU/GPU    4096       4 minutes from now",
    ])
    info = parse_ollama_ps(raw, "qwen3:8b")
    assert info["found"] is True
    assert info["size_gb"] == 6.0
    assert info["gpu_share"] == 0.70
    assert info["context"] == 4096


def test_parse_ollama_ps_missing_model():
    info = parse_ollama_ps("NAME  ID  SIZE  PROCESSOR", "qwen3:8b")
    assert info["found"] is False
    assert info["gpu_share"] is None
