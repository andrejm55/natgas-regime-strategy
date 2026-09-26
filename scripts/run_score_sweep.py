from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.backtest.engine import CostConfig, run_daily_backtest
from natgas_regime.backtest.metrics import summarize_performance
from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.strategy.signals import ScoredSignalConfig, generate_scored_positions
from natgas_regime.strategy.sizing import SizingConfig, add_contract_sizing
from natgas_regime.workflow import build_features_from_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_regime_score_v1.yaml")
    parser.add_argument("--entry-scores", default="0.75,1.00,1.25,1.50,1.75,2.00")
    parser.add_argument("--exit-scores", default="0.25,0.35,0.50,0.75")
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    data_cfg = load_yaml(cfg["data_config"])
    features = build_features_from_config(args.config)
    entry_scores = [float(x) for x in args.entry_scores.split(",")]
    exit_scores = [float(x) for x in args.exit_scores.split(",")]
    rows: list[dict] = []

    for entry_score in entry_scores:
        for exit_score in exit_scores:
            signal_values = {
                key: value for key, value in cfg["signals"].items() if key != "model"
            }
            signal_cfg = ScoredSignalConfig(
                **{
                    **signal_values,
                    "entry_score": entry_score,
                    "exit_score": exit_score,
                }
            )
            signals = generate_scored_positions(features, signal_cfg)
            sized = add_contract_sizing(
                signals,
                SizingConfig(
                    **cfg["sizing"],
                    multiplier=cfg["instrument"]["multiplier"],
                    price_col=cfg["instrument"].get("sizing_price_col", "ng1_settle"),
                    vol_col=cfg["instrument"].get("sizing_vol_col", "rv20"),
                    vol_kind=cfg["instrument"].get("sizing_vol_kind", "return"),
                ),
            )
            backtest = run_daily_backtest(
                sized,
                multiplier=cfg["instrument"]["multiplier"],
                initial_equity=cfg["sizing"]["initial_equity"],
                costs=CostConfig(
                    commission_per_contract=cfg["costs"]["commission_per_contract"],
                    slippage_ticks=cfg["costs"]["slippage_ticks"],
                    tick_value=cfg["instrument"]["tick_value"],
                    turnover_multiplier=cfg["instrument"].get("cost_turnover_multiplier", 1.0),
                ),
                price_col=cfg["instrument"].get("backtest_price_col", "ng1_settle"),
            )
            metrics = summarize_performance(backtest)
            rows.append(
                {
                    "entry_score": entry_score,
                    "exit_score": exit_score,
                    "active_days": int((backtest["signed_contracts"] != 0).sum()),
                    "position_changes": int(
                        (
                            backtest["signed_contracts"]
                            .diff()
                            .fillna(backtest["signed_contracts"])
                            != 0
                        ).sum()
                    ),
                    **metrics,
                }
            )

    result = pd.DataFrame(rows).sort_values(["sharpe", "end_equity"], ascending=False)
    output_dir = resolve_path(data_cfg["outputs"]["backtests"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{cfg['name']}_score_sweep.csv"
    result.to_csv(output_path, index=False)
    print(f"Wrote score sweep to {output_path}")
    print(result.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
