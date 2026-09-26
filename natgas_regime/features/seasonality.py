from __future__ import annotations
import pandas as pd

def season_bucket(dates: pd.Series) -> pd.Series:
    month = pd.to_datetime(dates).dt.month
    winter = month.isin([11, 12, 1, 2, 3])
    summer = month.isin([6, 7, 8])
    return pd.Series(
        ["winter" if w else "summer" if s else "shoulder" for w, s in zip(winter, summer)],
        index=dates.index,
        dtype="object",
    )

