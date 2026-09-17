import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sales_df() -> pd.DataFrame:
    """A small synthetic sales table with planted defects."""
    rng = np.random.default_rng(42)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    regions = rng.choice(["North", "South", "East", "West"], size=n)
    units = rng.integers(1, 50, size=n).astype(float)
    price = rng.normal(20, 3, size=n).round(2)
    revenue = (units * price).round(2)
    df = pd.DataFrame(
        {
            "order_id": np.arange(1, n + 1),
            "order_date": dates.strftime("%Y-%m-%d"),
            "region": regions,
            "units": units,
            "unit_price": price,
            "revenue": revenue,
            "notes": ["" for _ in range(n)],
        }
    )
    # Planted defects: nulls, duplicates, an outlier, inconsistent casing.
    df.loc[5:14, "units"] = np.nan
    df.loc[20, "revenue"] = 1_000_000
    df.loc[30:34, "region"] = "north"
    df = pd.concat([df, df.iloc[:3]], ignore_index=True)
    return df


@pytest.fixture
def sales_csv(sales_df) -> bytes:
    return sales_df.to_csv(index=False).encode()
