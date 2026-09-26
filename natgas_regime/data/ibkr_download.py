from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
import pandas as pd


@dataclass(frozen=True)
class IBKRConfig:
    host: str
    port: int
    client_id: int
    exchange: str
    symbol: str
    currency: str
    bar_size: str
    what_to_show: str
    use_rth: bool

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> IBKRConfig:
        return cls(
            host=os.getenv(cfg.get("host_env", "IBKR_HOST"), "127.0.0.1"),
            port=int(os.getenv(cfg.get("port_env", "IBKR_PORT"), "4002")),
            client_id=int(os.getenv(cfg.get("client_id_env", "IBKR_CLIENT_ID"), "11")),
            exchange=cfg.get("exchange", "NYMEX"),
            symbol=cfg.get("symbol", "NG"),
            currency=cfg.get("currency", "USD"),
            bar_size=cfg.get("bar_size", "1 day"),
            what_to_show=cfg.get("what_to_show", "TRADES"),
            use_rth=bool(cfg.get("use_rth", False)),
        )


async def fetch_future_history(
    cfg: IBKRConfig,
    contract_month: str,
    duration: str = "1 Y",
) -> pd.DataFrame:
    """Fetch one NG futures contract from IB Gateway/TWS via ib_async.

    contract_month should be in IBKR's YYYYMM format, for example "202601".
    """
    try:
        from ib_async import IB, Future, util
    except ImportError as exc:
        raise RuntimeError("Install ib_async to use IBKR downloads") from exc

    ib = IB()
    await ib.connectAsync(cfg.host, cfg.port, clientId=cfg.client_id)
    try:
        contract = Future(
            symbol=cfg.symbol,
            lastTradeDateOrContractMonth=contract_month,
            exchange=cfg.exchange,
            currency=cfg.currency,
        )
        qualified = await ib.qualifyContractsAsync(contract)
        if not qualified:
            raise RuntimeError(f"IBKR could not qualify contract {cfg.symbol} {contract_month}")

        bars = await ib.reqHistoricalDataAsync(
            qualified[0],
            endDateTime="",
            durationStr=duration,
            barSizeSetting=cfg.bar_size,
            whatToShow=cfg.what_to_show,
            useRTH=cfg.use_rth,
            formatDate=1,
        )
        frame = util.df(bars)
        if frame.empty:
            return frame
        frame["contract_month"] = contract_month
        frame["contract"] = f"{cfg.symbol}{contract_month}"
        return frame.rename(columns={"date": "date", "close": "settle"})
    finally:
        ib.disconnect()

