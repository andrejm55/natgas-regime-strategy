from __future__ import annotations

import pandas as pd

from natgas_regime.features.weather_anomaly import add_weather_anomalies


def test_weather_anomaly_uses_prior_years() -> None:
    dates = pd.date_range("2020-01-01", "2026-01-15", freq="D")
    weather = pd.DataFrame(
        {
            "date": dates,
            "hdd": [20.0] * len(dates),
            "cdd": [0.0] * len(dates),
        }
    )
    weather.loc[weather["date"] == pd.Timestamp("2026-01-08"), "hdd"] = 35.0
    out = add_weather_anomalies(weather)
    row = out[out["date"] == pd.Timestamp("2026-01-08")].iloc[0]
    assert pd.notna(row["hdd_z"])
    assert row["weather_demand_z"] >= 0

