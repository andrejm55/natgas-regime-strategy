from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.data.weather import build_weighted_weather_basket, fetch_noaa_cdo_daily_station


def rebuild_from_existing_files(weather_cfg: dict, output_dir: Path) -> bool:
    region_frames: list[pd.DataFrame] = []
    metadata_rows: list[dict] = []
    for region in weather_cfg["regions"]:
        region_path = output_dir / f"noaa_cdo_{region['name']}_daily.csv"
        if not region_path.exists():
            return False
        frame = pd.read_csv(region_path, parse_dates=["date", "available_date"])
        frame["weight"] = float(region["weight"])
        frame["region"] = region["name"]
        frame["station_id"] = region["station_id"]
        frame["station_name"] = region.get("station_name", "")
        frame.to_csv(region_path, index=False)
        region_frames.append(frame)
        metadata_rows.append(
            {
                "region": region["name"],
                "station_id": region["station_id"],
                "station_name": region.get("station_name", ""),
                "weight": float(region["weight"]),
                "rows": len(frame),
                "start_date": frame["date"].min().date().isoformat() if not frame.empty else "",
                "end_date": frame["date"].max().date().isoformat() if not frame.empty else "",
            }
        )

    basket = build_weighted_weather_basket(region_frames)
    availability = (
        pd.concat(region_frames, ignore_index=True).groupby("date", as_index=False)["available_date"].max()
    )
    basket = basket.merge(availability, on="date", how="left")
    basket.to_csv(output_dir / "noaa_cdo_daily.csv", index=False)
    pd.DataFrame(metadata_rows).to_csv(output_dir / "noaa_cdo_station_basket.csv", index=False)
    print(f"Rebuilt NOAA basket from existing station files in {output_dir}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-config", default="config/data.yaml")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--reuse-existing", action="store_true")
    args = parser.parse_args()

    load_dotenv(".env")
    data_cfg = load_yaml(args.data_config)
    weather_cfg = data_cfg["weather"]
    token = os.getenv(weather_cfg.get("token_env", "NOAA_CDO_TOKEN"), "")
    if not token:
        raise RuntimeError("NOAA_CDO_TOKEN is missing from .env")

    start_date = args.start_date or weather_cfg.get("start_date", "2015-01-01")
    end_date = args.end_date or weather_cfg.get("end_date") or datetime.now(UTC).date().isoformat()
    output_dir = resolve_path(weather_cfg["raw_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.reuse_existing and rebuild_from_existing_files(weather_cfg, output_dir):
        return

    region_frames: list[pd.DataFrame] = []
    metadata_rows: list[dict] = []
    for region in weather_cfg["regions"]:
        name = region["name"]
        station_id = region["station_id"]
        print(f"Fetching NOAA CDO GHCND weather for {name} ({station_id})...")
        frame = fetch_noaa_cdo_daily_station(
            token=token,
            station_id=station_id,
            start_date=start_date,
            end_date=end_date,
            base_temperature_f=float(weather_cfg.get("base_temperature_f", 65.0)),
            observation_lag_days=int(weather_cfg.get("observation_lag_days", 1)),
        )
        frame["region"] = name
        frame["station_id"] = station_id
        frame["station_name"] = region.get("station_name", "")
        frame["weight"] = float(region["weight"])
        region_path = output_dir / f"noaa_cdo_{name}_daily.csv"
        frame.to_csv(region_path, index=False)
        print(f"  wrote {len(frame)} rows to {region_path}")
        region_frames.append(frame)
        metadata_rows.append(
            {
                "region": name,
                "station_id": station_id,
                "station_name": region.get("station_name", ""),
                "weight": float(region["weight"]),
                "rows": len(frame),
                "start_date": frame["date"].min().date().isoformat() if not frame.empty else "",
                "end_date": frame["date"].max().date().isoformat() if not frame.empty else "",
            }
        )

    basket = build_weighted_weather_basket(region_frames)
    if "available_date" in pd.concat(region_frames, ignore_index=True).columns:
        availability = (
            pd.concat(region_frames, ignore_index=True)
            .groupby("date", as_index=False)["available_date"]
            .max()
        )
        basket = basket.merge(availability, on="date", how="left")

    basket_path = output_dir / "noaa_cdo_daily.csv"
    metadata_path = output_dir / "noaa_cdo_station_basket.csv"
    basket.to_csv(basket_path, index=False)
    pd.DataFrame(metadata_rows).to_csv(metadata_path, index=False)
    print(
        f"Wrote NOAA weather basket to {basket_path}. "
        f"Date range {basket['date'].min().date()} to {basket['date'].max().date()}."
    )
    print(f"Wrote NOAA station basket metadata to {metadata_path}")


if __name__ == "__main__":
    main()
