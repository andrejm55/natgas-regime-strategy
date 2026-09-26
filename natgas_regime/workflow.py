from __future__ import annotations
from pathlib import Path
import pandas as pd
from natgas_regime.backtest.engine import CostConfig, run_daily_backtest
from natgas_regime.backtest.metrics import summarize_performance
from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.data.sample import make_sample_daily_data, make_sample_storage
from natgas_regime.data.store import DuckDBStore
from natgas_regime.features.pipeline import build_feature_table
from natgas_regime.strategy.signals import (
    EventOutrightConfig,
    ScoredSignalConfig,
    SignalConfig,
    SpreadSignalConfig,
    WeatherOutrightConfig,
    generate_event_outright_positions,
    generate_positions,
    generate_scored_positions,
    generate_spread_positions,
    generate_weather_outright_positions,
)
from natgas_regime.strategy.sizing import SizingConfig, add_contract_sizing


def load_or_sample_inputs(
    strategy_config_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, dict]:
    strategy_cfg = load_yaml(strategy_config_path)
    data_cfg = load_yaml(strategy_cfg["data_config"])
    csv_cfg = data_cfg.get("csv", {})

    futures_path = csv_cfg.get("futures_contracts")
    storage_path = csv_cfg.get("storage")
    weather_path = csv_cfg.get("weather")

    if futures_path and resolve_path(futures_path).exists():
        daily = pd.read_csv(resolve_path(futures_path), parse_dates=["date"])
    else:
        daily = make_sample_daily_data()

    if storage_path and resolve_path(storage_path).exists():
        storage = pd.read_csv(resolve_path(storage_path), parse_dates=["release_date"])
    else:
        storage = make_sample_storage()

    weather = None
    if weather_path and resolve_path(weather_path).exists():
        weather = pd.read_csv(resolve_path(weather_path), parse_dates=["date"])

    return daily, storage, weather, strategy_cfg


def build_features_from_config(strategy_config_path: str | Path) -> pd.DataFrame:
    daily, storage, weather, cfg = load_or_sample_inputs(strategy_config_path)
    features_cfg = cfg["features"]
    return build_feature_table(
        daily=daily,
        storage=storage,
        baseline_years=features_cfg["storage_baseline_years"],
        realized_vol_window=features_cfg["realized_vol_window"],
        riskoff_percentile_window=features_cfg["riskoff_percentile_window"],
        riskoff_percentile=features_cfg["riskoff_percentile"],
        weather=weather,
        weather_baseline_years=features_cfg.get("weather_baseline_years", 10),
    )


def generate_positions_from_config(features: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    signal_cfg = cfg["signals"]
    model = signal_cfg.get("model", "regime_strict")
    if model == "regime_strict":
        strict_keys = {
            "z_tight",
            "z_loose",
            "long_exit_storage_z",
            "short_exit_storage_z",
            "max_holding_days",
        }
        return generate_positions(
            features,
            SignalConfig(**{key: signal_cfg[key] for key in strict_keys}),
        )
    if model == "regime_score_v1":
        scored_keys = {
            "entry_score",
            "exit_score",
            "max_holding_days",
            "slope_scale",
            "storage_weight",
            "slope_weight",
            "weather_weight",
            "weather_7d_weight",
            "season_weight",
            "trend_weight",
            "momentum_window",
            "momentum_scale",
            "short_momentum_ceiling",
            "long_allowed_seasons",
            "short_allowed_seasons",
            "max_component_abs",
        }
        return generate_scored_positions(
            features,
            ScoredSignalConfig(**{key: signal_cfg[key] for key in scored_keys}),
        )
    if model == "weather_outright_v1":
        outright_keys = {
            "entry_score",
            "exit_score",
            "max_holding_days",
            "weather_weight",
            "weather_7d_weight",
            "trend_weight",
            "storage_weight",
            "storage_change_weight",
            "storage_percentile_weight",
            "storage_change_scale",
            "slope_weight",
            "season_weight",
            "momentum_window",
            "confirmation_momentum_window",
            "momentum_scale",
            "min_abs_price_vs_sma",
            "allow_longs",
            "allow_shorts",
            "long_momentum_floor",
            "short_momentum_ceiling",
            "loose_storage_avoid_long_z",
            "contango_avoid_long_slope",
            "max_component_abs",
        }
        return generate_weather_outright_positions(
            features,
            WeatherOutrightConfig(**{key: signal_cfg[key] for key in outright_keys}),
        )
    if model == "spread_score_v1":
        spread_keys = {
            "entry_score",
            "long_entry_score",
            "short_entry_score",
            "allow_longs",
            "allow_shorts",
            "exit_score",
            "max_holding_days",
            "storage_weight",
            "storage_change_weight",
            "storage_percentile_weight",
            "storage_change_scale",
            "slope_weight",
            "weather_weight",
            "weather_7d_weight",
            "season_weight",
            "slope_scale",
            "momentum_window",
            "long_spread_momentum_floor",
            "short_spread_momentum_ceiling",
            "short_min_contango_slope",
            "short_min_storage_z",
            "max_component_abs",
        }
        return generate_spread_positions(
            features,
            SpreadSignalConfig(**{key: signal_cfg[key] for key in spread_keys}),
        )
    if model == "event_outright_v1":
        event_keys = {
            "allow_longs",
            "allow_shorts",
            "max_holding_days",
            "exit_score",
            "event_entry_score",
            "long_event_entry_score",
            "short_event_entry_score",
            "reversion_entry_score",
            "long_reversion_entry_score",
            "short_reversion_entry_score",
            "weather_anomaly_threshold",
            "weather_change_threshold",
            "storage_surprise_threshold",
            "curve_confirm_threshold",
            "curve_lookback_days",
            "weather_weight",
            "weather_change_weight",
            "storage_surprise_weight",
            "curve_weight",
            "storage_entry_mode",
            "event_direction",
            "reversion_weather_threshold",
            "reversion_change_threshold",
            "profit_protection_trigger",
            "profit_giveback",
            "allow_storage_only_events",
            "allow_combined_storage_longs",
            "allow_combined_storage_shorts",
            "weak_long_min_contracts",
            "weak_long_max_contracts",
            "strong_long_min_contracts",
            "strong_long_max_contracts",
            "weak_short_min_contracts",
            "weak_short_max_contracts",
            "strong_short_min_contracts",
            "strong_short_max_contracts",
            "max_component_abs",
            "allow_curve_only_events",
            "allow_contango_weather_events",
            "summer_max_entry_rv20",
        }
        return generate_event_outright_positions(
            features,
            EventOutrightConfig(
                **{key: signal_cfg[key] for key in event_keys if key in signal_cfg}
            ),
        )
    raise ValueError(f"unknown signal model: {model}")


def run_backtest_from_config(strategy_config_path: str | Path) -> tuple[pd.DataFrame, dict[str, float]]:
    cfg = load_yaml(strategy_config_path)
    if cfg["signals"].get("model") == "event_regime_overlay_v1":
        return run_event_regime_overlay_from_config(strategy_config_path)

    features = build_features_from_config(strategy_config_path)
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
    costs = CostConfig(
        commission_per_contract=cfg["costs"]["commission_per_contract"],
        slippage_ticks=cfg["costs"]["slippage_ticks"],
        tick_value=cfg["instrument"]["tick_value"],
        turnover_multiplier=cfg["instrument"].get("cost_turnover_multiplier", 1.0),
    )
    backtest = run_daily_backtest(
        sized,
        multiplier=cfg["instrument"]["multiplier"],
        initial_equity=cfg["sizing"]["initial_equity"],
        costs=costs,
        price_col=cfg["instrument"].get("backtest_price_col", "ng1_settle"),
    )
    return backtest, summarize_performance(backtest)


def run_event_regime_overlay_from_config(
    strategy_config_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, float]]:
    cfg = load_yaml(strategy_config_path)
    signal_cfg = cfg["signals"]
    event_cfg_path = signal_cfg["event_config"]
    overlay_cfg_path = signal_cfg["overlay_config"]
    event_cfg = load_yaml(event_cfg_path)
    overlay_cfg = load_yaml(overlay_cfg_path)

    event_features = build_features_from_config(event_cfg_path)
    event_signals = generate_positions_from_config(event_features, event_cfg)
    event_sized = add_contract_sizing(
        event_signals,
        SizingConfig(
            **event_cfg["sizing"],
            multiplier=event_cfg["instrument"]["multiplier"],
            price_col=event_cfg["instrument"].get("sizing_price_col", "ng1_settle"),
            vol_col=event_cfg["instrument"].get("sizing_vol_col", "rv20"),
            vol_kind=event_cfg["instrument"].get("sizing_vol_kind", "return"),
        ),
    )

    overlay_features = build_features_from_config(overlay_cfg_path)
    overlay_signals = generate_positions_from_config(overlay_features, overlay_cfg)
    overlay_sized = add_contract_sizing(
        overlay_signals,
        SizingConfig(
            **overlay_cfg["sizing"],
            multiplier=overlay_cfg["instrument"]["multiplier"],
            price_col=overlay_cfg["instrument"].get("sizing_price_col", "ng1_settle"),
            vol_col=overlay_cfg["instrument"].get("sizing_vol_col", "rv20"),
            vol_kind=overlay_cfg["instrument"].get("sizing_vol_kind", "return"),
        ),
    )

    overlay_cols = overlay_sized[["date", "signed_contracts"]].rename(
        columns={"signed_contracts": "overlay_signed_contracts"}
    )
    combined = event_sized.merge(overlay_cols, on="date", how="left")
    combined["overlay_signed_contracts"] = combined["overlay_signed_contracts"].fillna(0)

    storage_z_max = float(signal_cfg["overlay_storage_z_max"])
    overlay_allowed = combined["storage_z"] < storage_z_max
    if signal_cfg.get("overlay_allow_high_storage_winter_backwardation_longs", False):
        high_storage_months = signal_cfg.get(
            "overlay_high_storage_winter_backwardation_months"
        )
        if high_storage_months is None:
            month_allowed = True
        else:
            month_allowed = combined["date"].dt.month.isin(high_storage_months)
        high_storage_z_max = signal_cfg.get("overlay_high_storage_z_max")
        if high_storage_z_max is None:
            high_storage_z_allowed = True
        else:
            high_storage_z_allowed = combined["storage_z"] < float(high_storage_z_max)
        high_storage_long_overlay_allowed = (
            (combined["season"] == "winter")
            & (combined["curve_regime"] == "backwardation")
            & (combined["overlay_signed_contracts"] > 0)
            & month_allowed
            & high_storage_z_allowed
        )
    else:
        high_storage_long_overlay_allowed = False
    overlay_allowed = overlay_allowed | high_storage_long_overlay_allowed
    if signal_cfg.get("overlay_require_warm_features", False):
        overlay_allowed = (
            overlay_allowed
            & combined["rv20"].notna()
            & combined["momentum_20d"].notna()
        )
    overlay_long_momentum_min = signal_cfg.get("overlay_long_momentum_min")
    if overlay_long_momentum_min is not None:
        overlay_allowed = overlay_allowed & ~(
            (combined["overlay_signed_contracts"] > 0)
            & (combined["momentum_20d"] < float(overlay_long_momentum_min))
        )
    overlay_short_storage_z_max = signal_cfg.get("overlay_short_storage_z_max")
    if overlay_short_storage_z_max is not None:
        overlay_allowed = overlay_allowed & ~(
            (combined["overlay_signed_contracts"] < 0)
            & (combined["storage_z"] >= float(overlay_short_storage_z_max))
        )
    overlay_short_momentum_max = signal_cfg.get("overlay_short_momentum_max")
    if overlay_short_momentum_max is not None:
        overlay_allowed = overlay_allowed & ~(
            (combined["overlay_signed_contracts"] < 0)
            & (combined["momentum_20d"] > float(overlay_short_momentum_max))
        )
    overlay_contracts = (
        combined["overlay_signed_contracts"] * float(signal_cfg.get("overlay_scale", 1.0))
    ).round()
    if signal_cfg.get("overlay_mode", "flat_only") == "flat_only":
        overlay_contracts = overlay_contracts.where(combined["signed_contracts"] == 0, 0)
    elif signal_cfg.get("overlay_mode") != "additive":
        raise ValueError(f"unknown overlay_mode: {signal_cfg.get('overlay_mode')}")
    overlay_contracts = overlay_contracts.where(overlay_allowed, 0)

    max_abs_contracts = int(signal_cfg.get("max_abs_contracts", cfg["sizing"]["max_contracts"]))
    combined["event_signed_contracts"] = combined["signed_contracts"]
    combined["overlay_applied_contracts"] = overlay_contracts.astype(int)
    combined["auxiliary_applied_contracts"] = 0
    for auxiliary_rule in signal_cfg.get("auxiliary_overlays", []):
        rule_allowed = pd.Series(True, index=combined.index)
        seasons = auxiliary_rule.get("seasons")
        if seasons is not None:
            rule_allowed = rule_allowed & combined["season"].isin(seasons)
        curve_regimes = auxiliary_rule.get("curve_regimes")
        if curve_regimes is not None:
            rule_allowed = rule_allowed & combined["curve_regime"].isin(curve_regimes)
        months = auxiliary_rule.get("months")
        if months is not None:
            rule_allowed = rule_allowed & combined["date"].dt.month.isin(months)
        momentum_20d_min = auxiliary_rule.get("momentum_20d_min")
        if momentum_20d_min is not None:
            rule_allowed = rule_allowed & (
                combined["momentum_20d"] >= float(momentum_20d_min)
            )
        momentum_20d_max = auxiliary_rule.get("momentum_20d_max")
        if momentum_20d_max is not None:
            rule_allowed = rule_allowed & (
                combined["momentum_20d"] <= float(momentum_20d_max)
            )
        storage_z_min = auxiliary_rule.get("storage_z_min")
        if storage_z_min is not None:
            rule_allowed = rule_allowed & (
                combined["storage_z"] >= float(storage_z_min)
            )
        storage_z_max = auxiliary_rule.get("storage_z_max")
        if storage_z_max is not None:
            rule_allowed = rule_allowed & (
                combined["storage_z"] <= float(storage_z_max)
            )
        if auxiliary_rule.get("require_warm_features", False):
            rule_allowed = (
                rule_allowed
                & combined["rv20"].notna()
                & combined["momentum_20d"].notna()
            )
        rule_contracts = int(auxiliary_rule["contracts"])
        rule_applied_contracts = pd.Series(0, index=combined.index)
        rule_applied_contracts = rule_applied_contracts.where(
            ~rule_allowed, rule_contracts
        )
        if auxiliary_rule.get("mode", "additive") == "flat_only":
            rule_applied_contracts = rule_applied_contracts.where(
                combined["signed_contracts"] == 0, 0
            )
        elif auxiliary_rule.get("mode", "additive") != "additive":
            raise ValueError(
                f"unknown auxiliary overlay mode: {auxiliary_rule.get('mode')}"
            )
        combined["auxiliary_applied_contracts"] = (
            combined["auxiliary_applied_contracts"] + rule_applied_contracts
        )
    combined["signed_contracts"] = (
        combined["event_signed_contracts"] + combined["overlay_applied_contracts"]
    ).clip(lower=-max_abs_contracts, upper=max_abs_contracts)
    combined["signed_contracts"] = (
        combined["signed_contracts"] + combined["auxiliary_applied_contracts"]
    ).clip(lower=-max_abs_contracts, upper=max_abs_contracts)
    portfolio_position_scale = signal_cfg.get("portfolio_position_scale")
    if portfolio_position_scale is not None:
        combined["signed_contracts"] = (
            combined["signed_contracts"] * float(portfolio_position_scale)
        ).round().clip(lower=-max_abs_contracts, upper=max_abs_contracts)
    combined["contracts"] = combined["signed_contracts"].abs()

    costs = CostConfig(
        commission_per_contract=cfg["costs"]["commission_per_contract"],
        slippage_ticks=cfg["costs"]["slippage_ticks"],
        tick_value=cfg["instrument"]["tick_value"],
        turnover_multiplier=cfg["instrument"].get("cost_turnover_multiplier", 1.0),
    )
    backtest = run_daily_backtest(
        combined,
        multiplier=cfg["instrument"]["multiplier"],
        initial_equity=cfg["sizing"]["initial_equity"],
        costs=costs,
        price_col=cfg["instrument"].get("backtest_price_col", "ng1_settle"),
    )
    return backtest, summarize_performance(backtest)


def persist_feature_table(strategy_config_path: str | Path) -> Path:
    cfg = load_yaml(strategy_config_path)
    data_cfg = load_yaml(cfg["data_config"])
    db_path = resolve_path(data_cfg["database_path"])
    features = build_features_from_config(strategy_config_path)
    store = DuckDBStore(db_path)
    store.write_frame("features", features)
    return db_path
