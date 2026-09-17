"""Tools for the data-quality agent: closures over a single DataFrame.

Every tool returns a small JSON-able dict and never raises: `safe_tool`
turns exceptions into an {"error": ...} payload the model can read and
recover from.
"""

import pandas as pd
from langchain_core.tools import BaseTool, tool

from app.analysis.tools.common import (
    MAX_ROWS_IN_RESULT,
    ToolError,
    fmt,
    num,
    require_column,
    require_numeric,
    safe_tool,
    series_summary,
)

MAX_EXAMPLE_ROWS = 5
MAX_GROUPS = MAX_ROWS_IN_RESULT
ALL_UNIQUE_RATIO = 0.98
NEAR_CONSTANT_RATIO = 0.99
MOSTLY_NULL_PCT = 95.0
NUMERIC_LIKE_RATIO = 0.5


def build_tools(df: pd.DataFrame) -> list[BaseTool]:
    """Build the data-quality tool set, closed over `df`."""

    @tool
    @safe_tool
    def missing_values() -> dict:
        """List columns that contain nulls, with the count and percent
        missing for each, plus how many rows have at least one null in any
        column. Call this first to see where nulls are concentrated.
        """
        n = len(df)
        cols = []
        for c in df.columns:
            count = int(df[c].isna().sum())
            if count:
                cols.append(
                    {"column": str(c), "count": count, "pct": round(100 * count / max(n, 1), 2)}
                )
        cols.sort(key=lambda x: -x["count"])
        return {
            "columns": cols[:MAX_ROWS_IN_RESULT],
            "rows_with_any_null": int(df.isna().any(axis=1).sum()),
            "total_rows": n,
        }

    @tool
    @safe_tool
    def duplicate_rows(subset: list[str] | None = None) -> dict:
        """Count fully duplicated rows, or rows duplicated on a subset of
        column names if `subset` is given. Returns the duplicate count,
        percent of all rows, and up to 5 example duplicated rows (as lists
        of formatted values matching the `columns` field).
        """
        cols = [require_column(df, c) for c in subset] if subset else None
        count = int(df.duplicated(subset=cols, keep="first").sum())
        n = len(df)
        example_cols = cols or list(df.columns)
        dup_rows = df.loc[df.duplicated(subset=cols, keep=False), example_cols]
        examples = [
            [fmt(v) for v in row] for row in dup_rows.head(MAX_EXAMPLE_ROWS).itertuples(index=False)
        ]
        return {
            "count": count,
            "pct": round(100 * count / max(n, 1), 2),
            "columns": [str(c) for c in example_cols],
            "example_rows": examples,
        }

    @tool
    @safe_tool
    def text_consistency(column: str) -> dict:
        """For a text/categorical column, find casing and whitespace
        problems: groups of distinct values that collapse to the same value
        after strip+lowercase (e.g. "North" and "north"), how many values
        have leading/trailing whitespace, how many are empty strings, and
        how many look numeric while the rest of the column does not. Use on
        string/categorical columns, not numeric ones.
        """
        col = require_column(df, column)
        s = df[col]
        if not (pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s)):
            raise ToolError(f"Column '{col}' is not a text column.")
        non_null = s.dropna().astype(str)
        groups_by_norm: dict[str, set[str]] = {}
        for v in non_null.unique():
            key = v.strip().lower()
            groups_by_norm.setdefault(key, set()).add(v)
        groups = [
            {
                "normalized": key,
                "variants": sorted(variants),
                "count": int(non_null.isin(variants).sum()),
            }
            for key, variants in groups_by_norm.items()
            if len(variants) > 1
        ]
        groups.sort(key=lambda g: -g["count"])
        whitespace_count = int((non_null != non_null.str.strip()).sum())
        empty_count = int((non_null.str.strip() == "").sum())
        numeric_like = pd.to_numeric(non_null.str.strip(), errors="coerce").notna()
        numeric_hits = int(numeric_like.sum())
        mixed_numeric_count = numeric_hits if 0 < numeric_hits < len(non_null) else 0
        return {
            "column": col,
            "inconsistent_groups": groups[:MAX_GROUPS],
            "whitespace_count": whitespace_count,
            "empty_string_count": empty_count,
            "mixed_numeric_count": mixed_numeric_count,
        }

    @tool
    @safe_tool
    def numeric_range(column: str) -> dict:
        """Summary statistics for a numeric column (count, mean, std,
        quartiles, min, max), plus counts of negative values, zero values,
        and outliers outside 1.5*IQR from the quartiles, with the outlier
        bounds.
        """
        col = require_numeric(df, column)
        s = df[col]
        summary = series_summary(s)
        non_null = s.dropna()
        negatives = int((non_null < 0).sum())
        zeros = int((non_null == 0).sum())
        lower = upper = None
        outlier_count = 0
        if len(non_null) >= 4:
            q1 = non_null.quantile(0.25)
            q3 = non_null.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_count = int(((non_null < lower) | (non_null > upper)).sum())
        return {
            "column": col,
            "summary": summary,
            "negative_count": negatives,
            "zero_count": zeros,
            "outlier_count": outlier_count,
            "outlier_lower_bound": num(lower),
            "outlier_upper_bound": num(upper),
        }

    @tool
    @safe_tool
    def column_overview() -> dict:
        """Column-level quality overview for the whole dataset: constant
        columns (only one distinct value), near-constant columns (>=99% one
        value), columns where almost every value is unique (candidate
        identifiers), columns that are >=95% null, and string columns whose
        values look mostly numeric (candidate for a type fix). Call this
        first to decide which columns need closer inspection.
        """
        n = len(df)
        constant: list[dict] = []
        near_constant: list[dict] = []
        all_unique: list[dict] = []
        mostly_null: list[dict] = []
        numeric_like_text: list[dict] = []
        for c in df.columns:
            name = str(c)
            s = df[c]
            non_null = s.dropna()
            null_pct = 100 * (n - len(non_null)) / max(n, 1)
            if null_pct >= MOSTLY_NULL_PCT:
                mostly_null.append({"column": name, "null_pct": round(null_pct, 2)})
            if non_null.empty:
                continue
            nunique = int(non_null.nunique())
            top_frac = float(non_null.value_counts(normalize=True).iloc[0])
            if nunique == 1:
                constant.append({"column": name, "value": fmt(non_null.iloc[0])})
            elif top_frac >= NEAR_CONSTANT_RATIO:
                near_constant.append(
                    {
                        "column": name,
                        "top_value": fmt(non_null.value_counts().idxmax()),
                        "pct": round(100 * top_frac, 2),
                    }
                )
            if len(non_null) > 1 and nunique / len(non_null) >= ALL_UNIQUE_RATIO:
                all_unique.append(
                    {"column": name, "unique_pct": round(100 * nunique / len(non_null), 2)}
                )
            if pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s):
                numeric_frac = float(
                    pd.to_numeric(non_null.astype(str), errors="coerce").notna().mean()
                )
                if numeric_frac >= NUMERIC_LIKE_RATIO:
                    numeric_like_text.append(
                        {"column": name, "numeric_like_pct": round(100 * numeric_frac, 2)}
                    )
        return {
            "constant_columns": constant[:MAX_ROWS_IN_RESULT],
            "near_constant_columns": near_constant[:MAX_ROWS_IN_RESULT],
            "all_unique_columns": all_unique[:MAX_ROWS_IN_RESULT],
            "mostly_null_columns": mostly_null[:MAX_ROWS_IN_RESULT],
            "numeric_like_text_columns": numeric_like_text[:MAX_ROWS_IN_RESULT],
        }

    return [missing_values, duplicate_rows, text_consistency, numeric_range, column_overview]
