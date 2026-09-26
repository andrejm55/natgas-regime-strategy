from __future__ import annotations

from dataclasses import replace

import pandas as pd

from natgas_regime.strategy.signals import (
    EventOutrightConfig,
    generate_event_outright_positions,
)


def _cfg() -> EventOutrightConfig:
    return EventOutrightConfig(
        allow_longs=True,
        allow_shorts=True,
        max_holding_days=5,
        exit_score=0.25,
        event_entry_score=1.50,
        long_event_entry_score=1.50,
        short_event_entry_score=1.50,
        reversion_entry_score=1.25,
        long_reversion_entry_score=1.25,
        short_reversion_entry_score=1.25,
        weather_anomaly_threshold=1.00,
        weather_change_threshold=1.00,
        storage_surprise_threshold=50.0,
        curve_confirm_threshold=0.025,
        curve_lookback_days=3,
        weather_weight=0.75,
        weather_change_weight=1.00,
        storage_surprise_weight=0.60,
        curve_weight=0.75,
        storage_entry_mode="score",
        event_direction="follow",
        reversion_weather_threshold=1.50,
        reversion_change_threshold=0.75,
        profit_protection_trigger=0.0,
        profit_giveback=0.0,
        allow_storage_only_events=True,
        allow_combined_storage_longs=True,
        allow_combined_storage_shorts=True,
        weak_long_min_contracts=1,
        weak_long_max_contracts=1,
        strong_long_min_contracts=3,
        strong_long_max_contracts=5,
        weak_short_min_contracts=0,
        weak_short_max_contracts=3,
        strong_short_min_contracts=0,
        strong_short_max_contracts=5,
        max_component_abs=2.0,
    )


def test_event_outright_requires_curve_confirmation_for_event_trade() -> None:
    features = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=4),
            "season": ["winter"] * 4,
            "hdd_z": [1.2] * 4,
            "hdd_7d_z": [1.2] * 4,
            "cdd_z": [0.0] * 4,
            "cdd_7d_z": [0.0] * 4,
            "storage_change_vs_normal": [-80.0] * 4,
            "spread_change_3d": [0.0, 0.0, 0.0, 0.03],
            "riskoff": [False] * 4,
        }
    )
    out = generate_event_outright_positions(features, _cfg())
    assert out["target_direction"].iloc[:3].sum() == 0
    assert out["target_direction"].iloc[3] == 1


def test_event_outright_scales_longs_only_when_storage_confirms() -> None:
    features = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=2),
            "season": ["winter"] * 2,
            "hdd_z": [1.2, 1.2],
            "hdd_7d_z": [1.2, 1.2],
            "cdd_z": [0.0, 0.0],
            "cdd_7d_z": [0.0, 0.0],
            "storage_change_vs_normal": [-80.0, 80.0],
            "spread_change_3d": [0.03, 0.03],
            "riskoff": [False, False],
        }
    )
    out = generate_event_outright_positions(features, _cfg())
    assert out["target_direction"].tolist() == [1, 1]
    assert out["target_contract_floor"].tolist() == [3, 3]
    assert out["target_contract_cap"].tolist() == [5, 5]

    weak_features = features.copy()
    weak_features["storage_change_vs_normal"] = [80.0, 80.0]
    weak_out = generate_event_outright_positions(weak_features, _cfg())
    assert weak_out["target_direction"].tolist() == [1, 1]
    assert weak_out["target_contract_floor"].tolist() == [1, 1]
    assert weak_out["target_contract_cap"].tolist() == [1, 1]


def test_event_outright_does_not_trade_curve_alone() -> None:
    features = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-04-01", periods=3),
            "season": ["shoulder"] * 3,
            "hdd_z": [0.0] * 3,
            "hdd_7d_z": [0.0] * 3,
            "cdd_z": [0.0] * 3,
            "cdd_7d_z": [0.0] * 3,
            "storage_change_vs_normal": [0.0] * 3,
            "spread_change_3d": [0.03] * 3,
            "riskoff": [False] * 3,
        }
    )
    out = generate_event_outright_positions(features, _cfg())
    assert out["target_direction"].sum() == 0


def test_event_outright_can_exclude_storage_from_entry_score() -> None:
    features = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=3),
            "season": ["winter"] * 3,
            "hdd_z": [0.2] * 3,
            "hdd_7d_z": [0.2] * 3,
            "cdd_z": [0.0] * 3,
            "cdd_7d_z": [0.0] * 3,
            "storage_change_vs_normal": [-120.0] * 3,
            "spread_change_3d": [0.03] * 3,
            "riskoff": [False] * 3,
        }
    )
    score_cfg = replace(_cfg(), storage_entry_mode="score")
    boost_cfg = replace(_cfg(), storage_entry_mode="confirm_boost")

    score_out = generate_event_outright_positions(features, score_cfg)
    boost_out = generate_event_outright_positions(features, boost_cfg)

    assert score_out["target_direction"].iloc[0] == 1
    assert boost_out["target_direction"].sum() == 0


def test_event_outright_uses_storage_confirmation_as_short_size_boost() -> None:
    features = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-07-01", periods=2),
            "season": ["summer"] * 2,
            "hdd_z": [0.0, 0.0],
            "hdd_7d_z": [0.0, 0.0],
            "cdd_z": [1.4, 1.4],
            "cdd_7d_z": [1.4, 1.4],
            "storage_change_vs_normal": [-80.0, 80.0],
            "spread_change_3d": [0.03, 0.03],
            "riskoff": [False, False],
        }
    )
    cfg = replace(_cfg(), event_direction="fade", storage_entry_mode="confirm_boost")
    out = generate_event_outright_positions(features, cfg)

    assert out["target_direction"].tolist() == [-1, -1]
    assert out["target_contract_cap"].tolist() == [5, 5]

    weak_features = features.copy()
    weak_features["storage_change_vs_normal"] = [80.0, 80.0]
    weak_out = generate_event_outright_positions(weak_features, cfg)
    assert weak_out["target_direction"].tolist() == [-1, -1]
    assert weak_out["target_contract_cap"].tolist() == [3, 3]


def test_event_outright_can_fade_peaking_bullish_weather() -> None:
    features = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-07-01", periods=3),
            "season": ["summer"] * 3,
            "hdd_z": [0.0] * 3,
            "hdd_7d_z": [0.0] * 3,
            "cdd_z": [1.8] * 3,
            "cdd_7d_z": [-1.0] * 3,
            "storage_change_vs_normal": [0.0] * 3,
            "spread_change_3d": [0.0] * 3,
            "riskoff": [False] * 3,
        }
    )
    out = generate_event_outright_positions(features, _cfg())
    assert out["target_direction"].iloc[0] == -1
