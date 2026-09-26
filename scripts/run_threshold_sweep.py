from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.backtest.engine import CostConfig, run_daily_backtest
from natgas_regime.backtest.metrics import summarize_performance
from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.strategy.signals import SignalConfig, generate_positions
from natgas_regime.strategy.sizing import SizingConfig, add_contract_sizing
from natgas_regime.workflow import build_features_from_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_outright.yaml")
    parser.add_argument("--thresholds", default="0.25,0.50,0.75,1.00,1.25,1.50")
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    data_cfg = load_yaml(cfg["data_config"])
    features = build_features_from_config(args.config)
    thresholds = [float(x) for x in args.thresholds.split(",")]
    rows: list[dict] = []

    for z_tight in thresholds:
        for z_loose in thresholds:
            signal_cfg = SignalConfig(
                **{
                    **cfg["signals"],
                    "z_tight": z_tight,
                    "z_loose": z_loose,
                }
            )
            signals = generate_positions(features, signal_cfg)
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
                    "z_tight": z_tight,
                    "z_loose": z_loose,
                    "active_days": int((backtest["signed_contracts"] != 0).sum()),
                    **metrics,
                }
            )

    result = pd.DataFrame(rows).sort_values(["sharpe", "end_equity"], ascending=False)
    output_dir = resolve_path(data_cfg["outputs"]["backtests"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{cfg['name']}_threshold_sweep.csv"
    result.to_csv(output_path, index=False)
    print(f"Wrote threshold sweep to {output_path}")
    print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
