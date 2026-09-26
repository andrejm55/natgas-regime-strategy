from __future__ import annotations
import numpy as np
import pandas as pd

def add_realized_vol(
    frame: pd.DataFrame,
    price_col: str = "ng1_settle",
    window: int = 20,
    percentile_window: int = 252,
    riskoff_percentile: float = 0.80,
) -> pd.DataFrame:
    out = frame.sort_values("date").copy()
    returns = np.log(out[price_col]).diff()
    out["return"] = returns
    out["rv20"] = returns.rolling(window).std() * np.sqrt(252)
    out["rv_threshold"] = out["rv20"].rolling(percentile_window, min_periods=window).quantile(
        riskoff_percentile
    )
    out["riskoff"] = out["rv20"] > out["rv_threshold"]
    return out

