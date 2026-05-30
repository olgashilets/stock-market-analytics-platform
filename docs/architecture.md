# Architecture

The platform separates ingestion, storage, SQL analytics and UI rendering.

```text
+--------------------+
| data/source        |
| monthly data.xlsx  |
+---------+----------+
          |
          v
+-------------------------------+
| etl/generate_demo_archives.py |
| demo Excel trading archives   |
+---------------+---------------+
                |
                v
+--------------------------------+
| etl/load_archives_to_postgres  |
| transaction-based ETL          |
+-------+------------------------+
        |
        v
+-------------------------+       +-------------------------------+
| raw_market_archive      | ----> | normalized PostgreSQL tables  |
| import_files            |       | issuers, instruments, calendar|
+-------------------------+       | market_daily_stats            |
                                  +---------------+---------------+
                                                  |
                                                  v
                                  +-------------------------------+
                                  | SQL analytical layer           |
                                  | views + materialized view      |
                                  +---------------+---------------+
                                                  |
                                                  v
                                  +-------------------------------+
                                  | Streamlit dashboard            |
                                  | market overview, card, compare |
                                  +-------------------------------+
```

## Design choices

- Raw records are preserved for traceability.
- The normalized layer separates issuers, instruments, trading calendar and daily market statistics.
- Financial metrics are calculated in SQL views/materialized views, not duplicated in the Streamlit UI.
- ETL uses transactions: if loading a file fails, the database rolls back that file load.
- Database credentials are read from environment variables, not hard-coded.
