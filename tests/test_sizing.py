from __future__ import annotations

import pandas as pd

from natgas_regime.strategy.sizing import SizingConfig, add_contract_sizing


def test_spread_sizing_uses_price_vol_dollars() -> None:
    frame = pd.DataFrame(
        {
            "position_direction": [1],
            "ng1_settle": [3.0],
            "spread_rv20": [0.50],
        }
    )
    out = add_contract_sizing(
        frame,
        SizingConfig(
            initial_equity=1_000_000,
            target_vol=0.05,
            max_contracts=99,
            max_notional_leverage=10.0,
            min_realized_vol=0.01,
            multiplier=10_000,
            price_col="ng1_settle",
            vol_col="spread_rv20",
            vol_kind="price",
        ),
    )
    # 5% of 1mm is 50k annual risk. One spread contract has 0.50*10k = 5k annual vol.
    assert out.loc[0, "signed_contracts"] == 10


def test_sizing_supports_side_specific_contract_caps() -> None:
    frame = pd.DataFrame(
        {
            "position_direction": [1, -1],
            "ng1_settle": [3.0, 3.0],
            "rv20": [0.20, 0.20],
        }
    )
    out = add_contract_sizing(
        frame,
        SizingConfig(
            initial_equity=1_000_000,
            target_vol=0.10,
            max_contracts=10,
            max_long_contracts=2,
            max_short_contracts=4,
            max_notional_leverage=10.0,
            min_realized_vol=0.01,
            multiplier=10_000,
        ),
    )
    assert out["signed_contracts"].tolist() == [2, -4]


def test_sizing_honors_position_contract_cap() -> None:
    frame = pd.DataFrame(
        {
            "position_direction": [1, -1],
            "position_contract_cap": [1, 3],
            "ng1_settle": [3.0, 3.0],
            "rv20": [0.20, 0.20],
        }
    )
    out = add_contract_sizing(
        frame,
        SizingConfig(
            initial_equity=1_000_000,
            target_vol=0.10,
            max_contracts=10,
            max_long_contracts=5,
            max_short_contracts=5,
            max_notional_leverage=10.0,
            min_realized_vol=0.01,
            multiplier=10_000,
        ),
    )
    assert out["signed_contracts"].tolist() == [1, -3]


def test_sizing_honors_position_contract_floor_before_cap() -> None:
    frame = pd.DataFrame(
        {
            "position_direction": [1, 1, 0],
            "position_contract_floor": [3, 3, 3],
            "position_contract_cap": [5, 2, 5],
            "ng1_settle": [3.0, 3.0, 3.0],
            "rv20": [2.00, 2.00, 2.00],
        }
    )
    out = add_contract_sizing(
        frame,
        SizingConfig(
            initial_equity=1_000_000,
            target_vol=0.01,
            max_contracts=10,
            max_long_contracts=5,
            max_short_contracts=5,
            max_notional_leverage=10.0,
            min_realized_vol=0.01,
            multiplier=10_000,
        ),
    )
    assert out["signed_contracts"].tolist() == [3, 2, 0]


def test_position_scale_scales_risk_and_contract_limits() -> None:
    frame = pd.DataFrame(
        {
            "position_direction": [1, -1],
            "position_contract_floor": [1, 0],
            "position_contract_cap": [1, 3],
            "ng1_settle": [3.0, 3.0],
            "rv20": [0.20, 0.20],
        }
    )
    out = add_contract_sizing(
        frame,
        SizingConfig(
            initial_equity=1_000_000,
            target_vol=0.10,
            max_contracts=10,
            max_long_contracts=5,
            max_short_contracts=5,
            max_notional_leverage=10.0,
            min_realized_vol=0.01,
            multiplier=10_000,
            position_scale=2.0,
        ),
    )
    assert out["signed_contracts"].tolist() == [2, -6]
