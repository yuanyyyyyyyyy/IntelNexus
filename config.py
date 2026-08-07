import os
from dotenv import load_dotenv

load_dotenv()

# ========== LLM配置 ==========
# 模型仅支持「本地 Ollama」与「用户在界面添加的自定义模型」，不内置任何云端预设。
# Ollama 本地服务地址（必填，用于自动探测本地模型）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
# 以下为可选：仅当你在「自定义模型」中选择 OpenRouter / Google 类型并留空密钥时作为兜底，
# 实际密钥优先取自自定义模型自身配置。
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ========== 搜索配置 ==========
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# ========== 功能开关 ==========
ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"
TOR_PROXY_PORT = int(os.getenv("TOR_PROXY_PORT", "9150"))
ENABLE_CREDIBILITY = os.getenv("ENABLE_CREDIBILITY", "true").lower() == "true"

# ========== 代理配置（仅在使用时生效；为空则不走代理） ==========
HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
HTTPS_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
USE_TOR = os.getenv("USE_TOR", "false").lower() == "true"
