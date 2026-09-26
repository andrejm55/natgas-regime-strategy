# Nat Gas Regime Strategy

Research framework for daily NYMEX Henry Hub natural gas futures strategies. The project builds NG1/NG2 continuous futures, aligns public storage and weather data, computes regime/event features, and runs daily backtests with contract-level sizing and costs.

## Current Research Configs

The recent research branch is centered on the event/regime overlay family:

| Config | Purpose |
| --- | --- |
| `config/natgas_event_regime_overlay_v6.yaml` | Balanced current candidate. |
| `config/natgas_event_regime_overlay_v6_2x.yaml` | Same signals as `v6`, final portfolio exposure scaled 2.0x. |
| `config/natgas_event_regime_overlay_v6_3x.yaml` | Same signals as `v6`, final portfolio exposure scaled 3.0x. |

The final exposure scale is applied after event, regime, and auxiliary overlays are combined. It changes contract size, not signal timing or signal direction.

## Data Licensing Boundary

The repository is structured so code, configs, documentation, contract metadata, weather data, storage data, and generated methodology can be public.

Do not commit or redistribute:

- IBKR historical futures bars.
- Databento historical futures bars.
- Local DuckDB databases built from licensed futures bars.
- Generated backtest output files that embed licensed futures prices.

Publicly reproducible inputs:

- EIA weekly Lower 48 working gas in storage.
- NOAA CDO observed station temperatures.
- Open-Meteo weather data, if used.
- Contract metadata reconstructed from public NG expiration rules or from each user's own vendor account.

See [docs/reproducibility.md](docs/reproducibility.md) for exact dates, contracts, fields, symbols, and rebuild steps.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Fill in only the keys needed for the data you intend to rebuild:

```bash
EIA_API_KEY=
NOAA_CDO_TOKEN=
DATABENTO_API_KEY=
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=23
```

IBKR uses a local Gateway/TWS socket session rather than a project API key.

## Rebuild Public Inputs

```bash
python scripts/download_eia_storage.py
python scripts/download_noaa_weather.py
```

Optional weather source:

```bash
python scripts/download_open_meteo_weather.py
```

## Rebuild Licensed Futures Inputs

Databento historical futures bars:

```bash
python scripts/download_databento_ng.py --estimate-only
python scripts/download_databento_ng.py
```

IBKR Gateway/TWS futures bars:

```bash
python scripts/check_ibkr_connection.py
python scripts/download_ibkr_ng.py --start-month 202510 --end-month 202712
```

Then rebuild the continuous futures dataset:

```bash
python scripts/build_continuous.py --config config/natgas_event_regime_overlay_v6.yaml
```

## Run Backtests

```bash
python scripts/run_backtest.py --config config/natgas_event_regime_overlay_v6.yaml --save
python scripts/run_backtest.py --config config/natgas_event_regime_overlay_v6_2x.yaml --save
python scripts/run_backtest.py --config config/natgas_event_regime_overlay_v6_3x.yaml --save
```

The output directory is ignored by git because saved backtests can contain derived licensed price data.

## Dashboard

```bash
python -m streamlit run natgas_regime/app/streamlit_app.py
```

## Project Layout

```text
config/                    Strategy and data configuration.
data/                      Local data; raw vendor price data is ignored.
docs/                      Rebuild instructions and data specifications.
natgas_regime/             Package code.
outputs/                   Local research outputs; ignored except placeholders.
scripts/                   Data, build, diagnostic, and backtest entry points.
tests/                     Unit and smoke tests.
```

More detail:

- [docs/data_sources.md](docs/data_sources.md)
- [docs/data_layout.md](docs/data_layout.md)
- [docs/reproducibility.md](docs/reproducibility.md)

## Tests

```bash
python -m pytest
```
