from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.workflow import run_backtest_from_config


def _bucket(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(series, bins=bins, labels=labels, include_lowest=True).astype("string")


def _safe_mean(series: pd.Series) -> float:
    return float(series.dropna().mean()) if series.notna().any() else 0.0


def forward_return_summary(frame: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    out = frame.copy()
    for horizon in horizons:
        out[f"ng1_fwd_{horizon}d"] = out["ng1_settle"].shift(-horizon) / out["ng1_settle"] - 1.0
        out[f"spread_fwd_{horizon}d"] = out["spread_settle"].shift(-horizon) - out["spread_settle"]

    out["weather_bucket"] = _bucket(
        out["outright_score_weather"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["very_bearish", "bearish", "neutral", "bullish", "very_bullish"],
    )
    out["weather_7d_bucket"] = _bucket(
        out["outright_score_weather_7d"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["very_bearish", "bearish", "neutral", "bullish", "very_bullish"],
    )
    out["storage_bucket"] = _bucket(
        out["outright_score_storage"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["loose", "mild_loose", "neutral", "mild_tight", "tight"],
    )
    out["storage_change_bucket"] = _bucket(
        out["outright_score_storage_change"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["bearish_change", "mild_bearish", "neutral", "mild_bullish", "bullish_change"],
    )
    out["curve_bucket"] = _bucket(
        out["outright_score_slope"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["contango", "mild_contango", "neutral", "mild_backwardated", "backwardated"],
    )
    out["score_bucket"] = _bucket(
        out["outright_score"],
        [-float("inf"), -2.0, -1.25, -0.5, 0.5, 1.25, 2.0, float("inf")],
        ["strong_short", "short", "weak_short", "neutral", "weak_long", "long", "strong_long"],
    )

    bucket_specs = [
        ("season", "season"),
        ("weather", "weather_bucket"),
        ("weather_7d", "weather_7d_bucket"),
        ("storage", "storage_bucket"),
        ("storage_change", "storage_change_bucket"),
        ("curve", "curve_bucket"),
        ("total_score", "score_bucket"),
    ]
    rows: list[dict] = []
    for feature_name, column in bucket_specs:
        grouped = out.groupby(column, observed=True)
        for bucket, group in grouped:
            row = {
                "feature": feature_name,
                "bucket": str(bucket),
                "days": len(group),
                "avg_outright_score": _safe_mean(group["outright_score"]),
            }
            for horizon in horizons:
                row[f"avg_ng1_fwd_{horizon}d"] = _safe_mean(group[f"ng1_fwd_{horizon}d"])
                row[f"avg_spread_fwd_{horizon}d"] = _safe_mean(group[f"spread_fwd_{horizon}d"])
            rows.append(row)
    return pd.DataFrame(rows)


def pnl_attribution(backtest: pd.DataFrame) -> pd.DataFrame:
    out = backtest.copy()
    out["active"] = out["prior_contracts"] != 0
    out["position_side"] = out["prior_contracts"].map(
        lambda value: "long" if value > 0 else "short" if value < 0 else "flat"
    )
    out["weather_bucket"] = _bucket(
        out["outright_score_weather"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["very_bearish", "bearish", "neutral", "bullish", "very_bullish"],
    )
    out["storage_bucket"] = _bucket(
        out["outright_score_storage"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["loose", "mild_loose", "neutral", "mild_tight", "tight"],
    )
    out["curve_bucket"] = _bucket(
        out["outright_score_slope"],
        [-float("inf"), -1.0, -0.25, 0.25, 1.0, float("inf")],
        ["contango", "mild_contango", "neutral", "mild_backwardated", "backwardated"],
    )

    rows: list[dict] = []
    for feature_name, column in [
        ("season", "season"),
        ("position_side", "position_side"),
        ("weather", "weather_bucket"),
        ("storage", "storage_bucket"),
        ("curve", "curve_bucket"),
    ]:
        for bucket, group in out[out["active"]].groupby(column, observed=True):
            rows.append(
                {
                    "feature": feature_name,
                    "bucket": str(bucket),
                    "active_days": len(group),
                    "avg_contracts": float(group["prior_contracts"].mean()),
                    "gross_pnl": float(group["gross_pnl"].sum()),
                    "net_pnl": float(group["net_pnl"].sum()),
                }
            )
    return pd.DataFrame(rows).sort_values(["feature", "net_pnl"], ascending=[True, False])


def write_report(
    report_path: Path,
    metrics: dict[str, float],
    forward: pd.DataFrame,
    pnl: pd.DataFrame,
    backtest: pd.DataFrame,
) -> None:
    weather_rows = forward[forward["feature"].eq("weather")].copy()
    bullish = weather_rows[weather_rows["bucket"].isin(["bullish", "very_bullish"])]
    bearish = weather_rows[weather_rows["bucket"].isin(["bearish", "very_bearish"])]

    lines = [
        "# Outright Direction Diagnostics",
        "",
        "## Backtest",
        "",
        "```text",
        f"start_date: {backtest['date'].min().date()}",
        f"end_date:   {backtest['date'].max().date()}",
        f"end_equity: {metrics['end_equity']:,.0f}",
        f"sharpe:     {metrics['sharpe']:.2f}",
        f"max_dd:     {metrics['max_drawdown']:.2%}",
        "```",
        "",
        "## Weather Direction Check",
        "",
        "Average NG1 forward returns after bullish weather buckets:",
        "",
        "```text",
        bullish[
            ["bucket", "days", "avg_ng1_fwd_1d", "avg_ng1_fwd_5d", "avg_ng1_fwd_10d", "avg_ng1_fwd_20d"]
        ].to_string(index=False),
        "```",
        "",
        "Average NG1 forward returns after bearish weather buckets:",
        "",
        "```text",
        bearish[
            ["bucket", "days", "avg_ng1_fwd_1d", "avg_ng1_fwd_5d", "avg_ng1_fwd_10d", "avg_ng1_fwd_20d"]
        ].to_string(index=False),
        "```",
        "",
        "## PnL Attribution",
        "",
        "```text",
        pnl.to_string(index=False),
        "```",
        "",
        "## Files",
        "",
        "- Forward bucket diagnostics: `outputs/01_backtests/natgas_weather_outright_v1_forward_return_buckets.csv`",
        "- PnL attribution: `outputs/01_backtests/natgas_weather_outright_v1_pnl_attribution.csv`",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_weather_outright_v1.yaml")
    parser.add_argument("--horizons", default="1,5,10,20")
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    data_cfg = load_yaml(cfg["data_config"])
    output_dir = resolve_path(data_cfg["outputs"]["backtests"])
    report_dir = resolve_path(data_cfg["outputs"]["reports"])
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    horizons = [int(item) for item in args.horizons.split(",")]
    backtest, metrics = run_backtest_from_config(args.config)
    forward = forward_return_summary(backtest, horizons)
    pnl = pnl_attribution(backtest)

    forward_path = output_dir / f"{cfg['name']}_forward_return_buckets.csv"
    pnl_path = output_dir / f"{cfg['name']}_pnl_attribution.csv"
    metrics_path = output_dir / f"{cfg['name']}_direction_diagnostics.json"
    report_path = report_dir / f"{cfg['name']}_direction_diagnostics.md"
    forward.to_csv(forward_path, index=False)
    pnl.to_csv(pnl_path, index=False)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_report(report_path, metrics, forward, pnl, backtest)

    print(f"Wrote forward return diagnostics to {forward_path}")
    print(f"Wrote PnL attribution to {pnl_path}")
    print(f"Wrote report to {report_path}")
    print(forward[forward["feature"].eq("weather")].to_string(index=False))
    print(pnl.to_string(index=False))


if __name__ == "__main__":
    main()
