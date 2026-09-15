"""论文 A 实验管线（回填 not-yet-measured 的可复现实测设施）。

设计约束（与论文 A 数据回填清单一致）：

- 每个写入稿件的数值必须能反查到一次真实运行（run_id 到 run_manifest.json）；
- 未实测的项一律保留 not-yet-measured，禁止估算、禁止占位替代；
- 零侵入：不修改 intelnexus 业务代码，埋点通过包装实现。

典型流程：

    python -m experiments.cli env
    python -m experiments.cli collect
    python -m experiments.cli run smoke
    python -m experiments.cli aggregate
    python -m experiments.cli fill
    python -m experiments.cli verify
"""

__version__ = "0.1.0"
