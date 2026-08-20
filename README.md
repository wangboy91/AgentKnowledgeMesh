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

### V0.3 - Agent 集成

- ✅ Context API（`/api/context`）
- ✅ MCP Server 集成
- ✅ 向量搜索 (RAG)
- ✅ 语义搜索 API

### V1.0 - 高级功能（规划中）

- ⏳ 知识图谱
- ⏳ 在线文档转换 (PDF/Word → MD)
- ⏳ 在线 Markdown 编辑器

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Package Manager | uv (10-100x faster than pip) |
| Database | SQLite / PostgreSQL (switchable) |
| Frontend | React + Vite + TypeScript |
| Markdown | react-markdown + remark-gfm |
| Communication | WebSocket |
| AI Integration | MCP (Model Context Protocol) |

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
cd src/server
uv sync
uv run python main.py

# 前端（另一个终端）
cd src/web
npm install
npm run dev

# 访问
open http://localhost:5173
```

**Node 端（另一台机器）:**

```bash
cd src/node
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

## MCP Server 集成

AgentKnowledgeMesh 支持 MCP (Model Context Protocol)，让 AI 工具可以直接访问知识库。

### 配置 Claude Code

在项目根目录创建 `.claude/mcp.json`：

```json
{
  "mcpServers": {
    "agentknowledge": {
      "command": "uv",
      "args": ["run", "python", "main.py", "--mcp"],
      "cwd": "src/server"
    }
  }
}
```

或使用 HTTP 模式：

```json
{
  "mcpServers": {
    "agentknowledge": {
      "url": "http://localhost:8000/api/mcp/sse"
    }
  }
}
```

### 可用工具

| 工具 | 描述 |
|------|------|
| `search_documents` | 搜索知识库文档 |
| `get_document` | 获取文档详情 |
| `list_documents` | 列出文档列表 |

### 测试 MCP

```bash
# 使用 MCP Inspector
npx @modelcontextprotocol/inspector http://localhost:8000/api/mcp/sse
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

### Context (for AI Agents)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/context?q=xxx` | Get context for AI prompt |

### Nodes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/nodes` | Node list |
| GET | `/api/nodes/:id` | Node detail |
| GET | `/api/nodes/:id/documents` | Node documents |
| POST | `/api/nodes/:id/sync` | Request sync |
| DELETE | `/api/nodes/:id` | Delete node |

### RAG (Vector Search)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/rag/search?q=xxx` | Semantic search |
| GET | `/api/rag/context?q=xxx` | RAG context for AI |
| POST | `/api/rag/index` | Index all documents |
| GET | `/api/rag/stats` | Vector store stats |

### MCP

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/mcp/sse` | MCP SSE endpoint |
| POST | `/api/mcp/messages` | MCP messages endpoint |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats` | System stats |
| GET | `/api/health` | Health check |
| WS | `/ws` | WebSocket endpoint |

## Project Structure

```
AgentKnowledgeMesh/
├── src/
│   ├── server/            # Hub backend (FastAPI)
│   │   ├── main.py        # Entry point
│   │   ├── config.py      # Configuration
│   │   ├── db.py          # Database connection
│   │   ├── models/        # SQLAlchemy models
│   │   ├── services/      # Business logic
│   │   │   ├── scanner.py
│   │   │   ├── indexer.py
│   │   │   ├── websocket.py
│   │   │   └── mcp_server.py  # MCP Server
│   │   └── api/           # REST API handlers
│   │       ├── documents.py
│   │       ├── search.py
│   │       ├── nodes.py
│   │       ├── context.py
│   │       └── mcp.py
│   ├── node/              # Node client
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── scanner.py
│   │   └── hub_client.py
│   └── web/               # React frontend
│       └── src/
│           ├── components/
│           ├── pages/
│           └── api/
├── openspec/              # OpenSpec documentation
├── AGENTS.md              # AI Agent guide
├── README.md
├── .gitignore
├── Makefile
├── Dockerfile
├── Dockerfile.node
├── docker-compose.yml
├── docker-compose.pg.yml
└── docker-compose.node.yml
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
cd src/server && uv sync --extra postgres
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

- V0.3: ✅ Agent Context API, ✅ MCP Server
- V1.0: ⏳ Knowledge Graph, ⏳ Vector search (RAG), ⏳ Document conversion, ⏳ Online editor

## License

MIT
