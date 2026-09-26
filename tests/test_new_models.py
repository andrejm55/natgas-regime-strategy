from __future__ import annotations

import pandas as pd

from natgas_regime.strategy.signals import (
    SpreadSignalConfig,
    WeatherOutrightConfig,
    generate_spread_positions,
    generate_weather_outright_positions,
)


def _outright_cfg() -> WeatherOutrightConfig:
    return WeatherOutrightConfig(
        entry_score=1.0,
        exit_score=0.25,
        max_holding_days=10,
        weather_weight=1.0,
        weather_7d_weight=0.5,
        trend_weight=1.0,
        storage_weight=0.2,
        storage_change_weight=0.15,
        storage_percentile_weight=0.10,
        storage_change_scale=50.0,
        slope_weight=0.2,
        season_weight=0.1,
        momentum_window=20,
        confirmation_momentum_window=60,
        momentum_scale=0.10,
        min_abs_price_vs_sma=0.015,
        allow_longs=True,
        allow_shorts=True,
        long_momentum_floor=0.02,
        short_momentum_ceiling=-0.02,
        loose_storage_avoid_long_z=0.75,
        contango_avoid_long_slope=0.03,
        max_component_abs=2.0,
    )


def test_weather_outright_blocks_long_on_loose_contango() -> None:
    dates = pd.bdate_range("2026-07-01", periods=3)
    features = pd.DataFrame(
        {
            "date": dates,
            "season": ["summer"] * 3,
            "storage_z": [0.9] * 3,
            "slope": [0.04] * 3,
            "hdd_z": [0.0] * 3,
            "cdd_z": [2.0] * 3,
            "hdd_7d_z": [0.0] * 3,
            "cdd_7d_z": [2.0] * 3,
            "momentum_20d": [0.10] * 3,
            "momentum_60d": [0.10] * 3,
            "price_vs_sma_20d": [0.10] * 3,
            "price_vs_sma_60d": [0.10] * 3,
            "riskoff": [False] * 3,
            "spread_momentum_20d": [0.1] * 3,
        }
    )
    out = generate_weather_outright_positions(features, _outright_cfg())
    assert out["target_direction"].sum() == 0


def test_spread_score_can_go_long_tight_backwardated_weather() -> None:
    dates = pd.bdate_range("2026-01-01", periods=3)
    features = pd.DataFrame(
        {
            "date": dates,
            "season": ["winter"] * 3,
            "storage_z": [-1.0] * 3,
            "slope": [-0.05] * 3,
            "hdd_z": [1.0] * 3,
            "hdd_7d_z": [1.0] * 3,
            "cdd_z": [0.0] * 3,
            "cdd_7d_z": [0.0] * 3,
            "riskoff": [False] * 3,
        }
    )
    cfg = SpreadSignalConfig(
        entry_score=1.0,
        long_entry_score=1.0,
        short_entry_score=1.5,
        allow_longs=True,
        allow_shorts=False,
        exit_score=0.25,
        max_holding_days=10,
        storage_weight=0.35,
        storage_change_weight=0.35,
        storage_percentile_weight=0.20,
        storage_change_scale=50.0,
        slope_weight=0.9,
        weather_weight=0.75,
        weather_7d_weight=0.55,
        season_weight=0.15,
        slope_scale=0.05,
        momentum_window=20,
        long_spread_momentum_floor=0.0,
        short_spread_momentum_ceiling=-0.02,
        short_min_contango_slope=0.03,
        short_min_storage_z=0.75,
        max_component_abs=2.0,
    )
    out = generate_spread_positions(features, cfg)
    assert out["target_direction"].iloc[0] == 1
