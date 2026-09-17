"""Tools the visualization agent uses to build chart data for the report.

Each tool computes chart data, registers a `ChartSpec` in the `ArtifactStore`
under an id like "chart_1", and returns a small summary dict (not the spec
itself) so the model can see what it made without seeing all the data. The
model only picks which chart ids to keep and writes captions; `assemble()`
(in `app.analysis.agents.visualization`) joins those picks with the store.
"""

import numpy as np
import pandas as pd
from langchain_core.tools import BaseTool, tool

from app.analysis.schemas import ChartSpec
from app.analysis.tools.common import (
    ArtifactStore,
    ToolError,
    num,
    require_column,
    require_numeric,
    safe_tool,
)

_BAR_AGGS = {"count", "sum", "mean", "median"}
_LINE_AGGS = {"sum", "mean", "median", "count"}
_LINE_FREQS = {"D", "W", "ME", "QE"}
_FREQ_WORDS = {"D": "daily", "W": "weekly", "ME": "monthly", "QE": "quarterly"}
_AUTO_CANDIDATES = ["D", "W", "ME", "QE"]
_MAX_POINTS = 60


def build_tools(df: pd.DataFrame, store: ArtifactStore) -> list[BaseTool]:
    """Build the chart-building toolset bound to a single dataframe and store."""

    @tool
    @safe_tool
    def bar_chart(
        category_column: str,
        value_column: str | None = None,
        agg: str = "count",
        top_n: int = 12,
        group_column: str | None = None,
        stacked: bool = False,
    ) -> dict:
        """Build a bar chart of a category column, optionally aggregating a value.

        Args:
            category_column: Column to group by (bars are its distinct values).
            value_column: Numeric column to aggregate. Required unless agg="count".
            agg: One of "count", "sum", "mean", "median".
            top_n: Max number of bars to keep, sorted by value descending (max 50).
            group_column: Optional column to split each bar into up to 5 series
                (by total value_column descending).
            stacked: Whether the browser should render grouped series stacked
                instead of side by side.

        Returns:
            A dict with chart_id, title, n_points, and a preview of the first rows.
        """
        category_column = require_column(df, category_column)
        if agg not in _BAR_AGGS:
            raise ToolError(f"agg must be one of count, sum, mean, median, got '{agg}'")
        if agg != "count":
            if value_column is None:
                raise ToolError("value_column is required when agg is not 'count'")
            value_column = require_numeric(df, value_column)

        if group_column is not None:
            group_column = require_column(df, group_column)
            subset = df[df[category_column].notna() & df[group_column].notna()].copy()
            cats_str = subset[category_column].astype(str)
            groups_str = subset[group_column].astype(str)
            if agg == "count":
                totals_by_group = groups_str.groupby(groups_str, observed=True).size()
            else:
                totals_by_group = (
                    subset[value_column]
                    .groupby(groups_str, observed=True)
                    .agg("sum" if agg in ("sum", "count") else agg)
                )
            top_groups = totals_by_group.sort_values(ascending=False).head(5).index.tolist()

            # pick the categories to show using the same ranking as the ungrouped case
            if agg == "count":
                cat_totals = cats_str.groupby(cats_str, observed=True).size()
            else:
                cat_totals = subset[value_column].groupby(cats_str, observed=True).agg(agg)
            capped_n = max(1, min(top_n, 50))
            top_cats = cat_totals.sort_values(ascending=False).head(capped_n).index.tolist()

            data = []
            for cat in top_cats:
                row: dict[str, float | str | None] = {category_column: cat}
                cat_mask = cats_str == cat
                for grp in top_groups:
                    mask = cat_mask & (groups_str == grp)
                    if not mask.any():
                        row[str(grp)] = None
                    elif agg == "count":
                        row[str(grp)] = num(int(mask.sum()))
                    else:
                        row[str(grp)] = num(subset.loc[mask, value_column].agg(agg))
                data.append(row)

            series = [str(g) for g in top_groups]
            value_label = "count" if agg == "count" else f"{value_column} ({agg})"
            verb = {"count": "Count", "sum": "Total", "mean": "Average", "median": "Median"}[agg]
            if agg == "count":
                title = f"Count by {category_column}, split by {group_column}"
            else:
                title = f"{verb} {value_column} by {category_column}, split by {group_column}"

            spec = ChartSpec(
                id="",
                type="bar",
                title=title,
                caption="",
                x_key=category_column,
                x_label=category_column,
                y_label=value_label,
                series=series,
                stacked=stacked,
                data=data,
            )
            chart_id = store.add("chart", spec)
            spec.id = chart_id
            return {
                "chart_id": chart_id,
                "title": title,
                "n_points": len(spec.data),
                "preview": spec.data[:3],
            }

        subset = df[df[category_column].notna()]
        categories = subset[category_column].astype(str)
        if agg == "count":
            agg_series = categories.groupby(categories, observed=True).size()
            value_label = "count"
        else:
            agg_series = subset[value_column].groupby(categories, observed=True).agg(agg)
            value_label = f"{value_column} ({agg})"

        agg_series = agg_series.sort_values(ascending=False)
        capped_n = max(1, min(top_n, 50))
        agg_series = agg_series.head(capped_n)

        data = [{category_column: str(cat), value_label: num(v)} for cat, v in agg_series.items()]

        if agg == "count":
            title = f"Count by {category_column}"
        elif agg == "sum":
            title = f"Total {value_column} by {category_column}"
        elif agg == "mean":
            title = f"Average {value_column} by {category_column}"
        else:
            title = f"Median {value_column} by {category_column}"

        spec = ChartSpec(
            id="",
            type="bar",
            title=title,
            caption="",
            x_key=category_column,
            x_label=category_column,
            y_label=value_label,
            series=[value_label],
            stacked=stacked,
            data=data,
        )
        chart_id = store.add("chart", spec)
        spec.id = chart_id
        return {
            "chart_id": chart_id,
            "title": title,
            "n_points": len(spec.data),
            "preview": spec.data[:3],
        }

    @tool
    @safe_tool
    def line_chart(
        date_column: str,
        value_column: str,
        agg: str = "sum",
        freq: str = "auto",
        group_column: str | None = None,
    ) -> dict:
        """Build a line chart of a numeric column over time, optionally split by group.

        Args:
            date_column: A column already parsed as datetime.
            value_column: Numeric column to aggregate per period.
            agg: One of "sum", "mean", "median", "count".
            freq: Resample frequency: "D", "W", "ME", "QE", or "auto" to pick the
                finest one that keeps the number of points reasonable.
            group_column: Optional column to split into up to 5 lines (by total
                value_column descending).

        Returns:
            A dict with chart_id, title, n_points, and a preview of the first rows.
        """
        date_column = require_column(df, date_column)
        if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
            raise ToolError(f"Column '{date_column}' is not a date column.")
        value_column = require_numeric(df, value_column)
        if agg not in _LINE_AGGS:
            raise ToolError(f"agg must be one of sum, mean, median, count, got '{agg}'")

        subset = df[[date_column, value_column]].dropna()
        if group_column is not None:
            group_column = require_column(df, group_column)
            subset = df[[date_column, value_column, group_column]].dropna(
                subset=[date_column, value_column]
            )

        resolved_freq = _resolve_freq(subset, date_column, value_column, freq)
        word = _FREQ_WORDS[resolved_freq]

        if group_column is None:
            resampled = subset.set_index(date_column)[value_column].resample(resolved_freq).agg(agg)
            resampled = resampled.dropna()
            value_label = "count" if agg == "count" else f"{value_column} ({agg})"
            data = [
                {date_column: ts.strftime("%Y-%m-%d"), value_label: num(v)}
                for ts, v in resampled.items()
            ]
            series = [value_label]
            title = f"{value_column.capitalize()} over time ({word})"
            y_label = value_label
        else:
            totals = subset.groupby(group_column, observed=True)[value_column].sum()
            top_groups = totals.sort_values(ascending=False).head(5).index.tolist()

            per_group = {}
            all_periods: set = set()
            for grp in top_groups:
                grp_subset = subset[subset[group_column] == grp]
                resampled = (
                    grp_subset.set_index(date_column)[value_column].resample(resolved_freq).agg(agg)
                )
                resampled = resampled.dropna()
                per_group[grp] = resampled
                all_periods.update(resampled.index)

            sorted_periods = sorted(all_periods)
            data = []
            for period in sorted_periods:
                row: dict[str, float | str | None] = {date_column: period.strftime("%Y-%m-%d")}
                for grp in top_groups:
                    series_for_grp = per_group[grp]
                    has_period = period in series_for_grp.index
                    row[str(grp)] = num(series_for_grp[period]) if has_period else None
                data.append(row)

            series = [str(g) for g in top_groups]
            title = f"{value_column.capitalize()} over time by {group_column} ({word})"
            y_label = value_column

        spec = ChartSpec(
            id="",
            type="line",
            title=title,
            caption="",
            x_key=date_column,
            x_label=date_column,
            y_label=y_label,
            series=series,
            data=data,
        )
        chart_id = store.add("chart", spec)
        spec.id = chart_id
        return {
            "chart_id": chart_id,
            "title": title,
            "n_points": len(spec.data),
            "preview": spec.data[:3],
        }

    @tool
    @safe_tool
    def histogram(column: str, bins: int = 20, group_column: str | None = None) -> dict:
        """Build a histogram of a numeric column's distribution, optionally split by group.

        Extreme values are folded into the first and last bins so one outlier
        cannot squash the rest of the distribution into a single bar.

        Args:
            column: Numeric column to bin.
            bins: Number of bins (capped at 40).
            group_column: Optional column to split into up to 5 series (by count
                of non-null `column` values, largest first); all series share the
                same bin edges, computed over the whole column.

        Returns:
            A dict with chart_id, title, n_points, how many values were folded
            into the edge bins, and a preview of the first rows.
        """
        column = require_numeric(df, column)
        capped_bins = max(1, min(bins, 40))

        if group_column is not None:
            group_column = require_column(df, group_column)
            subset = df[[column, group_column]].dropna()
            if subset.empty:
                raise ToolError(f"Column '{column}' has no non-null values to plot.")
            edges, folded = _robust_edges(subset[column].to_numpy(), capped_bins)
            group_counts = subset.groupby(group_column, observed=True)[column].count()
            top_groups = group_counts.sort_values(ascending=False).head(5).index.tolist()
            per_group = {
                str(grp): _bin_counts(subset.loc[subset[group_column] == grp, column], edges)
                for grp in top_groups
            }
            data: list[dict[str, float | str | None]] = []
            for i, label in enumerate(_bin_labels(edges, folded)):
                row: dict[str, float | str | None] = {"bin": label}
                for grp, counts in per_group.items():
                    row[grp] = int(counts[i])
                data.append(row)
            series = list(per_group)
            title = f"Distribution of {column} by {group_column}"
        else:
            values = df[column].dropna()
            if values.empty:
                raise ToolError(f"Column '{column}' has no non-null values to plot.")
            edges, folded = _robust_edges(values.to_numpy(), capped_bins)
            counts = _bin_counts(values, edges)
            data = [
                {"bin": label, "count": int(counts[i])}
                for i, label in enumerate(_bin_labels(edges, folded))
            ]
            series = ["count"]
            title = f"Distribution of {column}"

        spec = ChartSpec(
            id="",
            type="histogram",
            title=title,
            caption="",
            x_key="bin",
            x_label=column,
            y_label="count",
            series=series,
            data=data,
        )
        chart_id = store.add("chart", spec)
        spec.id = chart_id
        return {
            "chart_id": chart_id,
            "title": title,
            "n_points": len(spec.data),
            "folded_into_edge_bins": folded,
            "preview": spec.data[:3],
        }

    @tool
    @safe_tool
    def scatter_chart(x_column: str, y_column: str, max_points: int = 300) -> dict:
        """Build a scatter chart between two numeric columns.

        Args:
            x_column: Numeric column for the x axis.
            y_column: Numeric column for the y axis.
            max_points: Max number of points to plot; sampled if more rows exist.

        Returns:
            A dict with chart_id, title, n_points, and a preview of the first rows.
        """
        x_column = require_numeric(df, x_column)
        y_column = require_numeric(df, y_column)
        subset = df[[x_column, y_column]].dropna()
        if subset.empty:
            raise ToolError("No rows have both values present.")
        if len(subset) > max_points:
            subset = subset.sample(n=max_points, random_state=0)

        data = [
            {"x": num(x), "y": num(y)}
            for x, y in zip(subset[x_column], subset[y_column], strict=True)
        ]
        title = f"{y_column} vs {x_column}"

        spec = ChartSpec(
            id="",
            type="scatter",
            title=title,
            caption="",
            x_key="x",
            x_label=x_column,
            y_label=y_column,
            series=["y"],
            data=data,
        )
        chart_id = store.add("chart", spec)
        spec.id = chart_id
        return {
            "chart_id": chart_id,
            "title": title,
            "n_points": len(spec.data),
            "preview": spec.data[:3],
        }

    @tool
    @safe_tool
    def box_plot(value_column: str, group_column: str | None = None) -> dict:
        """Build a box plot of a numeric column, optionally split by group.

        Whiskers are the 1.5*IQR fences (min/max in the data are 'min'/'max' in each
        row only if no more extreme point exists inside the fence); points beyond the
        fences are counted in 'outliers' rather than stretching the whiskers.

        Args:
            value_column: Numeric column to summarize.
            group_column: Optional column to split into up to 10 groups (by count,
                largest first). Without it, a single box for the whole column.

        Returns:
            A dict with chart_id, title, n_points, and a preview of the first rows.
        """
        value_column = require_numeric(df, value_column)
        if group_column is None:
            groups: list[tuple[str, pd.Series]] = [(value_column, df[value_column].dropna())]
        else:
            group_column = require_column(df, group_column)
            subset = df[[group_column, value_column]].dropna()
            counts = subset.groupby(group_column, observed=True)[value_column].count()
            top = counts.sort_values(ascending=False).head(10).index
            groups = [
                (str(grp), subset.loc[subset[group_column] == grp, value_column]) for grp in top
            ]

        data = []
        for label, s in groups:
            if s.empty:
                continue
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            inliers = s[(s >= lo_fence) & (s <= hi_fence)]
            whisker_min = float(inliers.min()) if not inliers.empty else float(s.min())
            whisker_max = float(inliers.max()) if not inliers.empty else float(s.max())
            outliers = int(((s < lo_fence) | (s > hi_fence)).sum())
            data.append(
                {
                    "group": label,
                    "min": num(whisker_min),
                    "q1": num(q1),
                    "median": num(s.median()),
                    "q3": num(q3),
                    "max": num(whisker_max),
                    "n": int(s.count()),
                    "outliers": outliers,
                }
            )
        if not data:
            raise ToolError(f"No non-null values found to plot for '{value_column}'.")
        data.sort(key=lambda r: r["n"], reverse=True)

        title = (
            f"Distribution of {value_column} by {group_column}"
            if group_column is not None
            else f"Distribution of {value_column}"
        )
        spec = ChartSpec(
            id="",
            type="box",
            title=title,
            caption="",
            x_key="group",
            x_label=group_column if group_column is not None else value_column,
            y_label=value_column,
            series=["median"],
            data=data,
        )
        chart_id = store.add("chart", spec)
        spec.id = chart_id
        return {
            "chart_id": chart_id,
            "title": title,
            "n_points": len(spec.data),
            "preview": spec.data[:3],
        }

    @tool
    @safe_tool
    def cumulative_chart(column: str, points: int = 50) -> dict:
        """Build an empirical cumulative distribution (CDF) chart of a numeric column.

        Args:
            column: Numeric column to plot.
            points: Roughly how many points to sample along the CDF (capped at 200).

        Returns:
            A dict with chart_id, title, n_points, and a preview of the first rows.
        """
        column = require_numeric(df, column)
        s = df[column].dropna()
        if s.empty:
            raise ToolError(f"Column '{column}' has no non-null values to plot.")

        capped_points = max(2, min(points, 200))
        k = min(capped_points, int(s.count()))
        quantiles = np.linspace(0, 1, k)
        values = s.quantile(quantiles)

        data = [
            {"value": num(v), "pct": num(q * 100)} for q, v in zip(quantiles, values, strict=True)
        ]
        title = f"Cumulative distribution of {column}"

        spec = ChartSpec(
            id="",
            type="line",
            title=title,
            caption="",
            x_key="value",
            x_label=column,
            y_label="% of rows at or below",
            series=["pct"],
            data=data,
        )
        chart_id = store.add("chart", spec)
        spec.id = chart_id
        return {
            "chart_id": chart_id,
            "title": title,
            "n_points": len(spec.data),
            "preview": spec.data[:3],
        }

    return [bar_chart, line_chart, histogram, scatter_chart, box_plot, cumulative_chart]


def _resolve_freq(subset: pd.DataFrame, date_column: str, value_column: str, freq: str) -> str:
    if freq != "auto":
        if freq not in _LINE_FREQS:
            raise ToolError(f"freq must be one of D, W, ME, QE, auto, got '{freq}'")
        return freq
    indexed = subset.set_index(date_column)[value_column]
    for candidate in _AUTO_CANDIDATES:
        n_periods = len(indexed.resample(candidate).size())
        if n_periods <= _MAX_POINTS:
            return candidate
    return "QE"


def _robust_edges(values: np.ndarray, bins: int) -> tuple[np.ndarray, int]:
    """Bin edges over the bulk of the data; returns how many values fall outside.

    The range is clipped to 3 IQRs beyond the quartiles so a lone extreme value
    does not stretch the axis. Values outside land in the first or last bin.
    """
    values = values[np.isfinite(values)]
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    lo = max(float(values.min()), float(q1 - 3 * iqr))
    hi = min(float(values.max()), float(q3 + 3 * iqr))
    if hi <= lo:
        lo, hi = float(values.min()), float(values.max())
    if hi <= lo:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)
    folded = int(((values < lo) | (values > hi)).sum())
    return edges, folded


def _bin_counts(values: pd.Series, edges: np.ndarray) -> np.ndarray:
    clipped = np.clip(values.to_numpy(dtype=float), edges[0], edges[-1])
    counts, _ = np.histogram(clipped, bins=edges)
    return counts


def _bin_labels(edges: np.ndarray, folded: int) -> list[str]:
    labels = [f"{edges[i]:.1f}–{edges[i + 1]:.1f}" for i in range(len(edges) - 1)]
    if folded:
        labels[0] = f"≤{edges[1]:.1f}"
        labels[-1] = f"≥{edges[-2]:.1f}"
    return labels
