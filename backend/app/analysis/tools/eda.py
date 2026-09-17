"""Tools the EDA agent uses to explore a dataset before writing findings."""

import numpy as np
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

    @tool
    @safe_tool
    def distribution(column: str, bins: int = 20) -> dict:
        """Characterize a numeric column's distribution: spread, skew, and shape.

        Args:
            column: Numeric column to analyze.
            bins: Number of histogram bins to compute (capped at 40).

        Returns:
            A dict with the resolved column, series_summary, skewness, excess
            kurtosis, percentiles (p1/p5/p95/p99), pct_zero, pct_negative, a
            histogram (list of {bin, count}), the modal_bin, a deterministic
            shape_hint, and a one-line reading explaining it.
        """
        col = require_numeric(df, column)
        s = df[col].dropna()
        if s.empty:
            raise ToolError(f"Column '{col}' has no non-null values to analyze.")

        capped_bins = max(1, min(bins, 40))
        summary = series_summary(s)
        skew = num(s.skew())
        kurt = num(s.kurt())  # pandas' kurt() is already excess kurtosis (normal = 0)

        percentiles = {
            "p1": num(s.quantile(0.01)),
            "p5": num(s.quantile(0.05)),
            "p95": num(s.quantile(0.95)),
            "p99": num(s.quantile(0.99)),
        }
        pct_zero = num(100 * (s == 0).mean())
        pct_negative = num(100 * (s < 0).mean())

        # Robust histogram range: clip to the IQR whiskers so one or two extreme
        # outliers don't swallow everything into a single bin. Outliers still
        # land in the edge bins, they just don't blow out the axis.
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = float(s.min()), float(s.max())
        if iqr > 0:
            lo = max(lo, q1 - 1.5 * iqr)
            hi = min(hi, q3 + 1.5 * iqr)
        if lo >= hi:
            lo, hi = float(s.min()), float(s.max())

        clipped = s.clip(lower=lo, upper=hi)
        counts, edges = np.histogram(clipped, bins=capped_bins, range=(lo, hi))
        counts_list = [int(c) for c in counts]
        histogram = [
            {"bin": f"{edges[i]:.1f}–{edges[i + 1]:.1f}", "count": counts_list[i]}
            for i in range(len(counts_list))
        ]
        total = sum(counts_list)
        modal_idx = counts_list.index(max(counts_list))
        modal_pct = num(100 * counts_list[modal_idx] / total) if total else None
        modal_bin = {
            "bin": histogram[modal_idx]["bin"],
            "count": counts_list[modal_idx],
            "pct": modal_pct,
        }

        shape_hint, reading = _shape_hint(counts_list, skew, kurt, modal_pct)

        return {
            "column": col,
            "series_summary": summary,
            "skewness": skew,
            "kurtosis": kurt,
            "percentiles": percentiles,
            "pct_zero": pct_zero,
            "pct_negative": pct_negative,
            "histogram": histogram,
            "modal_bin": modal_bin,
            "shape_hint": shape_hint,
            "reading": reading,
        }

    @tool
    @safe_tool
    def distribution_by_group(value_column: str, group_column: str) -> dict:
        """Summarize a numeric column's spread (min/quartiles/max) within each group.

        Useful for describing what a box plot of value_column by group_column would show.

        Args:
            value_column: Numeric column whose distribution to summarize.
            group_column: Column whose distinct values define the groups.

        Returns:
            A dict with the resolved column names, "groups" (top 8 by count, each with
            group, n, min, q1, median, q3, max, mean, sorted by median descending), and
            "overall" (the same stats across the full column).
        """
        value_col = require_numeric(df, value_column)
        group_col = require_column(df, group_column)
        subset = df[[group_col, value_col]].dropna()
        counts = subset.groupby(group_col, observed=True)[value_col].count()
        top_groups = counts.sort_values(ascending=False).head(8).index

        def _stats(s: pd.Series) -> dict:
            return {
                "n": int(s.count()),
                "min": num(s.min()),
                "q1": num(s.quantile(0.25)),
                "median": num(s.median()),
                "q3": num(s.quantile(0.75)),
                "max": num(s.max()),
                "mean": num(s.mean()),
            }

        rows = []
        for grp in top_groups:
            s = subset.loc[subset[group_col] == grp, value_col]
            row = {"group": fmt(grp)}
            row.update(_stats(s))
            rows.append(row)
        rows.sort(
            key=lambda r: r["median"] if r["median"] is not None else float("-inf"), reverse=True
        )

        return {
            "value_column": value_col,
            "group_column": group_col,
            "groups": rows,
            "overall": _stats(df[value_col].dropna()),
        }

    @tool
    @safe_tool
    def top_and_bottom(column: str, n: int = 5, label_column: str | None = None) -> dict:
        """Get the n largest and n smallest values in a numeric column, with a label per row.

        Args:
            column: Numeric column to find extremes in.
            n: How many top and bottom values to return (capped at 15 each).
            label_column: Column to label each extreme value with (e.g. an id or name).
                If omitted, an id-looking column is used if one exists, else the row position.

        Returns:
            A dict with the resolved column, the label column used (or null), "top"
            (largest first) and "bottom" (smallest first), each a list of {label, value}.
        """
        col = require_numeric(df, column)
        capped_n = max(1, min(n, MAX_LIST))
        if label_column is not None:
            label_col = require_column(df, label_column)
        else:
            id_like = [c for c in df.columns if "id" in str(c).lower()]
            label_col = id_like[0] if id_like else None

        s = df[col].dropna().sort_values(ascending=False)

        def _rows(sub: pd.Series) -> list[dict]:
            out = []
            for idx, value in sub.items():
                label = fmt(df.loc[idx, label_col]) if label_col is not None else f"row {idx}"
                out.append({"label": label, "value": num(value)})
            return out

        top = _rows(s.head(capped_n))
        bottom = _rows(s.tail(capped_n).sort_values())

        return {
            "column": col,
            "label_column": label_col,
            "top": top,
            "bottom": bottom,
        }

    return [
        describe_numeric,
        value_counts,
        correlations,
        group_summary,
        time_trend,
        crosstab,
        distribution,
        distribution_by_group,
        top_and_bottom,
    ]


def _shape_hint(
    counts: list[int], skew: float | None, kurt: float | None, modal_pct: float | None
) -> tuple[str, str]:
    """Deterministically classify a histogram's shape from its bin counts."""
    if modal_pct is not None and modal_pct >= 60:
        return (
            "concentrated",
            f"About {modal_pct:.0f}% of values fall in a single bin — "
            "the data clusters tightly around one value.",
        )

    # Smooth to at most 10 buckets before peak-finding so bin-to-bin noise in
    # a fine histogram doesn't manufacture spurious peaks.
    factor = max(1, -(-len(counts) // 10))
    merged = [sum(counts[i : i + factor]) for i in range(0, len(counts), factor)]
    m_max = max(merged) if merged else 0
    thr = 0.3 * m_max
    peaks = [
        i
        for i in range(1, len(merged) - 1)
        if merged[i] > merged[i - 1] and merged[i] > merged[i + 1] and merged[i] >= thr
    ]
    bimodal = False
    for a in range(len(peaks)):
        for b in range(a + 1, len(peaks)):
            i, j = peaks[a], peaks[b]
            valley = merged[i + 1 : j]
            if valley and min(valley) < thr:
                bimodal = True
                break
        if bimodal:
            break
    if bimodal:
        return (
            "bimodal",
            "The histogram shows two separated peaks rather than one central cluster.",
        )

    nonzero = [c for c in counts if c > 0]
    ratio = (max(nonzero) / min(nonzero)) if nonzero else None
    if ratio is not None and ratio <= 1.5 and skew is not None and -0.5 <= skew <= 0.5:
        return "uniform", "Values are spread fairly evenly across the range with no strong peak."

    if skew is not None and skew > 1:
        return (
            "right_skewed",
            f"The distribution has a long right tail (skew {skew:.2f}); most values sit "
            "below the mean, pulled up by a few large ones.",
        )
    if skew is not None and skew < -1:
        return (
            "left_skewed",
            f"The distribution has a long left tail (skew {skew:.2f}); most values sit "
            "above the mean, pulled down by a few small ones.",
        )
    if skew is not None and abs(skew) <= 1 and kurt is not None and kurt > 3:
        return (
            "heavy_tailed",
            f"The distribution is centered but has fatter tails than normal "
            f"(excess kurtosis {kurt:.2f}).",
        )
    return (
        "roughly_symmetric",
        "Values cluster fairly evenly around the center with no strong skew.",
    )
