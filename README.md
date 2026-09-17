# Wheel

Wheel is a minimal starter template for FastAPI + React apps. It ships with no
database and no authentication — just the wiring between a FastAPI backend and a
React frontend, demonstrated by one trivial example endpoint. Build on top of it.

## Stack

| Layer    | Technology |
|----------|------------|
| Backend  | FastAPI |
| Backend  | Pydantic Settings |
| Backend  | uv |
| Backend  | ruff |
| Frontend | React 19 |
| Frontend | Vite 7 |
| Frontend | Tailwind CSS v4 |
| Frontend | shadcn/ui |
| Frontend | TanStack Query |
| Frontend | Axios |
| Frontend | Ramda |
| Frontend | react-router-dom |
| Frontend | Sonner |
| Frontend | pnpm |
| Frontend | ESLint + Prettier |

## Getting started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node 22+
- pnpm

### Setup

```bash
make setup        # uv sync, pnpm install, copies env.sample to .env
```

### Run

```bash
make dev          # honcho runs Procfile.dev: FastAPI on :8000 and Vite on :5173
```

`make dev` wraps `uv run honcho -f Procfile.dev start`. Run one side alone with
`make backend` or `make frontend`.

In dev, Vite proxies `/api` requests to `http://localhost:8000`, so `VITE_API_URL`
can be left empty locally — the frontend just calls `/api/...` and Vite forwards it
to the backend.

## Project layout

```
app/
├── __init__.py
├── config.py                  # pydantic-settings Settings
├── main.py                    # create_app() factory, CORS, router registration
├── schemas.py                 # pydantic request/response models
└── routers/
    ├── __init__.py             # ROUTERS list included by main.py
    └── greetings.py            # example GET /greetings endpoint

ui/
├── index.html
├── public/
│   └── favicon.svg
├── stylesheets/                # custom Tailwind classes
└── src/
    ├── main.jsx                # entry: QueryClientProvider, Toaster, axios interceptors
    ├── index.css               # Tailwind + shadcn theme tokens
    ├── apis/                   # axios calls per resource (e.g. greetings.js)
    ├── components/
    │   ├── App.jsx             # router
    │   ├── routeConstants.jsx  # route paths + ROUTES array
    │   ├── Home/               # example page calling GET /api/greetings
    │   ├── commons/            # NotFound
    │   └── shadcn/             # generated UI primitives (button, empty, sonner)
    ├── constants/              # query keys
    ├── hooks/reactQuery/       # TanStack Query hooks per resource
    ├── lib/                    # cn() helper
    └── utils/                  # queryClient, ramda helpers
```

## API

| Method | Path                    | Description                    |
|--------|-------------------------|---------------------------------|
| GET    | `/health`               | Health check                    |
| GET    | `/api/greetings?name=`  | Example endpoint, returns a greeting |

## Linting

```bash
make lint         # uv run ruff check . && pnpm lint
```

## Adding a resource

1. Add a schema in `app/schemas.py`.
2. Add a router in `app/routers/` and register it in `ROUTERS` (`app/routers/__init__.py`).
3. Add `ui/src/apis/<resource>.js` for the API call.
4. Add a hook in `ui/src/hooks/reactQuery`.
5. Add a component and route in `ui/src/components/routeConstants.jsx`.

## Deploying

The two halves deploy separately.

- **Frontend on Vercel**: import the repo; `vercel.json` sets the build command,
  output directory (`dist/`) and the SPA rewrite. Set `VITE_API_URL` to the
  backend's public URL in the Vercel project's environment variables.
- **Backend anywhere that runs a container** (Render, Fly.io, Railway, ECS): use the
  included `Dockerfile`. Set `FRONTEND_URL` to the Vercel domain so CORS allows it.

Vercel does not run the FastAPI server as configured. Hosting it there would mean
converting it to a Vercel Python serverless function, which is out of scope for this
template.

## Using as a template

1. Clone this repository.
2. Rename `name` in `pyproject.toml` and in `package.json`.
3. Update `APP_NAME` in your `.env`.
