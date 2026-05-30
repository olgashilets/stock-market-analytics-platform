# Data model

## Core tables

| Table | Role |
|---|---|
| `import_files` | registry of uploaded archive files |
| `raw_market_archive` | raw archive rows for traceability |
| `issuers` | issuer directory |
| `instruments` | instrument directory, linked to issuers |
| `trading_calendar` | trading dates and calendar attributes |
| `market_daily_stats` | normalized daily market statistics by instrument and date |

## Analytical objects

| Object | Role |
|---|---|
| `vw_instrument_daily_metrics` | daily return, active-day flag, price changes and other row-level metrics |
| `mv_instrument_summary` | materialized instrument-level summary for fast screening |
| `vw_market_anomalies` | price jumps, turnover spikes and deals spikes |

## Integrity controls

The schema includes primary keys, foreign keys, unique constraints and check constraints. The key analytical constraint is:

```sql
UNIQUE (instrument_id, trade_date)
```

This guarantees that the normalized layer contains only one daily record per instrument and date, even if the raw archive contains multiple rows for that pair.
