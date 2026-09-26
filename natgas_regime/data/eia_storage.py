from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
import pandas as pd
import requests


@dataclass(frozen=True)
class EIAStorageClient:
    api_key: str
    route: str
    frequency: str = "weekly"
    data_field: str = "value"
    series_id: str = "NW2_EPG0_SWO_R48_BCF"
    release_lag_days: int = 6

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> EIAStorageClient:
        api_key = os.getenv(cfg.get("api_key_env", "EIA_API_KEY"), "")
        if not api_key:
            raise RuntimeError("EIA API key is not set")
        return cls(
            api_key=api_key,
            route=cfg["route"],
            frequency=cfg.get("frequency", "weekly"),
            data_field=cfg.get("data_field", "value"),
            series_id=cfg.get("series_id", "NW2_EPG0_SWO_R48_BCF"),
            release_lag_days=int(cfg.get("release_lag_days", 6)),
        )

    def fetch(self, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "frequency": self.frequency,
            "data[0]": self.data_field,
            "facets[series][]": self.series_id,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": 0,
            "length": 5000,
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        response = requests.get(self.route, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("response", {}).get("data", [])
        if not records:
            raise RuntimeError("EIA response did not include response.data records")

        frame = pd.DataFrame(records)
        if "period" not in frame.columns or self.data_field not in frame.columns:
            raise RuntimeError(
                f"EIA response missing expected period/{self.data_field} columns: {frame.columns}"
            )

        week_ending = pd.to_datetime(frame["period"])
        release_date = week_ending + pd.to_timedelta(self.release_lag_days, unit="D")
        out = pd.DataFrame(
            {
                "week_ending_date": week_ending,
                "release_date": release_date,
                "storage_bcf": pd.to_numeric(frame[self.data_field], errors="coerce"),
                "series_id": frame.get("series", self.series_id),
            }
        )
        return out.dropna().sort_values("release_date").reset_index(drop=True)
