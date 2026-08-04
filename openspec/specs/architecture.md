# Architecture Spec

## Overview

AgentVault uses a Hub + Node distributed architecture for managing knowledge across multiple machines.

## Components

### Hub (server/)

The central server that:
- Manages node registration and status
- Provides Web UI for browsing knowledge
- Offers unified search across all nodes
- Serves as WebSocket server for node connections
- Stores document index in SQLite/PostgreSQL

### Node (node/)

A lightweight client that:
- Runs on each machine with local Markdown files
- Scans local directories for .md files
- Connects to Hub via WebSocket
- Responds to document requests from Hub
- Sends heartbeat to maintain online status

### Frontend (web/)

React SPA that:
- Displays file tree with collapsible folders
- Renders Markdown with GitHub-flavored styling
- Supports dark/light theme switching
- Shows node status and management interface
- Provides real-time search with dropdown results

## Data Flow

```
Local Markdown Files
        ↓
    Node Scanner
        ↓
    WebSocket
        ↓
    Hub Indexer
        ↓
    SQLite/PostgreSQL
        ↓
    Hub API
        ↓
    Frontend
```

## Communication Protocol

### WebSocket Messages

All messages use JSON format with a `type` field:

1. **Registration**: Node registers with Hub on connect
2. **Heartbeat**: Node sends periodic heartbeats (default 30s)
3. **Doc Update**: Node notifies Hub of document changes
4. **Sync Request**: Hub requests full document list from Node
5. **Doc Request**: Hub requests specific document content
6. **Doc Response**: Node sends document content to Hub

### REST API

Standard CRUD operations for:
- Documents (list, detail, scan)
- Search (keyword-based)
- Nodes (list, detail, sync, delete)
- Stats (counts, sizes)

## Database Schema

### documents

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment PK |
| node_id | STRING | Node ID ("local" for Hub) |
| path | STRING | Relative file path |
| title | STRING | Document title |
| hash | STRING | SHA256 of content |
| size | INTEGER | File size in bytes |
| tags | TEXT | JSON array of tags |
| content | TEXT | Full file content |
| created_at | DATETIME | Creation time |
| updated_at | DATETIME | Last update time |

Unique constraint: (node_id, path)

### nodes

| Column | Type | Description |
|--------|------|-------------|
| id | STRING | UUID primary key |
| name | STRING | Display name |
| platform | STRING | darwin/windows/linux |
| ip | STRING | Node IP address |
| status | STRING | online/offline |
| token | STRING | Auth token |
| last_heartbeat | DATETIME | Last heartbeat time |
| created_at | DATETIME | Registration time |
| updated_at | DATETIME | Last update time |

## Deployment

### Single Machine (Development)

```bash
# Terminal 1: Hub
cd server && uv run python main.py

# Terminal 2: Frontend
cd web && npm run dev

# Terminal 3: Node (optional)
cd node && uv run python main.py
```

### Docker (Production)

```bash
# Hub with SQLite
docker compose up -d

# Hub with PostgreSQL
docker compose -f docker-compose.pg.yml up -d

# Node
docker compose -f docker-compose.node.yml up -d
```
