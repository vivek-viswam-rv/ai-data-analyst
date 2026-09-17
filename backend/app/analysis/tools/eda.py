"""Tools the EDA agent uses to explore a dataset before writing findings."""

import pandas as pd
from langchain_core.tools import BaseTool, tool

from app.analysis.tools.common import (
    ToolError,
    fmt,
    num,
    numeric_columns,
    require_column,
    require_numeric,
    safe_tool,
    series_summary,
)

MAX_LIST = 15
_AGGS = {"count", "sum", "mean", "median", "min", "max"}
_FREQ_ALIASES = {"D": "D", "W": "W", "M": "ME", "Q": "QE", "Y": "YE"}
_FREQ_LADDER = ["D", "W", "ME", "QE", "YE"]


def build_tools(df: pd.DataFrame) -> list[BaseTool]:
    """Build the EDA toolset bound to a single dataframe."""

    @tool
    @safe_tool
    def describe_numeric(columns: list[str] | None = None) -> dict:
        """Summarize numeric columns: count, mean, std, quartiles, skew, and pct of zeros.

        Args:
            columns: Column names to summarize. If omitted, summarizes up to the first
                12 numeric columns in the dataset.

        Returns:
            A dict with key "columns" mapping each column name to its summary stats.
        """
        if columns is None:
            cols = numeric_columns(df)[:12]
        else:
            cols = [require_numeric(df, c) for c in columns]
        out = {}
        for col in cols:
            s = df[col]
            summary = series_summary(s)
            summary["skew"] = num(s.skew())
            summary["pct_zero"] = num(100 * (s == 0).mean())
            out[col] = summary
        return {"columns": out}

    @tool
    @safe_tool
    def value_counts(column: str, top_n: int = 10) -> dict:
        """Get the most frequent values in a column and how much of the data they cover.

        Args:
            column: The column to count values in.
            top_n: How many top values to return (capped at 15).

        Returns:
            A dict with the resolved column name, the top values with counts and
            percentages, the number of distinct values, and the pct of non-null rows
            covered by the returned top values.
        """
        col = require_column(df, column)
        capped_n = min(top_n, MAX_LIST)
        vc = df[col].value_counts(dropna=True)
        total = int(vc.sum())
        top = vc.head(capped_n)
        top_sum = int(top.sum())
        top_list = [
            {
                "value": fmt(idx),
                "count": int(count),
                "pct": num(100 * count / total) if total else None,
            }
            for idx, count in top.items()
        ]
        return {
            "column": col,
            "top": top_list,
            "distinct": int(df[col].nunique(dropna=True)),
            "pct_covered": num(100 * top_sum / total) if total else None,
        }

    @tool
    @safe_tool
    def correlations(min_abs: float = 0.3, method: str = "pearson") -> dict:
        """Find pairs of numeric columns that are correlated with each other.

        Args:
            min_abs: Minimum absolute correlation coefficient to report a pair.
            method: Correlation method: "pearson", "spearman", or "kendall".

        Returns:
            A dict with "pairs" (each with column_a, column_b, r), sorted by strength
            descending and capped at 15, plus "columns_considered".
        """
        if method not in {"pearson", "spearman", "kendall"}:
            raise ToolError(f"Unknown method '{method}'. Use one of: pearson, spearman, kendall.")
        candidates = []
        for c in numeric_columns(df):
            s = df[c]
            if s.nunique(dropna=True) <= 1:
                continue
            std = s.std()
            if std is None or pd.isna(std) or std == 0:
                continue
            candidates.append(c)
        if len(candidates) < 2:
            return {"pairs": [], "columns_considered": candidates}
        corr = df[candidates].corr(method=method)
        pairs = []
        for i, a in enumerate(candidates):
            for b in candidates[i + 1 :]:
                r = corr.loc[a, b]
                if pd.isna(r):
                    continue
                if abs(r) >= min_abs:
                    pairs.append({"column_a": a, "column_b": b, "r": num(r)})
        pairs.sort(key=lambda p: abs(p["r"]) if p["r"] is not None else 0, reverse=True)
        return {"pairs": pairs[:MAX_LIST], "columns_considered": candidates}

    @tool
    @safe_tool
    def group_summary(group_column: str, value_column: str, agg: str = "mean") -> dict:
        """Aggregate a numeric column by the groups of a categorical column.

        Args:
            group_column: Column to group by.
            value_column: Numeric column to aggregate.
            agg: One of "count", "sum", "mean", "median", "min", "max".

        Returns:
            A dict with the resolved column names, a list of groups (each with
            group label, row count, and aggregated value) sorted by value descending
            and capped at 15, and the overall aggregate across the full column.
        """
        if agg not in _AGGS:
            raise ToolError(f"Unknown agg '{agg}'. Use one of: {', '.join(sorted(_AGGS))}.")
        group_col = require_column(df, group_column)
        value_col = require_numeric(df, value_column)
        g = df.groupby(group_col, observed=True, dropna=True)[value_col]
        counts = g.count()
        agg_values = g.agg(agg)
        rows = [
            {
                "group": fmt(idx),
                "count": int(counts.loc[idx]),
                "value": num(agg_values.loc[idx]),
            }
            for idx in agg_values.index
        ]
        sort_key = "count" if agg == "count" else "value"
        rows.sort(
            key=lambda r: r[sort_key] if r[sort_key] is not None else float("-inf"), reverse=True
        )
        rows = rows[:MAX_LIST]
        overall = df[value_col].count() if agg == "count" else df[value_col].agg(agg)
        return {
            "group_column": group_col,
            "value_column": value_col,
            "agg": agg,
            "groups": rows,
            "overall": num(overall),
        }

    @tool
    @safe_tool
    def time_trend(date_column: str, value_column: str, freq: str = "M", agg: str = "sum") -> dict:
        """Aggregate a numeric column over time to see trend and change.

        Args:
            date_column: A column already parsed as a datetime.
            value_column: Numeric column to aggregate per period.
            freq: Period length: "D", "W", "M", "Q", or "Y". Coarsened automatically
                if the requested frequency would produce more than 36 points.
            agg: One of "count", "sum", "mean", "median", "min", "max".

        Returns:
            A dict with the resolved column names, the frequency actually used, the
            list of {period, value} points, the first/last values, pct_change from
            first to last, and the max/min periods.
        """
        date_col = require_column(df, date_column)
        if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            raise ToolError(
                f"Column '{date_col}' is not a parsed datetime. "
                "Use a column that has already been converted to a datetime dtype."
            )
        value_col = require_numeric(df, value_column)
        if agg not in _AGGS:
            raise ToolError(f"Unknown agg '{agg}'. Use one of: {', '.join(sorted(_AGGS))}.")
        freq_key = freq.upper()
        if freq_key not in _FREQ_ALIASES:
            raise ToolError(f"Unknown freq '{freq}'. Use one of: D, W, M, Q, Y.")
        alias = _FREQ_ALIASES[freq_key]
        s = df.set_index(date_col)[value_col].sort_index()

        rung = _FREQ_LADDER.index(alias)
        resampled = None
        while True:
            candidate_alias = _FREQ_LADDER[rung]
            grouped = s.resample(candidate_alias)
            resampled = grouped.count() if agg == "count" else grouped.agg(agg)
            if len(resampled) <= 36 or candidate_alias == "YE":
                alias = candidate_alias
                break
            rung += 1

        resampled = resampled.dropna()
        points = [{"period": fmt(idx), "value": num(v)} for idx, v in resampled.items()][:36]

        first = points[0]["value"] if points else None
        last = points[-1]["value"] if points else None
        pct_change = (
            num(100 * (last - first) / first)
            if first not in (None, 0) and last is not None
            else None
        )

        def _extreme(pick_max: bool) -> dict | None:
            valid = [p for p in points if p["value"] is not None]
            if not valid:
                return None
            chosen = (
                max(valid, key=lambda p: p["value"])
                if pick_max
                else min(valid, key=lambda p: p["value"])
            )
            return {"period": chosen["period"], "value": chosen["value"]}

        return {
            "date_column": date_col,
            "value_column": value_col,
            "freq_used": alias,
            "points": points,
            "first": first,
            "last": last,
            "pct_change": pct_change,
            "max_period": _extreme(True),
            "min_period": _extreme(False),
        }

    @tool
    @safe_tool
    def crosstab(column_a: str, column_b: str) -> dict:
        """Cross-tabulate counts between two columns (top 10 categories each; rest as "other").

        Args:
            column_a: First column (becomes rows).
            column_b: Second column (becomes columns).

        Returns:
            A dict with the resolved column names, "rows", "columns", and "counts"
            (a nested dict of row label -> column label -> count).
        """
        col_a = require_column(df, column_a)
        col_b = require_column(df, column_b)

        def _bucketed(col: str) -> pd.Series:
            s = df[col]
            if s.nunique(dropna=True) <= 10:
                return s
            top = s.value_counts().head(10).index
            return s.where(s.isin(top), other="other")

        temp_a = _bucketed(col_a)
        temp_b = _bucketed(col_b)
        table = pd.crosstab(temp_a, temp_b)

        rows = [fmt(idx) for idx in table.index]
        columns = [fmt(c) for c in table.columns]
        counts = {
            fmt(r_idx): {fmt(c_idx): int(table.loc[r_idx, c_idx]) for c_idx in table.columns}
            for r_idx in table.index
        }
        return {
            "column_a": col_a,
            "column_b": col_b,
            "rows": rows,
            "columns": columns,
            "counts": counts,
        }

    return [describe_numeric, value_counts, correlations, group_summary, time_trend, crosstab]
