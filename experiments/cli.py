"""论文 A 实验管线命令行入口。

用法::

    python -m experiments.cli env
    python -m experiments.cli collect --limit 300
    python -m experiments.cli run smoke|pilot|full
    python -m experiments.cli aggregate
    python -m experiments.cli fill --content-dir <稿件目录>
    python -m experiments.cli verify
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from experiments.logging_utils import get_logger
from experiments.paths import ensure_dirs

logger = get_logger("exp.cli")


@click.group()
@click.version_option("0.1.0", prog_name="experiments")
def cli() -> None:
    """论文 A 实测管线：回填 not-yet-measured 的每一步都可复跑。"""


@cli.command()
@click.option("--out", default=None, help="报告输出路径")
@click.option("--no-network", is_flag=True, help="跳过云端端点与信源探测")
def env(out: str | None, no_network: bool) -> None:
    """环境探测：GPU / Ollama / 云端端点 / 抓包工具 / 信源可达性。"""
    from experiments.harness.env_probe import main as env_main

    ensure_dirs()
    env_main(out=out, with_network=not no_network)


@cli.command()
@click.option("--limit", default=300, show_default=True, help="每个信源最多采集条数")
@click.option("--out", default=None, help="快照输出目录")
def collect(limit: int, out: str | None) -> None:
    """采集固定数据快照（robots + 限速 + 哈希存证）。"""
    from experiments.collect.build_dataset import main as collect_main

    ensure_dirs()
    collect_main(limit=limit, out=out)


@cli.command("run")
@click.argument("stage", type=click.Choice(["smoke", "pilot", "full"]), default="smoke")
@click.option("--configs", default=None, help="逗号分隔的配置 id（默认全部）")
@click.option("--repeats", type=int, default=None, help="重复次数（默认取 experiment.yaml）")
@click.option("--sample-n", type=int, default=None, help="样本条数（默认取 experiment.yaml）")
@click.option("--dry-run", is_flag=True, help="只校验配置可用性，不实际生成")
def run(stage: str, configs: str | None, repeats: int | None, sample_n: int | None, dry_run: bool) -> None:
    """执行一个实验阶段（smoke / pilot / full）。"""
    from experiments.harness.runner import main as run_main

    ensure_dirs()
    run_main(stage=stage, configs=configs.split(",") if configs else None,
             repeats=repeats, sample_n=sample_n, dry_run=dry_run)


@cli.command("aggregate")
@click.option("--stage", default=None, help="只汇总某阶段（smoke/pilot/full）")
@click.option("--configs", default=None, help="逗号分隔的配置 id")
@click.option("--no-bertscore", is_flag=True, help="跳过 BERTScore")
@click.option("--gold-csv", default=None, help="人工校对的实体金标 CSV")
@click.option("--human-csv", default=None, help="已填写的盲评表 CSV")
def aggregate(stage: str | None, configs: str | None, no_bertscore: bool,
              gold_csv: str | None, human_csv: str | None) -> None:
    """汇总所有运行记录 → reports/aggregate.json。"""
    from experiments.metrics.aggregate import main as agg_main

    ensure_dirs()
    agg_main(stage=stage, configs=configs, no_bertscore=no_bertscore,
             gold_csv=gold_csv, human_csv=human_csv)


@cli.command("privacy")
@click.option("--configs", default=None, help="逗号分隔的配置 id")
@click.option("--sample-n", type=int, default=10, show_default=True)
def privacy(configs: str | None, sample_n: int) -> None:
    """出域字节与外联目的地测量（计量代理）。"""
    from experiments.privacy.capture import measure_config

    ensure_dirs()
    from experiments import config_loader

    exp = config_loader.experiment_config()
    ids = configs.split(",") if configs else [str(c["id"]) for c in exp.get("configs", [])
                                              if c.get("backend") != "baseline"]
    for cid in ids:
        try:
            r = measure_config(cid, sample_n=sample_n)
            print(f"  {cid:<18} 出域 {r.get('bytes_out')} 字节，目的地 {r.get('destinations')}")
        except Exception as e:  # noqa: BLE001
            print(f"  {cid:<18} 测量失败: {type(e).__name__}: {e}")


@cli.command("token-recount")
@click.option("--keep", is_flag=True, help="保留已有结果，不强制重算")
def token_recount(keep: bool) -> None:
    """云端 token 用量重算（用官方分词器，不重新调用 API）。"""
    from experiments.cost.token_recount import main as recount_main

    ensure_dirs()
    recount_main(force=not keep)


@cli.command("bertscore-fetch")
def bertscore_fetch() -> None:
    """把 BERTScore 的多语言基座固定下载到本地（走镜像，只需一次）。"""
    from experiments.metrics import bertscore

    ensure_dirs()
    cfg = bertscore.config()
    print(f"基座: {cfg['model']}　镜像: {cfg['mirror']}")
    d = bertscore.ensure_local_model()
    print(f"已落盘: {d}")
    info = bertscore.model_info() or {}
    print(f"下载时间: {info.get('downloaded_at')}　文件数: {len(info.get('files') or {})}")
    print(f"可用性: {bertscore.available().get('ready')}")


@cli.command("bertscore-check")
def bertscore_check() -> None:
    """只探测 BERTScore 依赖与基座是否就绪（不下载、不计算）。"""
    import json

    from experiments.metrics import bertscore

    print(json.dumps(bertscore.available(), ensure_ascii=False, indent=1))


@cli.command("token-calib")
@click.option("--n", type=int, default=3, show_default=True, help="每个配置校准条数")
@click.option("--configs", default=None, help="逗号分隔的配置 id")
def token_calib(n: int, configs: str | None) -> None:
    """校准 token 计数口径（**同一次调用内**：API usage vs 该次提示词计数）。

    需云端密钥，会发起少量真实请求。输出的偏差才是分词器口径偏差；
    ``reports/token_recount.json`` 里的 ``calibration_cross_call`` 是历史
    跨调用观测，只用于给输入侧定界，不能当作口径误差。
    """
    from experiments.cost.token_recount import calibrate

    ensure_dirs()
    try:
        out = calibrate(n=n, configs=configs.split(",") if configs else None)
    except RuntimeError as e:
        # 缺密钥是最常见的失败原因：给出可操作的指引，而不是抛一整页堆栈
        print(f"！校准未执行：{e}")
        print("  请在 PowerShell 里先设置密钥再重试：")
        print('    $env:DASHSCOPE_API_KEY="sk-你的百炼密钥"')
        print("    .venv\\Scripts\\python.exe -m experiments.cli token-calib --n 3")
        print("  未校准时论文须写明：token 用量为官方分词器重算、未做 API 校验。")
        return
    print(f"同调用口径（comparison_type={out.get('comparison_type')}）："
          "in = 本次 API usage → 本次提示词计数；out = 本次 API usage → 本次文本计数")
    for cid, v in (out.get("configs") or {}).items():
        print(f"  {cid:<18} {v.get('model')}  最大绝对偏差 {v.get('max_abs_dev_pct')}%")
        for r in v.get("rows") or []:
            print(f"      {r['sample_id'][:34]:<34} in {r['api_tokens_in']}→{r['prompt_tokens_in']}"
                  f"  out {r['api_tokens_out']}→{r['recount_tokens_out']}"
                  f"  calls={r.get('prompt_calls')} render={r.get('prompt_render')}")


@cli.command("scan")
def scan() -> None:
    """本地明文残留扫描（日志/缓存/临时文件）。"""
    from experiments import config_loader
    from experiments.privacy.scan import scan_targets

    ensure_dirs()
    from experiments.paths import ROOT

    cfg = config_loader.experiment_config()
    targets = ((cfg.get("privacy", {}) or {}).get("scan_targets")) or ["logs"]
    res = scan_targets(list(targets), ROOT)
    print(f"明文残留命中 {res['total_hits']} 条：{res['by_type']}")


@cli.command("cost")
@click.option("--latency", type=float, default=None,
              help="本地单条耗时（秒）；缺省取 aggregate 中本地组实测均值")
def cost(latency: float | None) -> None:
    """成本折算与敏感性分析，并归档 reports/cost_sensitivity.json。"""
    from experiments.cost.cost_model import SENSITIVITY_PATH, sensitivity_report

    s = sensitivity_report(latency_s=latency)
    print(f"本地单条折算: {s.get('base_cost')}（按 {s.get('latency_s')} s）  云端单条: {s.get('cloud_cost')}")
    for r in s.get("rows") or []:
        print(f"  {r['param']:<20} {r['low']} -> {r['cost_low']}   {r['high']} -> {r['cost_high']}")
    print(f"已写入 {SENSITIVITY_PATH}")
    if not s.get("available"):
        print("  ! pricing.yaml 的 local 段未填写完整，表5 相关格子保持 not-yet-measured")


@cli.command("scan-slots")
@click.option("--content-dir", default=None, help="稿件 content 目录")
def scan_slots(content_dir: str | None) -> None:
    """扫描稿件中的 not-yet-measured 占位，生成 slots.json。"""
    from experiments.fill.scan_slots import scan

    ensure_dirs()
    scan(Path(content_dir) if content_dir else None)


@cli.command("gen-mapping")
def gen_mapping_cmd() -> None:
    """按表结构生成 slot → 指标的绑定 mapping.yaml。"""
    from experiments.fill.gen_mapping import generate
    from experiments.paths import SLOTS
    from experiments.common import read_json

    ensure_dirs()
    generate(read_json(SLOTS))


@cli.command("fill")
@click.option("--content-dir", default=None)
@click.option("--out-dir", default=None, help="输出目录（默认 <content-dir>/../content_filled）")
@click.option("--mapping", default=None)
@click.option("--require-zero", is_flag=True, help="要求输出中占位为 0，否则提示")
def fill(content_dir: str | None, out_dir: str | None, mapping: str | None, require_zero: bool) -> None:
    """把实测数据回填到稿件副本（不覆盖原稿）。"""
    from experiments.fill.apply import main as fill_main

    ensure_dirs()
    fill_main(content_dir=content_dir, out_dir=out_dir, mapping=mapping, require_zero=require_zero)


@cli.command("verify")
def verify_cmd() -> None:
    """校验每个已填数值可反查到 run 与 manifest。"""
    from experiments.fill.verify import verify

    ensure_dirs()
    verify()


@cli.command("figure")
def figure_cmd() -> None:
    """用实测数据重绘图3（质量—成本帕累托前沿）。"""
    from experiments.figures.fig3_pareto import draw

    ensure_dirs()
    p = draw()
    print(f"图3: {p or '数据不足，未生成'}")


@cli.command("human-sheet")
@click.option("--out", default="experiments/reports/human_eval_sheet.csv", show_default=True)
@click.option("--per-config", type=int, default=30, help="每个配置抽取的样本数")
def human_sheet(out: str, per_config: int) -> None:
    """生成人工盲评表（配置匿名化）。"""
    import glob
    import json
    from pathlib import Path

    from experiments.metrics.human_eval import make_sheet

    ensure_dirs()
    rows = []
    for rec in sorted(glob.glob("experiments/runs/*/records.jsonl")):
        rdir = Path(rec).parent
        for line in open(rec, encoding="utf-8"):
            r = json.loads(line)
            if r.get("repeat") != 1 or not r.get("output_path"):
                continue
            rows.append({"sample_id": r["sample_id"], "config": r["config"],
                         "output_path": str(rdir / r["output_path"]), "repeat": r["repeat"]})
    picked: Dict[str, int] = {}
    slim = []
    for r in rows:
        c = r["config"]
        if picked.get(c, 0) >= per_config:
            continue
        picked[c] = picked.get(c, 0) + 1
        slim.append(r)
    make_sheet(slim, Path(out))
    print(f"盲评表: {out}（{len(slim)} 条）")


@cli.command("results")
@click.option("--out", default=None, help="输出 markdown 路径")
def results(out: str | None) -> None:
    """生成人读的结果汇总（含 run_id 反查表）。"""
    from experiments.fill.results_doc import build

    ensure_dirs()
    build(Path(out) if out else None)


@cli.command("probe-chat")
@click.option("--full-input", is_flag=True, help="额外用真实输入长度再测一次")
@click.option("--stream", is_flag=True, help="用流式请求并测首块延迟与最大静默间隔")
@click.option("--timeout", type=int, default=None, help="覆盖请求超时（秒）")
@click.option("--max-tokens", type=int, default=None, help="限制输出 token 数")
@click.option("--model", default=None, help="只测指定模型")
def probe_chat(full_input: bool, stream: bool, timeout: int | None,
               max_tokens: int | None, model: str | None) -> None:
    """云端最小请求探针：定位超时是网络/代理、生成过长还是流式静默。"""
    from experiments.harness.probe_chat import run as probe_run

    ensure_dirs()
    probe_run(full_input=full_input, timeout=timeout, max_tokens=max_tokens,
              model=model, stream=stream)


@cli.command("residency")
@click.option("--config", "config_id", default="qwen3:8b", show_default=True, help="本地配置 id")
@click.option("--ctx", "ctx_variants", default=None, help="逗号分隔的 num_ctx 变体，如 4096,2048")
@click.option("--items", "n_items", type=int, default=2, show_default=True, help="每个变体跑几条")
def residency(config_id: str, ctx_variants: str | None, n_items: int) -> None:
    """本地显存驻留体检：判断 7–8B 能否全 GPU 驻留并给出规模判定。"""
    from experiments.harness.local_residency import check_model

    ensure_dirs()
    variants = [int(x) for x in ctx_variants.split(",")] if ctx_variants else None
    check_model(config_id=config_id, ctx_variants=variants, n_items=n_items)


@cli.command("power-probe")
@click.option("--config", "config_id", default="qwen3:8b", show_default=True, help="本地配置 id")
def power_probe(config_id: str) -> None:
    """在受控负载下实测推理功耗（CPU 封装 + GPU），作为式(1) 的 P_avg 依据。"""
    from experiments.harness.power_probe import main as power_main

    ensure_dirs()
    power_main(config_id)


@cli.command("probe-sources")
@click.option("--limit", default=1, show_default=True, help="每个信源的探测请求条数")
@click.option("--out", default=None, help="探测结果输出路径")
def probe_sources(limit: int, out: str | None) -> None:
    """信源可达性探测（只看连通性，不采集数据）。"""
    from experiments.collect.probe_sources import main as probe_main

    ensure_dirs()
    probe_main(limit=limit, out=out)


def main() -> int:
    try:
        cli(standalone_mode=True)
        return 0
    except SystemExit as e:  # click 正常退出
        return int(e.code or 0)


if __name__ == "__main__":
    sys.exit(main())
