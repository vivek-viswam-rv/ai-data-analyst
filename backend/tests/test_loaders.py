import io

import pandas as pd
import pytest

from app.analysis.loaders import LoadError, load_dataframe, sample_rows


def test_loads_csv(sales_csv):
    df = load_dataframe("sales.csv", sales_csv)
    assert list(df.columns)[:3] == ["order_id", "order_date", "region"]
    assert len(df) == 203


def test_sniffs_semicolon_delimiter():
    data = b"a;b;c\n1;2;3\n4;5;6\n"
    df = load_dataframe("data.csv", data)
    assert list(df.columns) == ["a", "b", "c"]
    assert df.shape == (2, 3)


def test_loads_excel(sales_df):
    buf = io.BytesIO()
    sales_df.to_excel(buf, index=False)
    df = load_dataframe("sales.xlsx", buf.getvalue())
    assert "revenue" in df.columns
    assert len(df) == 203


def test_rejects_unknown_extension():
    with pytest.raises(LoadError):
        load_dataframe("data.parquet", b"whatever")


def test_rejects_empty_file():
    with pytest.raises(LoadError):
        load_dataframe("data.csv", b"")


def test_names_unnamed_columns():
    df = load_dataframe("data.csv", b",b\n1,2\n")
    assert list(df.columns) == ["column_1", "b"]


def test_decodes_latin1():
    data = "name,city\nJosé,Zürich\n".encode("latin-1")
    df = load_dataframe("data.csv", data)
    assert df.loc[0, "name"] == "José"


def test_sample_rows_caps_and_flags():
    df = pd.DataFrame({"x": range(100)})
    kept, sampled = sample_rows(df, 10)
    assert len(kept) == 10 and sampled
    kept, sampled = sample_rows(df, 100)
    assert len(kept) == 100 and not sampled
