"""Visualization agent: builds chart data with tools and picks/captions charts."""

from pathlib import Path

import pandas as pd
from langchain_core.language_models import BaseChatModel

from app.analysis.agents.base import run_agent, worker_model
from app.analysis.profiling import DatasetBrief
from app.analysis.schemas import EDAReport, VisualizationPlan, VisualizationReport
from app.analysis.tools.charts import build_tools
from app.analysis.tools.common import ArtifactStore

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "visualization.md").read_text()

MAX_CHARTS = 6


def user_message(
    brief: DatasetBrief,
    goal: str | None,
    eda: EDAReport | None,
) -> str:
    """Build the human message: brief, optional goal and the EDA findings."""
    parts = [brief.to_prompt()]
    if goal:
        parts.append(f"\nGoal: {goal}")
    if eda is not None:
        lines = ["\nEDA findings:"]
        for i, finding in enumerate(eda.findings, start=1):
            lines.append(f"{i}. {finding.title}: {finding.detail}")
        parts.append("\n".join(lines))
    return "\n".join(parts)


def assemble(plan: VisualizationPlan, store: ArtifactStore) -> VisualizationReport:
    """Join the model's chart picks with the ArtifactStore into the final report."""
    charts = []
    used_ids: set[str] = set()
    for note in plan.charts:
        if len(charts) >= MAX_CHARTS:
            break
        if not store.has(note.chart_id) or note.chart_id in used_ids:
            continue
        spec = store.get(note.chart_id)
        if len(spec.data) == 0:
            continue
        used_ids.add(note.chart_id)
        caption = note.caption.strip() or spec.title
        charts.append(spec.model_copy(update={"caption": caption}))
    return VisualizationReport(summary=plan.summary, charts=charts)


async def run(
    df: pd.DataFrame,
    brief: DatasetBrief,
    goal: str | None = None,
    eda: EDAReport | None = None,
    model: BaseChatModel | None = None,
) -> VisualizationReport:
    """Run the visualization agent over `df` and return a validated VisualizationReport."""
    store = ArtifactStore()
    tools = build_tools(df, store)
    msg = user_message(brief, goal, eda)
    plan = await run_agent(
        name="visualization",
        model=model or worker_model(),
        system_prompt=PROMPT,
        tools=tools,
        response_format=VisualizationPlan,
        user_message=msg,
        max_tool_calls=10,
    )
    return assemble(plan, store)
