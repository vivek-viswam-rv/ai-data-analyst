import pandas as pd

from app.analysis.profiling import coerce_types
from app.analysis.tools.quality import build_tools


def _tools(df: pd.DataFrame) -> dict:
    return {t.name: t for t in build_tools(df)}


def test_missing_values_finds_units(sales_df):
    df = coerce_types(sales_df)
    tools = _tools(df)
    result = tools["missing_values"].invoke({})
    cols = {c["column"]: c for c in result["columns"]}
    assert "units" in cols
    assert cols["units"]["count"] == 10
    assert result["rows_with_any_null"] >= 10


def test_duplicate_rows_finds_three(sales_df):
    df = coerce_types(sales_df)
    tools = _tools(df)
    result = tools["duplicate_rows"].invoke({"subset": None})
    assert result["count"] == 3
    assert 0 < len(result["example_rows"]) <= 5


def test_text_consistency_finds_region_collision(sales_df):
    df = coerce_types(sales_df)
    tools = _tools(df)
    result = tools["text_consistency"].invoke({"column": "region"})
    normalized = {g["normalized"]: g for g in result["inconsistent_groups"]}
    assert "north" in normalized
    assert set(normalized["north"]["variants"]) == {"North", "north"}


def test_numeric_range_finds_revenue_outlier(sales_df):
    df = coerce_types(sales_df)
    tools = _tools(df)
    result = tools["numeric_range"].invoke({"column": "revenue"})
    assert result["outlier_count"] >= 1
    assert result["outlier_upper_bound"] is not None
    assert result["summary"]["count"] == 203


def test_column_overview_lists_order_id_as_all_unique(sales_df):
    df = coerce_types(sales_df)
    tools = _tools(df)
    result = tools["column_overview"].invoke({})
    unique_cols = [c["column"] for c in result["all_unique_columns"]]
    assert "order_id" in unique_cols
    constant_cols = [c["column"] for c in result["constant_columns"]]
    assert "notes" in constant_cols


def test_bad_column_returns_error_dict_not_exception(sales_df):
    df = coerce_types(sales_df)
    tools = _tools(df)
    result = tools["numeric_range"].invoke({"column": "does_not_exist"})
    assert "error" in result
    result = tools["text_consistency"].invoke({"column": "does_not_exist"})
    assert "error" in result
