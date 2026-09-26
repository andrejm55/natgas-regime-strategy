from __future__ import annotations

import pandas as pd

from natgas_regime.strategy.signals import (
    ScoredSignalConfig,
    add_regime_score,
    generate_scored_positions,
)


def _cfg() -> ScoredSignalConfig:
    return ScoredSignalConfig(
        entry_score=1.0,
        exit_score=0.25,
        max_holding_days=10,
        slope_scale=0.05,
        storage_weight=1.0,
        slope_weight=1.0,
        weather_weight=0.5,
        weather_7d_weight=0.25,
        season_weight=0.1,
        trend_weight=0.5,
        momentum_window=20,
        momentum_scale=0.10,
        short_momentum_ceiling=0.0,
        long_allowed_seasons=["winter", "summer"],
        short_allowed_seasons=["shoulder"],
        max_component_abs=2.0,
    )


def test_regime_score_positive_for_tight_backwardated_cold_winter() -> None:
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "season": ["winter"],
            "storage_z": [-1.0],
            "slope": [-0.05],
            "hdd_z": [1.0],
            "cdd_z": [0.0],
            "hdd_7d_z": [1.0],
            "cdd_7d_z": [0.0],
            "momentum_20d": [0.10],
        }
    )
    out = add_regime_score(features, _cfg())
    assert out.loc[0, "regime_score"] > 0


def test_scored_positions_can_short_loose_contango_shoulder() -> None:
    dates = pd.bdate_range("2026-04-01", periods=5)
    features = pd.DataFrame(
        {
            "date": dates,
            "season": ["shoulder"] * len(dates),
            "storage_z": [1.0] * len(dates),
            "slope": [0.05] * len(dates),
            "hdd_z": [0.0] * len(dates),
            "cdd_z": [0.0] * len(dates),
            "hdd_7d_z": [0.0] * len(dates),
            "cdd_7d_z": [0.0] * len(dates),
            "momentum_20d": [-0.01] * len(dates),
            "riskoff": [False] * len(dates),
        }
    )
    out = generate_scored_positions(features, _cfg())
    assert out["target_direction"].iloc[0] == -1
    assert out["position_direction"].iloc[1] == -1


def test_scored_positions_do_not_short_positive_momentum() -> None:
    dates = pd.bdate_range("2026-04-01", periods=5)
    features = pd.DataFrame(
        {
            "date": dates,
            "season": ["shoulder"] * len(dates),
            "storage_z": [1.0] * len(dates),
            "slope": [0.05] * len(dates),
            "hdd_z": [0.0] * len(dates),
            "cdd_z": [0.0] * len(dates),
            "hdd_7d_z": [0.0] * len(dates),
            "cdd_7d_z": [0.0] * len(dates),
            "momentum_20d": [0.05] * len(dates),
            "riskoff": [False] * len(dates),
        }
    )
    out = generate_scored_positions(features, _cfg())
    assert out["target_direction"].abs().sum() == 0
