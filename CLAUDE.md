# ai-data-analyst

Upload a CSV or Excel file and a team of agents analyses it: data quality, EDA,
statistics, anomalies, charts and a business summary. FastAPI backend in
`backend/`, Vite + React frontend in `frontend/`, both deployed to one Vercel
project as services. No database.

## Commands

- All-in-one: `make setup`, `make dev` (both servers via honcho), `make lint`
- Backend (from `backend/`): `uv sync`, `uv run fastapi dev app/main.py`, `uv run ruff check .`, `uv run pytest`
- Frontend (from `frontend/`): `pnpm install`, `pnpm dev`, `pnpm lint`, `pnpm build`
- Env: `cp env.sample .env` at the repo root; both halves read it

## Layout

- `backend/app/` FastAPI. `main.py` app factory, `config.py` pydantic-settings,
  `schemas.py` API models, `routers/` one file per resource registered in `ROUTERS`,
  `analysis/` the agent pipeline (loaders, profiling, tools, agents, graph).
- `frontend/ui/src/` React. `apis/` axios calls, `hooks/reactQuery/` TanStack Query wrappers,
  `components/<Feature>/` pages, `components/shadcn/` generated primitives,
  `components/routeConstants.jsx` routes, `utils/`, `constants/`.
- `vercel.json` at the root defines the two services and the `/api` rewrite.

## Conventions

- Python: `Annotated[...]` for deps and field constraints, routers use `APIRouter(prefix=...)`.
- JS: JSX not TSX, double quotes, semicolons, trailing commas (ESLint enforces).
  Import through aliases (`apis/`, `hooks/`, `shadcn/`, `utils/`, `constants/`, `components/`).
  Toasts via sonner from the axios error interceptor.
- Commit messages are past tense, short, no prefixes.
