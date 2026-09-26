from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SizingConfig:
    initial_equity: float
    target_vol: float
    max_contracts: int
    max_notional_leverage: float
    min_realized_vol: float
    multiplier: float
    price_col: str = "ng1_settle"
    vol_col: str = "rv20"
    vol_kind: str = "return"
    max_long_contracts: int | None = None
    max_short_contracts: int | None = None
    position_scale: float = 1.0


def add_contract_sizing(frame: pd.DataFrame, cfg: SizingConfig) -> pd.DataFrame:
    out = frame.copy()
    vol = out[cfg.vol_col].fillna(cfg.min_realized_vol).clip(lower=cfg.min_realized_vol)
    position_scale = max(float(cfg.position_scale), 0.0)
    target_risk_dollars = cfg.initial_equity * cfg.target_vol * position_scale
    leverage_cap_notional = cfg.initial_equity * cfg.max_notional_leverage * position_scale
    max_contracts = _scale_contract_limit(cfg.max_contracts, position_scale)

    if cfg.vol_kind == "return":
        target_notional = target_risk_dollars / vol
        contract_notional = out[cfg.price_col] * cfg.multiplier
        capped_notional = np.minimum(target_notional, leverage_cap_notional)
        contracts = np.floor(capped_notional / contract_notional)
    elif cfg.vol_kind == "price":
        dollar_vol_per_contract = vol * cfg.multiplier
        risk_contracts = np.floor(target_risk_dollars / dollar_vol_per_contract)
        contract_notional = out[cfg.price_col] * cfg.multiplier
        leverage_contracts = np.floor(leverage_cap_notional / contract_notional)
        contracts = np.minimum(risk_contracts, leverage_contracts)
    else:
        raise ValueError(f"unknown sizing vol_kind: {cfg.vol_kind}")

    contracts = contracts.fillna(0).astype(int)
    contracts = contracts.clip(lower=0, upper=max_contracts)
    long_cap = _scale_contract_limit(cfg.max_long_contracts or cfg.max_contracts, position_scale)
    short_cap = _scale_contract_limit(cfg.max_short_contracts or cfg.max_contracts, position_scale)
    long_contracts = contracts.clip(lower=0, upper=long_cap)
    short_contracts = contracts.clip(lower=0, upper=short_cap)
    contracts = np.where(out["position_direction"] > 0, long_contracts, contracts)
    contracts = np.where(out["position_direction"] < 0, short_contracts, contracts)
    contracts = pd.Series(contracts, index=out.index).astype(int)
    if "position_contract_floor" in out.columns:
        row_floor = _scale_contract_series(out["position_contract_floor"].fillna(0), position_scale)
        active = out["position_direction"] != 0
        contracts = pd.Series(
            np.where(active, np.maximum(contracts, row_floor), contracts),
            index=out.index,
        ).astype(int)
    if "position_contract_cap" in out.columns:
        row_cap = _scale_contract_series(
            out["position_contract_cap"].fillna(cfg.max_contracts), position_scale
        )
        row_cap = row_cap.where(row_cap > 0, max_contracts)
        contracts = pd.Series(np.minimum(contracts, row_cap), index=out.index).astype(int)
    out["contracts"] = contracts * out["position_direction"].abs()
    out["signed_contracts"] = out["contracts"] * out["position_direction"]
    return out


def _scale_contract_limit(limit: int, scale: float) -> int:
    if scale <= 0:
        return 0
    return max(1, int(np.floor(limit * scale)))


def _scale_contract_series(values: pd.Series, scale: float) -> pd.Series:
    if scale <= 0:
        return pd.Series(0, index=values.index, dtype=int)
    scaled = np.floor(values.astype(float).clip(lower=0) * scale)
    return pd.Series(scaled, index=values.index).astype(int)
