# Development Spec

## Package Management

**Always use `uv`** for Python package management. Never use `pip` directly.

```bash
# Install dependencies
cd server && uv sync
cd node && uv sync

# Add a dependency
cd server && uv add package-name

# Add dev dependency
cd server && uv add --dev pytest

# Run Python scripts
uv run python main.py
uv run pytest
```

## Environment Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- uv (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Hub Development

```bash
# Terminal 1: Backend
cd server
uv sync
uv run python main.py

# Terminal 2: Frontend
cd web
npm install
npm run dev
```

Access: http://localhost:5173

### Node Development

```bash
cd node
uv sync

# Configure
export AV_HUB_URL=ws://localhost:8000/ws
export AV_KNOWLEDGE_ROOTS=~/Knowledge

# Run
uv run python main.py
```

## Code Style

### Python

- Use type hints throughout
- Async/await for all I/O operations
- Pydantic models for data validation
- SQLAlchemy 2.0 async style

```python
# Good
async def get_documents(session: AsyncSession) -> list[Document]:
    result = await session.execute(select(Document))
    return result.scalars().all()

# Bad
def get_documents(session):
    return session.query(Document).all()
```

### TypeScript/React

- Functional components with hooks
- TypeScript strict mode
- CSS variables for theming

```tsx
// Good
export default function MyComponent() {
  const [count, setCount] = useState(0)
  return <div>{count}</div>
}

// Bad
export class MyComponent extends React.Component {
  render() {
    return <div>{this.state.count}</div>
  }
}
```

## Database

### Migrations

Currently using `create_all()` for schema creation. No migration tool yet.

When changing models:
1. Update model in `server/models/`
2. Delete `data/agentvault.db` (SQLite)
3. Restart server to recreate tables

### Testing Both Databases

```bash
# SQLite
AV_DB_TYPE=sqlite uv run python main.py

# PostgreSQL
AV_DB_TYPE=postgres AV_DB_HOST=localhost uv run python main.py
```

## Testing

### Backend Tests

```bash
cd server
uv run pytest
```

### Frontend Tests

```bash
cd web
npm test
```

### Manual Testing

1. Start Hub: `cd server && uv run python main.py`
2. Start frontend: `cd web && npm run dev`
3. Open http://localhost:5173
4. Click "Scan Knowledge Base"
5. Browse documents
6. Test search

## Docker

### Build Images

```bash
# Hub
docker build -t agentvault .

# Node
docker build -t agentvault-node -f Dockerfile.node .
```

### Run with Docker Compose

```bash
# Hub (SQLite)
docker compose up -d

# Hub (PostgreSQL)
docker compose -f docker-compose.pg.yml up -d

# Node
docker compose -f docker-compose.node.yml up -d
```

## Common Tasks

### Add New API Endpoint

1. Create handler in `server/api/`
2. Add router in `server/api/router.py`
3. Add client method in `web/src/api/client.ts`
4. Update frontend to use new endpoint

### Add New WebSocket Message Type

1. Add handler in `server/services/websocket.py`
2. Add sender in `node/hub_client.py`
3. Update protocol docs in `AGENTS.md`

### Add New Frontend Page

1. Create component in `web/src/pages/`
2. Add route in `web/src/App.tsx`
3. Add nav link in `web/src/components/Layout.tsx`

## Debugging

### Backend

```bash
# Enable debug mode
AV_DEBUG=true uv run python main.py
```

Logs will show SQL queries.

### Frontend

Open browser DevTools:
- Console for errors
- Network tab for API calls
- React DevTools for component state

### WebSocket

Use browser DevTools Network tab → WS to inspect messages.

## Release

### Version Bump

1. Update version in `server/config.py`
2. Update version in `node/pyproject.toml`
3. Update version in `web/package.json`
4. Update CHANGELOG.md

### Docker Release

```bash
docker build -t agentvault:v0.2.0 .
docker push agentvault:v0.2.0
```
