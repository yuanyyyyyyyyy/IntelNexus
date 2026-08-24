import threading
import os

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

_shared_model = None
_model_load_lock = threading.Lock()
# 模型加载超时（秒）：超过则本次搜索降级，避免首次使用长时间挂起。
# 实测：import sentence_transformers ≈14s + 本地模型构造 ≈2.5s，冷启动合计
# ~17s——15s 窗口会让「本地缓存直载」也偶发超时降级，故放宽到 30s。
# 首次下载（约470MB权重）超过该窗口时本次降级，但下载线程继续断点续传，
# 后续搜索即可在窗口内完成加载（自愈设计）。
_MODEL_LOAD_TIMEOUT = 30

# sentence-transformer 开关：默认**启用**。历史默认 true 曾让语义排序/弱相关过滤
# （relevance.py 全链）在所有默认安装下静默失效。国内网络由 ModelScope 离线
# 下载兜底；确需关闭时显式设 DISABLE_SENTENCE_TRANSFORMER=true。
DISABLE_SENTENCE_TRANSFORMER = os.getenv("DISABLE_SENTENCE_TRANSFORMER", "false").lower() == "true"

# 锚定仓库根目录（不依赖进程 cwd）
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 本地模型缓存目录：一旦就绪（.complete 标记），后续全部纯离线加载。
# 选型 paraphrase-multilingual-MiniLM-L12-v2：本项目查询/语料中英混合，
# 实测中文查询「九江」下它把相关条目排前、英文科技噪声降权；
# 英文单语的 all-MiniLM-L6-v2 对同一查询打分近乎噪声（0.819 给无关 CVE 新闻）。
_LOCAL_MODEL_DIR = os.path.join(_REPO_ROOT, "data", "models", "para-multi-minilm")

# ModelScope（阿里魔搭）镜像仓库。选型记录（2026-08 实测）：hf-mirror.com 的
# DNS 在本机所在网络被污染——解析到无关服务器，其证书 CN 为裸 IP，任何 TLS
# 校验策略都过不去；ModelScope 走阿里 CDN，无污染且稳定。
_MODELSCOPE_REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_MODEL_BASE_FILES = (
    "config.json",
    "modules.json",
    "1_Pooling/config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)

# 下载单飞锁：15s 窗口超时后的重试线程不得并发截断彼此的下载进度
_download_lock = threading.Lock()


def _hf_reachable() -> bool:
    """huggingface.co 主站能否 2s 内直连可达（海外/代理用户走官方路径）。"""
    import requests as _requests
    try:
        _requests.head("https://huggingface.co", timeout=2,
                       proxies={"http": None, "https": None})
        return True
    except Exception:
        return False


def _ensure_local_model_from_modelscope() -> str:
    """从 ModelScope 下载模型到本地目录（逐文件断点续传），返回目录路径。

    任一文件失败即抛异常由调用方降级；已完成文件在重试时跳过，
    半成品 .part 按 Range 续传不重来——「首次搜索降级 + 后台继续下载 +
    下次搜索恢复」是自愈过程。全局单飞锁：并发调用只允许一个下载者，
    避免 15s 窗口超时后的重试线程互相截断对方的进度。
    """
    import requests

    marker = os.path.join(_LOCAL_MODEL_DIR, ".complete")
    if os.path.exists(marker):
        return _LOCAL_MODEL_DIR

    with _download_lock:
        # 双检：等锁期间可能已被前一个持有者完成
        if os.path.exists(marker):
            return _LOCAL_MODEL_DIR

        base = f"https://www.modelscope.cn/{_MODELSCOPE_REPO}/resolve/master/"
        # 权重优先 safetensors（无 pickle 风险）；镜像缺失该文件则回退 pytorch 权重
        weights = "model.safetensors"
        session = requests.Session()
        session.trust_env = False  # 直连：绕过环境变量与系统注册表代理
        try:
            head = session.head(base + weights, timeout=8)
            if head.status_code >= 400:
                raise RuntimeError(f"safetensors missing (HTTP {head.status_code})")
        except Exception:
            weights = "pytorch_model.bin"

        files = list(_MODEL_BASE_FILES) + [weights]
        os.makedirs(os.path.join(_LOCAL_MODEL_DIR, "1_Pooling"), exist_ok=True)

        for rel in files:
            dest = os.path.join(_LOCAL_MODEL_DIR, *rel.split("/"))
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                continue
            url = base + rel
            tmp = dest + ".part"
            resume_from = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
            with session.get(url, stream=True, timeout=(8, 300),
                             headers=headers) as r:
                if resume_from and r.status_code == 200:
                    # 服务端不支持 Range：从头来
                    resume_from = 0
                    mode = "wb"
                else:
                    r.raise_for_status()
                    mode = "ab" if resume_from and r.status_code == 206 else "wb"
                with open(tmp, mode) as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
            os.replace(tmp, dest)
            if rel == weights:
                from intelnexus.core.logger import get_logger
                get_logger(__name__).info(
                    "语义模型权重已从 ModelScope 下载完成: %s (%.0f MB)",
                    rel, os.path.getsize(dest) / 1048576)

        open(marker, "w").close()
        return _LOCAL_MODEL_DIR


def _build_sentence_model():
    """构造 SentenceTransformer 实例，失败抛异常（由调用方捕获处理）。

    三级策略：
    ① 用户显式设置 HF_ENDPOINT → 尊重其配置在线加载；
    ② huggingface.co 可直连（海外网络）→ 官方端点在线加载；
    ③ 国内网络（主站被墙/DNS 污染）→ 从 ModelScope 下载到本地后离线加载。
    """
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    # 注意：import sentence_transformers 本身就要 ~14s（torch 全家桶），因此
    # 「本地缓存直载」分支必须在任何 st 导入之前判断——否则 15s 加载窗口必然超时。

    # ① 已有本地副本：纯离线加载，零网络依赖
    if os.path.exists(os.path.join(_LOCAL_MODEL_DIR, ".complete")):
        from sentence_transformers import SentenceTransformer as _ST
        return _ST(_LOCAL_MODEL_DIR)

    if os.environ.get("HF_ENDPOINT"):
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")

    if _hf_reachable():
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")

    # ③ 国内网络：ModelScope 离线下载兜底
    local_dir = _ensure_local_model_from_modelscope()
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(local_dir)


def load_sentence_model():
    """Load the shared SentenceTransformer model (lazy singleton).

    若模型尚未加载，会在后台线程中加载并最多等待 ``_MODEL_LOAD_TIMEOUT`` 秒。
    超时或加载失败时返回 ``None``，调用方应降级运行（使用默认分数）。

    历史：曾因 HuggingFace 主站被墙导致加载超时 20+ 分钟而整体默认禁用，
    造成语义排序静默失效；现以 ModelScope 离线下载兜底，恢复默认启用。
    """
    global _shared_model

    # 禁用检查：直接跳过，不尝试加载
    if DISABLE_SENTENCE_TRANSFORMER:
        return None

    if _shared_model is not None:
        return _shared_model

    with _model_load_lock:
        # 双检锁：避免重复触发加载
        if _shared_model is not None:
            return _shared_model

        result = {}

        def _do_load():
            try:
                result["model"] = _build_sentence_model()
            except Exception as e:
                result["error"] = e

        t = threading.Thread(target=_do_load, daemon=True)
        t.start()
        t.join(_MODEL_LOAD_TIMEOUT)

        if t.is_alive():
            # 加载线程仍未结束（通常是首次下载中）：本次降级，后台继续
            return None
        if "error" in result:
            # 加载失败（库缺失/网络异常等）：缓存失败标记，降级返回 None。
            # 语义排序是增强能力，绝不能让单次加载异常打断搜索主流程。
            logger.warning("语义模型加载失败，相关性排序降级: %s: %s",
                           type(result["error"]).__name__, result["error"])
            return None
        _shared_model = result.get("model")
        return _shared_model


def warm_up_models():
    """
    预热分析所需的重模型（sentence-transformers），非阻塞带超时。
    模型加载慢或失败时不会阻塞主流程，调用方负责降级处理。
    """
    try:
        load_sentence_model()
    except Exception:
        pass
