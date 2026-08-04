# Change: V0.2 Multi-Node Architecture

## Summary

Implement Hub + Node distributed architecture with WebSocket communication, enabling multiple machines to share knowledge.

## Motivation

Users have Markdown files across multiple computers (MacBook, desktop, server). Need a way to:
- Connect multiple machines to a central Hub
- Browse remote documents from any machine
- Search across all connected nodes
- Monitor node status

## Non-Goals

- Real-time bidirectional sync (future)
- Conflict resolution (future)
- File transfer between nodes (future)
- Authentication/authorization (future)

## Implementation

### Files Changed

**Hub (server/)**

- `server/models/document.py`: Added `node_id` field with unique constraint (node_id, path)
- `server/models/node.py`: New Node model (id, name, platform, status, token, last_heartbeat)
- `server/services/websocket.py`: WebSocket server (register, heartbeat, doc sync)
- `server/api/nodes.py`: Node management API (list, detail, sync, delete)
- `server/api/router.py`: Added nodes router, updated stats to include node counts
- `server/main.py`: Added WebSocket endpoint at `/ws`

**Node (node/)**

- `node/main.py`: Node client entry point
- `node/config.py`: Node configuration (hub_url, knowledge_roots)
- `node/scanner.py`: Local Markdown scanner (adapted from Hub)
- `node/hub_client.py`: WebSocket client (connect, register, heartbeat, doc request)

**Frontend (web/)**

- `web/src/api/client.ts`: Added Node types and API methods
- `web/src/components/NodeList.tsx`: Node selector component
- `web/src/pages/Nodes.tsx`: Node management page
- `web/src/components/Layout.tsx`: Added Nodes nav link and NodeList in sidebar
- `web/src/App.tsx`: Added `/nodes` route
- `web/src/index.css`: Added node-related styles

**Docker**

- `Dockerfile.node`: Node client image
- `docker-compose.node.yml`: Node deployment config
- `node/pyproject.toml`: Node dependencies
- `node/.python-version`: Python 3.11

**Documentation**

- `README.md`: Updated with V0.2 features, architecture, node config
- `AGENTS.md`: New file - project overview for AI agents
- `openspec/`: New directory - spec-driven development docs

### Database Changes

- New table: `nodes` (id, name, platform, ip, status, token, last_heartbeat, created_at, updated_at)
- Modified table: `documents` - added `node_id` column, changed unique constraint from `path` to `(node_id, path)`

## Testing

### Manual Testing

1. Start Hub: `cd server && uv run python main.py`
2. Start Node: `cd node && AV_HUB_URL=ws://localhost:8000/ws uv run python main.py`
3. Open http://localhost:5173/nodes
4. Verify node appears as "Online"
5. Click "Sync" to trigger document sync
6. Browse remote documents in Knowledge tab

### Automated Tests

```bash
# TODO: Add tests
```

## Checklist

- [x] Code follows project style
- [ ] Tests added/updated
- [x] Documentation updated
- [x] Works with SQLite
- [x] Works with PostgreSQL (if DB change)
- [x] Frontend works in both themes

## Future Work

- V0.3: Context API for Agent integration
- V0.3: MCP Server for Claude Code/Codex
- V1.0: Vector search with embeddings
- V1.0: Knowledge graph
