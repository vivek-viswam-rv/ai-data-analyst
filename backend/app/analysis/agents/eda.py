"""The EDA agent: explores a dataset with tools and writes up findings."""

from pathlib import Path

import pandas as pd
from langchain_core.language_models import BaseChatModel

from app.analysis.agents.base import run_agent, worker_model
from app.analysis.profiling import DatasetBrief
from app.analysis.schemas import EDAReport
from app.analysis.tools.eda import build_tools

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "eda.md").read_text()

MAX_FINDINGS = 8


def user_message(brief: DatasetBrief, goal: str | None) -> str:
    """Build the human message: the dataset brief plus an optional analysis goal."""
    parts = [brief.to_prompt()]
    if goal:
        parts.append(f"\nAnalysis goal: {goal}")
    return "\n".join(parts)


async def run(
    df: pd.DataFrame,
    brief: DatasetBrief,
    goal: str | None = None,
    model: BaseChatModel | None = None,
) -> EDAReport:
    """Run the EDA agent over `df` and return a validated, cleaned-up EDAReport."""
    tools = build_tools(df)
    report = await run_agent(
        name="eda",
        model=model or worker_model(),
        system_prompt=PROMPT,
        tools=tools,
        response_format=EDAReport,
        user_message=user_message(brief, goal),
        max_tool_calls=12,
    )
    return _postprocess(report, df)


def _postprocess(report: EDAReport, df: pd.DataFrame) -> EDAReport:
    """Keep at most MAX_FINDINGS findings; drop/fix column names that don't exist in df."""
    lower_to_actual = {str(c).lower(): str(c) for c in df.columns}
    findings = []
    for finding in report.findings[:MAX_FINDINGS]:
        fixed_columns = []
        for col in finding.columns:
            if col in df.columns:
                fixed_columns.append(col)
            elif col.lower() in lower_to_actual:
                fixed_columns.append(lower_to_actual[col.lower()])
            # else: drop the bogus column name
        findings.append(finding.model_copy(update={"columns": fixed_columns}))
    return report.model_copy(update={"findings": findings})
