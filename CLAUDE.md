# Wheel

Minimal starter template for FastAPI + React apps. No database, no auth — just
the wiring between backend and frontend, demonstrated by one example endpoint.

## Commands

- All-in-one: `make setup`, `make dev` (honcho + Procfile.dev, both servers), `make lint`
- Backend: `uv sync`, `uv run fastapi dev app/main.py`, `uv run ruff check .`
- Frontend: `pnpm install`, `pnpm dev`, `pnpm lint`, `pnpm build`
- Env: `cp env.sample .env`

## Layout

- `app/` FastAPI. `main.py` app factory, `config.py` pydantic-settings,
  `schemas.py` pydantic models, `routers/` one file per resource registered in `ROUTERS`.
- `ui/src/` React. `apis/` axios calls per resource, `hooks/reactQuery/` TanStack Query wrappers,
  `components/<Feature>/` pages, `components/shadcn/` generated UI primitives,
  `components/routeConstants.jsx` route paths + ROUTES array, `utils/`, `constants/`.

## Conventions

- Python: `Annotated[...]` for deps and field constraints, routers use `APIRouter(prefix=...)`.
- JS: JSX not TSX, double quotes, semicolons, trailing commas (ESLint enforces).
  Import through aliases (`apis/`, `hooks/`, `shadcn/`, `utils/`, `constants/`, `components/`).
  Toasts via sonner from the axios error interceptor.
- Add a resource: schema in `app/schemas.py` -> router in `app/routers/` + `ROUTERS` ->
  `ui/src/apis/<resource>.js` -> hook in `ui/src/hooks/reactQuery/` -> component + route.
