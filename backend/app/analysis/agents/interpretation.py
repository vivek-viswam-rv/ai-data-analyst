"""The interpretation agent: turns every other agent's report into a business narrative.

Runs no tools of its own — it only reads the briefing built from the other
agents' reports and writes an executive summary, insights, recommendations,
open questions and limitations for someone who has not seen the data.
"""

from collections.abc import Sequence
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from app.analysis.agents.base import interpreter_model, run_agent
from app.analysis.profiling import DatasetBrief
from app.analysis.schemas import (
    AgentError,
    AnomalyReport,
    DataQualityReport,
    EDAReport,
    InterpretationReport,
    StatisticsReport,
    VisualizationReport,
)

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "interpretation.md").read_text()

_MAX_ITEMS = 12
_NOT_AVAILABLE = "not available (the agent failed or was skipped)"
_LABELS = {
    "data_quality": "data quality",
    "eda": "exploratory analysis",
    "statistics": "statistical testing",
    "anomaly": "anomaly detection",
    "visualization": "charts",
}


def digest(
    brief: DatasetBrief,
    goal: str | None,
    quality: DataQualityReport | None,
    eda: EDAReport | None,
    stats: StatisticsReport | None,
    anomalies: AnomalyReport | None,
    charts: VisualizationReport | None,
    errors: list[AgentError],
) -> str:
    """Render a compact plain-text briefing for the interpretation model."""
    sections: list[str] = []
    if goal:
        sections.append(f"Goal: {goal}")
    sections.append(brief.to_prompt())
    sections.append(_quality_section(quality))
    sections.append(_eda_section(eda))
    sections.append(_stats_section(stats))
    sections.append(_anomaly_section(anomalies))
    sections.append(_charts_section(charts))
    sections.append(_errors_section(errors))
    return "\n\n".join(sections)


def _quality_section(quality: DataQualityReport | None) -> str:
    if quality is None:
        return f"Data quality: {_NOT_AVAILABLE}"
    lines = [f"Data quality (score {quality.score}/100): {quality.summary}"]
    for issue in quality.issues[:_MAX_ITEMS]:
        column = issue.column or "dataset-level"
        lines.append(f"- [{issue.severity}] {column}: {issue.description}")
    return "\n".join(lines)


def _eda_section(eda: EDAReport | None) -> str:
    if eda is None:
        return f"EDA: {_NOT_AVAILABLE}"
    lines = [f"EDA: {eda.summary}"]
    for finding in eda.findings[:_MAX_ITEMS]:
        lines.append(f"- {finding.title}: {finding.detail}")
    return "\n".join(lines)


def _stats_section(stats: StatisticsReport | None) -> str:
    if stats is None:
        return f"Statistics: {_NOT_AVAILABLE}"
    lines = [f"Statistics: {stats.summary}"]
    for test in stats.tests[:_MAX_ITEMS]:
        columns = ", ".join(test.columns)
        p = "n/a" if test.p_value is None else f"{test.p_value:.4g}"
        effect = "n/a" if test.effect_size is None else f"{test.effect_size:.4g}"
        lines.append(f"- {test.name} on {columns}: {test.conclusion} (p={p}, effect={effect})")
    return "\n".join(lines)


def _anomaly_section(anomalies: AnomalyReport | None) -> str:
    if anomalies is None:
        return f"Anomalies: {_NOT_AVAILABLE}"
    lines = [f"Anomalies: {anomalies.summary} (total flagged: {anomalies.total_flagged})"]
    for group in anomalies.groups[:_MAX_ITEMS]:
        columns = ", ".join(group.columns)
        lines.append(f"- {group.method} on {columns}: {group.count} rows. {group.interpretation}")
    return "\n".join(lines)


def _charts_section(charts: VisualizationReport | None) -> str:
    if charts is None:
        return f"Charts: {_NOT_AVAILABLE}"
    lines = [f"Charts: {charts.summary}"]
    for chart in charts.charts[:_MAX_ITEMS]:
        lines.append(f"- {chart.caption}")
    return "\n".join(lines)


def _errors_section(errors: list[AgentError]) -> str:
    if not errors:
        return "Sections that failed: none"
    lines = ["Sections that failed:"]
    for error in errors:
        lines.append(f"- {_LABELS.get(error.agent, error.agent)}: {error.message}")
    return "\n".join(lines)


async def run(
    brief: DatasetBrief,
    goal: str | None = None,
    quality: DataQualityReport | None = None,
    eda: EDAReport | None = None,
    stats: StatisticsReport | None = None,
    anomalies: AnomalyReport | None = None,
    charts: VisualizationReport | None = None,
    errors: Sequence[AgentError] = (),
    model: BaseChatModel | None = None,
) -> InterpretationReport:
    errors = list(errors)
    report = await run_agent(
        name="interpretation",
        model=model or interpreter_model(),
        system_prompt=PROMPT,
        tools=[],
        response_format=InterpretationReport,
        user_message=digest(brief, goal, quality, eda, stats, anomalies, charts, errors),
        max_tool_calls=0,
        max_model_calls=3,
        timeout_s=120,
    )
    report.key_insights = report.key_insights[:8]
    report.recommendations = report.recommendations[:6]
    report.open_questions = report.open_questions[:6]
    report.limitations = _ensure_failures_named(report.limitations[:8], errors)
    return report


def _ensure_failures_named(limitations: list[str], errors: list[AgentError]) -> list[str]:
    """Make sure every failed section is named in limitations, even if the model forgot."""
    missing = [
        e
        for e in errors
        if not any(_LABELS.get(e.agent, e.agent) in line.lower() for line in limitations)
    ]
    if not missing:
        return limitations
    forced = [
        f"The {_LABELS.get(e.agent, e.agent)} section failed and was not available: {e.message}"
        for e in missing
    ]
    kept = limitations[: max(0, 8 - len(forced))]
    return kept + forced
