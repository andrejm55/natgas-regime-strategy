from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.calendar import build_roll_calendar


MONTH_CODES = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}

MONTH_BY_CODE = {v: k for k, v in MONTH_CODES.items()}


@dataclass(frozen=True)
class ContractRequest:
    month: pd.Period
    raw_symbol: str
    canonical_symbol: str
    contract_month: str
    start_date: str
    end_date: str


def month_range(start_month: str, end_month: str) -> list[pd.Period]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    return list(pd.period_range(start, end, freq="M"))


def databento_symbol(root: str, month: pd.Period, year_digits: int) -> str:
    code = MONTH_CODES[month.month]
    year = month.year % (10 if year_digits == 1 else 100)
    return f"{root}{code}{year:0{year_digits}d}"


def build_contract_requests(
    root: str,
    start_month: str,
    end_month: str,
    year_digits: int,
    months_before_contract: int,
    months_after_contract: int,
) -> list[ContractRequest]:
    requests = []
    for month in month_range(start_month, end_month):
        start = (month - months_before_contract).to_timestamp(how="start").date().isoformat()
        end = (month + months_after_contract).to_timestamp(how="end").date().isoformat()
        requests.append(
            ContractRequest(
                month=month,
                raw_symbol=databento_symbol(root, month, year_digits),
                canonical_symbol=databento_symbol(root, month, 2),
                contract_month=f"{month.year}{month.month:02d}",
                start_date=start,
                end_date=end,
            )
        )
    return requests


def normalize_bars(frame: pd.DataFrame, request: ContractRequest) -> pd.DataFrame:
    if frame.empty:
        return frame

    out = frame.copy()
    if "ts_event" in out.columns:
        timestamps = out["ts_event"]
    elif "ts_recv" in out.columns:
        timestamps = out["ts_recv"]
    elif out.index.name in {"ts_event", "ts_recv"}:
        timestamps = out.index
    else:
        raise ValueError(f"Databento bars missing timestamp column/index: {out.columns.tolist()}")
    out["date"] = pd.to_datetime(timestamps, utc=True).tz_convert(None).normalize()
    out["contract"] = request.canonical_symbol
    out["contract_month"] = request.contract_month
    out = out.rename(columns={"close": "settle"})
    keep_cols = ["date", "contract_month", "contract", "open", "high", "low", "settle", "volume"]
    return out[keep_cols].sort_values(["contract_month", "date"]).reset_index(drop=True)


def ng_expiration_date(delivery_month: pd.Period) -> pd.Timestamp:
    """NG expires 3 business days before the first calendar day of delivery month."""
    first_delivery_day = delivery_month.to_timestamp(how="start")
    return first_delivery_day - pd.offsets.BDay(3)


def build_expiration_rows(requests: list[ContractRequest]) -> pd.DataFrame:
    rows = []
    for req in requests:
        rows.append(
            {
                "contract_month": req.contract_month,
                "contract": req.canonical_symbol,
                "local_symbol": req.canonical_symbol,
                "con_id": pd.NA,
                "symbol": "NG",
                "exchange": "NYMEX",
                "currency": "USD",
                "trading_class": "NG",
                "multiplier": 10000,
                "min_tick": 0.001,
                "expiration_date": ng_expiration_date(req.month).date().isoformat(),
                "last_trade_time": "",
                "time_zone_id": "US/Eastern",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-config", default="config/data.yaml")
    parser.add_argument("--start-month", default=None, help="YYYY-MM, overrides config")
    parser.add_argument("--end-month", default=None, help="YYYY-MM, overrides config")
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD, overrides config")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD, overrides config")
    parser.add_argument("--year-digits", type=int, choices=[1, 2], default=None)
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument("--include-definitions", action="store_true")
    parser.add_argument("--no-merge-existing", action="store_true")
    parser.add_argument("--no-update-consolidated", action="store_true")
    args = parser.parse_args()

    try:
        import databento as db
    except ImportError as exc:
        raise RuntimeError("databento is not installed. Run: pip install -e .") from exc

    load_dotenv(".env")
    data_cfg = load_yaml(args.data_config)
    db_cfg = data_cfg["databento"]
    api_key = os.getenv(db_cfg.get("api_key_env", "DATABENTO_API_KEY"))
    if not api_key:
        raise RuntimeError("Set DATABENTO_API_KEY in .env before running this script.")

    start_month = args.start_month or db_cfg["start_month"]
    end_month = args.end_month or db_cfg["end_month"]
    year_digits = args.year_digits or int(db_cfg.get("symbol_year_digits", 1))
    requests = build_contract_requests(
        root=db_cfg.get("root_symbol", "NG"),
        start_month=start_month,
        end_month=end_month,
        year_digits=year_digits,
        months_before_contract=int(db_cfg.get("months_before_contract", 6)),
        months_after_contract=int(db_cfg.get("months_after_contract", 1)),
    )
    if args.start_date or args.end_date:
        requests = [
            ContractRequest(
                month=req.month,
                raw_symbol=req.raw_symbol,
                canonical_symbol=req.canonical_symbol,
                contract_month=req.contract_month,
                start_date=args.start_date or req.start_date,
                end_date=args.end_date or req.end_date,
            )
            for req in requests
        ]

    client = db.Historical(api_key)
    dataset = db_cfg.get("dataset", "GLBX.MDP3")

    if args.estimate_only:
        total_cost = 0.0
        for req in requests:
            total_cost += float(
                client.metadata.get_cost(
                    dataset=dataset,
                    symbols=[req.raw_symbol],
                    schema="ohlcv-1d",
                    stype_in="raw_symbol",
                    start=req.start_date,
                    end=req.end_date,
                )
            )
        print(f"Estimated Databento cost for {len(requests)} contract requests: {total_cost:.6f}")
        print(",".join(req.canonical_symbol for req in requests))
        return

    bar_frames: list[pd.DataFrame] = []
    definition_frames: list[pd.DataFrame] = []
    for i, req in enumerate(requests, start=1):
        print(f"[{i}/{len(requests)}] {req.canonical_symbol} via {req.raw_symbol}")
        bars_store = client.timeseries.get_range(
            dataset=dataset,
            symbols=[req.raw_symbol],
            schema="ohlcv-1d",
            stype_in="raw_symbol",
            start=req.start_date,
            end=req.end_date,
        )
        bars_frame = normalize_bars(bars_store.to_df(price_type="float", map_symbols=True), req)
        if not bars_frame.empty:
            bar_frames.append(bars_frame)

        if args.include_definitions:
            definitions_store = client.timeseries.get_range(
                dataset=dataset,
                symbols=[req.raw_symbol],
                schema="definition",
                stype_in="raw_symbol",
                start=req.start_date,
                end=req.end_date,
            )
            definitions_frame = definitions_store.to_df(price_type="float", map_symbols=True)
            if not definitions_frame.empty:
                definitions_frame["requested_contract"] = req.canonical_symbol
                definitions_frame["requested_contract_month"] = req.contract_month
                definition_frames.append(definitions_frame)

    if not bar_frames:
        raise RuntimeError("Databento returned no OHLCV bars for the requested contracts.")
    bars = pd.concat(bar_frames, ignore_index=True)
    bars = bars.drop_duplicates(subset=["contract_month", "date"], keep="last")
    bars = bars.sort_values(["contract_month", "date"]).reset_index(drop=True)
    bars_path = resolve_path(db_cfg["bars_file"])
    bars_path.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(bars_path, index=False)
    print(
        f"Wrote {len(bars)} Databento daily bars to {bars_path}. "
        f"Date range {bars['date'].min().date()} to {bars['date'].max().date()}."
    )

    if not args.no_update_consolidated:
        consolidated_path = resolve_path(data_cfg["ibkr"]["consolidated_bars_file"])
        consolidated_frames = [bars]
        if consolidated_path.exists() and not args.no_merge_existing:
            existing_bars = pd.read_csv(consolidated_path, parse_dates=["date"])
            existing_bars["contract_month"] = existing_bars["contract_month"].astype(str)
            consolidated_frames.insert(0, existing_bars)
        consolidated = pd.concat(consolidated_frames, ignore_index=True)
        consolidated["date"] = pd.to_datetime(consolidated["date"]).dt.normalize()
        consolidated["contract_month"] = consolidated["contract_month"].astype(str)
        consolidated = consolidated.drop_duplicates(
            subset=["contract_month", "date"], keep="last"
        ).sort_values(["contract_month", "date"])
        consolidated_path.parent.mkdir(parents=True, exist_ok=True)
        consolidated.to_csv(consolidated_path, index=False)
        print(f"Wrote/merged {len(consolidated)} rows to {consolidated_path}.")

    metadata = build_expiration_rows(requests)
    metadata = build_roll_calendar(metadata, business_days_before_expiration=2)
    metadata_path = resolve_path(data_cfg["csv"]["contract_expirations"])
    if metadata_path.exists() and not args.no_merge_existing:
        existing = pd.read_csv(metadata_path)
        existing["contract_month"] = existing["contract_month"].astype(str)
        metadata["contract_month"] = metadata["contract_month"].astype(str)
        metadata = pd.concat([existing, metadata], ignore_index=True)
        metadata = metadata.drop_duplicates(subset=["contract_month"], keep="last")
    metadata = metadata.sort_values("contract_month")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata.to_csv(metadata_path, index=False)
    print(f"Wrote/merged {len(metadata)} expiration rows to {metadata_path}.")

    if args.include_definitions:
        definitions = (
            pd.concat(definition_frames, ignore_index=True)
            if definition_frames
            else pd.DataFrame()
        )
        definitions_path = resolve_path(db_cfg["definitions_file"])
        definitions_path.parent.mkdir(parents=True, exist_ok=True)
        definitions.to_csv(definitions_path, index=False)
        print(f"Wrote {len(definitions)} Databento definitions to {definitions_path}.")


if __name__ == "__main__":
    main()
