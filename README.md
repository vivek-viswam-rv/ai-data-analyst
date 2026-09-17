# AI Data Analyst

Live at https://ai-data-analyst-vivek.vercel.app

Upload a CSV or Excel file and a small team of agents works through it the way
an analyst would: check the data, explore how every measure is distributed,
draw the charts that show it, and write a summary a manager can read. Each
agent has its own tools and its own report, and the results stream into the
browser as they finish.

The whole thing deploys to a single Vercel project. There is no database and
nothing is stored server-side: a run lives for the length of one request.

## How it works

```
upload -> profile -> data quality --\
                  -> eda -----------+-> charts -> summary
```

The profile step is plain pandas. It parses dates and currency-looking
strings, classifies columns and builds a short brief. That brief, not the raw
rows, is what every agent sees.

Each agent is a tool-calling loop (LangGraph, `langchain-openai`) over a
handful of pandas functions that run on the full dataset and return small
summaries. The model decides what to call and interprets the numbers; it never
computes them. Chart data is built by a tool and registered under an id, and
the model only picks ids and writes captions, so nothing numeric passes
through it. Every agent returns a Pydantic model through strict structured
output.

Data quality and EDA run concurrently. If an agent fails, its section is
reported as missing and the summary says so.

| Agent | Model | What it does |
|---|---|---|
| Data quality | worker | Nulls, duplicates, inconsistent text, ranges, constant and id columns, cleaning steps |
| EDA | worker | Shape of every key measure (skew, tails, modes, spread), distributions by group, value counts, correlations, time trends |
| Charts | worker | Histograms, box plots, grouped and stacked bars, time series, scatter and cumulative charts as Recharts-ready specs |
| Summary | interpreter | Executive summary, insights, recommendations, open questions, limitations |

The worker model defaults to `gpt-5.6-luna` and the interpreter to
`gpt-5.6-terra`. Both are set by environment variable.

## Running locally

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22+, pnpm.

```bash
make setup          # uv sync, pnpm install, copies env.sample to .env
```

Put your key in `.env`:

```
OPENAI_API_KEY="sk-..."
```

Then:

```bash
make dev            # FastAPI on :8000 and Vite on :5173
```

Open http://localhost:5173 and drop in `examples/sales.csv`. The sample has a
few planted problems (missing units, a lowercase region, two implausible
revenues, duplicated rows) so there is something to find.

`make backend` and `make frontend` run one side at a time. `make lint` runs
ruff and eslint. Backend tests:

```bash
cd backend && uv run pytest
```

The tests never call a model. Tools are tested against a synthetic dataset,
the graph is tested with stubbed agents, and the API with FastAPI's test
client.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | |
| GET | `/api/analyses/limits` | Upload limit, row cap, model names |
| POST | `/api/analyses/preview` | multipart `file`; returns the dataset brief |
| POST | `/api/analyses` | multipart `file` and optional `goal`; streams server-sent events |

Events on the stream: `brief`, then `agent_started`, `agent_finished` or
`agent_failed` per agent, then `done` with every report. An `error` event
means the run itself died.

## Deploying to Vercel

Import the repository as one project. `vercel.json` defines two services:
the Vite build served at `/` and the FastAPI app behind `/api`. Set
`OPENAI_API_KEY` in the project's environment variables; `WORKER_MODEL` and
`INTERPRETER_MODEL` are optional overrides.

Two platform limits shape the design. Request bodies are capped at 4.5 MB, so
that is the upload limit. Functions run for at most 300 seconds on the Hobby
plan (800 on Pro), so an analysis is a single streamed request and each agent
has a hard cap on tool calls and a timeout. A run on the sample file takes
about a minute.

## Layout

```
backend/
  app/main.py            FastAPI app factory
  app/routers/           analyses endpoints
  app/analysis/
    loaders.py           CSV and Excel reading
    profiling.py         column typing and the dataset brief
    schemas.py           report models
    tools/               pandas functions each agent can call
    agents/              one module per agent, plus the shared runner
    prompts/             system prompts, one file per agent
    graph.py             LangGraph wiring
    pipeline.py          prepare an upload and stream a run
  tests/
frontend/
  ui/src/apis/           axios calls and the SSE client
  ui/src/components/     Upload and Analysis pages, chart components
examples/sales.csv
vercel.json
```

## Adding an agent

Add a tools module under `app/analysis/tools/`, a prompt under
`app/analysis/prompts/`, an agent module with a `run()` under
`app/analysis/agents/`, a report model in `schemas.py`, then register a node
and its edges in `graph.py` and a key in `state.py`. The frontend section
list in `frontend/ui/src/components/Analysis/` renders whatever reports arrive.

## Limitations

Files over 4.5 MB are rejected. Datasets above 200,000 rows are sampled
before analysis. The agents only see summaries, so questions that need
row-level reasoning across the whole table will not be answered well. Nothing
is saved: refresh the page and the run is gone, apart from a copy of the last
completed run kept in the browser's session storage.
