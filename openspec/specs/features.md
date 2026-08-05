# Features Spec

## V0.1 - Single Machine Knowledge Base

### Markdown Scanning

- Recursive scan of configured directories
- Support `.md` file extension
- Skip hidden files/directories (starting with `.`)
- Skip files larger than 10MB
- Extract title from first `# Heading` or filename
- Compute SHA256 hash for change detection

### Document Indexing

- Store in SQLite (default) or PostgreSQL
- Incremental sync: create/update/delete based on hash
- Support multiple root directories
- Track node_id for distributed documents

### Web Interface

- **Dashboard**: Statistics (documents, size, nodes) + scan button
- **Knowledge**: File tree + Markdown viewer
- **Nodes**: Node management table
- **Search**: Real-time search with dropdown results

### UI Features

- Dark/Light theme toggle (persisted in localStorage)
- Collapsible folder tree (default collapsed)
- Draggable sidebar divider (width persisted in localStorage)
- Responsive layout

### Search

- Keyword-based search using SQL LIKE
- Search in title, path, and content
- Title matches prioritized in results
- Configurable result limit (default 20)

## V0.2 - Multi-Node Architecture

### Node Registration

- Auto-generate node ID from hostname
- Custom node name support
- Platform detection (darwin/windows/linux)
- Token-based authentication (future)

### WebSocket Communication

- Persistent connection between Node and Hub
- JSON message protocol
- Automatic reconnection on disconnect
- Message types: register, heartbeat, doc_update, sync_request, doc_request, doc_response

### Heartbeat

- Default interval: 30 seconds
- Configurable via `AV_HEARTBEAT_INTERVAL`
- Hub marks node offline after missed heartbeats
- Status visible in Web UI

### Remote Document Access

- Hub can request document list from Node
- Hub can request specific document content
- Documents indexed with node_id prefix
- Search includes remote documents

### Node Management

- List all registered nodes
- Show online/offline status
- Manual sync trigger
- Delete node and its documents

## V0.3 - Agent Integration (Planned)

### Context API

- `GET /api/context?q=xxx` for Agent queries
- Returns relevant documents with content
- Formatted for prompt injection

### MCP Server

- Model Context Protocol support
- Let Claude Code, Codex, etc. call AgentKnowledgeMesh
- Standard tool interface

## V1.0 - Advanced Features (Planned)

### Vector Search

- Embedding-based semantic search
- Qdrant or similar vector DB
- RAG (Retrieval Augmented Generation)

### Knowledge Graph

- Entity extraction (projects, people, tech)
- Relationship mapping
- Visual graph exploration
