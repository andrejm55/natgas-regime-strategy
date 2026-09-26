from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class SignalConfig:
    z_tight: float
    z_loose: float
    long_exit_storage_z: float
    short_exit_storage_z: float
    max_holding_days: int


@dataclass(frozen=True)
class ScoredSignalConfig:
    entry_score: float
    exit_score: float
    max_holding_days: int
    slope_scale: float
    storage_weight: float
    slope_weight: float
    weather_weight: float
    weather_7d_weight: float
    season_weight: float
    trend_weight: float
    momentum_window: int
    momentum_scale: float
    short_momentum_ceiling: float
    long_allowed_seasons: list[str]
    short_allowed_seasons: list[str]
    max_component_abs: float


@dataclass(frozen=True)
class WeatherOutrightConfig:
    entry_score: float
    exit_score: float
    max_holding_days: int
    weather_weight: float
    weather_7d_weight: float
    trend_weight: float
    storage_weight: float
    storage_change_weight: float
    storage_percentile_weight: float
    storage_change_scale: float
    slope_weight: float
    season_weight: float
    momentum_window: int
    confirmation_momentum_window: int
    momentum_scale: float
    min_abs_price_vs_sma: float
    allow_longs: bool
    allow_shorts: bool
    long_momentum_floor: float
    short_momentum_ceiling: float
    loose_storage_avoid_long_z: float
    contango_avoid_long_slope: float
    max_component_abs: float


@dataclass(frozen=True)
class SpreadSignalConfig:
    entry_score: float
    long_entry_score: float
    short_entry_score: float
    allow_longs: bool
    allow_shorts: bool
    exit_score: float
    max_holding_days: int
    storage_weight: float
    storage_change_weight: float
    storage_percentile_weight: float
    storage_change_scale: float
    slope_weight: float
    weather_weight: float
    weather_7d_weight: float
    season_weight: float
    slope_scale: float
    momentum_window: int
    long_spread_momentum_floor: float
    short_spread_momentum_ceiling: float
    short_min_contango_slope: float
    short_min_storage_z: float
    max_component_abs: float


@dataclass(frozen=True)
class EventOutrightConfig:
    allow_longs: bool
    allow_shorts: bool
    max_holding_days: int
    exit_score: float
    event_entry_score: float
    long_event_entry_score: float
    short_event_entry_score: float
    reversion_entry_score: float
    long_reversion_entry_score: float
    short_reversion_entry_score: float
    weather_anomaly_threshold: float
    weather_change_threshold: float
    storage_surprise_threshold: float
    curve_confirm_threshold: float
    curve_lookback_days: int
    weather_weight: float
    weather_change_weight: float
    storage_surprise_weight: float
    curve_weight: float
    storage_entry_mode: str
    event_direction: str
    reversion_weather_threshold: float
    reversion_change_threshold: float
    profit_protection_trigger: float
    profit_giveback: float
    allow_storage_only_events: bool
    allow_combined_storage_longs: bool
    allow_combined_storage_shorts: bool
    weak_long_min_contracts: int
    weak_long_max_contracts: int
    strong_long_min_contracts: int
    strong_long_max_contracts: int
    weak_short_min_contracts: int
    weak_short_max_contracts: int
    strong_short_min_contracts: int
    strong_short_max_contracts: int
    max_component_abs: float
    allow_curve_only_events: bool = False
    allow_contango_weather_events: bool = True
    summer_max_entry_rv20: float | None = None


def generate_positions(features: pd.DataFrame, cfg: SignalConfig) -> pd.DataFrame:
    """Generate daily target direction: 1 long, -1 short, 0 flat."""
    out = features.sort_values("date").copy()
    positions: list[int] = []
    current = 0
    holding_days = 0

    for _, row in out.iterrows():
        riskoff = bool(row.get("riskoff", False))
        storage_z = row.get("storage_z")
        slope = row.get("slope")
        season = row.get("season")

        if pd.isna(storage_z) or pd.isna(slope) or riskoff:
            current = 0
            holding_days = 0
        elif current == 1:
            holding_days += 1
            if (
                storage_z > cfg.long_exit_storage_z
                or slope > 0
                or holding_days >= cfg.max_holding_days
            ):
                current = 0
                holding_days = 0
        elif current == -1:
            holding_days += 1
            if (
                storage_z < cfg.short_exit_storage_z
                or slope < 0
                or holding_days >= cfg.max_holding_days
            ):
                current = 0
                holding_days = 0
        else:
            if season in {"winter", "summer"} and storage_z < -cfg.z_tight and slope < 0:
                current = 1
                holding_days = 1
            elif season == "shoulder" and storage_z > cfg.z_loose and slope > 0:
                current = -1
                holding_days = 1

        positions.append(current)

    out["target_direction"] = positions
    # EOD signal executed next session.
    out["position_direction"] = out["target_direction"].shift(1).fillna(0).astype(int)
    return out


def _clip_component(value: float, max_abs: float) -> float:
    return max(-max_abs, min(max_abs, value))


def _storage_components(row: pd.Series, max_abs: float, change_scale: float) -> tuple[float, float, float]:
    storage_z = 0.0 if pd.isna(row.get("storage_z")) else float(row["storage_z"])
    change_vs_normal = (
        0.0
        if pd.isna(row.get("storage_change_vs_normal"))
        else float(row["storage_change_vs_normal"])
    )
    percentile = (
        0.5
        if pd.isna(row.get("storage_percentile_by_week"))
        else float(row["storage_percentile_by_week"])
    )
    level_component = _clip_component(-storage_z, max_abs)
    change_component = _clip_component(-change_vs_normal / change_scale, max_abs)
    percentile_component = _clip_component(1.0 - 2.0 * percentile, max_abs)
    return level_component, change_component, percentile_component


def add_regime_score(features: pd.DataFrame, cfg: ScoredSignalConfig) -> pd.DataFrame:
    """Add transparent score components for regime_score_v1."""
    out = features.sort_values("date").copy()
    storage_component: list[float] = []
    slope_component: list[float] = []
    weather_component: list[float] = []
    weather_7d_component: list[float] = []
    season_component: list[float] = []
    trend_component: list[float] = []

    for _, row in out.iterrows():
        storage_z = 0.0 if pd.isna(row.get("storage_z")) else float(row["storage_z"])
        slope = 0.0 if pd.isna(row.get("slope")) else float(row["slope"])
        hdd_z = 0.0 if pd.isna(row.get("hdd_z")) else float(row["hdd_z"])
        cdd_z = 0.0 if pd.isna(row.get("cdd_z")) else float(row["cdd_z"])
        hdd_7d_z = 0.0 if pd.isna(row.get("hdd_7d_z")) else float(row["hdd_7d_z"])
        cdd_7d_z = 0.0 if pd.isna(row.get("cdd_7d_z")) else float(row["cdd_7d_z"])
        momentum_col = f"momentum_{cfg.momentum_window}d"
        momentum = 0.0 if pd.isna(row.get(momentum_col)) else float(row[momentum_col])
        season = row.get("season")

        storage_component.append(_clip_component(-storage_z, cfg.max_component_abs))
        slope_component.append(_clip_component(-slope / cfg.slope_scale, cfg.max_component_abs))
        trend_component.append(_clip_component(momentum / cfg.momentum_scale, cfg.max_component_abs))

        if season == "winter":
            weather_component.append(_clip_component(hdd_z, cfg.max_component_abs))
            weather_7d_component.append(_clip_component(hdd_7d_z, cfg.max_component_abs))
            season_component.append(1.0)
        elif season == "summer":
            weather_component.append(_clip_component(cdd_z, cfg.max_component_abs))
            weather_7d_component.append(_clip_component(cdd_7d_z, cfg.max_component_abs))
            season_component.append(0.5)
        else:
            weather_component.append(0.0)
            weather_7d_component.append(0.0)
            season_component.append(-0.5)

    out["score_storage"] = storage_component
    out["score_slope"] = slope_component
    out["score_weather"] = weather_component
    out["score_weather_7d"] = weather_7d_component
    out["score_season"] = season_component
    out["score_trend"] = trend_component
    out["regime_score"] = (
        cfg.storage_weight * out["score_storage"]
        + cfg.slope_weight * out["score_slope"]
        + cfg.weather_weight * out["score_weather"]
        + cfg.weather_7d_weight * out["score_weather_7d"]
        + cfg.season_weight * out["score_season"]
        + cfg.trend_weight * out["score_trend"]
    )
    return out


def generate_scored_positions(features: pd.DataFrame, cfg: ScoredSignalConfig) -> pd.DataFrame:
    """Generate target direction from regime_score_v1."""
    out = add_regime_score(features, cfg)
    positions: list[int] = []
    current = 0
    holding_days = 0

    for _, row in out.iterrows():
        riskoff = bool(row.get("riskoff", False))
        score = float(row["regime_score"])
        season = row.get("season")
        momentum_col = f"momentum_{cfg.momentum_window}d"
        momentum = 0.0 if pd.isna(row.get(momentum_col)) else float(row[momentum_col])

        if riskoff:
            current = 0
            holding_days = 0
        elif current == 1:
            holding_days += 1
            if (
                score < cfg.exit_score
                or holding_days >= cfg.max_holding_days
                or season not in cfg.long_allowed_seasons
            ):
                current = 0
                holding_days = 0
        elif current == -1:
            holding_days += 1
            if (
                score > -cfg.exit_score
                or holding_days >= cfg.max_holding_days
                or momentum > cfg.short_momentum_ceiling
                or season not in cfg.short_allowed_seasons
            ):
                current = 0
                holding_days = 0
        elif score >= cfg.entry_score and season in cfg.long_allowed_seasons:
            current = 1
            holding_days = 1
        elif (
            score <= -cfg.entry_score
            and momentum <= cfg.short_momentum_ceiling
            and season in cfg.short_allowed_seasons
        ):
            current = -1
            holding_days = 1

        positions.append(current)

    out["target_direction"] = positions
    out["position_direction"] = out["target_direction"].shift(1).fillna(0).astype(int)
    return out


def _season_weather(row: pd.Series) -> tuple[float, float]:
    season = row.get("season")
    if season == "winter":
        return (
            0.0 if pd.isna(row.get("hdd_z")) else float(row["hdd_z"]),
            0.0 if pd.isna(row.get("hdd_7d_z")) else float(row["hdd_7d_z"]),
        )
    if season == "summer":
        return (
            0.0 if pd.isna(row.get("cdd_z")) else float(row["cdd_z"]),
            0.0 if pd.isna(row.get("cdd_7d_z")) else float(row["cdd_7d_z"]),
        )
    return (0.0, 0.0)


def add_weather_outright_score(features: pd.DataFrame, cfg: WeatherOutrightConfig) -> pd.DataFrame:
    """NOAA-first outright score with storage/curve as secondary filters."""
    out = features.sort_values("date").copy()
    weather_components: list[float] = []
    weather_7d_components: list[float] = []
    trend_components: list[float] = []
    storage_components: list[float] = []
    storage_change_components: list[float] = []
    storage_percentile_components: list[float] = []
    slope_components: list[float] = []
    season_components: list[float] = []

    for _, row in out.iterrows():
        weather, weather_7d = _season_weather(row)
        momentum_col = f"momentum_{cfg.momentum_window}d"
        momentum = 0.0 if pd.isna(row.get(momentum_col)) else float(row[momentum_col])
        slope = 0.0 if pd.isna(row.get("slope")) else float(row["slope"])
        season = row.get("season")

        weather_components.append(_clip_component(weather, cfg.max_component_abs))
        weather_7d_components.append(_clip_component(weather_7d, cfg.max_component_abs))
        trend_components.append(_clip_component(momentum / cfg.momentum_scale, cfg.max_component_abs))
        storage_level, storage_change, storage_percentile = _storage_components(
            row, cfg.max_component_abs, cfg.storage_change_scale
        )
        storage_components.append(storage_level)
        storage_change_components.append(storage_change)
        storage_percentile_components.append(storage_percentile)
        slope_components.append(_clip_component(-slope / cfg.contango_avoid_long_slope, cfg.max_component_abs))
        season_components.append(1.0 if season in {"winter", "summer"} else -0.5)

    out["outright_score_weather"] = weather_components
    out["outright_score_weather_7d"] = weather_7d_components
    out["outright_score_trend"] = trend_components
    out["outright_score_storage"] = storage_components
    out["outright_score_storage_change"] = storage_change_components
    out["outright_score_storage_percentile"] = storage_percentile_components
    out["outright_score_slope"] = slope_components
    out["outright_score_season"] = season_components
    out["outright_score"] = (
        cfg.weather_weight * out["outright_score_weather"]
        + cfg.weather_7d_weight * out["outright_score_weather_7d"]
        + cfg.trend_weight * out["outright_score_trend"]
        + cfg.storage_weight * out["outright_score_storage"]
        + cfg.storage_change_weight * out["outright_score_storage_change"]
        + cfg.storage_percentile_weight * out["outright_score_storage_percentile"]
        + cfg.slope_weight * out["outright_score_slope"]
        + cfg.season_weight * out["outright_score_season"]
    )
    return out


def generate_weather_outright_positions(
    features: pd.DataFrame, cfg: WeatherOutrightConfig
) -> pd.DataFrame:
    out = add_weather_outright_score(features, cfg)
    positions: list[int] = []
    current = 0
    holding_days = 0

    for _, row in out.iterrows():
        riskoff = bool(row.get("riskoff", False))
        season = row.get("season")
        score = float(row["outright_score"])
        momentum_col = f"momentum_{cfg.momentum_window}d"
        momentum = 0.0 if pd.isna(row.get(momentum_col)) else float(row[momentum_col])
        confirmation_momentum_col = f"momentum_{cfg.confirmation_momentum_window}d"
        confirmation_momentum = (
            0.0
            if pd.isna(row.get(confirmation_momentum_col))
            else float(row[confirmation_momentum_col])
        )
        price_vs_sma_col = f"price_vs_sma_{cfg.momentum_window}d"
        confirmation_price_vs_sma_col = f"price_vs_sma_{cfg.confirmation_momentum_window}d"
        price_vs_sma = 0.0 if pd.isna(row.get(price_vs_sma_col)) else float(row[price_vs_sma_col])
        confirmation_price_vs_sma = (
            0.0
            if pd.isna(row.get(confirmation_price_vs_sma_col))
            else float(row[confirmation_price_vs_sma_col])
        )
        storage_z = 0.0 if pd.isna(row.get("storage_z")) else float(row["storage_z"])
        slope = 0.0 if pd.isna(row.get("slope")) else float(row["slope"])
        long_blocked = (
            storage_z >= cfg.loose_storage_avoid_long_z
            or slope >= cfg.contango_avoid_long_slope
            or season not in {"winter", "summer"}
        )
        long_trend_confirmed = (
            momentum >= cfg.long_momentum_floor
            and confirmation_momentum > 0
            and price_vs_sma >= cfg.min_abs_price_vs_sma
            and confirmation_price_vs_sma > 0
        )
        short_trend_confirmed = (
            momentum <= cfg.short_momentum_ceiling
            and confirmation_momentum < 0
            and price_vs_sma <= -cfg.min_abs_price_vs_sma
            and confirmation_price_vs_sma < 0
        )
        choppy = (
            abs(price_vs_sma) < cfg.min_abs_price_vs_sma
            or abs(confirmation_price_vs_sma) < cfg.min_abs_price_vs_sma
        )

        if riskoff:
            current = 0
            holding_days = 0
        elif current == 1:
            holding_days += 1
            if (
                score < cfg.exit_score
                or not long_trend_confirmed
                or long_blocked
                or holding_days >= cfg.max_holding_days
            ):
                current = 0
                holding_days = 0
        elif current == -1:
            holding_days += 1
            if (
                score > -cfg.exit_score
                or not short_trend_confirmed
                or holding_days >= cfg.max_holding_days
            ):
                current = 0
                holding_days = 0
        elif (
            cfg.allow_longs
            and score >= cfg.entry_score
            and long_trend_confirmed
            and not long_blocked
            and not choppy
        ):
            current = 1
            holding_days = 1
        elif (
            cfg.allow_shorts
            and score <= -cfg.entry_score
            and short_trend_confirmed
            and not choppy
        ):
            current = -1
            holding_days = 1

        positions.append(current)

    out["target_direction"] = positions
    out["position_direction"] = out["target_direction"].shift(1).fillna(0).astype(int)
    return out


def add_spread_score(features: pd.DataFrame, cfg: SpreadSignalConfig) -> pd.DataFrame:
    """Score for NG1-NG2 spread: positive means long NG1/short NG2."""
    out = features.sort_values("date").copy()
    storage_components: list[float] = []
    storage_change_components: list[float] = []
    storage_percentile_components: list[float] = []
    slope_components: list[float] = []
    weather_components: list[float] = []
    weather_7d_components: list[float] = []
    season_components: list[float] = []

    for _, row in out.iterrows():
        slope = 0.0 if pd.isna(row.get("slope")) else float(row["slope"])
        weather, weather_7d = _season_weather(row)
        season = row.get("season")

        storage_level, storage_change, storage_percentile = _storage_components(
            row, cfg.max_component_abs, cfg.storage_change_scale
        )
        storage_components.append(storage_level)
        storage_change_components.append(storage_change)
        storage_percentile_components.append(storage_percentile)
        slope_components.append(_clip_component(-slope / cfg.slope_scale, cfg.max_component_abs))
        weather_components.append(_clip_component(weather, cfg.max_component_abs))
        weather_7d_components.append(_clip_component(weather_7d, cfg.max_component_abs))
        season_components.append(1.0 if season in {"winter", "summer"} else -0.5)

    out["spread_score_storage"] = storage_components
    out["spread_score_storage_change"] = storage_change_components
    out["spread_score_storage_percentile"] = storage_percentile_components
    out["spread_score_slope"] = slope_components
    out["spread_score_weather"] = weather_components
    out["spread_score_weather_7d"] = weather_7d_components
    out["spread_score_season"] = season_components
    out["spread_score"] = (
        cfg.storage_weight * out["spread_score_storage"]
        + cfg.storage_change_weight * out["spread_score_storage_change"]
        + cfg.storage_percentile_weight * out["spread_score_storage_percentile"]
        + cfg.slope_weight * out["spread_score_slope"]
        + cfg.weather_weight * out["spread_score_weather"]
        + cfg.weather_7d_weight * out["spread_score_weather_7d"]
        + cfg.season_weight * out["spread_score_season"]
    )
    return out


def generate_spread_positions(features: pd.DataFrame, cfg: SpreadSignalConfig) -> pd.DataFrame:
    out = add_spread_score(features, cfg)
    positions: list[int] = []
    current = 0
    holding_days = 0

    for _, row in out.iterrows():
        riskoff = bool(row.get("riskoff", False))
        score = float(row["spread_score"])
        storage_z = 0.0 if pd.isna(row.get("storage_z")) else float(row["storage_z"])
        slope = 0.0 if pd.isna(row.get("slope")) else float(row["slope"])
        momentum_col = f"spread_momentum_{cfg.momentum_window}d"
        spread_momentum = 0.0 if pd.isna(row.get(momentum_col)) else float(row[momentum_col])
        short_confirmed = (
            slope >= cfg.short_min_contango_slope
            and storage_z >= cfg.short_min_storage_z
            and spread_momentum <= cfg.short_spread_momentum_ceiling
        )

        if riskoff:
            current = 0
            holding_days = 0
        elif current == 1:
            holding_days += 1
            if (
                score < cfg.exit_score
                or spread_momentum < cfg.long_spread_momentum_floor
                or holding_days >= cfg.max_holding_days
            ):
                current = 0
                holding_days = 0
        elif current == -1:
            holding_days += 1
            if (
                score > -cfg.exit_score
                or spread_momentum > cfg.short_spread_momentum_ceiling
                or holding_days >= cfg.max_holding_days
            ):
                current = 0
                holding_days = 0
        elif (
            cfg.allow_longs
            and score >= cfg.long_entry_score
            and spread_momentum >= cfg.long_spread_momentum_floor
        ):
            current = 1
            holding_days = 1
        elif cfg.allow_shorts and score <= -cfg.short_entry_score and short_confirmed:
            current = -1
            holding_days = 1

        positions.append(current)

    out["target_direction"] = positions
    out["position_direction"] = out["target_direction"].shift(1).fillna(0).astype(int)
    return out


def _seasonal_event_weather(row: pd.Series) -> tuple[float, float, bool]:
    season = row.get("season")
    if season == "winter":
        return (
            0.0 if pd.isna(row.get("hdd_z")) else float(row["hdd_z"]),
            0.0 if pd.isna(row.get("hdd_7d_z")) else float(row["hdd_7d_z"]),
            True,
        )
    if season == "summer":
        return (
            0.0 if pd.isna(row.get("cdd_z")) else float(row["cdd_z"]),
            0.0 if pd.isna(row.get("cdd_7d_z")) else float(row["cdd_7d_z"]),
            True,
        )
    return (0.0, 0.0, False)


def add_event_outright_score(features: pd.DataFrame, cfg: EventOutrightConfig) -> pd.DataFrame:
    """Add short-horizon event scores without long moving-average trend filters."""
    out = features.sort_values("date").copy()
    shock_weather: list[float] = []
    shock_weather_change: list[float] = []
    shock_storage: list[float] = []
    shock_curve: list[float] = []
    primary_shocks: list[bool] = []
    weather_shocks: list[bool] = []
    storage_shocks: list[bool] = []
    event_scores: list[float] = []
    entry_scores: list[float] = []
    event_trade_scores: list[float] = []
    entry_trade_scores: list[float] = []
    reversion_scores: list[float] = []
    trade_scores: list[float] = []
    if cfg.event_direction == "follow":
        event_direction_multiplier = 1.0
    elif cfg.event_direction == "fade":
        event_direction_multiplier = -1.0
    else:
        raise ValueError(f"unknown event_direction: {cfg.event_direction}")
    if cfg.storage_entry_mode not in {"score", "confirm_boost"}:
        raise ValueError(f"unknown storage_entry_mode: {cfg.storage_entry_mode}")

    curve_col = f"spread_change_{cfg.curve_lookback_days}d"
    for _, row in out.iterrows():
        weather, weather_change, is_demand_season = _seasonal_event_weather(row)
        storage_surprise = (
            0.0
            if pd.isna(row.get("storage_change_vs_normal"))
            else -float(row["storage_change_vs_normal"])
        )
        curve_change = 0.0 if pd.isna(row.get(curve_col)) else float(row[curve_col])

        weather_component = 0.0
        weather_change_component = 0.0
        if is_demand_season and (
            abs(weather) >= cfg.weather_anomaly_threshold
            or abs(weather_change) >= cfg.weather_change_threshold
        ):
            weather_component = _clip_component(weather, cfg.max_component_abs)
            weather_change_component = _clip_component(weather_change, cfg.max_component_abs)

        storage_component = 0.0
        if abs(storage_surprise) >= cfg.storage_surprise_threshold:
            storage_component = _clip_component(
                storage_surprise / cfg.storage_surprise_threshold, cfg.max_component_abs
            )

        curve_component = 0.0
        if abs(curve_change) >= cfg.curve_confirm_threshold:
            curve_component = _clip_component(
                curve_change / cfg.curve_confirm_threshold, cfg.max_component_abs
            )

        event_score = (
            cfg.weather_weight * weather_component
            + cfg.weather_change_weight * weather_change_component
            + cfg.storage_surprise_weight * storage_component
            + cfg.curve_weight * curve_component
        )
        entry_score = (
            event_score
            if cfg.storage_entry_mode == "score"
            else event_score - cfg.storage_surprise_weight * storage_component
        )
        has_primary_shock = any(
            abs(value) > 0
            for value in (weather_component, weather_change_component, storage_component)
        ) or (cfg.allow_curve_only_events and abs(curve_component) > 0)
        has_weather_shock = abs(weather_component) > 0 or abs(weather_change_component) > 0
        has_storage_shock = abs(storage_component) > 0

        reversion_score = 0.0
        if is_demand_season:
            if weather >= cfg.reversion_weather_threshold and weather_change <= -cfg.reversion_change_threshold:
                reversion_score = -min(cfg.max_component_abs, weather)
            elif weather <= -cfg.reversion_weather_threshold and weather_change >= cfg.reversion_change_threshold:
                reversion_score = min(cfg.max_component_abs, abs(weather))

        shock_weather.append(weather_component)
        shock_weather_change.append(weather_change_component)
        shock_storage.append(storage_component)
        shock_curve.append(curve_component)
        primary_shocks.append(has_primary_shock)
        weather_shocks.append(has_weather_shock)
        storage_shocks.append(has_storage_shock)
        event_scores.append(event_score)
        entry_scores.append(entry_score)
        event_trade_score = event_direction_multiplier * event_score
        entry_trade_score = event_direction_multiplier * entry_score
        event_trade_scores.append(event_trade_score)
        entry_trade_scores.append(entry_trade_score)
        reversion_scores.append(reversion_score)
        trade_scores.append(entry_trade_score + reversion_score)

    out["event_score_weather"] = shock_weather
    out["event_score_weather_change"] = shock_weather_change
    out["event_score_storage_surprise"] = shock_storage
    out["event_score_curve"] = shock_curve
    out["event_has_primary_shock"] = primary_shocks
    out["event_has_weather_shock"] = weather_shocks
    out["event_has_storage_shock"] = storage_shocks
    out["event_score"] = event_scores
    out["event_entry_score_value"] = entry_scores
    out["event_trade_score"] = event_trade_scores
    out["event_entry_trade_score"] = entry_trade_scores
    out["event_reversion_score"] = reversion_scores
    out["event_total_score"] = out["event_score"] + out["event_reversion_score"]
    out["event_position_score"] = trade_scores
    return out


def generate_event_outright_positions(
    features: pd.DataFrame, cfg: EventOutrightConfig
) -> pd.DataFrame:
    out = add_event_outright_score(features, cfg)
    positions: list[int] = []
    contract_floors: list[int] = []
    contract_caps: list[int] = []
    current = 0
    current_contract_floor = 0
    current_contract_cap = 0
    holding_days = 0
    entry_price = 0.0
    best_favorable_move = 0.0
    event_direction_multiplier = 1.0 if cfg.event_direction == "follow" else -1.0

    for _, row in out.iterrows():
        riskoff = bool(row.get("riskoff", False))
        season = str(row.get("season", ""))
        rv20 = row.get("rv20")
        summer_vol_block = (
            cfg.summer_max_entry_rv20 is not None
            and season == "summer"
            and pd.notna(rv20)
            and float(rv20) > cfg.summer_max_entry_rv20
        )
        price = 0.0 if pd.isna(row.get("ng1_settle")) else float(row["ng1_settle"])
        score = float(row["event_position_score"])
        entry_event_score = float(row["event_entry_score_value"])
        entry_trade_score = float(row["event_entry_trade_score"])
        reversion_score = float(row["event_reversion_score"])
        weather_score = float(row["event_score_weather"]) + float(row["event_score_weather_change"])
        storage_score = float(row["event_score_storage_surprise"])
        curve_score = float(row["event_score_curve"])
        has_primary_shock = bool(row["event_has_primary_shock"])
        has_weather_shock = bool(row["event_has_weather_shock"])
        has_storage_shock = bool(row["event_has_storage_shock"])
        storage_only = has_storage_shock and not has_weather_shock
        combined_storage = has_storage_shock and has_weather_shock
        contango_weather_event = (
            str(row.get("curve_regime", "")) == "contango" and has_weather_shock
        )
        trade_weather_score = event_direction_multiplier * weather_score
        trade_storage_score = event_direction_multiplier * storage_score
        trade_curve_score = event_direction_multiplier * curve_score
        strong_long_setup = (
            trade_weather_score > 0
            and trade_storage_score > 0
            and trade_curve_score > 0
        )
        strong_short_setup = (
            trade_weather_score < 0
            and trade_storage_score < 0
            and trade_curve_score < 0
        )
        has_raw_curve_confirmation = (
            curve_score >= 1.0
            if entry_event_score > 0
            else curve_score <= -1.0
            if entry_event_score < 0
            else False
        )
        long_event = (
            has_primary_shock
            and (cfg.allow_storage_only_events or not storage_only)
            and (cfg.allow_contango_weather_events or not contango_weather_event)
            and (cfg.allow_combined_storage_longs or not combined_storage)
            and score > 0
            and abs(entry_event_score) >= cfg.long_event_entry_score
            and entry_trade_score >= cfg.long_event_entry_score
            and has_raw_curve_confirmation
        )
        short_event = (
            has_primary_shock
            and (cfg.allow_storage_only_events or not storage_only)
            and (cfg.allow_contango_weather_events or not contango_weather_event)
            and (cfg.allow_combined_storage_shorts or not combined_storage)
            and score < 0
            and abs(entry_event_score) >= cfg.short_event_entry_score
            and entry_trade_score <= -cfg.short_event_entry_score
            and has_raw_curve_confirmation
        )
        long_reversion = reversion_score >= cfg.long_reversion_entry_score
        short_reversion = reversion_score <= -cfg.short_reversion_entry_score
        is_reversion = long_reversion or short_reversion
        signal_decayed = not has_primary_shock and not is_reversion
        favorable_move = 0.0
        if current == 1:
            favorable_move = price - entry_price
        elif current == -1:
            favorable_move = entry_price - price
        best_favorable_move = max(best_favorable_move, favorable_move)
        profit_protected = (
            cfg.profit_protection_trigger > 0
            and cfg.profit_giveback > 0
            and best_favorable_move >= cfg.profit_protection_trigger
            and favorable_move <= best_favorable_move - cfg.profit_giveback
        )

        if riskoff:
            current = 0
            current_contract_floor = 0
            current_contract_cap = 0
            holding_days = 0
            best_favorable_move = 0.0
        elif current == 1:
            holding_days += 1
            if (
                score < cfg.exit_score
                or signal_decayed
                or profit_protected
                or (cfg.max_holding_days > 0 and holding_days >= cfg.max_holding_days)
            ):
                current = 0
                current_contract_floor = 0
                current_contract_cap = 0
                holding_days = 0
                best_favorable_move = 0.0
        elif current == -1:
            holding_days += 1
            if (
                score > -cfg.exit_score
                or signal_decayed
                or profit_protected
                or (cfg.max_holding_days > 0 and holding_days >= cfg.max_holding_days)
            ):
                current = 0
                current_contract_floor = 0
                current_contract_cap = 0
                holding_days = 0
                best_favorable_move = 0.0
        elif (long_event or long_reversion) and cfg.allow_longs and not summer_vol_block:
            current = 1
            current_contract_floor = (
                cfg.strong_long_min_contracts
                if strong_long_setup
                else cfg.weak_long_min_contracts
            )
            current_contract_cap = (
                cfg.strong_long_max_contracts
                if strong_long_setup
                else cfg.weak_long_max_contracts
            )
            holding_days = 1
            entry_price = price
            best_favorable_move = 0.0
        elif (short_event or short_reversion) and cfg.allow_shorts and not summer_vol_block:
            current = -1
            current_contract_floor = (
                cfg.strong_short_min_contracts
                if strong_short_setup
                else cfg.weak_short_min_contracts
            )
            current_contract_cap = (
                cfg.strong_short_max_contracts
                if strong_short_setup
                else cfg.weak_short_max_contracts
            )
            holding_days = 1
            entry_price = price
            best_favorable_move = 0.0

        positions.append(current)
        contract_floors.append(current_contract_floor)
        contract_caps.append(current_contract_cap)

    out["target_direction"] = positions
    out["target_contract_floor"] = contract_floors
    out["target_contract_cap"] = contract_caps
    out["position_direction"] = out["target_direction"].shift(1).fillna(0).astype(int)
    out["position_contract_floor"] = out["target_contract_floor"].shift(1).fillna(0).astype(int)
    out["position_contract_cap"] = out["target_contract_cap"].shift(1).fillna(0).astype(int)
    return out
