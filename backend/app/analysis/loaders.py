"""Turn an uploaded file into a DataFrame."""

import io
from pathlib import PurePosixPath

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls"}


class LoadError(ValueError):
    """The upload could not be read as a table."""


def load_dataframe(filename: str, data: bytes) -> pd.DataFrame:
    if not data:
        raise LoadError("The file is empty.")

    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise LoadError(f"Unsupported file type '{suffix or 'none'}'. Upload a CSV or Excel file.")

    if suffix in {".xlsx", ".xlsm", ".xls"}:
        df = _read_excel(data)
    else:
        df = _read_delimited(data)

    if df.empty or df.shape[1] == 0:
        raise LoadError("The file has no rows or no columns.")

    return _tidy(df)


def _read_excel(data: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(data), sheet_name=0)
    except Exception as exc:  # openpyxl raises a range of things
        raise LoadError(f"Could not read the spreadsheet: {exc}") from exc


def _read_delimited(data: bytes) -> pd.DataFrame:
    text = _decode(data)
    try:
        # sep=None lets the python engine sniff commas, tabs, semicolons and pipes.
        return pd.read_csv(io.StringIO(text), sep=None, engine="python")
    except Exception:
        pass
    try:
        return pd.read_csv(io.StringIO(text))
    except Exception as exc:
        raise LoadError(f"Could not parse the file as CSV: {exc}") from exc


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise LoadError("Could not decode the file. Save it as UTF-8 and try again.")


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_clean_column_name(c, i) for i, c in enumerate(df.columns)]
    # Drop fully empty rows and columns; they carry no information for analysis.
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df = df.reset_index(drop=True)
    return df


def _clean_column_name(name: object, index: int) -> str:
    text = str(name).strip()
    if not text or text.lower().startswith("unnamed:"):
        return f"column_{index + 1}"
    return text


def sample_rows(df: pd.DataFrame, max_rows: int, seed: int = 0) -> tuple[pd.DataFrame, bool]:
    """Return at most max_rows rows. The second value says whether sampling happened."""
    if len(df) <= max_rows:
        return df, False
    return df.sample(n=max_rows, random_state=seed).sort_index().reset_index(drop=True), True
