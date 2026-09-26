from __future__ import annotations
import numpy as np
import pandas as pd
from natgas_regime.features.price_trend import add_price_trend
from natgas_regime.features.realized_vol import add_realized_vol
from natgas_regime.features.seasonality import season_bucket
from natgas_regime.features.storage_zscore import add_storage_zscore, align_storage_to_daily
from natgas_regime.features.term_structure import add_term_structure
from natgas_regime.features.weather_anomaly import add_weather_anomalies, align_weather_to_daily


def build_feature_table(
    daily: pd.DataFrame,
    storage: pd.DataFrame,
    baseline_years: int,
    realized_vol_window: int,
    riskoff_percentile_window: int,
    riskoff_percentile: float,
    weather: pd.DataFrame | None = None,
    weather_baseline_years: int = 10,
) -> pd.DataFrame:
    storage_with_z = add_storage_zscore(storage, baseline_years=baseline_years)
    frame = align_storage_to_daily(daily, storage_with_z)
    frame["season"] = season_bucket(frame["date"])
    frame = add_term_structure(frame)
    frame["spread_change"] = frame["spread_settle"].diff()
    frame["spread_change_3d"] = frame["spread_settle"] - frame["spread_settle"].shift(3)
    frame["spread_change_5d"] = frame["spread_settle"] - frame["spread_settle"].shift(5)
    frame[f"spread_momentum_{realized_vol_window}d"] = frame["spread_settle"] - frame[
        "spread_settle"
    ].shift(realized_vol_window)
    frame["spread_rv20"] = (
        frame["spread_change"].rolling(realized_vol_window).std().fillna(0) * np.sqrt(252)
    )
    frame = add_realized_vol(
        frame,
        window=realized_vol_window,
        percentile_window=riskoff_percentile_window,
        riskoff_percentile=riskoff_percentile,
    )
    frame = add_price_trend(frame, windows=tuple(sorted({realized_vol_window, 60})))
    if weather is not None and not weather.empty:
        weather_with_z = add_weather_anomalies(weather, baseline_years=weather_baseline_years)
        frame = align_weather_to_daily(frame, weather_with_z)
    else:
        frame["hdd"] = 0.0
        frame["cdd"] = 0.0
        frame["hdd_z"] = 0.0
        frame["cdd_z"] = 0.0
        frame["hdd_7d"] = 0.0
        frame["cdd_7d"] = 0.0
        frame["hdd_7d_z"] = 0.0
        frame["cdd_7d_z"] = 0.0
        frame["weather_demand_z"] = 0.0
        frame["weather_7d_demand_z"] = 0.0
    return frame
