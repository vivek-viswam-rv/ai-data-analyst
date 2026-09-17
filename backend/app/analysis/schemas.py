"""Reports the agents produce.

Models the LLM fills directly are kept strict-schema friendly: every field is
required, optional values are `X | None`, and there are no free-form dicts.
Anything with rows or chart data is computed by a tool and attached afterwards.
"""

from typing import Literal

from pydantic import BaseModel

Severity = Literal["low", "medium", "high"]
Priority = Literal["high", "medium", "low"]
ChartType = Literal["bar", "line", "scatter", "histogram"]


# Data quality -----------------------------------------------------------------


class QualityIssue(BaseModel):
    column: str | None
    kind: str
    severity: Severity
    affected_rows: int | None
    description: str
    suggestion: str


class DataQualityReport(BaseModel):
    score: int
    summary: str
    issues: list[QualityIssue]
    cleaning_steps: list[str]


# EDA --------------------------------------------------------------------------


class Finding(BaseModel):
    title: str
    detail: str
    columns: list[str]


class EDAReport(BaseModel):
    summary: str
    findings: list[Finding]


# Statistics -------------------------------------------------------------------


class StatTestNote(BaseModel):
    """What the model writes about a test a tool already ran."""

    test_id: str
    conclusion: str
    caveats: list[str]


class StatisticsPlan(BaseModel):
    summary: str
    tests: list[StatTestNote]


class StatTest(BaseModel):
    id: str
    name: str
    columns: list[str]
    hypothesis: str
    statistic: float | None
    p_value: float | None
    effect_size: float | None
    effect_size_name: str | None
    conclusion: str
    caveats: list[str]


class StatisticsReport(BaseModel):
    summary: str
    tests: list[StatTest]


# Anomalies --------------------------------------------------------------------


class AnomalyNote(BaseModel):
    group_id: str
    interpretation: str


class AnomalyPlan(BaseModel):
    summary: str
    groups: list[AnomalyNote]


class AnomalyGroup(BaseModel):
    id: str
    method: str
    columns: list[str]
    count: int
    description: str
    interpretation: str
    example_columns: list[str]
    example_rows: list[list[str]]


class AnomalyReport(BaseModel):
    summary: str
    total_flagged: int
    groups: list[AnomalyGroup]


# Charts -----------------------------------------------------------------------


class ChartNote(BaseModel):
    chart_id: str
    caption: str


class VisualizationPlan(BaseModel):
    summary: str
    charts: list[ChartNote]


class ChartSpec(BaseModel):
    id: str
    type: ChartType
    title: str
    caption: str
    x_key: str
    x_label: str
    y_label: str
    series: list[str]
    data: list[dict[str, float | str | None]]


class VisualizationReport(BaseModel):
    summary: str
    charts: list[ChartSpec]


# Interpretation ---------------------------------------------------------------


class Recommendation(BaseModel):
    title: str
    detail: str
    priority: Priority


class InterpretationReport(BaseModel):
    executive_summary: str
    key_insights: list[str]
    recommendations: list[Recommendation]
    open_questions: list[str]
    limitations: list[str]


class AgentError(BaseModel):
    agent: str
    message: str
