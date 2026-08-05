# AgentKnowledgeMesh

> Your distributed memory layer for AI Agents.

AgentKnowledgeMesh 是一个面向 AI Agent 时代的分布式知识库系统，适用于个人和企业。

## Features

### V0.1 - 单机知识库

- ✅ 递归扫描本地 Markdown 文件
- ✅ SQLite/PostgreSQL 建立文档索引
- ✅ Web 界面浏览知识库
- ✅ Markdown 渲染（GitHub 风格）
- ✅ 关键词搜索
- ✅ Docker 一键部署
- ✅ 暗黑/亮色主题切换
- ✅ 可拖动侧边栏

### V0.2 - 多节点架构

- ✅ Hub + Node 分布式架构
- ✅ WebSocket 实时通信
- ✅ 节点自动注册
- ✅ 心跳检测
- ✅ 远程文档访问
- ✅ 节点管理界面

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Package Manager | uv (10-100x faster than pip) |
| Database | SQLite / PostgreSQL (switchable) |
| Frontend | React + Vite + TypeScript |
| Markdown | react-markdown + remark-gfm |
| Communication | WebSocket |

## Architecture

```
                    AgentKnowledgeMesh Hub
                 (Web + API + WS Server)
                          |
                   WebSocket / HTTP
                          |
      ----------------------------------------
      |                    |                 |
   Node-Mac           Node-Windows       Node-Linux
   (本地Markdown)      (本地Markdown)     (服务端Markdown)
```

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
# 启动 Hub
KNOWLEDGE_DIR=~/Knowledge docker compose up -d

# 访问
open http://localhost:8000
```

### Manual Development

**Hub 端:**

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

**Node 端（另一台机器）:**

```bash
cd node
uv sync

# 配置 Hub 地址
export AV_HUB_URL=ws://hub-ip:8000/ws
export AV_KNOWLEDGE_ROOTS=~/Knowledge

# 启动
uv run python main.py
```

Or use Makefile:

```bash
make dev-backend   # Start Hub backend
make dev-frontend  # Start frontend
make dev-node      # Start node client
```

## API Endpoints

### Documents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/documents` | Document list |
| GET | `/api/documents/tree` | File tree structure |
| GET | `/api/documents/:id` | Document detail |
| POST | `/api/documents/scan` | Trigger scan |

### Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search?q=xxx` | Search documents |

### Nodes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/nodes` | Node list |
| GET | `/api/nodes/:id` | Node detail |
| GET | `/api/nodes/:id/documents` | Node documents |
| POST | `/api/nodes/:id/sync` | Request sync |
| DELETE | `/api/nodes/:id` | Delete node |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats` | System stats |
| WS | `/ws` | WebSocket endpoint |

## Project Structure

```
AgentKnowledgeMesh/
├── server/              # Hub backend (FastAPI)
│   ├── main.py          # Entry point
│   ├── config.py        # Configuration
│   ├── db.py            # Database connection
│   ├── models/          # SQLAlchemy models
│   │   ├── document.py  # Document model
│   │   └── node.py      # Node model
│   ├── services/        # Business logic
│   │   ├── scanner.py   # Markdown scanner
│   │   ├── indexer.py   # Index manager
│   │   └── websocket.py # WebSocket service
│   └── api/             # REST API handlers
├── node/                # Node client
│   ├── main.py          # Entry point
│   ├── config.py        # Configuration
│   ├── scanner.py       # Local scanner
│   └── hub_client.py    # WebSocket client
├── web/                 # React frontend
│   └── src/
│       ├── components/  # UI components
│       ├── pages/       # Page views
│       └── api/         # API client
├── Dockerfile           # Hub image
├── Dockerfile.node      # Node image
├── docker-compose.yml   # Hub deployment
├── docker-compose.node.yml  # Node deployment
└── Makefile
```

## Configuration

### Hub Configuration

Environment variables (prefix `AV_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `AV_HOST` | `0.0.0.0` | Server host |
| `AV_PORT` | `8000` | Server port |
| `AV_DB_TYPE` | `sqlite` | Database type: `sqlite` or `postgres` |
| `AV_DB_PATH` | `data/agentvault.db` | SQLite database path |
| `AV_KNOWLEDGE_ROOTS` | `~/Knowledge` | Knowledge directories (comma-separated) |
| `AV_DEBUG` | `false` | Debug mode |

### Node Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AV_HUB_URL` | `ws://localhost:8000/ws` | Hub WebSocket URL |
| `AV_HUB_API_URL` | `http://localhost:8000/api` | Hub API URL |
| `AV_NODE_NAME` | Auto (hostname) | Node display name |
| `AV_KNOWLEDGE_ROOTS` | `~/Knowledge` | Knowledge directories |
| `AV_HEARTBEAT_INTERVAL` | `30` | Heartbeat interval (seconds) |

### Multiple Knowledge Directories

```bash
# 单目录
AV_KNOWLEDGE_ROOTS=/Users/me/obsidian-doc

# 多目录（逗号分隔）
AV_KNOWLEDGE_ROOTS=/Users/me/obsidian-doc,/Users/me/projects/docs
```

### Database Switching

**SQLite (default)** - zero config:

```bash
AV_DB_TYPE=sqlite AV_DB_PATH=data/agentvault.db
```

**PostgreSQL** - for production:

```bash
cd server && uv sync --extra postgres
export AV_DB_TYPE=postgres
export AV_DB_HOST=localhost
export AV_DB_PASSWORD=your_password
```

Docker with PostgreSQL:

```bash
docker compose -f docker-compose.pg.yml up -d
```

## Docker Deployment

### Hub

```bash
# SQLite mode (default)
docker compose up -d

# PostgreSQL mode
docker compose -f docker-compose.pg.yml up -d
```

### Node

```bash
# 连接到本地 Hub
docker compose -f docker-compose.node.yml up -d

# 连接到远程 Hub
AV_HUB_URL=ws://hub-ip:8000/ws docker compose -f docker-compose.node.yml up -d
```

## Roadmap

- V0.3: Agent Context API, MCP Server integration
- V1.0: Knowledge Graph, Vector search (RAG)
