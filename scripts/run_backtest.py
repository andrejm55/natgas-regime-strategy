from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.workflow import run_backtest_from_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_outright.yaml")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    backtest, metrics = run_backtest_from_config(args.config)
    for key, value in metrics.items():
        if key in {"cagr", "annual_vol", "max_drawdown"}:
            print(f"{key}: {value:.2%}")
        else:
            print(f"{key}: {value:,.4f}")

    if args.save:
        strategy_cfg = load_yaml(args.config)
        data_cfg = load_yaml(strategy_cfg["data_config"])
        output_dir = resolve_path(data_cfg["outputs"]["backtests"])
        output_dir.mkdir(parents=True, exist_ok=True)
        backtest_path = output_dir / f"{strategy_cfg['name']}_daily_backtest.csv"
        metrics_path = output_dir / f"{strategy_cfg['name']}_metrics.json"
        backtest.to_csv(backtest_path, index=False)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"saved_backtest: {backtest_path}")
        print(f"saved_metrics: {metrics_path}")


if __name__ == "__main__":
    main()
