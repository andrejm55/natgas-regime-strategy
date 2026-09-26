from __future__ import annotations
from datetime import date
import pandas as pd


def business_days_before(day: date | pd.Timestamp, n: int) -> pd.Timestamp:
    """Return the business date n days before day using a Monday-Friday calendar."""
    ts = pd.Timestamp(day).normalize()
    return ts - pd.offsets.BDay(n)


def build_roll_calendar(
    expirations: pd.DataFrame,
    business_days_before_expiration: int = 2,
) -> pd.DataFrame:
    """Build roll dates from a contract expiration table.

    Expected input columns:
    - contract: e.g. NGJ2026
    - expiration_date: final trading/expiration date
    """
    required = {"contract", "expiration_date"}
    missing = required - set(expirations.columns)
    if missing:
        raise ValueError(f"expiration table missing columns: {sorted(missing)}")

    out = expirations.copy()
    out["expiration_date"] = pd.to_datetime(
        out["expiration_date"],
        format="mixed",
    ).dt.normalize()
    out["roll_date"] = out["expiration_date"].map(
        lambda x: business_days_before(x, business_days_before_expiration)
    )
    return out.sort_values("roll_date").reset_index(drop=True)
