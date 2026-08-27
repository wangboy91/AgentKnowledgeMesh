# API Spec

## Base URL

```
http://localhost:8000/api
```

## Authentication

Currently none. Token-based auth planned for V0.3.

## Endpoints

### Health Check

```http
GET /api/health
```

Response:
```json
{
  "name": "AgentKnowledgeMesh",
  "version": "0.2.0",
  "status": "running"
}
```

### Statistics

```http
GET /api/stats
```

Response:
```json
{
  "total_documents": 30,
  "total_size_bytes": 446443,
  "total_nodes": 2,
  "online_nodes": 1
}
```

### Documents

#### List Documents

```http
GET /api/documents
```

Query Parameters:
- `node_id` (optional): Filter by node

Response:
```json
[
  {
    "id": 1,
    "node_id": "local",
    "path": "projects/ai-crm.md",
    "title": "AI CRM System Design",
    "hash": "abc123...",
    "size": 1234,
    "tags": ["project", "ai"],
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
]
```

#### Get Document Tree

```http
GET /api/documents/tree
```

Response (nested object):
```json
{
  "projects": {
    "ai-crm.md": {
      "_title": "AI CRM System Design",
      "_path": "projects/ai-crm.md"
    }
  },
  "technology": {
    "agent.md": {
      "_title": "AI Agent Notes",
      "_path": "technology/agent.md"
    }
  }
}
```

#### Get Document Detail

```http
GET /api/documents/:id
```

Response:
```json
{
  "id": 1,
  "node_id": "local",
  "path": "projects/ai-crm.md",
  "title": "AI CRM System Design",
  "hash": "abc123...",
  "size": 1234,
  "tags": ["project", "ai"],
  "content": "# AI CRM System\n\n...",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### Scan Documents

```http
POST /api/documents/scan
```

Response:
```json
{
  "message": "Scan completed",
  "created": 5,
  "updated": 2,
  "deleted": 1
}
```

### Search

```http
GET /api/search?q=keyword&limit=20
```

Query Parameters:
- `q` (required): Search keyword
- `limit` (optional, default 20): Max results

Response:
```json
{
  "query": "AI",
  "count": 5,
  "documents": [
    {
      "id": 1,
      "node_id": "local",
      "path": "projects/ai-crm.md",
      "title": "AI CRM System Design",
      "hash": "abc123...",
      "size": 1234,
      "tags": [],
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### Nodes

#### List Nodes

```http
GET /api/nodes
```

Response:
```json
[
  {
    "id": "uuid-1",
    "name": "MacBook-Pro",
    "platform": "darwin",
    "ip": "192.168.1.100",
    "status": "online",
    "last_heartbeat": "2024-01-01T00:00:00",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

#### Get Node Detail

```http
GET /api/nodes/:id
```

Response: Same as node object above.

#### Get Node Documents

```http
GET /api/nodes/:id/documents
```

Response:
```json
{
  "node": { ... },
  "documents": [ ... ]
}
```

#### Sync Node

```http
POST /api/nodes/:id/sync
```

Response:
```json
{
  "message": "Sync request sent"
}
```

Error (node offline):
```json
{
  "detail": "Node is offline"
}
```

#### Delete Node

```http
DELETE /api/nodes/:id
```

Response:
```json
{
  "message": "Node and its documents deleted"
}
```

## WebSocket

### Endpoint

```
ws://localhost:8000/ws
```

### Message Format

All messages are JSON with `type` field.

#### Client → Server

**Register**
```json
{
  "type": "register",
  "node_id": "uuid",
  "name": "MacBook",
  "platform": "darwin"
}
```

**Heartbeat**
```json
{
  "type": "heartbeat",
  "node_id": "uuid"
}
```

**Document Update**
```json
{
  "type": "doc_update",
  "node_id": "uuid",
  "path": "projects/ai.md",
  "action": "create|update|delete"
}
```

**Document Response**
```json
{
  "type": "doc_response",
  "node_id": "uuid",
  "path": "projects/ai.md",
  "content": "...",
  "title": "...",
  "hash": "...",
  "size": 1234
}
```

#### Server → Client

**Register ACK**
```json
{
  "type": "register_ack",
  "node_id": "uuid",
  "status": "ok"
}
```

**Heartbeat ACK**
```json
{
  "type": "heartbeat_ack"
}
```

**Sync Request**
```json
{
  "type": "sync_request"
}
```

**Document Request**
```json
{
  "type": "doc_request",
  "path": "projects/ai.md"
}
```

## Error Responses

Standard HTTP error codes:
- `400`: Bad request
- `404`: Not found
- `500`: Internal server error

```json
{
  "detail": "Error message"
}
```
