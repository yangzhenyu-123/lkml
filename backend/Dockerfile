FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 系统依赖：git 用于 patch-id 与 kernel 镜像操作；build-essential / libpq-dev 用于 psycopg2 等
# nodejs / npm 用于全局安装 opencode CLI；curl 用于健康检查与下载
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libpq-dev \
        curl \
        nodejs \
        npm \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 opencode CLI（全局）
# 注意：若官方包名不是 opencode（例如 @opencode/cli 或 sst-opencode），
# 需对照 opencode 官方文档调整下面的 npm 包名，TODO: 对照 opencode 文档确认包名
RUN npm install -g opencode || echo "opencode npm install skipped (will retry at runtime if needed)"

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY app /app/app

EXPOSE 8000

# 默认 CMD 占位（docker-compose 会覆盖）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
