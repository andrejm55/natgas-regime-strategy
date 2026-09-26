from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main() -> None:
    try:
        from ib_async import IB
    except ImportError as exc:
        raise RuntimeError("ib_async is not installed. Run: pip install -e '.[dev]'") from exc

    load_dotenv()

    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", "4002"))
    client_id = int(os.getenv("IBKR_CLIENT_ID", "23"))

    ib = IB()
    print(f"Connecting to IBKR Gateway/TWS at {host}:{port} with clientId={client_id}...")
    await ib.connectAsync(host, port, clientId=client_id, timeout=15)
    try:
        print("Connected: yes")
        print(f"Server version: {ib.client.serverVersion()}")
        accounts = ib.managedAccounts()
        print(f"Managed accounts: {', '.join(accounts) if accounts else '(none returned)'}")
        current_time = await ib.reqCurrentTimeAsync()
        print(f"IBKR current time: {current_time}")
    finally:
        ib.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())

