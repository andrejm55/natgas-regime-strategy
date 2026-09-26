from __future__ import annotations
import numpy as np
import pandas as pd


def summarize_performance(backtest: pd.DataFrame) -> dict[str, float]:
    returns = backtest["daily_return"].dropna()
    years = max((backtest["date"].max() - backtest["date"].min()).days / 365.25, 1e-9)
    start_equity = float(backtest["equity"].iloc[0])
    end_equity = float(backtest["equity"].iloc[-1])
    cagr = (end_equity / start_equity) ** (1 / years) - 1
    vol = returns.std(ddof=0) * np.sqrt(252)
    sharpe = (returns.mean() * 252) / vol if vol > 0 else 0.0
    return {
        "start_equity": start_equity,
        "end_equity": end_equity,
        "cagr": cagr,
        "annual_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": float(backtest["drawdown"].min()),
        "turnover_contracts": float(backtest["turnover_contracts"].sum()),
    }

