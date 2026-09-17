.PHONY: setup dev backend frontend lint build clean

# Install everything and create .env if missing.
setup:
	cd backend && uv sync
	cd frontend && pnpm install
	@test -f .env || cp env.sample .env

# Start backend (:8000) and frontend (:5173) together via honcho. Ctrl+C stops both.
dev:
	-cd backend && uv run honcho -f ../Procfile.dev start

backend:
	cd backend && uv run fastapi dev app/main.py --port 8000

frontend:
	cd frontend && pnpm dev

lint:
	cd backend && uv run ruff check .
	cd frontend && pnpm lint

build:
	cd frontend && pnpm build

clean:
	rm -rf frontend/dist backend/.ruff_cache
	find . -name __pycache__ -type d -prune -not -path '*/.venv/*' -not -path '*/node_modules/*' -exec rm -rf {} +
