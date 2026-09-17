import datetime

import pytest

from app.analysis.agents.visualization import MAX_CHARTS, assemble
from app.analysis.profiling import coerce_types
from app.analysis.schemas import ChartNote, VisualizationPlan
from app.analysis.tools.charts import build_tools
from app.analysis.tools.common import ArtifactStore


@pytest.fixture
def df(sales_df):
    return coerce_types(sales_df)


@pytest.fixture
def tools(df):
    store = ArtifactStore()
    built = {t.name: t for t in build_tools(df, store)}
    return built, store


def test_bar_chart_sum_sorted_descending(tools):
    built, store = tools
    result = built["bar_chart"].invoke(
        {"category_column": "region", "value_column": "revenue", "agg": "sum"}
    )
    assert "error" not in result
    assert result["n_points"] == 5
    spec = store.get(result["chart_id"])
    values = [row[spec.series[0]] for row in spec.data]
    assert values == sorted(values, reverse=True)


def test_bar_chart_count_default(tools, df):
    built, store = tools
    result = built["bar_chart"].invoke({"category_column": "region"})
    assert result["n_points"] == 5
    spec = store.get(result["chart_id"])
    total = sum(row["count"] for row in spec.data)
    assert total == df["region"].notna().sum()


def test_line_chart_daily_points_iso_dates(tools):
    built, _store = tools
    result = built["line_chart"].invoke({"date_column": "order_date", "value_column": "revenue"})
    assert "error" not in result
    assert 4 <= result["n_points"] <= 60
    for row in result["preview"]:
        datetime.date.fromisoformat(row["order_date"])


def test_line_chart_grouped_series(tools):
    built, store = tools
    result = built["line_chart"].invoke(
        {"date_column": "order_date", "value_column": "revenue", "group_column": "region"}
    )
    assert "error" not in result
    spec = store.get(result["chart_id"])
    assert len(spec.series) <= 5
    present = set()
    for row in spec.data:
        present.update(row.keys())
    for name in spec.series:
        assert name in present


def test_histogram_bins_and_total_count(tools, df):
    built, store = tools
    result = built["histogram"].invoke({"column": "revenue", "bins": 10})
    assert result["n_points"] == 10
    spec = store.get(result["chart_id"])
    total = sum(row["count"] for row in spec.data)
    assert total == df["revenue"].notna().sum()


def test_scatter_chart_caps_points(tools):
    built, _store = tools
    result = built["scatter_chart"].invoke(
        {"x_column": "units", "y_column": "revenue", "max_points": 50}
    )
    assert result["n_points"] == 50


def test_bad_column_returns_error(tools):
    built, _store = tools
    result = built["bar_chart"].invoke({"category_column": "nope"})
    assert "error" in result


def test_assemble_dedupes_and_drops_unknown_ids(tools):
    built, store = tools
    result = built["bar_chart"].invoke({"category_column": "region"})
    chart_id = result["chart_id"]
    plan = VisualizationPlan(
        summary="A summary.",
        charts=[
            ChartNote(chart_id=chart_id, caption="Real chart caption."),
            ChartNote(chart_id="chart_999", caption="Fake chart."),
        ],
    )
    report = assemble(plan, store)
    assert len(report.charts) == 1
    assert report.charts[0].id == chart_id
    assert report.charts[0].caption == "Real chart caption."


def test_bar_chart_grouped_stacked_series(tools):
    built, store = tools
    result = built["bar_chart"].invoke(
        {
            "category_column": "order_date",
            "value_column": "units",
            "agg": "sum",
            "group_column": "region",
            "stacked": True,
        }
    )
    assert "error" not in result
    spec = store.get(result["chart_id"])
    assert spec.stacked is True
    assert 1 <= len(spec.series) <= 5
    for row in spec.data:
        assert row["order_date"]


def test_histogram_grouped_shares_series_and_bins(tools):
    built, store = tools
    result = built["histogram"].invoke({"column": "revenue", "bins": 10, "group_column": "region"})
    assert "error" not in result
    spec = store.get(result["chart_id"])
    assert 1 <= len(spec.series) <= 5
    present: set[str] = set()
    for row in spec.data:
        present.update(row.keys())
    for name in spec.series:
        assert name in present


def test_box_plot_grouped_quartiles_ordered(tools):
    built, store = tools
    result = built["box_plot"].invoke({"value_column": "revenue", "group_column": "region"})
    assert "error" not in result
    spec = store.get(result["chart_id"])
    assert len(spec.data) == 5
    for row in spec.data:
        assert row["q1"] <= row["median"] <= row["q3"]
        assert row["min"] <= row["q1"]


def test_box_plot_ungrouped_single_row(tools):
    built, store = tools
    result = built["box_plot"].invoke({"value_column": "revenue"})
    assert "error" not in result
    spec = store.get(result["chart_id"])
    assert len(spec.data) == 1


def test_cumulative_chart_monotonic_ending_at_100(tools):
    built, store = tools
    result = built["cumulative_chart"].invoke({"column": "revenue", "points": 20})
    assert "error" not in result
    spec = store.get(result["chart_id"])
    assert len(spec.data) <= 20
    pcts = [row["pct"] for row in spec.data]
    assert pcts == sorted(pcts)
    assert pcts[-1] == 100


def test_assemble_caps_at_max_charts(tools):
    built, store = tools
    chart_ids = [
        built["bar_chart"].invoke({"category_column": "region"})["chart_id"] for _ in range(10)
    ]
    notes = [ChartNote(chart_id=cid, caption=f"Caption {i}.") for i, cid in enumerate(chart_ids)]
    plan = VisualizationPlan(summary="A summary.", charts=notes)
    report = assemble(plan, store)
    assert len(report.charts) == MAX_CHARTS
