DB_NAME ?= investment_sbd
DB_USER ?= postgres
DB_HOST ?= localhost

init-db:
	psql -h $(DB_HOST) -U $(DB_USER) -d $(DB_NAME) -f db/schema.sql
	psql -h $(DB_HOST) -U $(DB_USER) -d $(DB_NAME) -f db/analytics_objects.sql

generate-data:
	python etl/generate_demo_archives.py --input data/source/data.xlsx --output data/generated_archives

load-data:
	python etl/load_archives_to_postgres.py --input-dir data/generated_archives --replace-existing --refresh-materialized-view

check-sql:
	psql -h $(DB_HOST) -U $(DB_USER) -d $(DB_NAME) -f db/testing_checks.sql

run-app:
	streamlit run app/Home.py
