# Data And Output Layout

The project separates source code, local data, and generated research outputs. Most data and output folders are ignored by git because they can contain licensed futures bars or derived price series.

## Directory Map

```text
data/
  01_raw_ibkr/              Licensed IBKR futures bars. Not redistributed.
  01_raw_databento/         Licensed Databento futures bars. Not redistributed.
  02_raw_fundamentals/      Public EIA storage downloads.
  02_raw_weather/           Public NOAA/Open-Meteo weather downloads.
  03_interim/               Derived continuous futures datasets. Not redistributed if built from licensed bars.
  04_processed/             Local DuckDB database. Not redistributed if it contains licensed bars.
  05_contract_metadata/     Contract metadata and roll calendars.

outputs/
  01_backtests/             Local backtest result tables.
  02_reports/               Local research notes and summaries.
  03_charts/                Exported figures.
  04_logs/                  Connection and run logs.
```

Only `.gitkeep` placeholders should be committed from `data/` and `outputs/`.

## Current Local Inputs

These are the expected local files after rebuilding the dataset:

```text
data/01_raw_databento/ng_databento_ohlcv_1d.csv
data/01_raw_ibkr/ng_contract_daily_bars.csv
data/05_contract_metadata/ng_contract_expirations.csv
data/03_interim/ng_continuous_daily.csv
data/02_raw_fundamentals/eia_weekly_storage.csv
data/02_raw_weather/noaa_cdo_daily.csv
```

Current observed local ranges:

| File | Range |
| --- | --- |
| Databento daily contract bars | 2014-06-01 to 2025-05-28 |
| Consolidated contract bars | 2014-06-01 to 2026-08-19 |
| Continuous NG1/NG2 | 2014-11-24 to 2026-08-19 |
| EIA storage | week ending 2010-01-01 to 2026-08-07 |
| NOAA weather basket | 2015-01-01 to 2026-08-14 |
| Contract months in metadata | 201412 to 202712 |

The app and tests fall back to sample data when configured CSV inputs are missing.

## Git Hygiene

Committed:

- Source code.
- Strategy configs.
- Documentation.
- Empty directory placeholders.

Ignored:

- `.env`
- `.venv/`
- Python caches and package build metadata.
- Raw licensed futures bars.
- Continuous price series derived from licensed bars.
- DuckDB databases.
- Generated backtests, reports, charts, and logs.
- Experimental config scratch space under `config/_candidates/`.
