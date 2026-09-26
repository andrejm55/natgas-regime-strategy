from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml
from natgas_regime.data.eia_storage import EIAStorageClient


def check_eia() -> None:
    data_cfg = load_yaml("config/data.yaml")
    client = EIAStorageClient.from_config(data_cfg["eia"])
    frame = client.fetch()
    latest = frame.iloc[-1]
    print(
        "EIA: ok "
        f"rows={len(frame)} "
        f"latest_week_ending={latest['week_ending_date'].date()} "
        f"latest_storage_bcf={latest['storage_bcf']:.0f}"
    )


def check_noaa() -> None:
    token = os.getenv("NOAA_CDO_TOKEN", "")
    if not token:
        print("NOAA: skipped, NOAA_CDO_TOKEN missing")
        return
    response = requests.get(
        "https://www.ncei.noaa.gov/cdo-web/api/v2/datasets",
        headers={"token": token},
        params={"limit": 1},
        timeout=30,
    )
    if not response.ok:
        print(f"NOAA: failed status={response.status_code}")
        return
    count = response.json().get("metadata", {}).get("resultset", {}).get("count", "unknown")
    print(f"NOAA: ok dataset_count={count}")


def main() -> None:
    load_dotenv(".env")
    check_eia()
    check_noaa()


if __name__ == "__main__":
    main()

