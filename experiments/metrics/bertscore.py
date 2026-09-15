"""BERTScore（跨语言多语言基座）封装。

纪律：依赖或模型不可用时**显式失败**，对应指标整列保留 not-yet-measured。
绝不用"向量余弦相似度"之类的近似冒充 BERTScore —— 那是另一回事。

口径（改口径必须同步论文表注与 PROTOCOL）：

- **基座**：``bert-base-multilingual-cased``。生成物为中文、参考摘要多为英文，
  必须用跨语言基座；中文单语基座无法处理英文参考摘要。
- **``idf=False``**：bert-score 默认按**本次调用批次内的参考文本**现算 IDF。
  若每个配置各调一次，IDF 会随批次变化，导致跨配置不可比；关闭后所有配置
  在同一口径下比较。
- **``rescale_with_baseline=False``**：官方基线重标定只对登记过的单语模型成立，
  多语言基座不适用；显式关闭以免静默改变量纲。
- **512 token 截断**：模型内部按 ``max_length`` 截断，长简报只在被截断的部分上
  比较，属该指标的固有限制 —— 论文须在表注说明，并以"首板块口径"作稳健性对照。

依赖与模型的落盘方式见 ``ensure_local_model``：模型被固定下载到
``experiments/data/<model>/``，运行时以 ``local_files_only`` 加载，保证离线可复现。
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from experiments.common import has_module, sha256_file, utc_now_iso, write_json
from experiments.logging_utils import get_logger

logger = get_logger("exp.bertscore")

# 生成物为中文、参考摘要多为英文，故使用多语言基座（跨语言语义相似度）。
# 中文单语基座（bert-base-chinese）无法处理英文参考摘要，会导致该指标失效。
DEFAULT_MODEL = "bert-base-multilingual-cased"
# 国内访问 HuggingFace 需镜像；不强制设置，由使用者按需配置
HF_MIRROR_ENV = "HF_ENDPOINT"
DEFAULT_MIRROR = "https://hf-mirror.com"
# 下载源（按顺序尝试，均为公开只读镜像）。{model} 与 {file} 由代码填充。
# 实测：huggingface.co 在国内不可达；hf-mirror 可用但时快时慢；
# ModelScope 稳定且快，故置于首位。多源 + 断点续传是本模块的固有设计，
# 不依赖 huggingface_hub 的版本行为（hub 1.x 的端点解析曾导致下载失败）。
DEFAULT_SOURCES = [
    "https://modelscope.cn/api/v1/models/AI-ModelScope/{model}/repo?Revision=master&FilePath={file}",
    "https://hf-mirror.com/{model}/resolve/main/{file}",
]
# 必须到位的文件（缺任一即无法加载）
REQUIRED_FILES = ["config.json", "vocab.txt", "tokenizer_config.json"]
# 可选文件：某些仓库没有（例如 ModelScope 上没有 special_tokens_map.json），
# 缺失不影响加载，但会试源；重试次数取 1，避免在确定性 404 上白等
OPTIONAL_FILES = ["special_tokens_map.json", "tokenizer.json"]
# 权重二选一（safetensors 优先）
WEIGHT_FILES = ["model.safetensors", "pytorch_model.bin"]
DOWNLOAD_TIMEOUT = 120.0
CHUNK_BYTES = 1 << 20
PROGRESS_EVERY = 32 << 20
# BERT 的位置编码上限；同时是 bert-score 的截断长度（论文表注须写明）
MAX_TOKENS = 512
# 这些状态码是确定性的（资源不存在/无权限），重试没有意义
PERMANENT_HTTP_CODES = {400, 401, 403, 404, 410}
# 配置缓存（避免每次调用都读 YAML）
_CFG: Optional[Dict[str, Any]] = None


class MetricUnavailable(RuntimeError):
    """指标不可用（依赖缺失、模型下载失败等）。"""


# ------------------------------------------------------------------ 配置
def config() -> Dict[str, Any]:
    """读取 ``experiment.yaml`` 的 ``evaluation.bertscore`` 段（带默认值）。"""
    global _CFG
    if _CFG is None:
        try:
            from experiments import config_loader

            _CFG = dict(((config_loader.experiment_config().get("evaluation") or {})
                         .get("bertscore") or {}))
        except Exception:  # noqa: BLE001 - 配置缺失时用默认值
            _CFG = {}
    merged = {
        "model": DEFAULT_MODEL,
        "local_dir": f"data/{DEFAULT_MODEL}",
        "mirror": DEFAULT_MIRROR,
        "sources": list(DEFAULT_SOURCES),
        "batch_size": 16,
        "idf": False,
        "rescale_with_baseline": False,
        "max_length": 512,
        "cache": "reports/bertscore_cache.jsonl",
    }
    merged.update({k: v for k, v in (_CFG or {}).items() if v is not None})
    return merged


def _exp_path(rel: str | Path) -> Path:
    """把配置里相对 ``experiments/`` 的路径解析成绝对路径。"""
    from experiments.paths import EXP_DIR

    p = Path(rel)
    return p if p.is_absolute() else (EXP_DIR / p)


def model_dir(local_dir: Optional[str | Path] = None) -> Path:
    """基座的固定落盘目录（绝对路径）。"""
    return _exp_path(local_dir or config()["local_dir"])


def cache_path(path: Optional[str | Path] = None) -> Path:
    """逐条 F1 缓存文件的实际路径（配置里是相对 experiments/ 的路径）。"""
    return _exp_path(path or config()["cache"])


def _is_complete(d: Path) -> bool:
    """目录里是否已有可离线加载的完整基座。"""
    if not (d / "config.json").exists():
        return False
    return any((d / f).exists() for f in ("model.safetensors", "pytorch_model.bin"))


def _ensure_tokenizer_limits(d: Path) -> None:
    """补齐 ``tokenizer_config.json`` 的 ``model_max_length``。

    实测缺陷：``bert-base-multilingual-cased`` 的 ``tokenizer_config.json`` 只有
    ``{"do_lower_case": false}``，没有 ``model_max_length``。transformers 5.x 会
    退回一个超大哨兵值，而该值最终被传给 Rust 分词器的 ``enable_truncation``，
    触发 ``OverflowError: int too big to convert``，使 BERTScore 完全算不出来。

    BERT 的真实位置编码上限就是 512，因此写死 512 既正确又是该指标的官方口径
    （bert-score 也按 512 截断）。幂等：已是合理值时不改动。
    """
    import json

    cfg_path = d / "tokenizer_config.json"
    cfg: Dict[str, Any] = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 - 损坏则重建
            cfg = {}
    cur = cfg.get("model_max_length")
    if isinstance(cur, int) and 0 < cur <= MAX_TOKENS:
        return
    cfg["model_max_length"] = MAX_TOKENS
    cfg.setdefault("do_lower_case", False)
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("已补齐 %s 的 model_max_length=%d（原值 %r）", cfg_path.name, MAX_TOKENS, cur)


# ------------------------------------------------------------------ 下载 / 探测
def _fetch(url: str, dest: Path, retries: int = 3) -> int:
    """流式下载单个文件，支持断点续传；返回最终字节数。

    续传依据同目录下的 ``<name>.part``：中断后重跑不会从零开始（大文件尤其重要）。
    确定性的 404/403 不重试——重试只会白等，尤其是镜像超时较长的场合。
    """
    part = dest.with_suffix(dest.suffix + ".part")
    last: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        offset = part.stat().st_size if part.exists() else 0
        req = urllib.request.Request(url)
        if offset:
            req.add_header("Range", f"bytes={offset}-")
        try:
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
                total = offset + int(resp.headers.get("Content-Length") or 0)
                mode = "ab" if (offset and resp.status == 206) else "wb"
                if mode == "wb":
                    offset = 0
                got = offset
                next_log = got + PROGRESS_EVERY
                with open(part, mode) as f:
                    while True:
                        chunk = resp.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if got >= next_log:
                            logger.info("  %s %.0f%%（%d MB）", dest.name,
                                        (got / total * 100) if total else 0, got >> 20)
                            next_log = got + PROGRESS_EVERY
            part.replace(dest)
            return dest.stat().st_size
        except urllib.error.HTTPError as e:
            last = e
            logger.debug("  %s HTTP %s（确定性失败，不再重试）", dest.name, e.code)
            if e.code in PERMANENT_HTTP_CODES:
                break
        except Exception as e:  # noqa: BLE001
            last = e
            logger.warning("  %s 第 %d/%d 次下载失败（已存 %d 字节）: %s: %s",
                           dest.name, attempt, retries,
                           part.stat().st_size if part.exists() else 0,
                           type(e).__name__, str(e)[:100])
    raise MetricUnavailable(f"{type(last).__name__}: {str(last)[:120]}")


def _download_model(model: str, d: Path, sources: Sequence[str]) -> Dict[str, str]:
    """按源逐个尝试下载基座文件；返回 {文件名: 使用的源}。"""
    d.mkdir(parents=True, exist_ok=True)
    used: Dict[str, str] = {}
    files = [(f, 3) for f in REQUIRED_FILES] + [(f, 1) for f in OPTIONAL_FILES] \
        + [(f, 3) for f in WEIGHT_FILES]
    for fname, retries in files:
        dest = d / fname
        if dest.exists() and dest.stat().st_size > 0:
            used[fname] = "cached"
            continue
        if fname in WEIGHT_FILES and any((d / w).exists() for w in WEIGHT_FILES):
            continue                       # 权重二选一，已有一个即可
        errors: List[str] = []
        for tpl in sources:
            url = str(tpl).format(model=model, file=fname)
            try:
                size = _fetch(url, dest, retries=retries)
                used[fname] = tpl.split("/")[2]
                logger.info("  %s 完成（%.1f MB，源 %s）", fname, size / (1 << 20), used[fname])
                break
            except MetricUnavailable as e:
                errors.append(f"{tpl.split('/')[2]}: {e}")
        else:
            if fname in REQUIRED_FILES or fname in WEIGHT_FILES:
                raise MetricUnavailable(f"{fname} 全部源均失败（{'；'.join(errors)}）")
            logger.warning("  跳过可选文件 %s（各源均失败）", fname)
    return used


def ensure_local_model(model: Optional[str] = None, local_dir: Optional[str | Path] = None,
                       sources: Optional[Sequence[str]] = None) -> Path:
    """确保基座已固定下载到本地目录，返回该目录。

    只在目录不完整时下载。下载走多源直连 + 断点续传，不经 huggingface_hub
    （hub 1.x 的端点解析在实测中导致过下载失败；直连更可控、可复核）。
    """
    cfg = config()
    model = model or cfg["model"]
    d = model_dir(local_dir)
    if _is_complete(d):
        # 已有旧版下载（缺 model_max_length）时顺手修好，避免必须重新下载
        _ensure_tokenizer_limits(d)
        logger.info("基座已就绪，跳过下载: %s", d)
        return d

    # 供 transformers 在极端情况下（未固定落盘时的兜底）使用
    os.environ.setdefault(HF_MIRROR_ENV, str(cfg["mirror"]))
    srcs = list(sources or cfg["sources"])
    logger.info("下载基座 %s → %s（%d 个源，按序尝试）", model, d, len(srcs))
    used = _download_model(model, d, srcs)
    if not _is_complete(d):
        raise MetricUnavailable(f"下载后仍不完整: {d}")

    files = {}
    for f in sorted(d.rglob("*")):
        if f.is_file() and f.name != "model_info.json":
            files[f.relative_to(d).as_posix()] = {
                "bytes": f.stat().st_size, "sha256": str(sha256_file(f))[:32],
            }
    info = {
        "model": model,
        "downloaded_at": utc_now_iso(),
        "sources_used": used,
        "sources_tried": srcs,
        "dir": str(d),
        "files": files,
        "note": ("运行时以 local_files_only 加载，保证离线可复现；"
                 "口径见 metrics/bertscore.py 的模块 docstring"),
    }
    try:
        import transformers  # type: ignore

        info["transformers_version"] = transformers.__version__
    except Exception:  # noqa: BLE001
        pass
    write_json(d / "model_info.json", info)
    _ensure_tokenizer_limits(d)
    logger.info("基座已落盘：%s（%d 个文件）", d, len(files))
    return d


def available(model: Optional[str] = None) -> Dict[str, Any]:
    """检查 bert-score 与基座是否可用。只探测，不下载。"""
    cfg = config()
    model = model or cfg["model"]
    d = model_dir()
    info: Dict[str, Any] = {
        "module": has_module("bert_score"),
        "model": model,
        "local_dir": str(d),
        "local_ready": _is_complete(d),
        "hf_endpoint": os.getenv(HF_MIRROR_ENV),
        "ready": False,
        "hint": None,
    }
    if not info["module"]:
        info["hint"] = "pip install bert-score（国内可先设置 HF_ENDPOINT=https://hf-mirror.com）"
        return info
    if not info["local_ready"]:
        info["hint"] = f"基座未固定落盘：请先运行 `python -m experiments.cli bertscore-fetch`（目标目录 {d}）"
        return info
    try:
        from transformers import AutoTokenizer  # type: ignore

        # use_fast=False：与打分路径一致（用 vocab.txt），避免 tokenizer.json
        # 在 transformers 5.x 下触发 pre_tokenizer 正则告警
        AutoTokenizer.from_pretrained(str(d), local_files_only=True, use_fast=False)
        info["ready"] = True
        info["num_layers"] = _layers_for(model)
    except Exception as e:  # noqa: BLE001
        info["hint"] = f"本地基座加载失败（{type(e).__name__}）：{str(e)[:120]}"
    return info


def _layers_for(model: str) -> int:
    """bert-score 官方注册表里该基座使用的层号（未登记时按 BERT-base 约定取 9）。"""
    try:
        from bert_score.utils import model2layers  # type: ignore

        return int(model2layers.get(model, 9))
    except Exception:  # noqa: BLE001
        return 9


def score_hash() -> Optional[str]:
    """bert-score 的配置指纹（模型/层号/idf/重标定），供论文注明评测口径。"""
    cfg = config()
    try:
        from bert_score.utils import get_hash  # type: ignore

        return str(get_hash(str(model_dir()), _layers_for(cfg["model"]),
                            bool(cfg["idf"]), bool(cfg["rescale_with_baseline"])))
    except Exception:  # noqa: BLE001
        return None


def model_info() -> Optional[Dict[str, Any]]:
    """读取基座的 model_info.json（不存在返回 None）。"""
    from experiments.common import read_json

    p = model_dir() / "model_info.json"
    return read_json(p) if p.exists() else None


def weight_fingerprint(length: int = 12) -> str:
    """权重文件指纹：取 model_info.json 里权重 sha256 的前若干位。

    没有指纹时返回 ``"nofp"`` —— 此时仍可用，只是无法察觉"同名基座换了权重"。
    """
    info = model_info() or {}
    files = info.get("files") or {}
    for name in WEIGHT_FILES:
        sha = (files.get(name) or {}).get("sha256")
        if sha:
            return str(sha)[:length]
    return "nofp"


def cache_model_id(model: Optional[str] = None) -> str:
    """逐条缓存键里使用的模型标识：基座名 + idf 开关 + 权重指纹。

    只写基座名是不够的：换一版权重、或把 ``idf`` 从 false 改成 true，都会改变
    BERTScore 的数值口径，但缓存键不变 —— 那样会静默复用旧分数，且没有任何提示。
    """
    cfg = config()
    return f"{model or cfg['model']}@idf={bool(cfg['idf'])}@{weight_fingerprint()}"


# ------------------------------------------------------------------ 打分
def score(candidates: Sequence[str], references: Sequence[str],
          model: Optional[str] = None, batch_size: Optional[int] = None,
          lang: Optional[str] = None, local_files_only: bool = True,
          idf: Optional[bool] = None,
          rescale_with_baseline: Optional[bool] = None,
          nthreads: Optional[int] = None) -> List[Optional[float]]:
    """返回逐条 BERTScore F1；不可用抛 MetricUnavailable。

    ``lang=None`` 表示使用多语言基座（不指定单语分词/词表行为）。
    """
    if not has_module("bert_score"):
        raise MetricUnavailable("未安装 bert-score，无法计算 BERTScore")
    try:
        import bert_score  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise MetricUnavailable(f"导入 bert-score 失败: {e}") from e

    cfg = config()
    model = model or cfg["model"]
    batch_size = int(batch_size or cfg["batch_size"])
    use_idf = bool(cfg["idf"] if idf is None else idf)
    rescale = bool(cfg["rescale_with_baseline"] if rescale_with_baseline is None else rescale_with_baseline)
    if nthreads is None:
        nthreads = max(1, min(os.cpu_count() or 4, 8))

    pairs = [(c, r) for c, r in zip(candidates, references) if c and r]
    if not pairs:
        return [None] * len(candidates)

    if local_files_only:
        d = model_dir()
        if not _is_complete(d):
            raise MetricUnavailable(
                f"基座未固定落盘（{d}）：请先运行 `python -m experiments.cli bertscore-fetch`")
        _ensure_tokenizer_limits(d)          # 修复旧版下载缺 model_max_length 的情况
        model_path = str(d)
        # bert-score 用一张硬编码的「模型名 → 取第几层」注册表（utils.model2layers）
        # 来选层；直接传本地路径会 KeyError。把本地目录注册为同名模型的别名，
        # 取层数与官方对 bert-base-multilingual-cased 的约定一致（第 9 层），
        # 这样既离线加载，又不改变该指标的官方口径。
        try:
            from bert_score.utils import model2layers  # type: ignore

            model2layers.setdefault(model_path, model2layers.get(model, 9))
        except Exception as e:  # noqa: BLE001
            raise MetricUnavailable(f"注册本地基座失败: {type(e).__name__}: {e}") from e
    else:
        model_path = model

    try:
        _, _, f1 = bert_score.score(
            [p[0] for p in pairs], [p[1] for p in pairs],
            lang=lang, model_type=model_path, batch_size=batch_size, verbose=False,
            idf=use_idf, rescale_with_baseline=rescale, nthreads=int(nthreads),
            # 与 local 加载一致：用 vocab.txt 的慢分词器，避免 tokenizer.json
            # 在 transformers 5.x 下触发 pre_tokenizer 正则告警
            use_fast_tokenizer=False,
        )
    except Exception as e:  # noqa: BLE001
        raise MetricUnavailable(f"BERTScore 计算失败: {type(e).__name__}: {e}") from e

    vals: List[Optional[float]] = []
    it = iter([float(x) for x in f1])
    for c, r in zip(candidates, references):
        vals.append(next(it) if (c and r) else None)
    return vals
