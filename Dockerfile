# IntelNexus 应用镜像
# 基础镜像满足 streamlit>=1.48、apscheduler>=3.10
FROM python:3.11-slim

# 系统依赖：lxml / trafilatura 等解析库编译所需；build-essential 兜底源码编译。
# 构建后清理 apt 缓存，保持镜像精简。
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev \
    libxslt1-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装 Python 依赖（独立层，源码变动不触发重装）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 复制应用源码（.dockerignore 已排除 .env / data / __pycache__ / tests 等）
COPY . .

# Streamlit 健康检查端点（供 compose healthcheck 与编排探测）
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)"

# 容器内监听 0.0.0.0 供 nginx 反代连通；--no-browser 关闭仅本机有意义的自动开浏览器线程。
# 数据目录默认 /app/data（PROJECT_ROOT=/app），由 compose 挂 named volume 持久化。
CMD ["python", "main.py", "ui", "--ui-host", "0.0.0.0", "--ui-port", "8501", "--no-browser"]
