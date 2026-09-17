"""The statistics agent: runs stats tools, then assembles the final report."""

from pathlib import Path

import pandas as pd

from app.analysis.agents.base import run_agent, worker_model
from app.analysis.profiling import DatasetBrief
from app.analysis.schemas import StatisticsPlan, StatisticsReport, StatTest
from app.analysis.tools.common import ArtifactStore
from app.analysis.tools.stats import build_tools

PROMPT = (Path(__file__).parent.parent / "prompts" / "statistics.md").read_text()


def user_message(brief: DatasetBrief, goal: str | None) -> str:
    goal_text = goal.strip() if goal and goal.strip() else "No specific analysis goal was given."
    return (
        f"{brief.to_prompt()}\n\n"
        f"Analysis goal: {goal_text}\n\n"
        "Pick a handful of statistical tests that matter for this dataset and goal, "
        "run them with the tools, and report your findings."
    )


def assemble(plan: StatisticsPlan, store: ArtifactStore) -> StatisticsReport:
    seen: set[str] = set()
    mentioned: list[StatTest] = []

    for note in plan.tests:
        if note.test_id in seen:
            continue
        if not store.has(note.test_id):
            continue
        test: StatTest = store.get(note.test_id)
        updated = test.model_copy(
            update={
                "conclusion": note.conclusion,
                "caveats": [*test.caveats, *note.caveats],
            }
        )
        mentioned.append(updated)
        seen.add(note.test_id)

    unmentioned: list[StatTest] = []
    for key, test in store.items("test"):
        if key in seen:
            continue
        unmentioned.append(_auto_conclusion(test))

    return StatisticsReport(summary=plan.summary, tests=[*mentioned, *unmentioned])


def _auto_conclusion(test: StatTest) -> StatTest:
    if test.p_value is not None and test.p_value < 0.05:
        conclusion = f"p = {test.p_value:.3g}, significant at the 5% level"
    elif test.p_value is not None:
        conclusion = f"p = {test.p_value:.3g}, not significant"
    else:
        conclusion = "No p-value available for this test."
    return test.model_copy(update={"conclusion": conclusion})


async def run(
    df: pd.DataFrame, brief: DatasetBrief, goal: str | None = None, model=None
) -> StatisticsReport:
    store = ArtifactStore()
    tools = build_tools(df, store)
    plan = await run_agent(
        name="statistics",
        model=model or worker_model(),
        system_prompt=PROMPT,
        tools=tools,
        response_format=StatisticsPlan,
        user_message=user_message(brief, goal),
        max_tool_calls=10,
    )
    return assemble(plan, store)
