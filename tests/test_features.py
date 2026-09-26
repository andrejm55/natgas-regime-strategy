from __future__ import annotations

import pandas as pd

from natgas_regime.features.seasonality import season_bucket
from natgas_regime.features.storage_zscore import add_storage_zscore, align_storage_to_daily


def test_season_bucket() -> None:
    dates = pd.Series(pd.to_datetime(["2026-01-15", "2026-07-15", "2026-04-15"]))
    assert season_bucket(dates).tolist() == ["winter", "summer", "shoulder"]


def test_storage_alignment_uses_latest_release_only() -> None:
    daily = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-09"])})
    storage = pd.DataFrame(
        {
            "release_date": pd.to_datetime(["2026-01-02", "2026-01-08"]),
            "storage_bcf": [3000, 2900],
        }
    )
    out = align_storage_to_daily(daily, storage)
    assert pd.isna(out.loc[0, "storage_bcf"])
    assert out.loc[1, "storage_bcf"] == 3000
    assert out.loc[2, "storage_bcf"] == 2900


def test_storage_zscore_uses_weekly_prior_years() -> None:
    storage = pd.DataFrame(
        {
            "release_date": pd.to_datetime(
                ["2024-01-11", "2025-01-09", "2026-01-08", "2027-01-07"]
            ),
            "week_ending_date": pd.to_datetime(
                ["2024-01-05", "2025-01-03", "2026-01-02", "2027-01-01"]
            ),
            "storage_bcf": [1000.0, 1100.0, 1200.0, 1300.0],
        }
    )
    out = add_storage_zscore(storage, baseline_years=5)
    assert pd.isna(out.loc[0, "storage_z"])
    assert pd.notna(out.loc[2, "storage_z"])


def test_storage_zscore_adds_change_surprise_and_percentile() -> None:
    storage = pd.DataFrame(
        {
            "release_date": pd.to_datetime(
                ["2023-01-12", "2024-01-11", "2025-01-09", "2026-01-08"]
            ),
            "week_ending_date": pd.to_datetime(
                ["2023-01-06", "2024-01-05", "2025-01-03", "2026-01-02"]
            ),
            "storage_bcf": [1000.0, 1050.0, 1075.0, 1060.0],
        }
    )
    out = add_storage_zscore(storage, baseline_years=5)
    assert "weekly_storage_change" in out.columns
    assert "storage_change_vs_normal" in out.columns
    assert "weekly_change_vs_5yr_normal" in out.columns
    assert "storage_percentile_by_week" in out.columns
    assert pd.notna(out.loc[3, "storage_percentile_by_week"])
