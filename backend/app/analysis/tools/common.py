"""Helpers shared by every tool module."""

import functools
import json
import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

MAX_ROWS_IN_RESULT = 20
MAX_TEXT = 60


class ToolError(ValueError):
    """Raised by a tool when the model asked for something it cannot do.

    The message is shown to the model so it should say what to do instead.
    """


class ArtifactStore:
    """Holds things tools computed that the model should reference by id.

    Rows, chart data and test results are big and easy to garble, so the model
    never copies them. It asks a tool, gets an id back, and the report is
    assembled from the store after the model finishes.
    """

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}
        self._counter = 0

    def add(self, prefix: str, payload: Any) -> str:
        self._counter += 1
        key = f"{prefix}_{self._counter}"
        self._items[key] = payload
        return key

    def get(self, key: str) -> Any:
        return self._items[key]

    def has(self, key: str) -> bool:
        return key in self._items

    def items(self, prefix: str | None = None) -> list[tuple[str, Any]]:
        return [
            (k, v) for k, v in self._items.items() if prefix is None or k.startswith(prefix + "_")
        ]


def safe_tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Turn tool exceptions into an error payload the model can read and recover from."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolError as exc:
            return {"error": str(exc)}
        except (KeyError, ValueError, TypeError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    return wrapper


def require_column(df: pd.DataFrame, name: str) -> str:
    if name in df.columns:
        return name
    lowered = {str(c).lower(): str(c) for c in df.columns}
    if name.lower() in lowered:
        return lowered[name.lower()]
    raise ToolError(
        f"No column named '{name}'. Available columns: {', '.join(map(str, df.columns))}"
    )


def require_numeric(df: pd.DataFrame, name: str) -> str:
    col = require_column(df, name)
    if not pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
        raise ToolError(
            f"Column '{col}' is not numeric. Numeric columns: {', '.join(numeric_columns(df))}"
        )
    return col


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [
        str(c)
        for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
    ]


def categorical_columns(df: pd.DataFrame, max_unique: int = 50) -> list[str]:
    out = []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_bool_dtype(s):
            out.append(str(c))
        elif pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s):
            if s.nunique(dropna=True) <= max_unique:
                out.append(str(c))
    return out


def datetime_columns(df: pd.DataFrame) -> list[str]:
    return [str(c) for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]


def fmt(value: Any) -> str:
    """Render a cell for the model or the UI: short, stable, JSON-safe."""
    if value is None:
        return ""
    if isinstance(value, float | np.floating):
        f = float(value)
        return "" if math.isnan(f) else f"{f:.6g}"
    if isinstance(value, np.integer):
        return str(int(value))
    if isinstance(value, pd.Timestamp):
        return "" if pd.isna(value) else value.isoformat(sep=" ", timespec="seconds")
    if value is pd.NaT or (isinstance(value, float) and math.isnan(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 3] + "..."


def num(value: Any) -> float | None:
    """Float that JSON can carry, or None for nan/inf/missing."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 6)


def rows_as_lists(df: pd.DataFrame, max_rows: int = MAX_ROWS_IN_RESULT) -> list[list[str]]:
    return [[fmt(v) for v in row] for row in df.head(max_rows).itertuples(index=False)]


def records(df: pd.DataFrame, max_rows: int = MAX_ROWS_IN_RESULT) -> list[dict[str, str]]:
    return [
        {str(k): fmt(v) for k, v in row.items()}
        for row in df.head(max_rows).to_dict(orient="records")
    ]


def series_summary(s: pd.Series) -> dict[str, float | None]:
    d = s.dropna()
    if d.empty:
        return {"count": 0}
    return {
        "count": int(d.count()),
        "mean": num(d.mean()),
        "std": num(d.std()) if len(d) > 1 else None,
        "min": num(d.min()),
        "p25": num(d.quantile(0.25)),
        "median": num(d.median()),
        "p75": num(d.quantile(0.75)),
        "max": num(d.max()),
    }


def compact_json(payload: Any) -> str:
    return json.dumps(payload, default=fmt, separators=(",", ":"))
