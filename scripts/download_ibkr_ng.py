from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from natgas_regime.config import load_yaml, resolve_path
from natgas_regime.data.ibkr_download import IBKRConfig


def month_range(start_month: str, end_month: str) -> list[str]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    return [str(p).replace("-", "") for p in pd.period_range(start, end, freq="M")]


async def download_contracts(
    start_month: str,
    end_month: str,
    duration: str | None = None,
    merge_existing: bool = True,
) -> None:
    try:
        from ib_async import IB, Future, util
    except ImportError as exc:
        raise RuntimeError("ib_async is not installed. Run: pip install -e '.[dev]'") from exc

    load_dotenv(".env")
    data_cfg = load_yaml("config/data.yaml")
    strategy_cfg = load_yaml("config/natgas_outright.yaml")
    ib_cfg = IBKRConfig.from_config(data_cfg["ibkr"])
    raw_dir = resolve_path(data_cfg["ibkr"]["raw_output_dir"])
    metadata_dir = resolve_path(data_cfg["ibkr"]["metadata_output_dir"])
    metadata_path = resolve_path(data_cfg["csv"]["contract_expirations"])
    consolidated_path = resolve_path(data_cfg["ibkr"]["consolidated_bars_file"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    duration_str = duration or data_cfg["ibkr"].get("duration", "2 Y")

    months = month_range(start_month, end_month)
    ib = IB()
    await ib.connectAsync(ib_cfg.host, ib_cfg.port, clientId=ib_cfg.client_id, timeout=20)
    metadata_rows: list[dict] = []
    bar_frames: list[pd.DataFrame] = []
    failures: list[dict] = []

    try:
        for i, month in enumerate(months, start=1):
            print(f"[{i}/{len(months)}] NG {month}: contract details")
            contract = Future(
                symbol=ib_cfg.symbol,
                lastTradeDateOrContractMonth=month,
                exchange=ib_cfg.exchange,
                currency=ib_cfg.currency,
                includeExpired=True,
            )
            details = await ib.reqContractDetailsAsync(contract)
            if not details:
                failures.append({"contract_month": month, "stage": "details", "error": "no details"})
                print(f"  no contract details for {month}")
                continue

            detail = details[0]
            qualified = detail.contract
            expiration_raw = getattr(detail, "realExpirationDate", None) or (
                qualified.lastTradeDateOrContractMonth
            )
            expiration_date = pd.to_datetime(str(expiration_raw)[:8], format="%Y%m%d")
            metadata_rows.append(
                {
                    "contract_month": month,
                    "contract": qualified.localSymbol or f"{ib_cfg.symbol}{month}",
                    "local_symbol": qualified.localSymbol,
                    "con_id": qualified.conId,
                    "symbol": qualified.symbol,
                    "exchange": qualified.exchange,
                    "currency": qualified.currency,
                    "trading_class": qualified.tradingClass,
                    "multiplier": qualified.multiplier,
                    "min_tick": detail.minTick,
                    "expiration_date": expiration_date.date().isoformat(),
                    "last_trade_time": getattr(detail, "lastTradeTime", ""),
                    "time_zone_id": getattr(detail, "timeZoneId", ""),
                }
            )

            end_dt = expiration_date + pd.Timedelta(hours=23, minutes=59)
            print(f"  historical bars through {expiration_date.date()}")
            try:
                bars = await ib.reqHistoricalDataAsync(
                    qualified,
                    endDateTime=end_dt.to_pydatetime(),
                    durationStr=duration_str,
                    barSizeSetting=ib_cfg.bar_size,
                    whatToShow=ib_cfg.what_to_show,
                    useRTH=ib_cfg.use_rth,
                    formatDate=1,
                )
                frame = util.df(bars)
            except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
                failures.append({"contract_month": month, "stage": "bars", "error": str(exc)})
                print(f"  bar download failed: {exc}")
                await asyncio.sleep(float(data_cfg["ibkr"].get("request_pause_seconds", 1.0)))
                continue

            if frame.empty:
                failures.append({"contract_month": month, "stage": "bars", "error": "empty bars"})
                print("  no bars returned")
                await asyncio.sleep(float(data_cfg["ibkr"].get("request_pause_seconds", 1.0)))
                continue

            frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None).dt.normalize()
            frame = frame.rename(columns={"close": "settle", "barCount": "bar_count"})
            frame["contract_month"] = month
            frame["contract"] = qualified.localSymbol or f"{ib_cfg.symbol}{month}"
            frame["con_id"] = qualified.conId
            keep_cols = [
                "date",
                "contract_month",
                "contract",
                "con_id",
                "open",
                "high",
                "low",
                "settle",
                "volume",
                "average",
                "bar_count",
            ]
            frame = frame[[c for c in keep_cols if c in frame.columns]]
            contract_path = raw_dir / f"NG_{month}_daily.csv"
            frame.to_csv(contract_path, index=False)
            bar_frames.append(frame)
            print(f"  wrote {len(frame)} bars to {contract_path}")
            await asyncio.sleep(float(data_cfg["ibkr"].get("request_pause_seconds", 1.0)))
    finally:
        ib.disconnect()

    metadata = pd.DataFrame(metadata_rows)
    if not metadata.empty:
        from natgas_regime.calendar import build_roll_calendar

        metadata = build_roll_calendar(
            metadata,
            business_days_before_expiration=strategy_cfg["roll"]["business_days_before_expiration"],
        )
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if merge_existing and metadata_path.exists():
            existing_metadata = pd.read_csv(metadata_path)
            metadata = pd.concat([existing_metadata, metadata], ignore_index=True)
            metadata = metadata.drop_duplicates(subset=["contract_month"], keep="last")
            metadata = metadata.sort_values("contract_month")
        metadata.to_csv(metadata_path, index=False)
        print(f"Wrote metadata to {metadata_path}")

    if bar_frames:
        frames = bar_frames
        if merge_existing and consolidated_path.exists():
            frames = [pd.read_csv(consolidated_path, parse_dates=["date"]), *bar_frames]
        consolidated = pd.concat(frames, ignore_index=True)
        consolidated["date"] = pd.to_datetime(consolidated["date"]).dt.normalize()
        consolidated["contract_month"] = consolidated["contract_month"].astype(str)
        consolidated = consolidated.drop_duplicates(
            subset=["contract_month", "date"], keep="last"
        ).sort_values(["contract_month", "date"])
        consolidated_path.parent.mkdir(parents=True, exist_ok=True)
        consolidated.to_csv(consolidated_path, index=False)
        print(f"Wrote consolidated bars to {consolidated_path}")

    if failures:
        failures_path = metadata_dir / "ng_download_failures.csv"
        pd.DataFrame(failures).to_csv(failures_path, index=False)
        print(f"Wrote failures to {failures_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-month", required=True, help="YYYYMM, e.g. 202401")
    parser.add_argument("--end-month", required=True, help="YYYYMM, e.g. 202712")
    parser.add_argument("--duration", default=None, help='IBKR duration string, e.g. "1 Y"')
    parser.add_argument("--no-merge-existing", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        download_contracts(
            args.start_month,
            args.end_month,
            duration=args.duration,
            merge_existing=not args.no_merge_existing,
        )
    )


if __name__ == "__main__":
    main()
