"""The anomaly agent: runs anomaly-detection tools, then assembles the final report."""

from pathlib import Path

import pandas as pd

from app.analysis.agents.base import run_agent, worker_model
from app.analysis.profiling import DatasetBrief
from app.analysis.schemas import AnomalyGroup, AnomalyPlan, AnomalyReport
from app.analysis.tools.anomaly import build_tools
from app.analysis.tools.common import ArtifactStore

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "anomaly.md").read_text()


def user_message(brief: DatasetBrief, goal: str | None = None) -> str:
    goal_text = goal.strip() if goal and goal.strip() else "No specific analysis goal was given."
    return (
        f"{brief.to_prompt()}\n\n"
        f"Analysis goal: {goal_text}\n\n"
        "Run the anomaly-detection tools on the columns that matter most for this "
        "dataset and goal, then report the groups you found with an interpretation "
        "for each."
    )


def assemble(
    plan: AnomalyPlan, store: ArtifactStore, flagged: dict[str, set[int]]
) -> AnomalyReport:
    """Turn the model's plan plus the store's registered groups into the final report."""
    registered = dict(store.items("group"))
    seen: set[str] = set()
    mentioned: list[AnomalyGroup] = []

    for note in plan.groups:
        if note.group_id in seen:
            continue
        group = registered.get(note.group_id)
        if not isinstance(group, AnomalyGroup):
            continue
        mentioned.append(group.model_copy(update={"interpretation": note.interpretation}))
        seen.add(note.group_id)

    unmentioned: list[AnomalyGroup] = []
    for key, group in registered.items():
        if key in seen:
            continue
        unmentioned.append(
            group.model_copy(
                update={"interpretation": f"Flagged by {group.method}; not discussed."}
            )
        )

    kept = [g for g in (*mentioned, *unmentioned) if g.count > 0]
    total_flagged = len(set().union(*[flagged.get(g.id, set()) for g in kept])) if kept else 0

    return AnomalyReport(summary=plan.summary, total_flagged=total_flagged, groups=kept)


async def run(
    df: pd.DataFrame, brief: DatasetBrief, goal: str | None = None, model=None
) -> AnomalyReport:
    store = ArtifactStore()
    tools, flagged = build_tools(df, store, brief.id_columns)
    plan = await run_agent(
        name="anomaly",
        model=model or worker_model(),
        system_prompt=PROMPT,
        tools=tools,
        response_format=AnomalyPlan,
        user_message=user_message(brief, goal),
        max_tool_calls=12,
    )
    return assemble(plan, store, flagged)
