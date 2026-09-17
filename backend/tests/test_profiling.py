import pandas as pd

from app.analysis.loaders import load_dataframe
from app.analysis.profiling import build_brief, coerce_types, column_kind


def test_coerce_types_parses_dates_and_numbers():
    df = pd.DataFrame(
        {
            "when": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "amount": ["$1,200", "$300", "$45"],
            "label": ["a", "b", "c"],
        }
    )
    out = coerce_types(df)
    assert pd.api.types.is_datetime64_any_dtype(out["when"])
    assert out["amount"].tolist() == [1200, 300, 45]
    assert column_kind(out["label"]) == "text"


def test_numeric_strings_are_not_dates():
    df = pd.DataFrame({"code": ["20250101", "20250102", "20250103"]})
    out = coerce_types(df)
    assert pd.api.types.is_numeric_dtype(out["code"])


def test_brief_classifies_columns(sales_csv):
    df = coerce_types(load_dataframe("sales.csv", sales_csv))
    brief = build_brief(df, "sales.csv")
    kinds = {c.name: c.kind for c in brief.columns}
    assert kinds["order_date"] == "datetime"
    assert kinds["region"] == "categorical"
    assert kinds["revenue"] == "numeric"
    assert "notes" not in kinds  # fully empty columns are dropped on load
    assert "units" in brief.numeric_columns
    assert brief.n_rows == 203 and not brief.sampled
    assert len(brief.preview) == 5


def test_brief_prompt_mentions_every_column(sales_csv):
    df = coerce_types(load_dataframe("sales.csv", sales_csv))
    text = build_brief(df, "sales.csv").to_prompt()
    for col in df.columns:
        assert col in text


def test_id_column_detection():
    df = pd.DataFrame({"customer_id": range(10), "score": range(10)})
    brief = build_brief(df, "x.csv")
    assert brief.id_columns == ["customer_id"]
