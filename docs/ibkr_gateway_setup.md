# IBKR Gateway Setup

IBKR's TWS/Gateway API is not normally configured with an API key. The API is a local TCP socket connection to a running IB Gateway or Workstation session.

## What You Need To Enter

Put these in `.env`:

```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=23
EIA_API_KEY=
NOAA_CDO_TOKEN=
DATABENTO_API_KEY=
```

Use:

- `IBKR_PORT=4002` for IB Gateway paper trading.
- `IBKR_PORT=4001` for IB Gateway live trading.
- `IBKR_PORT=7497` for TWS paper trading.
- `IBKR_PORT=7496` for TWS live trading.

`IBKR_CLIENT_ID` is not a secret. It just needs to be unique among applications connected to the same Gateway session.

## Gateway Settings

In IB Gateway or TWS:

1. Log in to paper or live.
2. Open API settings.
3. Enable socket clients if the setting is visible.
4. Keep localhost-only connections enabled if the strategy is running on the same machine.
5. Confirm the socket port matches `.env`.
6. Keep read-only enabled for connection tests and data downloads. Disable read-only only when intentionally testing orders.

## Connection Test

After Gateway is running and `.env` is filled in:

```bash
source .venv/bin/activate
python scripts/check_ibkr_connection.py
```

This only connects and prints basic account/session metadata. It does not place orders.

## Confirmed Connection

The local connection check is expected to use:

```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=23
```

Above is a paper Gateway style connection (unless you change the port).
