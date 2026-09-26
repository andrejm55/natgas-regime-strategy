from __future__ import annotations

import pandas as pd

from natgas_regime.calendar import build_roll_calendar


def test_roll_calendar_two_business_days_before_expiration() -> None:
    expirations = pd.DataFrame(
        {
            "contract": ["NGX2026"],
            "expiration_date": ["2026-10-28"],
        }
    )
    rolls = build_roll_calendar(expirations, business_days_before_expiration=2)
    assert rolls.loc[0, "roll_date"] == pd.Timestamp("2026-10-26")


def test_roll_calendar_skips_weekend() -> None:
    expirations = pd.DataFrame(
        {
            "contract": ["NGX2026"],
            "expiration_date": ["2026-10-26"],
        }
    )
    rolls = build_roll_calendar(expirations, business_days_before_expiration=2)
    assert rolls.loc[0, "roll_date"] == pd.Timestamp("2026-10-22")

