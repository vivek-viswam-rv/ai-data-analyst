"""The team, wired up.

    profile -> [data_quality, eda] -> visualization -> interpretation

Data quality and EDA run in the same LangGraph superstep, so they execute
concurrently. A failing agent records an error and the rest carry on; the
interpreter is told what is missing.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.analysis.agents import eda, interpretation, quality, visualization
from app.analysis.schemas import AgentError
from app.analysis.state import REPORT_KEYS, AnalysisContext, AnalysisState

log = logging.getLogger(__name__)


def _node(
    name: str, work: Callable[[AnalysisState, AnalysisContext], Awaitable[Any]]
) -> Callable[[AnalysisState, Runtime[AnalysisContext]], Awaitable[dict[str, Any]]]:
    key = REPORT_KEYS[name]

    async def node(state: AnalysisState, runtime: Runtime[AnalysisContext]) -> dict[str, Any]:
        writer = get_stream_writer()
        writer({"event": "agent_started", "agent": name})
        try:
            report = await work(state, runtime.context)
        except Exception as exc:  # one agent failing must not sink the run
            log.exception("%s failed", name)
            message = str(exc) or type(exc).__name__
            writer({"event": "agent_failed", "agent": name, "message": message})
            return {key: None, "errors": [AgentError(agent=name, message=message)]}
        writer({"event": "agent_finished", "agent": name, "report": report})
        return {key: report}

    node.__name__ = name
    return node


async def _quality(state: AnalysisState, ctx: AnalysisContext):
    return await quality.run(ctx.df, state["brief"], state.get("goal"), model=ctx.worker)


async def _eda(state: AnalysisState, ctx: AnalysisContext):
    return await eda.run(ctx.df, state["brief"], state.get("goal"), model=ctx.worker)


async def _visualization(state: AnalysisState, ctx: AnalysisContext):
    return await visualization.run(
        ctx.df,
        state["brief"],
        state.get("goal"),
        eda=state.get("eda"),
        model=ctx.worker,
    )


async def _interpretation(state: AnalysisState, ctx: AnalysisContext):
    return await interpretation.run(
        state["brief"],
        state.get("goal"),
        quality=state.get("quality"),
        eda=state.get("eda"),
        charts=state.get("charts"),
        errors=state.get("errors", []),
        model=ctx.interpreter,
    )


def build_graph():
    g = StateGraph(AnalysisState, context_schema=AnalysisContext)
    g.add_node("data_quality", _node("data_quality", _quality))
    g.add_node("eda", _node("eda", _eda))
    g.add_node("visualization", _node("visualization", _visualization))
    g.add_node("interpretation", _node("interpretation", _interpretation))

    for name in ("data_quality", "eda"):
        g.add_edge(START, name)
        g.add_edge(name, "visualization")
    g.add_edge("visualization", "interpretation")
    g.add_edge("interpretation", END)
    return g.compile()


graph = build_graph()
