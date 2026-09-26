from __future__ import annotations
import numpy as np
import pandas as pd


def make_sample_daily_data(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-02", "2026-07-31")
    returns = rng.normal(0.0001, 0.035, len(dates))
    price = 3.0 * np.exp(np.cumsum(returns))
    ng1 = np.maximum(price, 0.5)
    slope = rng.normal(0.015, 0.035, len(dates))
    ng2 = ng1 * (1.0 + slope)
    return pd.DataFrame(
        {
            "date": dates,
            "ng1_settle": ng1,
            "ng2_settle": ng2,
            "contract": "SAMPLE",
        }
    )


def make_sample_storage(seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    release_dates = pd.date_range("2018-01-04", "2026-07-30", freq="W-THU")
    seasonal = 2500 + 950 * np.sin(2 * np.pi * (release_dates.dayofyear / 365.25))
    noise = rng.normal(0, 180, len(release_dates))
    storage = np.maximum(seasonal + noise, 500)
    return pd.DataFrame(
        {
            "release_date": release_dates,
            "storage_bcf": storage,
        }
    )

