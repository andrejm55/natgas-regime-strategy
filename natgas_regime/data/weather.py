from __future__ import annotations
import pandas as pd
import requests


def fetch_open_meteo_hdd_cdd(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    timezone: str = "America/Chicago",
    base_temperature_f: float = 65.0,
) -> pd.DataFrame:
    """Fetch daily mean temperature from Open-Meteo and compute HDD/CDD.

    HDD/CDD are computed as max(base - temp, 0) and max(temp - base, 0), in Fahrenheit.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_mean",
        "temperature_unit": "fahrenheit",
        "timezone": timezone,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    daily = response.json().get("daily", {})
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(daily.get("time", [])),
            "temperature_mean_f": pd.to_numeric(daily.get("temperature_2m_mean", [])),
        }
    )
    if frame.empty:
        return frame
    frame["hdd"] = (base_temperature_f - frame["temperature_mean_f"]).clip(lower=0)
    frame["cdd"] = (frame["temperature_mean_f"] - base_temperature_f).clip(lower=0)
    return frame


def build_weighted_weather_basket(region_frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not region_frames:
        raise ValueError("no weather region frames supplied")

    combined = pd.concat(region_frames, ignore_index=True)
    required = {"date", "region", "weight", "temperature_mean_f", "hdd", "cdd"}
    missing = required - set(combined.columns)
    if missing:
        raise ValueError(f"weather basket missing columns: {sorted(missing)}")

    combined["weighted_temperature_mean_f"] = (
        combined["temperature_mean_f"] * combined["weight"]
    )
    combined["weighted_hdd"] = combined["hdd"] * combined["weight"]
    combined["weighted_cdd"] = combined["cdd"] * combined["weight"]
    basket = (
        combined.groupby("date", as_index=False)
        .agg(
            temperature_mean_f=("weighted_temperature_mean_f", "sum"),
            hdd=("weighted_hdd", "sum"),
            cdd=("weighted_cdd", "sum"),
            region_count=("region", "nunique"),
            total_weight=("weight", "sum"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    return basket


def fetch_noaa_cdo_daily_station(
    token: str,
    station_id: str,
    start_date: str,
    end_date: str,
    base_temperature_f: float = 65.0,
    observation_lag_days: int = 1,
) -> pd.DataFrame:
    """Fetch observed NOAA CDO daily station temperatures and compute HDD/CDD."""
    records: list[dict] = []
    start = pd.Period(start_date, freq="Y")
    end = pd.Period(end_date, freq="Y")
    for year in pd.period_range(start, end, freq="Y"):
        year_start = max(pd.Timestamp(start_date), year.start_time).date().isoformat()
        year_end = min(pd.Timestamp(end_date), year.end_time).date().isoformat()
        params = {
            "datasetid": "GHCND",
            "stationid": station_id,
            "startdate": year_start,
            "enddate": year_end,
            "datatypeid": ["TMAX", "TMIN"],
            "units": "standard",
            "limit": 1000,
        }
        response = requests.get(
            "https://www.ncei.noaa.gov/cdo-web/api/v2/data",
            headers={"token": token},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        records.extend(response.json().get("results", []))

    if not records:
        return pd.DataFrame(
            columns=["date", "available_date", "temperature_mean_f", "hdd", "cdd"]
        )

    raw = pd.DataFrame(records)
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    wide = raw.pivot_table(index="date", columns="datatype", values="value", aggfunc="last")
    temp = (wide["TMAX"] + wide["TMIN"]) / 2

    out = pd.DataFrame({"date": wide.index, "temperature_mean_f": temp}).dropna()
    out["available_date"] = out["date"] + pd.to_timedelta(observation_lag_days, unit="D")
    out["hdd"] = (base_temperature_f - out["temperature_mean_f"]).clip(lower=0)
    out["cdd"] = (out["temperature_mean_f"] - base_temperature_f).clip(lower=0)
    return out.reset_index(drop=True)
