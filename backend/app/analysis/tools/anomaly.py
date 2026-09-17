"""Tools for detecting and characterizing anomalies/outliers in a dataset.

Each tool runs a deterministic numpy/pandas/scipy computation, registers an
`AnomalyGroup` in the shared `ArtifactStore` (with `interpretation=""` left
for the model to fill in later via `assemble`), records which row positions
it flagged in the `flagged` dict, and returns a small JSON-able dict the
model can reason about without ever seeing raw rows.
"""

import numpy as np
import pandas as pd
from langchain_core.tools import BaseTool, tool
from scipy import stats

from app.analysis.schemas import AnomalyGroup
from app.analysis.tools.common import (
    ArtifactStore,
    ToolError,
    datetime_columns,
    fmt,
    numeric_columns,
    require_column,
    require_numeric,
    safe_tool,
)

MAX_EXAMPLES_STORE = 10
MAX_EXAMPLES_RETURN = 5
MAX_MULTIVARIATE_COLUMNS = 8
MAX_RARE_CATEGORIES = 20
MAHALANOBIS_CI = 0.999
TS_MAD_SCALE = 3.5 * 1.4826


def build_tools(
    df: pd.DataFrame, store: ArtifactStore, id_columns: list[str]
) -> tuple[list[BaseTool], dict[str, set[int]]]:
    """Build the anomaly-detection tool set, closed over `df`.

    Returns:
        The tools, plus a `flagged` dict the tools mutate as they run,
        mapping each registered group id to the set of positional (0-indexed)
        row indices it flagged.
    """
    flagged: dict[str, set[int]] = {}

    def register(
        *,
        method: str,
        columns: list[str],
        count: int,
        description: str,
        example_columns: list[str],
        example_rows: list[list[str]],
        positions: set[int],
    ) -> str:
        group = AnomalyGroup(
            id="",
            method=method,
            columns=columns,
            count=count,
            description=description,
            interpretation="",
            example_columns=example_columns,
            example_rows=example_rows,
        )
        group_id = store.add("group", group)
        store.get(group_id).id = group_id
        flagged[group_id] = positions
        return group_id

    @tool
    @safe_tool
    def iqr_outliers(column: str, k: float = 1.5) -> dict:
        """Flag values outside [Q1 - k*IQR, Q3 + k*IQR] for a numeric column.

        Args:
            column: Numeric column to check.
            k: IQR fence multiplier (default 1.5; larger is more permissive).

        Returns:
            A dict with group_id, count, pct, the bounds used, and up to 5
            example rows (most extreme first).
        """
        col = require_numeric(df, column)
        s = df[col]
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - k * iqr, q3 + k * iqr
        mask = s.notna() & ((s < lower) | (s > upper))
        positions = np.flatnonzero(mask.to_numpy())
        values = s.to_numpy()[positions]
        dist = np.maximum(lower - values, values - upper)
        reasons = [fmt(v) for v in values]

        example_columns, rows_full, rows_dict = _examples(
            df, id_columns, [col], positions, reasons, dist
        )
        count = int(len(positions))
        description = (
            f"IQR outliers on '{col}' (k={k}): {count} row(s) outside [{fmt(lower)}, {fmt(upper)}]."
        )
        group_id = register(
            method="iqr",
            columns=[col],
            count=count,
            description=description,
            example_columns=example_columns,
            example_rows=rows_full,
            positions={int(p) for p in positions},
        )
        return {
            "group_id": group_id,
            "count": count,
            "pct": _pct(count, len(df)),
            "column": col,
            "k": k,
            "lower_bound": fmt(lower),
            "upper_bound": fmt(upper),
            "examples": rows_dict,
        }

    @tool
    @safe_tool
    def robust_zscore_outliers(column: str, threshold: float = 3.5) -> dict:
        """Flag values with a large modified (median-based) z-score.

        Args:
            column: Numeric column to check.
            threshold: Absolute modified z-score above which a value is flagged.

        Returns:
            A dict with group_id, count, pct, the threshold used, and up to 5
            example rows (largest |z| first).
        """
        col = require_numeric(df, column)
        s = df[col]
        median = s.median()
        mad = (s - median).abs().median()
        if mad == 0:
            raise ToolError(
                f"Column '{col}' is too concentrated around its median to compute "
                "a robust z-score (MAD is 0)."
            )
        modified_z = 0.6745 * (s - median) / mad
        mask = s.notna() & (modified_z.abs() > threshold)
        positions = np.flatnonzero(mask.to_numpy())
        z_values = modified_z.to_numpy()[positions]
        reasons = [fmt(v) for v in z_values]

        example_columns, rows_full, rows_dict = _examples(
            df, id_columns, [col], positions, reasons, np.abs(z_values)
        )
        count = int(len(positions))
        description = (
            f"Robust z-score outliers on '{col}' (threshold={threshold}): "
            f"{count} row(s) with |modified z| > {threshold}."
        )
        group_id = register(
            method="robust_zscore",
            columns=[col],
            count=count,
            description=description,
            example_columns=example_columns,
            example_rows=rows_full,
            positions={int(p) for p in positions},
        )
        return {
            "group_id": group_id,
            "count": count,
            "pct": _pct(count, len(df)),
            "column": col,
            "threshold": threshold,
            "examples": rows_dict,
        }

    @tool
    @safe_tool
    def multivariate_outliers(columns: list[str] | None = None, top_n: int = 20) -> dict:
        """Flag rows that are jointly unusual across several numeric columns.

        Computes squared Mahalanobis distance from the column-wise mean using
        the (pseudo-inverse) covariance matrix, and flags rows above the
        99.9th percentile of the corresponding chi-square distribution.

        Args:
            columns: Numeric columns to consider (capped at 8). Defaults to
                the first 8 numeric columns in the dataset.
            top_n: Maximum number of flagged rows to keep, largest distance first.

        Returns:
            A dict with group_id, count, pct, the columns used, the distance
            threshold, and up to 5 example rows (largest distance first).
        """
        if columns is None:
            selected = numeric_columns(df)[:MAX_MULTIVARIATE_COLUMNS]
        else:
            resolved = [require_numeric(df, c) for c in columns]
            selected = resolved[:MAX_MULTIVARIATE_COLUMNS]

        kept = []
        for c in selected:
            s = df[c]
            if s.nunique(dropna=True) <= 1:
                continue
            std = s.std()
            if std is None or pd.isna(std) or std == 0:
                continue
            kept.append(c)
        selected = kept

        if len(selected) < 2:
            raise ToolError(
                "Need at least 2 non-constant numeric columns for a multivariate check."
            )

        clean = df[selected].dropna()
        n_cols = len(selected)
        if len(clean) < 5 * n_cols:
            raise ToolError(
                f"Need at least {5 * n_cols} rows without missing values across "
                f"{n_cols} columns; only {len(clean)} available."
            )

        matrix = clean.to_numpy(dtype=float)
        mean = matrix.mean(axis=0)
        cov = np.cov(matrix, rowvar=False)
        inv_cov = np.linalg.pinv(cov)
        diff = matrix - mean
        d2 = np.einsum("ij,jk,ik->i", diff, inv_cov, diff)
        threshold = float(stats.chi2.ppf(MAHALANOBIS_CI, df=n_cols))

        flagged_mask = d2 > threshold
        clean_positions = df.index.get_indexer(clean.index)
        flagged_positions = clean_positions[flagged_mask]
        flagged_d2 = d2[flagged_mask]

        order = np.argsort(flagged_d2)[::-1][:top_n]
        top_positions = flagged_positions[order]
        top_d2 = flagged_d2[order]
        reasons = [fmt(v) for v in top_d2]

        example_columns, rows_full, rows_dict = _examples(
            df, id_columns, selected, top_positions, reasons, top_d2
        )
        count = int(len(top_positions))
        description = (
            f"Multivariate outliers (Mahalanobis) on {', '.join(selected)}: "
            f"{count} row(s) with squared distance above the 99.9th percentile "
            f"threshold ({fmt(threshold)})."
        )
        group_id = register(
            method="mahalanobis",
            columns=selected,
            count=count,
            description=description,
            example_columns=example_columns,
            example_rows=rows_full,
            positions={int(p) for p in top_positions},
        )
        return {
            "group_id": group_id,
            "count": count,
            "pct": _pct(count, len(df)),
            "columns": selected,
            "threshold": fmt(threshold),
            "examples": rows_dict,
        }

    @tool
    @safe_tool
    def time_series_outliers(
        date_column: str, value_column: str, freq: str = "D", window: int = 7
    ) -> dict:
        """Flag time periods whose aggregated value deviates sharply from its rolling median.

        Aggregates `value_column` by `freq` using `date_column`, computes a
        centered rolling median baseline, and flags periods whose residual
        from that baseline is large relative to the median absolute residual.

        Args:
            date_column: A column already parsed as a datetime.
            value_column: Numeric column to sum per period and check.
            freq: Period length: "D" (day), "W" (week), or "M" (month).
            window: Rolling window size, in periods, for the median baseline.

        Returns:
            A dict with group_id, count (flagged rows), pct, the frequency
            used, how many periods were flagged, and up to 5 example periods
            (largest |residual| first).
        """
        date_col = require_column(df, date_column)
        if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            raise ToolError(
                f"Column '{date_col}' is not a datetime column. "
                f"Datetime columns: {', '.join(datetime_columns(df))}"
            )
        value_col = require_numeric(df, value_column)
        if freq not in {"D", "W", "M"}:
            raise ToolError("freq must be one of D, W, M")
        pandas_freq = "ME" if freq == "M" else freq

        grouper = pd.Grouper(key=date_col, freq=pandas_freq)
        series = df.groupby(grouper)[value_col].sum().sort_index()
        if len(series) < 3:
            raise ToolError("Not enough time periods to detect anomalies; need at least 3.")

        rolling_median = series.rolling(window=window, center=True, min_periods=3).median()
        valid = rolling_median.notna()
        residual = (series - rolling_median)[valid]
        mad = residual.abs().median()
        flagged_mask = residual.abs() > (TS_MAD_SCALE * mad)
        flagged_periods = residual.index[flagged_mask.to_numpy()]

        position_groups = df.groupby(grouper).indices
        positions: list[int] = []
        for period in flagged_periods:
            positions.extend(int(p) for p in position_groups.get(period, []))
        positions_arr = np.array(sorted(set(positions)), dtype=int)

        flagged_residuals = residual[flagged_mask]
        periods_df = pd.DataFrame(
            {
                "period": flagged_periods,
                "value": series.reindex(flagged_periods).to_numpy(),
                "residual": flagged_residuals.to_numpy(),
            }
        )
        reasons = [fmt(v) for v in flagged_residuals.to_numpy()]
        example_columns, rows_full, rows_dict = _examples(
            periods_df,
            [],
            ["period", "value", "residual"],
            np.arange(len(periods_df)),
            reasons,
            np.abs(flagged_residuals.to_numpy()),
        )

        count = int(len(positions_arr))
        description = (
            f"Time-series outliers on '{value_col}' by '{date_col}' "
            f"(freq={freq}, window={window}): {len(flagged_periods)} period(s), "
            f"{count} row(s)."
        )
        group_id = register(
            method="time_series",
            columns=[date_col, value_col],
            count=count,
            description=description,
            example_columns=example_columns,
            example_rows=rows_full,
            positions={int(p) for p in positions_arr},
        )
        return {
            "group_id": group_id,
            "count": count,
            "pct": _pct(count, len(df)),
            "date_column": date_col,
            "value_column": value_col,
            "freq": freq,
            "periods_flagged": int(len(flagged_periods)),
            "examples": rows_dict,
        }

    @tool
    @safe_tool
    def rare_categories(column: str, max_pct: float = 1.0) -> dict:
        """Find rare/uncommon values in a column (e.g. typos or casing variants).

        Args:
            column: Column to check.
            max_pct: Flag values whose share of rows is at or below this percent.

        Returns:
            A dict with group_id, count, pct, the rare values found (with each
            value's own pct), and up to 5 example rows (rarest first).
        """
        col = require_column(df, column)
        total = len(df)
        counts = df[col].value_counts(dropna=True)
        pct_by_value = counts / total * 100 if total else counts.astype(float)
        rare = pct_by_value[pct_by_value <= max_pct].sort_values().iloc[:MAX_RARE_CATEGORIES]

        present_ids = [c for c in id_columns if c in df.columns]
        if rare.empty:
            group_id = register(
                method="rare_category",
                columns=[col],
                count=0,
                description=f"Rare categories in '{col}' (<= {max_pct}% of rows): none found.",
                example_columns=[*present_ids, col, "_reason"],
                example_rows=[],
                positions=set(),
            )
            return {
                "group_id": group_id,
                "count": 0,
                "pct": 0.0,
                "column": col,
                "max_pct": max_pct,
                "rare_values": [],
                "examples": [],
            }

        rare_values = rare.index.tolist()
        value_pct = dict(zip(rare_values, (float(p) for p in rare.to_numpy()), strict=True))
        mask = df[col].isin(rare_values)
        positions = np.flatnonzero(mask.to_numpy())
        pos_values = df[col].to_numpy()[positions]
        sort_key = np.array([value_pct[v] for v in pos_values])
        reasons = [f"{fmt(v)} ({value_pct[v]:.2f}% of rows)" for v in pos_values]

        example_columns, rows_full, rows_dict = _examples(
            df, id_columns, [col], positions, reasons, sort_key, ascending=True
        )
        count = int(len(positions))
        description = (
            f"Rare categories in '{col}' (<= {max_pct}% of rows): "
            f"{len(rare_values)} distinct value(s), {count} row(s)."
        )
        group_id = register(
            method="rare_category",
            columns=[col],
            count=count,
            description=description,
            example_columns=example_columns,
            example_rows=rows_full,
            positions={int(p) for p in positions},
        )
        return {
            "group_id": group_id,
            "count": count,
            "pct": _pct(count, len(df)),
            "column": col,
            "max_pct": max_pct,
            "rare_values": [{"value": fmt(v), "pct": round(p, 2)} for v, p in value_pct.items()],
            "examples": rows_dict,
        }

    return (
        [
            iqr_outliers,
            robust_zscore_outliers,
            multivariate_outliers,
            time_series_outliers,
            rare_categories,
        ],
        flagged,
    )


def _pct(count: int, total: int) -> float:
    return round(100 * count / total, 2) if total else 0.0


def _examples(
    df: pd.DataFrame,
    id_columns: list[str],
    columns: list[str],
    positions: np.ndarray | list[int],
    reasons: list[str],
    sort_key: np.ndarray,
    ascending: bool = False,
) -> tuple[list[str], list[list[str]], list[dict[str, str]]]:
    """Build example rows for a flagged group, most-extreme-first by default.

    Args:
        df: Frame to pull example values from (the row-level dataframe, or a
            small synthetic per-period frame for the time-series check).
        id_columns: Identifier columns to prefix each example row with, when
            present in `df`.
        columns: The columns involved in the detection.
        positions: Positional (0-indexed) rows in `df` that were flagged.
        reasons: Per-position strings explaining why the row was flagged,
            aligned with `positions`.
        sort_key: Numeric severity per position, aligned with `positions`,
            used to order examples.
        ascending: Sort `sort_key` ascending instead of descending.

    Returns:
        (example_columns, up to 10 example rows, up to 5 example row dicts).
    """
    positions = np.asarray(positions, dtype=int)
    present_ids = [c for c in id_columns if c in df.columns]
    example_columns = [*present_ids, *columns, "_reason"]
    if len(positions) == 0:
        return example_columns, [], []

    sort_key = np.asarray(sort_key, dtype=float)
    order = np.argsort(sort_key)
    if not ascending:
        order = order[::-1]
    order = order[:MAX_EXAMPLES_STORE]

    rows_full: list[list[str]] = []
    for i in order:
        pos = int(positions[i])
        row = df.iloc[pos]
        values = [fmt(row[c]) for c in present_ids] + [fmt(row[c]) for c in columns]
        values.append(str(reasons[i]))
        rows_full.append(values)

    rows_dict = [
        dict(zip(example_columns, r, strict=True)) for r in rows_full[:MAX_EXAMPLES_RETURN]
    ]
    return example_columns, rows_full, rows_dict
