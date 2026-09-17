# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ .
RUN npm run build

# Stage 2: Python backend + serve frontend
FROM python:3.11-slim-bookworm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies with uv.
# 镜像默认走 ark 嵌入(HTTP API),不装 sentence-transformers/torch
# (那是 local 模式的可选依赖 `local-embedding`,需要时自建镜像加 --extra)。
# uv 下载缓存走 BuildKit cache mount:不进镜像层,本地重建时复用宿主缓存。
COPY server/pyproject.toml server/.python-version ./
# akm-shared 作为 path 依赖（../shared），需在 uv sync 前拷贝到 /shared
COPY shared/ /shared
# 可选依赖入口(源码构建用):留空 = 与发布镜像一致,只装运行必需依赖;
# 传 local-embedding = 额外装 sentence-transformers(离线本地嵌入模型)。
# 发布流水线不传该参数,行为不变。
ARG AKM_UV_EXTRAS=""
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -n "$AKM_UV_EXTRAS" ]; then \
        uv sync --no-dev --no-install-project --extra "$AKM_UV_EXTRAS"; \
    else \
        uv sync --no-dev --no-install-project; \
    fi

# Copy backend code
COPY server/ .

# Copy built frontend
COPY --from=frontend-builder /app/web/dist /app/static

# Create data directory
RUN mkdir -p /app/data

# Environment variables
ENV AKM_DB_PATH=/app/data/agentvault.db
ENV AKM_KNOWLEDGE_ROOTS=/knowledge
ENV AKM_HOST=0.0.0.0
ENV AKM_PORT=8000

# Expose port
EXPOSE 8000

# Run with uv
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
