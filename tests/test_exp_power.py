"""推理功耗实测的纯函数测试（离线，不触发真实采样）。

口径要点：P_avg 只在可测部件上求和，缺任一项时如实降级，不得用
估算值补齐；活跃样本过滤用于剔除生成前后的静息采样。
"""
from __future__ import annotations

import pytest

from experiments.harness import power_probe


def test_summarize_sums_cpu_and_gpu_means():
    out = power_probe.summarize([10.0, 20.0], [30.0, 40.0])
    assert out["cpu_pkg_w"]["mean"] == pytest.approx(15.0)
    assert out["gpu_w"]["mean"] == pytest.approx(35.0)
    assert out["p_avg_watt"] == pytest.approx(50.0)


def test_summarize_degrades_when_gpu_missing():
    """缺 GPU 读数时只用 CPU 实测值，不做任何估计补齐。"""
    out = power_probe.summarize([18.0], [])
    assert out["gpu_w"] is None
    assert out["p_avg_watt"] == pytest.approx(18.0)


def test_summarize_empty_inputs_returns_none():
    out = power_probe.summarize([], [])
    assert out["cpu_pkg_w"] is None and out["p_avg_watt"] is None


@pytest.mark.parametrize("gpu_util,expected", [
    (0.0, True),        # 两个读数都在 → 计入
    (40.0, True),
])
def test_activate_filter_counts_samples_with_readings(gpu_util, expected):
    assert power_probe._activate_filter((0.0, 20.0, 21.0, gpu_util)) is expected


def test_activate_filter_rejects_partial_samples():
    assert power_probe._activate_filter((0.0, None, None, 0.0)) is False
    assert power_probe._activate_filter((0.0, 20.0, None, 0.0)) is False


def test_rapl_counter_is_cpu_package_power():
    assert "Energy Meter" in power_probe.RAPL_COUNTER
    assert power_probe.CPU_PKG_MW_TO_W == 1000.0
