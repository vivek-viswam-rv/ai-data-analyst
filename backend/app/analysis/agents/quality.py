"""Data quality agent: runs the quality tools and produces a DataQualityReport."""

from pathlib import Path

import pandas as pd
from langchain_core.language_models import BaseChatModel

from app.analysis.agents.base import run_agent, worker_model
from app.analysis.profiling import DatasetBrief
from app.analysis.schemas import DataQualityReport
from app.analysis.tools.quality import build_tools

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "quality.md").read_text()


def user_message(brief: DatasetBrief, goal: str | None) -> str:
    parts = [brief.to_prompt()]
    if goal:
        parts.append(f"\nAnalysis goal: {goal}")
    return "\n".join(parts)


async def run(
    df: pd.DataFrame,
    brief: DatasetBrief,
    goal: str | None = None,
    model: BaseChatModel | None = None,
) -> DataQualityReport:
    tools = build_tools(df)
    report = await run_agent(
        name="data_quality",
        model=model or worker_model(),
        system_prompt=PROMPT,
        tools=tools,
        response_format=DataQualityReport,
        user_message=user_message(brief, goal),
        max_tool_calls=12,
    )
    report.score = max(0, min(100, report.score))

    columns_lower = {str(c).lower(): str(c) for c in df.columns}
    fixed_issues = []
    for issue in report.issues:
        if issue.column is None or issue.column in df.columns:
            fixed_issues.append(issue)
        elif issue.column.lower() in columns_lower:
            issue.column = columns_lower[issue.column.lower()]
            fixed_issues.append(issue)
        # else: the column doesn't exist even case-insensitively — drop the issue
    report.issues = fixed_issues

    return report
