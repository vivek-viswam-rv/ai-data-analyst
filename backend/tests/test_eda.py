import pytest

from app.analysis.profiling import coerce_types
from app.analysis.tools.eda import build_tools


@pytest.fixture
def tools_by_name(sales_df):
    df = coerce_types(sales_df)
    return {t.name: t for t in build_tools(df)}


def test_describe_numeric_default_columns(tools_by_name):
    result = tools_by_name["describe_numeric"].invoke({})
    assert "revenue" in result["columns"]
    assert result["columns"]["revenue"]["mean"] is not None


def test_describe_numeric_rejects_non_numeric_column(tools_by_name):
    result = tools_by_name["describe_numeric"].invoke({"columns": ["region"]})
    assert "error" in result


def test_value_counts_region(tools_by_name):
    result = tools_by_name["value_counts"].invoke({"column": "region", "top_n": 10})
    top_values = [row["value"] for row in result["top"]]
    assert set(top_values) & {"North", "South", "East", "West"}
    assert any(row["value"] == "north" for row in result["top"])
    assert result["distinct"] >= 5


def test_correlations_finds_units_revenue(tools_by_name):
    # Pearson is swamped by the fixture's planted outlier (revenue=1_000_000 at row 20),
    # so use spearman (rank-based, outlier-robust) to surface the real relationship:
    # revenue = units * unit_price is monotonic in units.
    result = tools_by_name["correlations"].invoke({"min_abs": 0.3, "method": "spearman"})
    pairs = result["pairs"]
    match = [p for p in pairs if {p["column_a"], p["column_b"]} == {"units", "revenue"}]
    assert match
    assert match[0]["r"] > 0.5


def test_group_summary_region_revenue(tools_by_name):
    result = tools_by_name["group_summary"].invoke(
        {"group_column": "region", "value_column": "revenue"}
    )
    assert len(result["groups"]) == 5
    for group in result["groups"]:
        assert "count" in group
        assert "value" in group


def test_time_trend_monthly(tools_by_name):
    result = tools_by_name["time_trend"].invoke(
        {"date_column": "order_date", "value_column": "revenue", "freq": "M", "agg": "sum"}
    )
    assert len(result["points"]) <= 12
    assert "pct_change" in result


def test_crosstab_structure(tools_by_name):
    result = tools_by_name["crosstab"].invoke({"column_a": "region", "column_b": "region"})
    assert "North" in result["rows"]
    assert "North" in result["columns"]
    assert isinstance(result["counts"], dict)
    for row_counts in result["counts"].values():
        assert isinstance(row_counts, dict)


def test_bad_column_name_returns_error(tools_by_name):
    result = tools_by_name["value_counts"].invoke({"column": "nonexistent_column"})
    assert "error" in result


def test_distribution_revenue_shape(tools_by_name):
    result = tools_by_name["distribution"].invoke({"column": "revenue"})
    assert "error" not in result
    assert result["shape_hint"] == "right_skewed"
    total = sum(row["count"] for row in result["histogram"])
    assert total == 203


def test_distribution_by_group_region(tools_by_name):
    result = tools_by_name["distribution_by_group"].invoke(
        {"value_column": "revenue", "group_column": "region"}
    )
    assert len(result["groups"]) == 5
    for group in result["groups"]:
        assert group["q1"] <= group["median"] <= group["q3"]


def test_top_and_bottom_outlier_first(tools_by_name):
    result = tools_by_name["top_and_bottom"].invoke(
        {"column": "revenue", "n": 3, "label_column": "order_id"}
    )
    assert result["top"][0]["value"] == 1_000_000
    assert len(result["top"]) == 3
    assert len(result["bottom"]) == 3


def test_distribution_bad_column_returns_error(tools_by_name):
    result = tools_by_name["distribution"].invoke({"column": "nonexistent_column"})
    assert "error" in result
