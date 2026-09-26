from __future__ import annotations

import pandas as pd

from natgas_regime.data.continuous import build_continuous_ng12


def test_continuous_rolls_on_roll_date() -> None:
    dates = pd.bdate_range("2026-01-01", "2026-01-09")
    bars = pd.concat(
        [
            pd.DataFrame({"date": dates, "contract_month": "202601", "settle": 3.0}),
            pd.DataFrame({"date": dates, "contract_month": "202602", "settle": 3.1}),
            pd.DataFrame({"date": dates, "contract_month": "202603", "settle": 3.2}),
        ],
        ignore_index=True,
    )
    expirations = pd.DataFrame(
        {
            "contract_month": ["202601", "202602", "202603"],
            "contract": ["NGF26", "NGG26", "NGH26"],
            "expiration_date": pd.to_datetime(["2026-01-07", "2026-02-05", "2026-03-05"]),
        }
    )
    out = build_continuous_ng12(bars, expirations, business_days_before_expiration=2)
    jan_5 = out[out["date"] == pd.Timestamp("2026-01-05")].iloc[0]

    assert jan_5["ng1_contract_month"] == "202602"
    assert jan_5["ng2_contract_month"] == "202603"
