from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.backtest.engine import CostConfig, run_daily_backtest
from natgas_regime.backtest.metrics import summarize_performance
from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.strategy.sizing import SizingConfig, add_contract_sizing
from natgas_regime.workflow import build_features_from_config, generate_positions_from_config

PositionMutator = Callable[[pd.Series], pd.Series]


def _force_signal_side(cfg: dict, side: str | None) -> None:
    signal_cfg = cfg.get("signals", {})
    if "allow_longs" not in signal_cfg or "allow_shorts" not in signal_cfg:
        return
    if side == "both":
        signal_cfg["allow_longs"] = True
        signal_cfg["allow_shorts"] = True
    elif side == "long_only":
        signal_cfg["allow_longs"] = True
        signal_cfg["allow_shorts"] = False
    elif side == "short_only":
        signal_cfg["allow_longs"] = False
        signal_cfg["allow_shorts"] = True


def run_variant(
    config_path: str,
    mutator: PositionMutator | None,
    signal_side: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    cfg = load_yaml(config_path)
    _force_signal_side(cfg, signal_side)
    features = build_features_from_config(config_path)
    signals = generate_positions_from_config(features, cfg)
    if mutator is not None:
        signals["position_direction"] = mutator(signals["position_direction"])

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
    return backtest, metrics


def monthly_attribution(backtest: pd.DataFrame) -> pd.DataFrame:
    out = backtest.copy()
    out["month"] = out["date"].dt.to_period("M").astype(str)
    return (
        out.groupby("month")
        .agg(
            days=("date", "count"),
            active_days=("signed_contracts", lambda s: int((s != 0).sum())),
            avg_contracts=("signed_contracts", "mean"),
            gross_pnl=("gross_pnl", "sum"),
            net_pnl=("net_pnl", "sum"),
            turnover_contracts=("turnover_contracts", "sum"),
            min_drawdown=("drawdown", "min"),
        )
        .reset_index()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_spread_score_v1.yaml")
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    data_cfg = load_yaml(cfg["data_config"])
    output_dir = resolve_path(data_cfg["outputs"]["backtests"])
    output_dir.mkdir(parents=True, exist_ok=True)

    variants: dict[str, tuple[PositionMutator | None, str | None]] = {
        "production": (None, None),
        "all_research": (None, "both"),
        "long_only": (lambda s: s.clip(lower=0), "long_only"),
        "short_only": (lambda s: s.clip(upper=0), "short_only"),
        "inverted_production": (lambda s: -s, None),
    }
    summary_rows: list[dict] = []
    for variant, (mutator, signal_side) in variants.items():
        backtest, metrics = run_variant(args.config, mutator, signal_side)
        backtest_path = output_dir / f"{cfg['name']}_{variant}_daily_backtest.csv"
        monthly_path = output_dir / f"{cfg['name']}_{variant}_monthly_attribution.csv"
        backtest.to_csv(backtest_path, index=False)
        monthly_attribution(backtest).to_csv(monthly_path, index=False)
        summary_rows.append({"variant": variant, **metrics})

    summary = pd.DataFrame(summary_rows).sort_values("sharpe", ascending=False)
    summary_path = output_dir / f"{cfg['name']}_side_diagnostics.csv"
    summary_json_path = output_dir / f"{cfg['name']}_side_diagnostics.json"
    summary.to_csv(summary_path, index=False)
    summary_json_path.write_text(
        json.dumps(summary.to_dict(orient="records"), indent=2), encoding="utf-8"
    )
    print(f"Wrote side diagnostics to {summary_path}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
