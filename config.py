import os
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default=None):
    """优先从 Streamlit secrets 读取，回退到环境变量。

    Streamlit Community Cloud 通过 UI Secrets 面板注入配置，
    不使用 .env 文件。本地开发时走 .env（dotenv 已 load）。

    注意：仅在 Streamlit 运行时上下文（ui.py 脚本执行、Cloud 部署）探测
    secrets。CLI 启动进程（`streamlit run` 之前的 bootstrap 阶段）里访问
    st.secrets 会触发首次配置解析，而 bootstrap 的二次解析会把
    STREAMLIT_SERVER_* 环境变量经 click flags 写入 [server] 段，两次解析
    不一致即触发 "An update to the [server] config option section was
    detected" 警告。runtime.exists() 为 False 时跳过探测，保证 CLI 进程
    不发生首次解析。
    """
    # 1) 尝试 Streamlit secrets（仅在 Streamlit 运行时可用）
    try:
        from streamlit import runtime
        if runtime.exists():
            import streamlit as st
            if hasattr(st, "secrets") and key in st.secrets:
                return st.secrets[key]
    except Exception:
        pass
    # 2) 回退到环境变量
    return os.getenv(key, default)


# ========== LLM配置 ==========
# 模型仅支持「本地 Ollama」与「用户在界面添加的自定义模型」，不内置任何云端预设。
# Ollama 本地服务地址（必填，用于自动探测本地模型）
OLLAMA_BASE_URL = _get_secret("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
# 以下为可选：仅当你在「自定义模型」中选择 OpenRouter / Google 类型并留空密钥时作为兜底，
# 实际密钥优先取自自定义模型自身配置。
OPENROUTER_BASE_URL = _get_secret("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = _get_secret("OPENROUTER_API_KEY")
GOOGLE_API_KEY = _get_secret("GOOGLE_API_KEY")

# ========== 搜索配置 ==========
NEWS_API_KEY = _get_secret("NEWS_API_KEY", "")
if NEWS_API_KEY and NEWS_API_KEY.startswith("your_"):
    NEWS_API_KEY = ""

# ========== 功能开关 ==========
ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"
TOR_PROXY_PORT = int(os.getenv("TOR_PROXY_PORT", "9150"))
ENABLE_CREDIBILITY = os.getenv("ENABLE_CREDIBILITY", "true").lower() == "true"
ENABLE_OTX = os.getenv("ENABLE_OTX", "false").lower() == "true"  # OTX SSL证书异常，暂时禁用
ENABLE_HN = os.getenv("ENABLE_HN", "true").lower() == "true"
ENABLE_EXPLOITDB = os.getenv("ENABLE_EXPLOITDB", "false").lower() == "true"
ENABLE_VISUALIZATION = os.getenv("ENABLE_VISUALIZATION", "true").lower() == "true"
# NVD API查询格式错误（404），暂时禁用
ENABLE_NVD = os.getenv("ENABLE_NVD", "false").lower() == "true"
# CISA KEV在中国被墙（超时30s），暂时禁用
ENABLE_CISA_KEV = os.getenv("ENABLE_CISA_KEV", "false").lower() == "true"
# CNVD连接被拒，暂时禁用
ENABLE_CNVD = os.getenv("ENABLE_CNVD", "false").lower() == "true"
# arXiv在中国不稳定，暂时禁用
ENABLE_ARXIV = os.getenv("ENABLE_ARXIV", "false").lower() == "true"
# HuggingFace在中国被墙，暂时禁用
ENABLE_HUGGINGFACE = os.getenv("ENABLE_HUGGINGFACE", "false").lower() == "true"
# 抓取时用 trafilatura 提取正文主内容（去导航/广告/侧栏），失败自动降级整页文本
ENABLE_MAIN_CONTENT_EXTRACTION = os.getenv("ENABLE_MAIN_CONTENT_EXTRACTION", "true").lower() == "true"

# 搜索源开关覆盖钩子：UI「搜索服务设置」面板保存的开关（data/search_settings.json）
# 优先于上面的环境变量默认值。导入失败（循环依赖防护）时保持 env 值不变。
try:
    from intelnexus.config.search_settings import get_source_toggles as _gst
    _toggles = _gst()
    for _k, _v in _toggles.items():
        globals()[_k] = bool(_v)
except Exception:
    pass

# ========== 代理配置（统一由 proxy_settings 模块管理） ==========
# 旧环境变量方式仍兼容（proxy_settings 会读取 HTTP_PROXY/HTTPS_PROXY 作为兜底），
# 但实际代理地址由 intelnexus.config.proxy_settings.get_effective_proxy() 统一提供。
# 此处保留变量仅为向后兼容，新代码应直接使用 proxy_settings 模块。
try:
    from intelnexus.config.proxy_settings import get_proxy_settings as _gps
    _proxy_cfg = _gps()
    HTTP_PROXY = _proxy_cfg.get("proxy_url", "") or None
    HTTPS_PROXY = HTTP_PROXY
except Exception:
    HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    HTTPS_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
USE_TOR = os.getenv("USE_TOR", "false").lower() == "true"
