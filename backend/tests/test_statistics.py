import pandas as pd

from app.analysis.agents.statistics import assemble
from app.analysis.profiling import coerce_types
from app.analysis.schemas import StatisticsPlan, StatTestNote
from app.analysis.tools.common import ArtifactStore
from app.analysis.tools.stats import build_tools


def _tools(df: pd.DataFrame):
    store = ArtifactStore()
    tools = {t.name: t for t in build_tools(df, store)}
    return store, tools


def test_normality_test_registers_a_test(sales_df):
    df = coerce_types(sales_df)
    store, tools = _tools(df)

    before = len(store.items("test"))
    result = tools["normality_test"].invoke({"column": "revenue"})

    assert "error" not in result
    assert len(store.items("test")) == before + 1
    assert store.has(result["test_id"])


def test_compare_groups_registers_two_tests_and_keeps_north_distinct(sales_df):
    df = coerce_types(sales_df)
    store, tools = _tools(df)

    result = tools["compare_groups"].invoke({"value_column": "revenue", "group_column": "region"})

    assert "error" not in result
    assert store.has(result["parametric_test_id"])
    assert store.has(result["nonparametric_test_id"])

    group_names = {g["group"] for g in result["groups"]}
    assert group_names == {"North", "South", "East", "West", "north"}
    assert "north" in group_names and "North" in group_names


def test_correlation_test_units_and_revenue(sales_df):
    # revenue = units * price by construction, so units and revenue should
    # correlate strongly and positively. The fixture also plants a single
    # massive revenue outlier (row 20), which is exactly the kind of point
    # that wrecks Pearson's r but leaves the rank-based Spearman rho intact
    # -- so we assert on Spearman here, which reflects the true underlying
    # relationship, rather than Pearson.
    df = coerce_types(sales_df)
    store, tools = _tools(df)

    result = tools["correlation_test"].invoke({"column_a": "units", "column_b": "revenue"})

    assert "error" not in result
    assert result["spearman_rho"] > 0.5
    assert result["spearman_p"] < 0.05
    assert store.has(result["pearson_test_id"])
    assert store.has(result["spearman_test_id"])


def test_chi_square_test_on_derived_categorical_column(sales_df):
    df = coerce_types(sales_df)
    df["big"] = df["revenue"] > df["revenue"].median()
    store, tools = _tools(df)

    result = tools["chi_square_test"].invoke({"column_a": "region", "column_b": "big"})

    assert "error" not in result
    assert store.has(result["test_id"])


def test_linear_regression_units_and_price_explain_revenue(sales_df):
    # The fixture's planted revenue outlier (row 20, revenue=1,000,000) is a
    # huge-residual point with ordinary units/price, so it single-handedly
    # collapses R^2 for an OLS fit on the raw data (units/price have no
    # leverage to explain it). Excluding that one row, units + unit_price
    # explain revenue almost perfectly, as they should since revenue is
    # constructed as units * price.
    df = coerce_types(sales_df)
    df = df[df["revenue"] < 100_000]
    store, tools = _tools(df)

    result = tools["linear_regression"].invoke(
        {"target": "revenue", "features": ["units", "unit_price"]}
    )

    assert "error" not in result
    assert result["r_squared"] > 0.5
    assert store.has(result["test_id"])


def test_normality_test_bad_column_returns_error_dict(sales_df):
    df = coerce_types(sales_df)
    _, tools = _tools(df)

    result = tools["normality_test"].invoke({"column": "nope"})

    assert "error" in result


def test_compare_groups_bad_column_returns_error_dict(sales_df):
    df = coerce_types(sales_df)
    _, tools = _tools(df)

    result = tools["compare_groups"].invoke({"value_column": "nope", "group_column": "region"})

    assert "error" in result


def test_assemble_keeps_all_tests_and_orders_mentioned_first(sales_df):
    df = coerce_types(sales_df)
    store, tools = _tools(df)

    tools["normality_test"].invoke({"column": "revenue"})
    compare_result = tools["compare_groups"].invoke(
        {"value_column": "revenue", "group_column": "region"}
    )
    tools["correlation_test"].invoke({"column_a": "units", "column_b": "revenue"})

    real_id = compare_result["nonparametric_test_id"]
    all_ids = {key for key, _ in store.items("test")}

    plan = StatisticsPlan(
        summary="Revenue varies by region and correlates with units.",
        tests=[
            StatTestNote(
                test_id=real_id,
                conclusion="Revenue distributions differ meaningfully across regions.",
                caveats=["Region casing is inconsistent."],
            ),
            StatTestNote(test_id="test_999", conclusion="Should be dropped.", caveats=[]),
        ],
    )

    report = assemble(plan, store)

    result_ids = {t.id for t in report.tests}
    assert result_ids == all_ids
    assert len(report.tests) == len(all_ids)

    assert report.tests[0].id == real_id
    assert report.tests[0].conclusion == "Revenue distributions differ meaningfully across regions."
    assert "Region casing is inconsistent." in report.tests[0].caveats

    assert all(t.conclusion for t in report.tests[1:])
    assert report.summary == plan.summary
