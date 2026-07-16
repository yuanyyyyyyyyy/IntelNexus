import os
from dotenv import load_dotenv

load_dotenv()

# ========== LLM配置 ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ========== 搜索配置 ==========
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# ========== 功能开关 ==========
ENABLE_DARKWEB = os.getenv("ENABLE_DARKWEB", "false").lower() == "true"
TOR_PROXY_PORT = int(os.getenv("TOR_PROXY_PORT", "9150"))
ENABLE_CREDIBILITY = os.getenv("ENABLE_CREDIBILITY", "true").lower() == "true"
