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
# PyPI 的 torch 轮子在 Linux 捆绑 CUDA(约 5G nvidia/triton 组件);容器按 CPU 运行,
# 同层换装 CPU 版 torch 并移除 CUDA 组件(同层操作才会真正减小镜像),并自检导入。
COPY server/pyproject.toml server/.python-version ./
# akm-shared 作为 path 依赖（../shared），需在 uv sync 前拷贝到 /shared
COPY shared/ /shared
# uv 下载缓存走 BuildKit cache mount:不进镜像层(否则缓存会把镜像撑到 ~10G),
# 且本地重建时复用宿主缓存
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project \
    && TORCH_VER=$(.venv/bin/python -c "import torch; print(torch.__version__.split('+')[0])") \
    && uv pip install --python .venv/bin/python "torch==${TORCH_VER}" \
        --torch-backend=cpu --reinstall-package torch \
    && uv pip uninstall --python .venv/bin/python -y \
        $(uv pip list --python .venv/bin/python | grep -E '^nvidia-|^triton ' | awk '{print $1}') \
    && .venv/bin/python -c "import torch; assert '+cpu' in torch.__version__, torch.__version__; import sentence_transformers"

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
