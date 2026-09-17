.PHONY: setup dev backend frontend lint build clean

# Install everything and create .env if missing.
setup:
	uv sync
	pnpm install
	@test -f .env || cp env.sample .env

# Start backend (:8000) and frontend (:5173) together via honcho. Ctrl+C stops both.
dev:
	-uv run honcho -f Procfile.dev start

backend:
	uv run fastapi dev app/main.py --port 8000

frontend:
	pnpm dev

lint:
	uv run ruff check .
	pnpm lint

build:
	pnpm build

clean:
	rm -rf dist .ruff_cache
	find . -name __pycache__ -type d -prune -not -path './.venv/*' -not -path './node_modules/*' -exec rm -rf {} +
