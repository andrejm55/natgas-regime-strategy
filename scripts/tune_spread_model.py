from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.backtest.engine import CostConfig, run_daily_backtest
from natgas_regime.backtest.metrics import summarize_performance
from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.strategy.sizing import SizingConfig, add_contract_sizing
from natgas_regime.workflow import build_features_from_config, generate_positions_from_config


def _float_grid(text: str) -> list[float]:
    return [float(item) for item in text.split(",")]


def _int_grid(text: str) -> list[int]:
    return [int(item) for item in text.split(",")]


def run_candidate(config_path: str, cfg: dict, features: pd.DataFrame) -> dict:
    signals = generate_positions_from_config(features, cfg)
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
    return {
        "config": config_path,
        "active_days": int((backtest["signed_contracts"] != 0).sum()),
        "position_changes": int(
            (backtest["signed_contracts"].diff().fillna(backtest["signed_contracts"]) != 0).sum()
        ),
        **metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_spread_score_v1.yaml")
    parser.add_argument("--long-entry", default="0.75,1.00,1.25,1.50")
    parser.add_argument("--short-entry", default="1.00,1.25,1.50,1.75,2.00")
    parser.add_argument("--long-momentum", default="-0.05,0.00,0.02,0.05")
    parser.add_argument("--short-momentum", default="-0.10,-0.05,-0.02,0.00")
    parser.add_argument("--weather-weight", default="0.50,0.75,1.00")
    parser.add_argument("--max-contracts", default="5,10,15,20")
    args = parser.parse_args()

    base_cfg = load_yaml(args.config)
    data_cfg = load_yaml(base_cfg["data_config"])
    features = build_features_from_config(args.config)
    rows: list[dict] = []

    for long_entry in _float_grid(args.long_entry):
        for short_entry in _float_grid(args.short_entry):
            for long_momentum in _float_grid(args.long_momentum):
                for short_momentum in _float_grid(args.short_momentum):
                    for weather_weight in _float_grid(args.weather_weight):
                        for max_contracts in _int_grid(args.max_contracts):
                            cfg = copy.deepcopy(base_cfg)
                            cfg["signals"]["long_entry_score"] = long_entry
                            cfg["signals"]["short_entry_score"] = short_entry
                            cfg["signals"]["long_spread_momentum_floor"] = long_momentum
                            cfg["signals"]["short_spread_momentum_ceiling"] = short_momentum
                            cfg["signals"]["weather_weight"] = weather_weight
                            cfg["sizing"]["max_contracts"] = max_contracts
                            metrics = run_candidate(args.config, cfg, features)
                            rows.append(
                                {
                                    "long_entry_score": long_entry,
                                    "short_entry_score": short_entry,
                                    "long_spread_momentum_floor": long_momentum,
                                    "short_spread_momentum_ceiling": short_momentum,
                                    "weather_weight": weather_weight,
                                    "max_contracts": max_contracts,
                                    **metrics,
                                }
                            )

    result = pd.DataFrame(rows).sort_values(["sharpe", "end_equity"], ascending=False)
    output_dir = resolve_path(data_cfg["outputs"]["backtests"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{base_cfg['name']}_tuning_grid.csv"
    result.to_csv(output_path, index=False)
    print(f"Wrote spread tuning grid to {output_path}")
    print(result.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
