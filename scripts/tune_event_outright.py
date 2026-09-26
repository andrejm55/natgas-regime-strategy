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


def run_candidate(cfg: dict, features: pd.DataFrame) -> dict:
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
    metrics["active_days"] = int((backtest["signed_contracts"] != 0).sum())
    metrics["position_changes"] = int(
        (backtest["signed_contracts"].diff().fillna(backtest["signed_contracts"]) != 0).sum()
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_event_outright_v1.yaml")
    parser.add_argument("--long-event", default="2.0,2.5,3.0")
    parser.add_argument("--short-event", default="1.0,1.5,2.0")
    parser.add_argument("--long-reversion", default="1.75,2.0,2.5")
    parser.add_argument("--short-reversion", default="1.0,1.25,1.5")
    parser.add_argument("--max-long", default="1,2,3")
    parser.add_argument("--max-short", default="3,5")
    parser.add_argument("--profit-trigger", default="0,0.15,0.20,0.30")
    parser.add_argument("--profit-giveback", default="0.05,0.10,0.15")
    args = parser.parse_args()

    base_cfg = load_yaml(args.config)
    data_cfg = load_yaml(base_cfg["data_config"])
    features = build_features_from_config(args.config)
    rows: list[dict] = []

    for long_event in _float_grid(args.long_event):
        for short_event in _float_grid(args.short_event):
            for long_reversion in _float_grid(args.long_reversion):
                for short_reversion in _float_grid(args.short_reversion):
                    for max_long in _int_grid(args.max_long):
                        for max_short in _int_grid(args.max_short):
                            for profit_trigger in _float_grid(args.profit_trigger):
                                for profit_giveback in _float_grid(args.profit_giveback):
                                    cfg = copy.deepcopy(base_cfg)
                                    cfg["signals"]["long_event_entry_score"] = long_event
                                    cfg["signals"]["short_event_entry_score"] = short_event
                                    cfg["signals"]["long_reversion_entry_score"] = long_reversion
                                    cfg["signals"]["short_reversion_entry_score"] = short_reversion
                                    cfg["signals"]["profit_protection_trigger"] = profit_trigger
                                    cfg["signals"]["profit_giveback"] = profit_giveback
                                    cfg["signals"]["allow_storage_only_events"] = False
                                    cfg["signals"]["allow_combined_storage_longs"] = False
                                    cfg["signals"]["allow_combined_storage_shorts"] = True
                                    cfg["sizing"]["max_long_contracts"] = max_long
                                    cfg["sizing"]["max_short_contracts"] = max_short
                                    metrics = run_candidate(cfg, features)
                                    rows.append(
                                        {
                                            "long_event_entry_score": long_event,
                                            "short_event_entry_score": short_event,
                                            "long_reversion_entry_score": long_reversion,
                                            "short_reversion_entry_score": short_reversion,
                                            "max_long_contracts": max_long,
                                            "max_short_contracts": max_short,
                                            "profit_protection_trigger": profit_trigger,
                                            "profit_giveback": profit_giveback,
                                            **metrics,
                                        }
                                    )

    result = pd.DataFrame(rows).sort_values(["sharpe", "end_equity"], ascending=False)
    output_dir = resolve_path(data_cfg["outputs"]["backtests"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{base_cfg['name']}_tuning_grid.csv"
    result.to_csv(output_path, index=False)
    print(f"Wrote event tuning grid to {output_path}")
    print(result.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
