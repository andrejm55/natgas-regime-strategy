from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.data.continuous import build_continuous_ng12
from natgas_regime.data.store import DuckDBStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/natgas_outright.yaml")
    args = parser.parse_args()

    strategy_cfg = load_yaml(args.config)
    data_cfg = load_yaml(strategy_cfg["data_config"])
    bars_path = resolve_path(data_cfg["ibkr"]["consolidated_bars_file"])
    metadata_path = resolve_path(data_cfg["csv"]["contract_expirations"])
    output_path = resolve_path(data_cfg["ibkr"]["continuous_file"])

    bars = pd.read_csv(bars_path, parse_dates=["date"])
    expirations = pd.read_csv(metadata_path, parse_dates=["expiration_date", "roll_date"])
    continuous = build_continuous_ng12(
        bars=bars,
        expirations=expirations,
        business_days_before_expiration=strategy_cfg["roll"]["business_days_before_expiration"],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    continuous.to_csv(output_path, index=False)
    db_path = resolve_path(data_cfg["database_path"])
    store = DuckDBStore(db_path)
    store.write_frame("continuous_daily", continuous)
    print(
        f"Wrote {len(continuous)} rows to {output_path}. "
        f"Date range {continuous['date'].min().date()} to {continuous['date'].max().date()}."
    )
    print(f"Wrote DuckDB table continuous_daily to {db_path}")


if __name__ == "__main__":
    main()
