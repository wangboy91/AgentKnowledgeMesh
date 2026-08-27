# Change: V0.1 Single Machine Knowledge Base

## Summary

Initial release of AgentVault with single-machine knowledge base functionality: Markdown scanning, SQLite indexing, Web UI, and keyword search.

## Motivation

Need a personal knowledge base system that:
- Scans local Markdown files
- Provides Web UI for browsing
- Supports keyword search
- Runs in Docker

## Non-Goals

- Multi-node support (V0.2)
- Agent integration (V0.3)
- Vector search (V1.0)
- Real-time collaboration

## Implementation

### New Files

**Hub (server/)**

- `server/main.py`: FastAPI entry point with lifespan, CORS, static files
- `server/config.py`: Settings with pydantic-settings (env prefix AV_)
- `server/db.py`: Async SQLAlchemy engine/session
- `server/models/document.py`: Document model (id, path, title, hash, size, content)
- `server/services/scanner.py`: Recursive Markdown scanner
- `server/services/indexer.py`: Incremental sync (create/update/delete)
- `server/api/documents.py`: Document CRUD + scan trigger
- `server/api/search.py`: Keyword search (SQLite LIKE)
- `server/api/router.py`: Route aggregation + stats
- `server/pyproject.toml`: Python dependencies

**Frontend (web/)**

- `web/package.json`: React + Vite + TypeScript
- `web/vite.config.ts`: Dev server with API proxy
- `web/src/main.tsx`: React entry point
- `web/src/App.tsx`: Routes (Dashboard, Knowledge)
- `web/src/ThemeContext.tsx`: Dark/Light theme provider
- `web/src/components/Layout.tsx`: Sidebar + resize handle
- `web/src/components/FileTree.tsx`: Collapsible folder tree
- `web/src/components/SearchBar.tsx`: Real-time search
- `web/src/components/MarkdownViewer.tsx`: Markdown renderer
- `web/src/components/ResizeHandle.tsx`: Draggable divider
- `web/src/pages/Dashboard.tsx`: Stats + scan button
- `web/src/pages/Knowledge.tsx`: Document viewer
- `web/src/api/client.ts`: Typed API client
- `web/src/index.css`: Styles with CSS variables

**Docker**

- `Dockerfile`: Multi-stage build (node + python)
- `docker-compose.yml`: Hub with SQLite
- `docker-compose.pg.yml`: Hub with PostgreSQL
- `Makefile`: Dev commands

**Documentation**

- `README.md`: Project overview, quick start, API docs
- `.env.example`: Configuration template
- `.gitignore`: Standard ignores

### Database Changes

- New table: `documents` (id, path, title, hash, size, tags, content, created_at, updated_at)
- Indexes: path (unique), title

## Testing

### Manual Testing

1. Start Hub: `cd server && uv run python main.py`
2. Start frontend: `cd web && npm run dev`
3. Open http://localhost:5173
4. Click "Scan Knowledge Base"
5. Browse documents in file tree
6. Test search functionality
7. Toggle dark/light theme
8. Resize sidebar

## Checklist

- [x] Code follows project style
- [x] Documentation updated
- [x] Works with SQLite
- [x] Works with PostgreSQL
- [x] Frontend works in both themes
