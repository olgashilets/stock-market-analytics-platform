# Stock Market Analytics Platform

[Русская версия](README.ru.md)

## Overview

This project is a PostgreSQL + Streamlit analytics platform for Belarusian equity market data. It demonstrates database design, ETL processing, SQL analytics, data quality checks and dashboard development.

The project is designed as a portfolio case for BI Analyst, Data Analyst and FinTech Data Analyst roles.

## Business problem

An analyst needs a reliable way to load, clean and analyze stock-market archive files. The system should preserve raw records, build normalized tables and provide analytical views for screening, instrument comparison and anomaly detection.

## What this project demonstrates

- relational database design;
- raw and normalized data layers;
- transaction-based ETL from Excel archives;
- SQL views and materialized views;
- data quality checks;
- Streamlit dashboard pages;
- market screening, instrument cards, comparison and anomaly detection.

## Architecture

```text
Excel source data → demo archive generator → ETL → PostgreSQL raw layer
                                             → PostgreSQL normalized layer
                                             → SQL views / materialized view
                                             → Streamlit dashboard
```

See [`docs/architecture.md`](docs/architecture.md) and [`docs/data_model.md`](docs/data_model.md).

## Repository structure

```text
stock-market-analytics-platform/
├── app/                         # Streamlit app and SQL query layer
├── data/
│   ├── source/                  # source file
│   └── generated_archives/      # generated demo archive files
├── db/
│   ├── schema.sql               # PostgreSQL tables, constraints, indexes
│   ├── analytics_objects.sql    # views and materialized view
│   └── testing_checks.sql       # data quality and performance checks
├── etl/
│   ├── generate_demo_archives.py
│   └── load_archives_to_postgres.py
├── docs/
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
└── README.ru.md
```

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start PostgreSQL

With Docker:

```bash
docker compose up -d
```

Or use your local PostgreSQL instance and set environment variables using `.env.example` as a template.

### 3. Create database objects

```bash
psql -h localhost -U postgres -d investment_sbd -f db/schema.sql
psql -h localhost -U postgres -d investment_sbd -f db/analytics_objects.sql
```

### 4. Generate demo archives

```bash
python etl/generate_demo_archives.py \
  --input data/source/data.xlsx \
  --output data/generated_archives
```

### 5. Load archives into PostgreSQL

```bash
python etl/load_archives_to_postgres.py \
  --input-dir data/generated_archives \
  --replace-existing \
  --refresh-materialized-view
```

### 6. Run quality checks

```bash
psql -h localhost -U postgres -d investment_sbd -f db/testing_checks.sql
```

### 7. Start Streamlit

```bash
streamlit run app/Home.py
```

## Main user scenarios

1. **Market overview** — filter instruments by return, risk, liquidity and drawdown.
2. **Instrument card** — inspect KPI, price history, trading activity and recent anomalies.
3. **Instrument comparison** — compare normalized price dynamics and metrics.
4. **Market anomalies** — review price jumps, turnover spikes and deals spikes.

## Data note

The generated archives are demo files built from monthly source data. They are used to validate ETL, database design and dashboard scenarios. They are not investment recommendations.
