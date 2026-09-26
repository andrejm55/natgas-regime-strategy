# Reproducibility Guide

This guide specifies the data ranges, fields, contracts, and commands needed to rebuild the current research dataset. Licensed futures bars are not included in the repository. Each user must obtain those bars through their own data vendor account.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Populate the relevant `.env` values:

```text
EIA_API_KEY
NOAA_CDO_TOKEN
DATABENTO_API_KEY
IBKR_HOST
IBKR_PORT
IBKR_CLIENT_ID
```

## Futures Price Reconstruction

### Instrument

```text
Exchange: NYMEX
Root symbol: NG
Currency: USD
Multiplier: 10,000
Tick size: 0.001
Tick value: $10
Backtest price: NG1 settle
```

### Historical Databento Section

Configured request:

```text
Dataset: GLBX.MDP3
Schema: ohlcv-1d
Input symbol type: raw_symbol
Root symbol: NG
Contract months: 2014-12 through 2025-09
Raw symbol year digits: 1
Per-contract request window: delivery month minus 6 months through delivery month plus 1 month
Global config start_date: 2014-01-01
Global config end_date: 2025-09-24
```

Run:

```bash
python scripts/download_databento_ng.py --estimate-only
python scripts/download_databento_ng.py
```

Normalized fields:

```text
date
contract_month
contract
open
high
low
settle
volume
```

Current local Databento output:

```text
Path: data/01_raw_databento/ng_databento_ohlcv_1d.csv
Rows: 19,358
Date range: 2014-06-01 to 2025-05-28
Contract months present: 201412 through 202506
```

The config requests through 2025-09, but a vendor response can only contribute rows where bars exist for the requested schema/symbol/date combination. Check the local row count and contract-month coverage after each rebuild.

### Later IBKR Section

Configured request:

```text
Exchange: NYMEX
Symbol: NG
Currency: USD
Bar size: 1 day
What to show: TRADES
Use RTH: false
Default duration: 2 Y
```

Recent local pull:

```text
Contract months: 202510 through 202712
Output files: data/01_raw_ibkr/NG_YYYYMM_daily.csv
```

Run:

```bash
python scripts/check_ibkr_connection.py
python scripts/download_ibkr_ng.py --start-month 202510 --end-month 202712
```

Normalized fields:

```text
date
contract_month
contract
con_id
open
high
low
settle
volume
average
bar_count
```

Current local consolidated contract-bar file:

```text
Path: data/01_raw_ibkr/ng_contract_daily_bars.csv
Rows: 30,404
Date range: 2014-06-01 to 2026-08-19
Contract months present: 201412 through 202712
```

Despite the directory name, the consolidated file can contain both Databento-sourced historical bars and IBKR-sourced later bars. It is still treated as licensed vendor price data and should not be redistributed.

## Contract Metadata And Roll Calendar

For historical contract metadata generated without broker details:

```text
Expiration date: three business days before the first calendar day of delivery month
Roll date: two business days before expiration date
```

Metadata fields:

```text
contract_month
contract
local_symbol
con_id
symbol
exchange
currency
trading_class
multiplier
min_tick
expiration_date
last_trade_time
time_zone_id
roll_date
```

Current local metadata:

```text
Path: data/05_contract_metadata/ng_contract_expirations.csv
Rows: 157
Contract months: 201412 through 202712
```

## Continuous Futures

Continuous output fields:

```text
date
ng1_settle
ng2_settle
ng1_contract_month
ng2_contract_month
ng1_contract
ng2_contract
ng1_expiration_date
ng1_front_start_date
ng1_roll_date
```

Roll rule:

```text
Use the next front contract starting two business days before the expiring front contract's expiration date.
```

Run:

```bash
python scripts/build_continuous.py --config config/natgas_event_regime_overlay_v6.yaml
```

Current local continuous output:

```text
Path: data/03_interim/ng_continuous_daily.csv
Rows: 3,485
Date range: 2014-11-24 to 2026-08-19
```

## Storage Data

EIA source:

```text
Route: https://api.eia.gov/v2/natural-gas/stor/wkly/data/
Frequency: weekly
Series: NW2_EPG0_SWO_R48_BCF
Description: Weekly Lower 48 States Natural Gas Working Underground Storage
```

Output fields:

```text
week_ending_date
release_date
storage_bcf
series_id
```

Release timing:

```text
EIA period is the week-ending Friday.
Configured release lag is 6 calendar days.
The resulting release date is the following Thursday under the normal schedule.
```

Run:

```bash
python scripts/download_eia_storage.py
```

Current local storage output:

```text
Path: data/02_raw_fundamentals/eia_weekly_storage.csv
Rows: 867
Week-ending range: 2010-01-01 to 2026-08-07
Release-date range: 2010-01-07 to 2026-08-13
```

## Weather Data

NOAA CDO source:

```text
Dataset: GHCND
Datatypes: TMAX, TMIN
Start date: 2015-01-01
End date: latest available date at download time
Observation lag: 1 calendar day
Base temperature: 65F
```

Station basket:

| Region | Station ID | Station | Weight |
| --- | --- | --- | ---: |
| South Central | `GHCND:USW00012960` | Houston Intercontinental Airport | 0.40 |
| East | `GHCND:USW00094823` | Pittsburgh International Airport | 0.25 |
| Midwest | `GHCND:USW00094846` | Chicago O'Hare International Airport | 0.25 |
| Mountain | `GHCND:USW00003017` | Denver International Airport | 0.05 |
| Pacific | `GHCND:USW00023174` | Los Angeles International Airport | 0.05 |

Derived fields:

```text
temperature_mean_f = (TMAX + TMIN) / 2
hdd = max(65 - temperature_mean_f, 0)
cdd = max(temperature_mean_f - 65, 0)
```

Weighted basket fields:

```text
date
temperature_mean_f
hdd
cdd
region_count
total_weight
available_date
```

Run:

```bash
python scripts/download_noaa_weather.py
```

Current local weather output:

```text
Path: data/02_raw_weather/noaa_cdo_daily.csv
Rows: 4,244
Observation-date range: 2015-01-01 to 2026-08-14
Available-date range: 2015-01-02 to 2026-08-15
```

## Strategy Configs To Reproduce Recent Backtests

Primary configs:

```text
config/natgas_event_regime_overlay_v6.yaml
config/natgas_event_regime_overlay_v6_2x.yaml
config/natgas_event_regime_overlay_v6_3x.yaml
```

Common cost assumptions:

```text
Commission: $2.50 per contract
Slippage: 1 tick per turnover contract
Tick value: $10
```

Run:

```bash
python scripts/run_backtest.py --config config/natgas_event_regime_overlay_v6.yaml --save
python scripts/run_backtest.py --config config/natgas_event_regime_overlay_v6_2x.yaml --save
python scripts/run_backtest.py --config config/natgas_event_regime_overlay_v6_3x.yaml --save
```

Saved outputs are local research artifacts and are ignored by git.
