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
- ✅ 文档转换 (PDF/Word/HTML → MD)
- ✅ 在线 Markdown 编辑器

### V1.0 - 高级功能（规划中）

- ⏳ 知识图谱

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
cp .env.example .env   # 按需修改配置（见下方「配置说明」）
uv run akm-hub

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
cp .env.example .env   # 配置 Hub 地址和本地知识库目录

# 启动
uv run akm-node
```

## 配置说明

所有配置通过环境变量管理，两个组件各有一份模板：

| 组件 | 模板文件 | 说明 |
|---|---|---|
| Server (Hub) | `src/server/.env.example` | 数据库、向量库、嵌入模型、知识库目录 |
| Node | `src/node/.env.example` | Hub 地址、本地知识库目录 |

复制模板后按需修改，`.env` 已被 gitignore，密钥不会提交：

```bash
cd src/server && cp .env.example .env
```

**零配置即可启动**：默认使用 SQLite + 本地嵌入模型（首次运行会下载模型）。
需要以下能力时再改配置：

- **PostgreSQL 存储**：`AKM_DB_TYPE=postgres` + 连接信息（向量表自动同库存放）
- **中文语义搜索效果更好**：`AKM_EMBEDDING_PROVIDER=ark` + 火山引擎 API Key
- **指定知识库目录**：`AKM_KNOWLEDGE_ROOTS=/path/to/docs`（多个用逗号分隔）

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
      "args": ["run", "akm-hub", "--mcp"],
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
| PUT | `/api/nodes/:id/documents` | Upload node documents (Bearer token) |
| POST | `/api/nodes/:id/sync` | Request sync |
| DELETE | `/api/nodes/:id` | Delete node |

### RAG (Vector Search)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/rag/search?q=xxx` | Semantic search |
| GET | `/api/rag/context?q=xxx` | RAG context for AI |
| POST | `/api/rag/index` | Index all documents |
| GET | `/api/rag/stats` | Vector store stats |

### Document Conversion

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/convert/upload` | Upload and convert file |
| POST | `/api/convert/url` | Convert from URL |

Supported formats: PDF, DOCX, HTML

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
│   │   ├── app/           # 应用主包（uv run akm-hub 启动）
│   │   │   ├── main.py    # FastAPI 入口 + lifespan
│   │   │   ├── config.py  # 配置（路径锚定项目根，CWD 无关）
│   │   │   ├── db.py      # 数据库连接
│   │   │   ├── models/    # SQLAlchemy models
│   │   │   ├── services/  # 业务逻辑
│   │   │   │   ├── scanner.py
│   │   │   │   ├── indexer.py
│   │   │   │   ├── websocket.py
│   │   │   │   ├── rag/   # RAG 子域（embeddings + vector_store）
│   │   │   │   ├── converters/  # 文档转换（PDF/Word/HTML/URL）
│   │   │   │   └── mcp_server.py  # MCP Server
│   │   │   └── api/       # REST API handlers
│   │   │       ├── documents.py
│   │   │       ├── search.py
│   │   │       ├── rag.py
│   │   │       ├── nodes.py
│   │   │       ├── context.py
│   │   │       └── mcp.py
│   │   ├── tests/         # 测试
│   │   ├── .env           # 环境变量（不入库）
│   │   └── pyproject.toml
│   ├── shared/            # Shared scanner (akm-shared)
│   │   └── akm_shared/
│   │       └── scanner.py
│   ├── node/              # Node client
│   │   └── app/           # 应用主包（uv run akm-node 启动）
│   │       ├── __main__.py
│   │       ├── config.py
│   │       ├── transport.py
│   │       ├── sync.py
│   │       └── runner.py
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

Environment variables (prefix `AKM_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `AKM_HOST` | `0.0.0.0` | Server host |
| `AKM_PORT` | `8000` | Server port |
| `AKM_DB_TYPE` | `sqlite` | Database type: `sqlite` or `postgres` |
| `AKM_DB_PATH` | `data/agentvault.db` | SQLite database path |
| `AKM_KNOWLEDGE_ROOTS` | `~/Knowledge` | Knowledge directories (comma-separated) |
| `AKM_DEBUG` | `false` | Debug mode |

### Node Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AKM_HUB_URL` | `ws://localhost:8000/ws` | Hub WebSocket URL |
| `AKM_HUB_API_URL` | `http://localhost:8000/api` | Hub API URL |
| `AKM_NODE_NAME` | Auto (hostname) | Node display name |
| `AKM_KNOWLEDGE_ROOTS` | `~/Knowledge` | Knowledge directories |
| `AKM_HEARTBEAT_INTERVAL` | `30` | Heartbeat interval (seconds) |

### Multiple Knowledge Directories

```bash
# 单目录
AKM_KNOWLEDGE_ROOTS=/Users/me/obsidian-doc

# 多目录（逗号分隔）
AKM_KNOWLEDGE_ROOTS=/Users/me/obsidian-doc,/Users/me/projects/docs
```

### Database Switching

**SQLite (default)** - zero config:

```bash
AKM_DB_TYPE=sqlite AKM_DB_PATH=data/agentvault.db
```

**PostgreSQL** - for production:

```bash
cd src/server && uv sync --extra postgres
export AKM_DB_TYPE=postgres
export AKM_DB_HOST=localhost
export AKM_DB_PASSWORD=your_password
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
AKM_HUB_URL=ws://hub-ip:8000/ws docker compose -f docker-compose.node.yml up -d
```

## Roadmap

- V0.3: ✅ Agent Context API, ✅ MCP Server
- V1.0: ⏳ Knowledge Graph, ⏳ Vector search (RAG), ⏳ Document conversion, ⏳ Online editor

## License

MIT
