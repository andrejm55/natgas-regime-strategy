from __future__ import annotations
import pandas as pd
from natgas_regime.calendar import build_roll_calendar


def build_continuous_ng12(
    bars: pd.DataFrame,
    expirations: pd.DataFrame,
    business_days_before_expiration: int,
) -> pd.DataFrame:
    """Build roll-adjusted NG1/NG2 daily series from individual contract bars.

    A delivery month is NG1 only from the prior contract's roll date up to, but
    not including, its own roll date. The first discovered contract is therefore
    used only as the prior anchor; this avoids treating a far-deferred contract
    as the front month before its real front-month window begins.
    """
    required_bars = {"date", "contract_month", "settle"}
    missing_bars = required_bars - set(bars.columns)
    if missing_bars:
        raise ValueError(f"bars missing columns: {sorted(missing_bars)}")

    bars = bars.copy()
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    bars["contract_month"] = bars["contract_month"].astype(str)
    bars = bars.dropna(subset=["settle"])

    rolls = build_roll_calendar(
        expirations=expirations,
        business_days_before_expiration=business_days_before_expiration,
    )
    rolls["contract_month"] = rolls["contract_month"].astype(str)
    rolls = rolls.sort_values("contract_month").reset_index(drop=True)
    rolls["front_start_date"] = rolls["roll_date"].shift(1)

    settle_by_month = bars.pivot_table(
        index="date",
        columns="contract_month",
        values="settle",
        aggfunc="last",
    )

    rows: list[dict] = []
    contract_months = rolls["contract_month"].tolist()
    roll_by_month = dict(zip(rolls["contract_month"], rolls["roll_date"]))
    contract_by_month = dict(zip(rolls["contract_month"], rolls["contract"]))
    expiration_by_month = dict(zip(rolls["contract_month"], rolls["expiration_date"]))
    start_by_month = dict(zip(rolls["contract_month"], rolls["front_start_date"]))

    for dt, settles in settle_by_month.sort_index().iterrows():
        eligible_fronts = [
            month
            for month in contract_months
            if pd.notna(start_by_month[month])
            and start_by_month[month] <= dt < roll_by_month[month]
            and pd.notna(settles.get(month))
        ]
        if not eligible_fronts:
            continue

        front = eligible_fronts[0]
        front_index = contract_months.index(front)
        if front_index + 1 >= len(contract_months):
            continue

        second = contract_months[front_index + 1]
        if pd.isna(settles.get(second)):
            continue

        rows.append(
            {
                "date": dt,
                "ng1_settle": float(settles[front]),
                "ng2_settle": float(settles[second]),
                "ng1_contract_month": front,
                "ng2_contract_month": second,
                "ng1_contract": contract_by_month[front],
                "ng2_contract": contract_by_month[second],
                "ng1_expiration_date": expiration_by_month[front],
                "ng1_front_start_date": start_by_month[front],
                "ng1_roll_date": roll_by_month[front],
            }
        )

    if not rows:
        raise RuntimeError("continuous series build produced no rows")

    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
