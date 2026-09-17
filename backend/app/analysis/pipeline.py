"""Entry points the API calls: prepare a dataset, then stream an analysis."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import pandas as pd

from app.analysis.graph import graph
from app.analysis.loaders import load_dataframe, sample_rows
from app.analysis.profiling import DatasetBrief, build_brief, coerce_types
from app.analysis.schemas import AgentError
from app.analysis.state import AGENT_ORDER, REPORT_KEYS, AnalysisContext, AnalysisState
from app.config import settings

log = logging.getLogger(__name__)


def prepare(filename: str, data: bytes) -> tuple[pd.DataFrame, DatasetBrief]:
    """Load, type-coerce and (if needed) sample an upload. Raises LoadError."""
    raw = load_dataframe(filename, data)
    original_rows = len(raw)
    df, _ = sample_rows(raw, settings.max_rows)
    df = coerce_types(df)
    return df, build_brief(df, filename, original_rows=original_rows)


async def stream_analysis(
    df: pd.DataFrame,
    brief: DatasetBrief,
    goal: str | None = None,
    context: AnalysisContext | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield progress events, then a final `done` event carrying every report."""
    yield {"event": "brief", "brief": brief, "agents": AGENT_ORDER}

    state: AnalysisState = {
        "filename": brief.filename,
        "goal": goal or None,
        "brief": brief,
        "errors": [],
    }
    ctx = context or AnalysisContext(df=df)
    final: dict[str, Any] = {}
    errors: list[AgentError] = []

    async for mode, chunk in graph.astream(state, context=ctx, stream_mode=["updates", "custom"]):
        if mode == "custom":
            yield chunk
        elif mode == "updates":
            for update in chunk.values():
                errors.extend(update.pop("errors", []))
                final.update(update)

    reports = {REPORT_KEYS[name]: final.get(REPORT_KEYS[name]) for name in AGENT_ORDER}
    yield {"event": "done", "reports": reports, "errors": errors}
