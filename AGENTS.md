# AGENTS.md

## Project Overview

AgentVault is a distributed personal knowledge base system designed for the AI Agent era.
It enables multiple computers to share Markdown knowledge files, Agent memory files, and
project documents through a unified knowledge network.

The system uses a Hub + Node architecture where:
- **Hub** (server/) manages nodes, provides Web UI, and offers unified search
- **Node** (node/) runs on each computer, scans local Markdown, and connects to Hub

## Repository Layout

```
AgentVault/
├── server/                    # Hub backend (FastAPI + SQLAlchemy)
│   ├── main.py                # FastAPI entry point, WebSocket endpoint
│   ├── config.py              # Settings with pydantic-settings
│   ├── db.py                  # Async SQLAlchemy engine/session
│   ├── models/
│   │   ├── document.py        # Document model (id, node_id, path, title, hash, content)
│   │   └── node.py            # Node model (id, name, platform, status, token)
│   ├── services/
│   │   ├── scanner.py         # Recursive Markdown scanner with hash detection
│   │   ├── indexer.py         # Incremental sync (create/update/delete by hash)
│   │   └── websocket.py       # WS server: register, heartbeat, doc sync
│   └── api/
│       ├── router.py          # Route aggregation + /stats
│       ├── documents.py       # CRUD + scan trigger
│       ├── search.py          # Keyword search (SQLite LIKE)
│       └── nodes.py           # Node management + remote sync
│
├── node/                      # Node client (lightweight)
│   ├── main.py                # Entry point
│   ├── config.py              # Node settings (hub_url, knowledge_roots)
│   ├── scanner.py             # Local Markdown scanner
│   └── hub_client.py          # WebSocket client (register, heartbeat, doc request)
│
├── web/                       # React frontend (Vite + TypeScript)
│   └── src/
│       ├── components/
│       │   ├── Layout.tsx     # Sidebar + resize handle + theme toggle
│       │   ├── FileTree.tsx   # Collapsible folder tree
│       │   ├── NodeList.tsx   # Node selector (local + remote)
│       │   ├── SearchBar.tsx  # Real-time search with dropdown
│       │   ├── MarkdownViewer.tsx  # react-markdown renderer
│       │   └── ResizeHandle.tsx    # Draggable sidebar divider
│       ├── pages/
│       │   ├── Dashboard.tsx  # Stats + scan button
│       │   ├── Knowledge.tsx  # Document viewer
│       │   └── Nodes.tsx      # Node management table
│       ├── api/client.ts      # Typed API client
│       └── ThemeContext.tsx    # Dark/Light theme provider
│
├── Dockerfile                 # Hub image (multi-stage: node build + python)
├── Dockerfile.node            # Node image
├── docker-compose.yml         # Hub with SQLite
├── docker-compose.pg.yml      # Hub with PostgreSQL
├── docker-compose.node.yml    # Node client
├── Makefile                   # Dev commands
└── pyproject.toml             # (unused, see server/ and node/)
```

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python 3.11 + FastAPI | Async throughout |
| Database | SQLite (default) / PostgreSQL | Switch via `AV_DB_TYPE` |
| ORM | SQLAlchemy 2.0 (async) | `aiosqlite` or `asyncpg` |
| Frontend | React 18 + Vite + TypeScript | SPA, dark/light theme |
| Markdown | react-markdown + remark-gfm | GitHub-flavored rendering |
| Communication | WebSocket (FastAPI native) | JSON messages |
| Package Manager | uv | 10-100x faster than pip |

## Development Commands

All Python commands use `uv` for package management.

### Hub (server)

```bash
cd server
uv sync                          # Install dependencies
uv run python main.py            # Start Hub on :8000

# With PostgreSQL
uv sync --extra postgres
AV_DB_TYPE=postgres uv run python main.py
```

### Frontend (web)

```bash
cd web
npm install
npm run dev                      # Dev server on :5173
npm run build                    # Build to web/dist/
```

### Node Client

```bash
cd node
uv sync
AV_HUB_URL=ws://localhost:8000/ws AV_KNOWLEDGE_ROOTS=~/Knowledge uv run python main.py
```

### Makefile Shortcuts

```bash
make dev-backend         # Start Hub
make dev-frontend        # Start frontend
make dev-node            # Start node client
make docker-up           # Docker (SQLite)
make docker-up-pg        # Docker (PostgreSQL)
make docker-up-node      # Docker (Node)
make clean               # Remove caches, venv, db
```

## Configuration

### Hub Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AV_HOST` | `0.0.0.0` | Server host |
| `AV_PORT` | `8000` | Server port |
| `AV_DB_TYPE` | `sqlite` | `sqlite` or `postgres` |
| `AV_DB_PATH` | `data/agentvault.db` | SQLite path |
| `AV_DB_HOST` | `localhost` | PostgreSQL host |
| `AV_DB_PORT` | `5432` | PostgreSQL port |
| `AV_DB_NAME` | `agentvault` | PostgreSQL database |
| `AV_DB_USER` | `postgres` | PostgreSQL user |
| `AV_DB_PASSWORD` | | PostgreSQL password |
| `AV_KNOWLEDGE_ROOTS` | `~/Knowledge` | Comma-separated directories |
| `AV_DEBUG` | `false` | Debug mode |

### Node Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AV_HUB_URL` | `ws://localhost:8000/ws` | Hub WebSocket URL |
| `AV_HUB_API_URL` | `http://localhost:8000/api` | Hub API URL |
| `AV_NODE_NAME` | hostname | Node display name |
| `AV_KNOWLEDGE_ROOTS` | `~/Knowledge` | Comma-separated directories |
| `AV_HEARTBEAT_INTERVAL` | `30` | Seconds between heartbeats |

## WebSocket Protocol

Messages between Hub and Node use JSON:

```json
// Node → Hub: Register
{"type": "register", "node_id": "uuid", "name": "MacBook", "platform": "darwin"}

// Hub → Node: Register ACK
{"type": "register_ack", "node_id": "uuid", "status": "ok"}

// Node → Hub: Heartbeat
{"type": "heartbeat", "node_id": "uuid"}

// Hub → Node: Heartbeat ACK
{"type": "heartbeat_ack"}

// Node → Hub: Document update notification
{"type": "doc_update", "node_id": "uuid", "path": "projects/ai.md", "action": "create"}

// Hub → Node: Request sync
{"type": "sync_request"}

// Hub → Node: Request document content
{"type": "doc_request", "path": "projects/ai.md"}

// Node → Hub: Document content response
{"type": "doc_response", "path": "projects/ai.md", "content": "...", "title": "..."}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | System statistics |
| GET | `/api/documents` | List documents |
| GET | `/api/documents/tree` | File tree structure |
| GET | `/api/documents/:id` | Document detail with content |
| POST | `/api/documents/scan` | Trigger local scan |
| GET | `/api/search?q=xxx` | Keyword search |
| GET | `/api/nodes` | List nodes |
| GET | `/api/nodes/:id` | Node detail |
| GET | `/api/nodes/:id/documents` | Node's documents |
| POST | `/api/nodes/:id/sync` | Request node sync |
| DELETE | `/api/nodes/:id` | Delete node |
| WS | `/ws` | WebSocket endpoint |

## Working Guidelines

- Use `uv` for all Python package management (not pip)
- Keep `.env` for local config only; never commit real secrets
- Database files (`data/*.db`) are gitignored
- Frontend builds to `web/dist/` and is served by Hub in production
- Theme preference is stored in localStorage
- Sidebar width is stored in localStorage
- Document hash (SHA256) is used for incremental sync
- Node ID is auto-generated from hostname if not configured

## Common Verification Targets

- Scanner changes: Test with `POST /api/documents/scan` and verify index
- Search changes: Test with `GET /api/search?q=xxx`
- WebSocket changes: Run Hub + Node and verify connection
- Frontend changes: Check both dark and light themes
- Database changes: Test with both SQLite and PostgreSQL
