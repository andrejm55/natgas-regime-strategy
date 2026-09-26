from __future__ import annotations
import pandas as pd

def add_weather_anomalies(weather: pd.DataFrame, baseline_years: int = 10) -> pd.DataFrame:
    """Compute weighted HDD/CDD anomalies from full daily weather history."""
    required = {"date", "hdd", "cdd"}
    missing = required - set(weather.columns)
    if missing:
        raise ValueError(f"weather missing columns: {sorted(missing)}")

    out = weather.sort_values("date").copy()
    out["date"] = pd.to_datetime(out["date"])
    out["dayofyear"] = out["date"].dt.dayofyear
    out["year"] = out["date"].dt.year
    out["hdd_7d"] = out["hdd"].rolling(7, min_periods=7).sum()
    out["cdd_7d"] = out["cdd"].rolling(7, min_periods=7).sum()

    hdd_z: list[float | None] = []
    cdd_z: list[float | None] = []
    hdd_7d_z: list[float | None] = []
    cdd_7d_z: list[float | None] = []
    for _, row in out.iterrows():
        prior = out[
            (out["dayofyear"].between(row["dayofyear"] - 7, row["dayofyear"] + 7))
            & (out["year"] < row["year"])
            & (out["year"] >= row["year"] - baseline_years)
        ]
        if len(prior) < 30:
            hdd_z.append(None)
            cdd_z.append(None)
            hdd_7d_z.append(None)
            cdd_7d_z.append(None)
            continue

        hdd_std = prior["hdd"].std(ddof=0)
        cdd_std = prior["cdd"].std(ddof=0)
        hdd_delta = row["hdd"] - prior["hdd"].mean()
        cdd_delta = row["cdd"] - prior["cdd"].mean()
        hdd_z.append(_zero_variance_z(hdd_delta) if hdd_std == 0 else hdd_delta / hdd_std)
        cdd_z.append(_zero_variance_z(cdd_delta) if cdd_std == 0 else cdd_delta / cdd_std)

        prior_7d = prior.dropna(subset=["hdd_7d", "cdd_7d"])
        if len(prior_7d) < 30 or pd.isna(row["hdd_7d"]) or pd.isna(row["cdd_7d"]):
            hdd_7d_z.append(None)
            cdd_7d_z.append(None)
            continue
        hdd_7d_std = prior_7d["hdd_7d"].std(ddof=0)
        cdd_7d_std = prior_7d["cdd_7d"].std(ddof=0)
        hdd_7d_delta = row["hdd_7d"] - prior_7d["hdd_7d"].mean()
        cdd_7d_delta = row["cdd_7d"] - prior_7d["cdd_7d"].mean()
        hdd_7d_z.append(
            _zero_variance_z(hdd_7d_delta) if hdd_7d_std == 0 else hdd_7d_delta / hdd_7d_std
        )
        cdd_7d_z.append(
            _zero_variance_z(cdd_7d_delta) if cdd_7d_std == 0 else cdd_7d_delta / cdd_7d_std
        )

    out["hdd_z"] = hdd_z
    out["cdd_z"] = cdd_z
    out["hdd_7d_z"] = hdd_7d_z
    out["cdd_7d_z"] = cdd_7d_z
    out["weather_demand_z"] = out["hdd_z"].fillna(0) + out["cdd_z"].fillna(0)
    out["weather_7d_demand_z"] = out["hdd_7d_z"].fillna(0) + out["cdd_7d_z"].fillna(0)
    return out


def align_weather_to_daily(daily: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    d = daily.sort_values("date").copy()
    w = weather.sort_values("date").copy()
    d["date"] = pd.to_datetime(d["date"])
    w["date"] = pd.to_datetime(w["date"])
    if "available_date" in w.columns:
        w["available_date"] = pd.to_datetime(w["available_date"])
        w = w.rename(columns={"date": "weather_date"})
        return pd.merge_asof(
            d.sort_values("date"),
            w.sort_values("available_date"),
            left_on="date",
            right_on="available_date",
            direction="backward",
        )
    return pd.merge_asof(d, w, on="date", direction="backward")


def _zero_variance_z(delta: float) -> float:
    if delta > 0:
        return 2.0
    if delta < 0:
        return -2.0
    return 0.0
