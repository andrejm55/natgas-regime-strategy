from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.workflow import run_backtest_from_config


def classify_event(row: pd.Series) -> str:
    weather = bool(row.get("event_has_weather_shock", False))
    storage = bool(row.get("event_has_storage_shock", False))
    reversion = abs(float(row.get("event_reversion_score", 0.0))) > 0

    if reversion and storage:
        return "weather_fade_plus_storage"
    if reversion:
        return "weather_fade"
    if weather and storage:
        return "combined_weather_storage"
    if weather:
        return "weather_shock"
    if storage:
        return "storage_surprise"
    return "other"


def add_trade_attribution(backtest: pd.DataFrame) -> pd.DataFrame:
    out = backtest.sort_values("date").copy()
    trade_id = 0
    current_type = "flat"
    trade_ids: list[int | None] = []
    event_types: list[str] = []

    previous_signed = 0
    previous_type = "flat"
    for _, row in out.iterrows():
        signed = int(row["signed_contracts"])
        if signed != 0 and previous_signed == 0:
            trade_id += 1
            current_type = classify_event(row)
        elif signed != 0:
            current_type = previous_type
        else:
            current_type = "flat"

        if row["prior_contracts"] != 0:
            trade_ids.append(trade_id if trade_id > 0 else None)
            event_types.append(previous_type)
        else:
            trade_ids.append(None)
            event_types.append("flat")

        previous_signed = signed
        previous_type = current_type

    out["event_trade_id"] = trade_ids
    out["event_type"] = event_types
    out["event_side"] = out["prior_contracts"].map(
        lambda value: "long" if value > 0 else "short" if value < 0 else "flat"
    )
    return out


def summarize(attributed: pd.DataFrame) -> pd.DataFrame:
    active = attributed[attributed["prior_contracts"] != 0].copy()
    if active.empty:
        return pd.DataFrame()
    return (
        active.groupby(["event_type", "event_side"], observed=True)
        .agg(
            active_days=("date", "count"),
            trades=("event_trade_id", "nunique"),
            avg_contracts=("prior_contracts", "mean"),
            gross_pnl=("gross_pnl", "sum"),
            net_pnl=("net_pnl", "sum"),
        )
        .reset_index()
        .sort_values("net_pnl", ascending=False)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_event_outright_v1.yaml")
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    data_cfg = load_yaml(cfg["data_config"])
    output_dir = resolve_path(data_cfg["outputs"]["backtests"])
    output_dir.mkdir(parents=True, exist_ok=True)

    backtest, _ = run_backtest_from_config(args.config)
    attributed = add_trade_attribution(backtest)
    summary = summarize(attributed)
    detail_path = output_dir / f"{cfg['name']}_event_attribution_daily.csv"
    summary_path = output_dir / f"{cfg['name']}_event_attribution_summary.csv"
    attributed.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(f"Wrote event attribution detail to {detail_path}")
    print(f"Wrote event attribution summary to {summary_path}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
