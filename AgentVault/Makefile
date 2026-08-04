.PHONY: dev dev-backend dev-frontend install-backend install-backend-pg install-frontend build docker-up docker-up-pg docker-down clean

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

# Install dependencies
install-backend:
	cd server && uv sync

install-backend-pg:
	cd server && uv sync --extra postgres

install-frontend:
	cd web && npm install

# Build
build: install-frontend
	cd web && npm run build

# Docker (SQLite)
docker-up:
	docker compose up -d --build

# Docker (PostgreSQL)
docker-up-pg:
	docker compose -f docker-compose.pg.yml up -d --build

docker-down:
	docker compose down
	docker compose -f docker-compose.pg.yml down 2>/dev/null || true

# Clean
clean:
	rm -rf web/dist web/node_modules
	rm -rf server/__pycache__ server/**/__pycache__
	rm -rf server/.venv
	rm -rf data/*.db
