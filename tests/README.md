# Tests

The main test asset for this SQL-focused project is `db/testing_checks.sql`. After loading data, run:

```bash
psql -h localhost -U postgres -d investment_sbd -f db/testing_checks.sql
```

For Python files, you can additionally run syntax checks:

```bash
python -m py_compile app/db_config.py app/db.py app/Home.py etl/generate_demo_archives.py etl/load_archives_to_postgres.py
```
