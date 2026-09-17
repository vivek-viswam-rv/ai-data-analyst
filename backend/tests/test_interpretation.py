import pandas as pd

from app.analysis.agents.interpretation import digest
from app.analysis.profiling import build_brief
from app.analysis.schemas import (
    AgentError,
    ChartSpec,
    DataQualityReport,
    DistributionSummary,
    EDAReport,
    Finding,
    QualityIssue,
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
        distributions=[
            DistributionSummary(
                column="revenue",
                shape="right_skewed",
                detail="Median revenue is $20 with a long tail from a few very large orders.",
            )
        ],
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
    return [AgentError(agent="eda", message="timed out after 120s")]


def test_digest_includes_goal_and_columns():
    text = digest(_brief(), "Why is revenue down?", _quality(), _eda(), _charts(), [])
    assert "Why is revenue down?" in text
    for column in ("customer_id", "revenue", "region"):
        assert column in text


def test_digest_includes_quality_issue():
    text = digest(_brief(), None, _quality(), None, None, [])
    assert "score 72/100" in text
    assert "revenue has 3 missing values" in text


def test_digest_includes_finding_titles():
    text = digest(_brief(), None, None, _eda(), None, [])
    assert "North leads revenue" in text
    assert "Revenue is right-skewed" in text


def test_digest_includes_distribution_detail():
    text = digest(_brief(), None, None, _eda(), None, [])
    assert "revenue is right skewed" in text
    assert "Median revenue is $20 with a long tail from a few very large orders." in text


def test_digest_includes_chart_caption():
    text = digest(_brief(), None, None, None, _charts(), [])
    assert "North has the highest total revenue among all regions." in text


def test_digest_includes_failed_agent_name():
    text = digest(_brief(), None, None, None, None, _errors())
    assert "exploratory analysis" in text
    assert "timed out after 120s" in text


def test_digest_marks_missing_reports_as_not_available():
    text = digest(_brief(), None, None, None, None, [])
    assert "not available" in text
