# Data Sources

This project combines licensed futures prices with public fundamental and weather data. The code and public-data specifications can be shared. Licensed vendor price files should be rebuilt by each user under their own data agreement.

## Shareability

| Dataset | Local path | Publicly shareable? | Notes |
| --- | --- | --- | --- |
| Databento NG daily OHLCV | `data/01_raw_databento/` | No | Licensed historical futures bars. |
| IBKR NG daily OHLCV | `data/01_raw_ibkr/` | No | Licensed/account-provided historical futures bars. |
| Continuous NG1/NG2 | `data/03_interim/ng_continuous_daily.csv` | No | Derived from licensed futures bars. |
| DuckDB database | `data/04_processed/natgas.duckdb` | No | May contain derived licensed price data. |
| Contract metadata | `data/05_contract_metadata/` | Yes, if rebuilt from public rules or own account | Contains contract months, symbols, expiration dates, and roll dates. |
| EIA storage | `data/02_raw_fundamentals/eia_weekly_storage.csv` | Yes | Public EIA data. |
| NOAA CDO weather | `data/02_raw_weather/noaa_cdo_*.csv` | Yes | Public NOAA station observations. |
| Open-Meteo weather | `data/02_raw_weather/open_meteo_*.csv` | Yes | Public API data subject to provider terms. |

## Futures Prices

### Databento

Configured source:

```yaml
dataset: GLBX.MDP3
schema: ohlcv-1d
stype_in: raw_symbol
root_symbol: NG
start_month: "2014-12"
end_month: "2025-09"
start_date: "2014-01-01"
end_date: "2025-09-24"
symbol_year_digits: 1
months_before_contract: 6
months_after_contract: 1
```

The downloader requests each contract month from six months before the delivery month through one month after the delivery month. The raw-symbol form uses one year digit because that is how the current Databento request path was configured. The normalized output uses two-digit canonical symbols, for example `NGZ14`.

Normalized output fields:

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

Local output:

```text
data/01_raw_databento/ng_databento_ohlcv_1d.csv
```

Run:

```bash
python scripts/download_databento_ng.py --estimate-only
python scripts/download_databento_ng.py
```

### IBKR

IBKR is used through the local Gateway/TWS socket API. No project API key is stored. The user logs into Gateway/TWS and supplies socket settings through environment variables.

Configured futures request:

```yaml
exchange: NYMEX
symbol: NG
currency: USD
bar_size: 1 day
what_to_show: TRADES
use_rth: false
duration: 2 Y
```

The recent local IBKR pulls covered:

```text
Contract months: 202510 through 202712
Files: data/01_raw_ibkr/NG_YYYYMM_daily.csv
```

Normalized output fields:

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

Local consolidated output:

```text
data/01_raw_ibkr/ng_contract_daily_bars.csv
```

Run:

```bash
python scripts/check_ibkr_connection.py
python scripts/download_ibkr_ng.py --start-month 202510 --end-month 202712
```

## Contract Metadata And Roll Rules

Henry Hub NG futures use a `10,000` MMBtu multiplier and `0.001` tick size. The public reconstruction rule used for Databento-sourced historical contracts is:

```text
expiration_date = three business days before the first calendar day of the delivery month
roll_date = two business days before expiration_date
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

Local output:

```text
data/05_contract_metadata/ng_contract_expirations.csv
```

## Continuous Futures

The continuous builder selects NG1 and NG2 from individual contract bars and the roll calendar.

Roll rule:

```text
Roll the front contract two business days before expiration.
```

Output fields:

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

Current local continuous date range:

```text
2014-11-24 through 2026-08-19
```

Run:

```bash
python scripts/build_continuous.py --config config/natgas_event_regime_overlay_v6.yaml
```

## EIA Storage

Source:

```text
https://api.eia.gov/v2/natural-gas/stor/wkly/data/
```

Configured series:

```text
NW2_EPG0_SWO_R48_BCF
Weekly Lower 48 States Natural Gas Working Underground Storage
```

Output fields:

```text
week_ending_date
release_date
storage_bcf
series_id
```

The EIA API `period` is the week-ending Friday. The project applies a six-calendar-day release lag, mapping Friday week-ending dates to the normal following-Thursday release date.

Current local storage history starts:

```text
2010-01-01 week ending
```

Run:

```bash
python scripts/download_eia_storage.py
```

## NOAA CDO Weather

Source dataset:

```text
GHCND
```

Requested datatypes:

```text
TMAX
TMIN
```

Derived fields:

```text
temperature_mean_f = (TMAX + TMIN) / 2
hdd = max(65F - temperature_mean_f, 0)
cdd = max(temperature_mean_f - 65F, 0)
available_date = date + 1 calendar day
```

Configured station basket:

| Region | Station | Weight |
| --- | --- | ---: |
| South Central | `GHCND:USW00012960`, Houston Intercontinental Airport | 0.40 |
| East | `GHCND:USW00094823`, Pittsburgh International Airport | 0.25 |
| Midwest | `GHCND:USW00094846`, Chicago O'Hare International Airport | 0.25 |
| Mountain | `GHCND:USW00003017`, Denver International Airport | 0.05 |
| Pacific | `GHCND:USW00023174`, Los Angeles International Airport | 0.05 |

Configured date range:

```text
start_date: 2015-01-01
end_date: current date unless overridden
```

Weighted basket output fields:

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

## Open-Meteo Weather

Open-Meteo is optional and not used by the current default configs. It remains useful for quick weather reconstruction when a NOAA token is not available.

Run:

```bash
python scripts/download_open_meteo_weather.py
```
