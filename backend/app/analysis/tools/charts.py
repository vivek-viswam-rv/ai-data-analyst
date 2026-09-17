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
    ) -> dict:
        """Build a bar chart of a category column, optionally aggregating a value.

        Args:
            category_column: Column to group by (bars are its distinct values).
            value_column: Numeric column to aggregate. Required unless agg="count".
            agg: One of "count", "sum", "mean", "median".
            top_n: Max number of bars to keep, sorted by value descending (max 50).

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
    def histogram(column: str, bins: int = 20) -> dict:
        """Build a histogram of a numeric column's distribution.

        Args:
            column: Numeric column to bin.
            bins: Number of bins (capped at 40).

        Returns:
            A dict with chart_id, title, n_points, and a preview of the first rows.
        """
        column = require_numeric(df, column)
        capped_bins = max(1, min(bins, 40))
        values = df[column].dropna()
        if values.empty:
            raise ToolError(f"Column '{column}' has no non-null values to plot.")

        counts, edges = np.histogram(values, bins=capped_bins)
        data = [
            {"bin": f"{edges[i]:.1f}–{edges[i + 1]:.1f}", "count": int(counts[i])}
            for i in range(len(counts))
        ]
        title = f"Distribution of {column}"

        spec = ChartSpec(
            id="",
            type="histogram",
            title=title,
            caption="",
            x_key="bin",
            x_label=column,
            y_label="count",
            series=["count"],
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

    return [bar_chart, line_chart, histogram, scatter_chart]


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
