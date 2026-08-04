.PHONY: dev dev-backend dev-frontend dev-node install-backend install-backend-pg install-frontend install-node build docker-up docker-up-pg docker-up-node docker-down clean

# Development
dev: install-backend install-frontend
	@echo "Starting backend and frontend..."
	@cd server && uv run python main.py &
	@cd web && npm run dev
	@wait

dev-backend: install-backend
	cd server && uv run python main.py

dev-frontend: install-frontend
	cd web && npm run dev

dev-node: install-node
	cd node && uv run python main.py

# Install dependencies
install-backend:
	cd server && uv sync

install-backend-pg:
	cd server && uv sync --extra postgres

install-frontend:
	cd web && npm install

install-node:
	cd node && uv sync

# Build
build: install-frontend
	cd web && npm run build

# Docker (SQLite)
docker-up:
	docker compose up -d --build

# Docker (PostgreSQL)
docker-up-pg:
	docker compose -f docker-compose.pg.yml up -d --build

# Docker (Node client)
docker-up-node:
	docker compose -f docker-compose.node.yml up -d --build

docker-down:
	docker compose down
	docker compose -f docker-compose.pg.yml down 2>/dev/null || true
	docker compose -f docker-compose.node.yml down 2>/dev/null || true

# Clean
clean:
	rm -rf web/dist web/node_modules
	rm -rf server/__pycache__ server/**/__pycache__ server/.venv
	rm -rf node/__pycache__ node/**/__pycache__ node/.venv
	rm -rf data/*.db
