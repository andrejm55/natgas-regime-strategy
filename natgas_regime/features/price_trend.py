from __future__ import annotations
import pandas as pd

def add_price_trend(
    frame: pd.DataFrame,
    price_col: str = "ng1_settle",
    windows: tuple[int, ...] = (20, 60),
) -> pd.DataFrame:
    out = frame.sort_values("date").copy()
    for window in windows:
        out[f"momentum_{window}d"] = out[price_col].pct_change(window)
        out[f"sma_{window}d"] = out[price_col].rolling(window).mean()
        out[f"price_vs_sma_{window}d"] = out[price_col] / out[f"sma_{window}d"] - 1.0
    return out
