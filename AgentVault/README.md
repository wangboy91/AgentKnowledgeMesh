# AgentVault

> Your distributed memory layer for AI Agents.

AgentVault 是一个面向 AI Agent 时代的分布式个人知识库系统。V0.1 实现单机知识库的核心功能。

## Features (V0.1)

- ✅ 递归扫描本地 Markdown 文件
- ✅ SQLite 建立文档索引
- ✅ Web 界面浏览知识库
- ✅ Markdown 渲染（GitHub 风格）
- ✅ 关键词搜索
- ✅ Docker 一键部署

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Package Manager | uv (10-100x faster than pip) |
| Database | SQLite / PostgreSQL (switchable) |
| Frontend | React + Vite + TypeScript |
| Markdown | react-markdown + remark-gfm |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Docker (Recommended)

```bash
# 设置知识库目录并启动
KNOWLEDGE_DIR=~/Knowledge docker compose up -d

# 访问
open http://localhost:8000
```

### Manual Development

```bash
# 后端
cd server
uv sync
uv run python main.py

# 前端（另一个终端）
cd web
npm install
npm run dev

# 访问
open http://localhost:5173
```

Or use Makefile:

```bash
make dev-backend   # Start backend with uv
make dev-frontend  # Start frontend
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/documents` | Document list |
| GET | `/api/documents/tree` | File tree structure |
| GET | `/api/documents/:id` | Document detail |
| POST | `/api/documents/scan` | Trigger scan |
| GET | `/api/search?q=xxx` | Search documents |
| GET | `/api/stats` | System stats |

## Project Structure

```
AgentVault/
├── server/           # Python backend (FastAPI)
│   ├── main.py       # Entry point
│   ├── config.py     # Configuration
│   ├── db.py         # Database connection
│   ├── models/       # SQLAlchemy models
│   ├── services/     # Business logic
│   │   ├── scanner.md    # Markdown scanner
│   │   └── indexer.py    # Index manager
│   └── api/          # REST API handlers
├── web/              # React frontend
│   └── src/
│       ├── components/   # UI components
│       ├── pages/        # Page views
│       └── api/          # API client
├── Dockerfile
├── docker-compose.yml
└── Makefile
```

## Configuration

Environment variables (prefix `AV_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `AV_HOST` | `0.0.0.0` | Server host |
| `AV_PORT` | `8000` | Server port |
| `AV_DB_TYPE` | `sqlite` | Database type: `sqlite` or `postgres` |
| `AV_DB_PATH` | `data/agentvault.db` | SQLite database path |
| `AV_DB_HOST` | `localhost` | PostgreSQL host |
| `AV_DB_PORT` | `5432` | PostgreSQL port |
| `AV_DB_NAME` | `agentvault` | PostgreSQL database name |
| `AV_DB_USER` | `postgres` | PostgreSQL user |
| `AV_DB_PASSWORD` | | PostgreSQL password |
| `AV_KNOWLEDGE_ROOTS` | `~/Knowledge` | Knowledge directories (comma-separated) |
| `AV_DEBUG` | `false` | Debug mode |

### Multiple Knowledge Directories

支持配置多个知识库目录，用逗号分隔：

```bash
# 单目录
AV_KNOWLEDGE_ROOTS=/Users/me/obsidian-doc

# 多目录
AV_KNOWLEDGE_ROOTS=/Users/me/obsidian-doc,/Users/me/projects/docs,/home/server/knowledge
```

### Database Switching

**SQLite (default)** - zero config, file-based:

```bash
AV_DB_TYPE=sqlite AV_DB_PATH=data/agentvault.db
```

**PostgreSQL** - for production or multi-user:

```bash
# Install PostgreSQL driver
cd server && uv sync --extra postgres

# Set environment
export AV_DB_TYPE=postgres
export AV_DB_HOST=localhost
export AV_DB_PASSWORD=your_password
```

Docker with PostgreSQL:

```bash
docker compose -f docker-compose.pg.yml up -d
```

## Roadmap

- V0.2: Multi-node support, WebSocket communication
- V0.3: Agent Context API, MCP Server integration
- V1.0: Knowledge Graph, Vector search (RAG)
