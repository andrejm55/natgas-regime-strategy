from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class CostConfig:
    commission_per_contract: float
    slippage_ticks: float
    tick_value: float
    turnover_multiplier: float = 1.0


def run_daily_backtest(
    frame: pd.DataFrame,
    multiplier: float,
    initial_equity: float,
    costs: CostConfig,
    price_col: str = "ng1_settle",
) -> pd.DataFrame:
    out = frame.sort_values("date").copy()
    out["price_change"] = out[price_col].diff().fillna(0)
    out["prior_contracts"] = out["signed_contracts"].shift(1).fillna(0)
    out["gross_pnl"] = out["prior_contracts"] * out["price_change"] * multiplier
    out["turnover_contracts"] = (out["signed_contracts"] - out["prior_contracts"]).abs()
    cost_turnover = out["turnover_contracts"] * costs.turnover_multiplier
    out["commission"] = cost_turnover * costs.commission_per_contract
    out["slippage"] = cost_turnover * costs.slippage_ticks * costs.tick_value
    out["net_pnl"] = out["gross_pnl"] - out["commission"] - out["slippage"]
    out["equity"] = initial_equity + out["net_pnl"].cumsum()
    out["daily_return"] = out["equity"].pct_change().fillna(0)
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0
    return out
