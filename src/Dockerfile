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
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies with uv
COPY server/pyproject.toml server/.python-version ./
# akm-shared 作为 path 依赖（../shared），需在 uv sync 前拷贝到 /shared
COPY shared/ /shared
RUN uv sync --no-dev --no-install-project

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
