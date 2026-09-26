from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.data.weather import build_weighted_weather_basket, fetch_open_meteo_hdd_cdd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-config", default="config/data.yaml")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    args = parser.parse_args()

    data_cfg = load_yaml(args.data_config)
    weather_cfg = data_cfg["weather"]
    start_date = args.start_date or weather_cfg.get("start_date", "2015-01-01")
    end_date = args.end_date or weather_cfg.get("end_date") or datetime.now(UTC).date().isoformat()
    output_dir = resolve_path(weather_cfg["raw_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    region_frames: list[pd.DataFrame] = []
    for region in weather_cfg["regions"]:
        name = region["name"]
        print(f"Fetching Open-Meteo weather for {name}...")
        frame = fetch_open_meteo_hdd_cdd(
            latitude=region["latitude"],
            longitude=region["longitude"],
            start_date=start_date,
            end_date=end_date,
            timezone=weather_cfg.get("timezone", "America/Chicago"),
            base_temperature_f=weather_cfg.get("base_temperature_f", 65.0),
        )
        frame["region"] = name
        frame["weight"] = float(region["weight"])
        region_path = output_dir / f"open_meteo_{name}_daily.csv"
        frame.to_csv(region_path, index=False)
        print(f"  wrote {len(frame)} rows to {region_path}")
        region_frames.append(frame)

    basket = build_weighted_weather_basket(region_frames)
    basket_path = output_dir / "open_meteo_daily.csv"
    basket.to_csv(basket_path, index=False)
    print(
        f"Wrote weighted weather basket to {basket_path}. "
        f"Date range {basket['date'].min().date()} to {basket['date'].max().date()}."
    )


if __name__ == "__main__":
    main()
