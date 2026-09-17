"""Deterministic first look at a dataset. No model calls happen here.

The brief this produces is what every agent sees instead of the raw rows.
"""

from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.analysis.tools.common import fmt as _fmt

ColumnKind = Literal["numeric", "datetime", "boolean", "categorical", "text", "empty"]

SAMPLE_VALUES = 5
PREVIEW_ROWS = 5
CATEGORICAL_MAX_UNIQUE = 50
CATEGORICAL_MAX_RATIO = 0.5


class ColumnProfile(BaseModel):
    name: str
    kind: ColumnKind
    pandas_dtype: str
    null_count: int
    null_pct: float
    unique: int
    sample_values: list[str]
    min: str | None = None
    max: str | None = None
    mean: float | None = None
    std: float | None = None


class DatasetBrief(BaseModel):
    filename: str
    n_rows: int
    n_cols: int
    original_rows: int
    sampled: bool
    columns: list[ColumnProfile]
    numeric_columns: list[str]
    datetime_columns: list[str]
    categorical_columns: list[str]
    id_columns: list[str]
    preview: list[dict[str, str]]

    def to_prompt(self) -> str:
        sampled_note = f" (sampled from {self.original_rows})" if self.sampled else ""
        lines = [
            f"Dataset: {self.filename}",
            f"Rows: {self.n_rows}" + sampled_note,
            f"Columns: {self.n_cols}",
            "",
            "Column | kind | nulls | unique | sample values | range",
        ]
        for c in self.columns:
            rng = ""
            if c.min is not None and c.max is not None:
                rng = f"{c.min} to {c.max}"
            samples = ", ".join(c.sample_values)
            lines.append(
                f"{c.name} | {c.kind} | {c.null_pct:.1f}% | {c.unique} | {samples} | {rng}"
            )
        if self.id_columns:
            lines += ["", f"Likely identifier columns: {', '.join(self.id_columns)}"]
        return "\n".join(lines)


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Parse string columns that are really dates or numbers. Returns a new frame."""
    out = df.copy()
    for col in out.columns:
        s = out[col]
        if not pd.api.types.is_string_dtype(s) and not pd.api.types.is_object_dtype(s):
            continue
        parsed = _try_datetime(s)
        if parsed is not None:
            out[col] = parsed
            continue
        parsed = _try_numeric(s)
        if parsed is not None:
            out[col] = parsed
    return out


def _try_datetime(s: pd.Series) -> pd.Series | None:
    non_null = s.dropna()
    if non_null.empty:
        return None
    # Pure numbers are not dates, even if to_datetime would accept them as epochs.
    if pd.to_numeric(non_null.head(50), errors="coerce").notna().mean() > 0.5:
        return None
    try:
        parsed = pd.to_datetime(s, errors="coerce", format="mixed")
    except (ValueError, TypeError):
        return None
    if parsed.notna().sum() >= 0.9 * len(non_null):
        return parsed
    return None


def _try_numeric(s: pd.Series) -> pd.Series | None:
    non_null = s.dropna()
    if non_null.empty:
        return None
    cleaned = non_null.astype(str).str.replace(r"[,$€£%\s]", "", regex=True)
    parsed = pd.to_numeric(cleaned, errors="coerce")
    if parsed.notna().sum() >= 0.95 * len(non_null):
        full = pd.to_numeric(
            s.astype(str).str.replace(r"[,$€£%\s]", "", regex=True), errors="coerce"
        )
        return full
    return None


def column_kind(s: pd.Series) -> ColumnKind:
    if s.dropna().empty:
        return "empty"
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_numeric_dtype(s):
        return "numeric"
    unique = s.nunique(dropna=True)
    n = int(s.notna().sum())
    if unique <= CATEGORICAL_MAX_UNIQUE and unique / max(n, 1) <= CATEGORICAL_MAX_RATIO:
        return "categorical"
    if unique <= 2:
        return "categorical"
    return "text"


def profile_column(name: str, s: pd.Series) -> ColumnProfile:
    kind = column_kind(s)
    null_count = int(s.isna().sum())
    profile = ColumnProfile(
        name=name,
        kind=kind,
        pandas_dtype=str(s.dtype),
        null_count=null_count,
        null_pct=round(100 * null_count / max(len(s), 1), 2),
        unique=int(s.nunique(dropna=True)),
        sample_values=[_fmt(v) for v in s.dropna().unique()[:SAMPLE_VALUES]],
    )
    non_null = s.dropna()
    if kind == "numeric" and not non_null.empty:
        profile.min = _fmt(non_null.min())
        profile.max = _fmt(non_null.max())
        profile.mean = _safe_float(non_null.mean())
        profile.std = _safe_float(non_null.std()) if len(non_null) > 1 else None
    elif kind == "datetime" and not non_null.empty:
        profile.min = _fmt(non_null.min())
        profile.max = _fmt(non_null.max())
    return profile


def build_brief(df: pd.DataFrame, filename: str, original_rows: int | None = None) -> DatasetBrief:
    original = original_rows if original_rows is not None else len(df)
    columns = [profile_column(str(c), df[c]) for c in df.columns]
    kinds = {c.name: c.kind for c in columns}
    id_columns = [
        c.name
        for c in columns
        if c.unique == len(df)
        and len(df) > 1
        and c.kind in ("numeric", "text", "categorical")
        and (c.kind != "numeric" or _looks_like_id(c.name))
    ]
    preview = [
        {str(k): _fmt(v) for k, v in row.items()}
        for row in df.head(PREVIEW_ROWS).to_dict(orient="records")
    ]
    return DatasetBrief(
        filename=filename,
        n_rows=len(df),
        n_cols=df.shape[1],
        original_rows=original,
        sampled=original != len(df),
        columns=columns,
        numeric_columns=[n for n, k in kinds.items() if k == "numeric"],
        datetime_columns=[n for n, k in kinds.items() if k == "datetime"],
        categorical_columns=[n for n, k in kinds.items() if k in ("categorical", "boolean")],
        id_columns=id_columns,
        preview=preview,
    )


def _looks_like_id(name: str) -> bool:
    lowered = name.lower()
    return lowered == "id" or lowered.endswith("_id") or lowered.endswith("id") or "key" in lowered


def _safe_float(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) or np.isinf(f) else round(f, 6)
