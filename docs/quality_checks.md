# Data quality checks

The file `db/testing_checks.sql` contains checks for:

- non-empty core tables after ETL;
- missing mandatory text fields;
- negative prices, turnover and deal counts;
- duplicate tickers, issuers and daily instrument/date pairs;
- broken logical links between facts and dimensions;
- consistency between base tables and analytical views;
- query-plan inspection through `EXPLAIN ANALYZE`.

A production version could extend this with a persistent load-error log and automated test execution in CI.
