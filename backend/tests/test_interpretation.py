import pandas as pd

from app.analysis.agents.interpretation import digest
from app.analysis.profiling import build_brief
from app.analysis.schemas import (
    AgentError,
    AnomalyGroup,
    AnomalyReport,
    ChartSpec,
    DataQualityReport,
    EDAReport,
    Finding,
    QualityIssue,
    StatisticsReport,
    StatTest,
    VisualizationReport,
)


def _brief():
    df = pd.DataFrame(
        {
            "customer_id": range(1, 6),
            "revenue": [10.0, 20.0, 30.0, 40.0, 50.0],
            "region": ["North", "South", "North", "East", "West"],
        }
    )
    return build_brief(df, "customers.csv")


def _quality():
    return DataQualityReport(
        score=72,
        summary="A few nulls and a duplicate row.",
        issues=[
            QualityIssue(
                column="revenue",
                kind="missing_values",
                severity="medium",
                affected_rows=3,
                description="revenue has 3 missing values",
                suggestion="Impute or drop the missing rows.",
            )
        ],
        cleaning_steps=["Drop duplicate rows."],
    )


def _eda():
    return EDAReport(
        summary="Revenue varies a lot by region.",
        findings=[
            Finding(
                title="North leads revenue",
                detail="North has the highest average revenue.",
                columns=["region", "revenue"],
            ),
            Finding(
                title="Revenue is right-skewed",
                detail="A few large orders pull the average up.",
                columns=["revenue"],
            ),
        ],
    )


def _stats():
    return StatisticsReport(
        summary="Region is associated with revenue.",
        tests=[
            StatTest(
                id="t1",
                name="ANOVA",
                columns=["region", "revenue"],
                hypothesis="Revenue differs by region.",
                statistic=4.2,
                p_value=0.01,
                effect_size=0.3,
                effect_size_name="eta squared",
                conclusion="Revenue differs significantly by region.",
                caveats=["Observational data."],
            )
        ],
    )


def _anomalies():
    return AnomalyReport(
        summary="A handful of unusually large orders.",
        total_flagged=2,
        groups=[
            AnomalyGroup(
                id="g1",
                method="z-score",
                columns=["revenue"],
                count=2,
                description="Two rows have revenue far above the mean.",
                interpretation="Likely large bulk orders.",
                example_columns=["customer_id", "revenue"],
                example_rows=[["3", "9000"]],
            )
        ],
    )


def _charts():
    return VisualizationReport(
        summary="One chart of revenue by region.",
        charts=[
            ChartSpec(
                id="c1",
                type="bar",
                title="Revenue by region",
                caption="North has the highest total revenue among all regions.",
                x_key="region",
                x_label="Region",
                y_label="Revenue",
                series=["revenue"],
                data=[{"region": "North", "revenue": 40.0}],
            )
        ],
    )


def _errors():
    return [AgentError(agent="statistics", message="timed out after 120s")]


def test_digest_includes_goal_and_columns():
    text = digest(
        _brief(),
        "Which region drives the most revenue?",
        _quality(),
        _eda(),
        _stats(),
        _anomalies(),
        _charts(),
        _errors(),
    )
    assert "Which region drives the most revenue?" in text
    for col in ("customer_id", "revenue", "region"):
        assert col in text


def test_digest_includes_quality_issue_description():
    text = digest(_brief(), None, _quality(), None, None, None, None, [])
    assert "revenue has 3 missing values" in text


def test_digest_includes_finding_titles():
    text = digest(_brief(), None, None, _eda(), None, None, None, [])
    assert "North leads revenue" in text
    assert "Revenue is right-skewed" in text


def test_digest_includes_anomaly_count_and_chart_caption():
    text = digest(_brief(), None, None, None, None, _anomalies(), _charts(), [])
    assert "2 rows" in text
    assert "North has the highest total revenue among all regions." in text


def test_digest_includes_failed_agent_name():
    text = digest(_brief(), None, None, None, None, None, None, _errors())
    assert "statistical testing" in text
    assert "timed out after 120s" in text


def test_digest_marks_missing_reports_as_not_available():
    text = digest(_brief(), None, None, None, None, None, None, [])
    assert "not available" in text
