import pytest

from app.analysis.agents.anomaly import assemble
from app.analysis.profiling import coerce_types
from app.analysis.schemas import AnomalyNote, AnomalyPlan
from app.analysis.tools.anomaly import build_tools
from app.analysis.tools.common import ArtifactStore


@pytest.fixture
def built(sales_df):
    df = coerce_types(sales_df)
    store = ArtifactStore()
    tools, flagged = build_tools(df, store, ["order_id"])
    return {"df": df, "store": store, "flagged": flagged, "tools": {t.name: t for t in tools}}


def test_iqr_outliers_flags_planted_outlier(built):
    tools = built["tools"]
    result = tools["iqr_outliers"].invoke({"column": "revenue"})

    assert result["count"] >= 1
    assert result["pct"] < 5

    order_ids = {row["order_id"] for row in result["examples"]}
    assert "21" in order_ids

    group = built["store"].get(result["group_id"])
    assert group.count >= 1
    assert 20 in built["flagged"][result["group_id"]]


def test_robust_zscore_outliers_flags_planted_outlier(built):
    tools = built["tools"]
    result = tools["robust_zscore_outliers"].invoke({"column": "revenue"})

    assert result["count"] >= 1
    assert 20 in built["flagged"][result["group_id"]]


def test_multivariate_outliers_flags_planted_outlier(built):
    tools = built["tools"]
    result = tools["multivariate_outliers"].invoke({"columns": ["units", "unit_price", "revenue"]})

    assert result["count"] >= 1
    assert 20 in built["flagged"][result["group_id"]]


def test_time_series_outliers_runs_without_error(built):
    tools = built["tools"]
    result = tools["time_series_outliers"].invoke(
        {"date_column": "order_date", "value_column": "revenue", "freq": "W"}
    )

    assert "error" not in result
    assert "group_id" in result


def test_rare_categories_flags_lowercase_north(built):
    tools = built["tools"]
    result = tools["rare_categories"].invoke({"column": "region", "max_pct": 5.0})

    values = {rv["value"] for rv in result["rare_values"]}
    assert "north" in values
    assert any(row.get("region") == "north" for row in result["examples"])


def test_bad_column_returns_error(built):
    tools = built["tools"]
    result = tools["iqr_outliers"].invoke({"column": "not_a_real_column"})
    assert "error" in result


def test_assemble_keeps_discussed_and_undiscussed_groups_and_drops_fake_note(built):
    tools = built["tools"]
    store = built["store"]
    flagged = built["flagged"]

    iqr_result = tools["iqr_outliers"].invoke({"column": "revenue"})
    robust_result = tools["robust_zscore_outliers"].invoke({"column": "revenue"})

    plan = AnomalyPlan(
        summary="Found a planted high-revenue outlier via two methods.",
        groups=[
            AnomalyNote(
                group_id=iqr_result["group_id"],
                interpretation="Looks like a data-entry error on order 21's revenue.",
            ),
            AnomalyNote(group_id="group_999", interpretation="fake, should be dropped"),
        ],
    )

    report = assemble(plan, store, flagged)

    registered_ids_with_count = {key for key, group in store.items("group") if group.count > 0}
    result_ids = {g.id for g in report.groups}
    assert registered_ids_with_count <= result_ids
    assert "group_999" not in result_ids

    kept_by_id = {g.id: g for g in report.groups}
    assert kept_by_id[iqr_result["group_id"]].interpretation == (
        "Looks like a data-entry error on order 21's revenue."
    )
    assert kept_by_id[robust_result["group_id"]].interpretation.startswith("Flagged by")

    max_single_count = max(g.count for g in report.groups)
    assert report.total_flagged >= max_single_count
