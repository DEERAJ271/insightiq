.PHONY: help setup etl dbt-run airflow-up n8n-up test lint all

VENV := venv/bin

## help: show this help message
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'

## setup: create venv, install Python deps, and install pre-commit git hooks
setup:
	python3 -m venv venv
	$(VENV)/pip install -r requirements.txt
	$(VENV)/pre-commit install

## etl: run the full ETL pipeline (extract -> transform -> load into Postgres)
etl:
	$(VENV)/python etl/run_pipeline.py

## dbt-run: build and test the insightiq_dbt project's models
dbt-run:
	cd insightiq_dbt && ../$(VENV)/dbt run && ../$(VENV)/dbt test

## airflow-up: start the project's own Postgres warehouse, then the Airflow Docker Compose stack
airflow-up:
	docker start insightiq-pg
	cd airflow && docker compose up -d

## n8n-up: start n8n with the Code node's child_process builtin allowed (needed by the JS-escaping workaround documented in n8n/README.md)
n8n-up:
	export NODE_FUNCTION_ALLOW_BUILTIN=child_process && n8n start

## test: run the Python test suite and the dbt test suite
test:
	$(VENV)/python -m pytest tests/ -v
	cd insightiq_dbt && ../$(VENV)/dbt test

## lint: run sqlfluff over the dbt models and ruff over the Python codebase
lint:
	cd insightiq_dbt && ../$(VENV)/sqlfluff lint models/ --dialect postgres
	$(VENV)/ruff check .

## all: full local bootstrap — setup, run the ETL pipeline, then build and test dbt models
all: setup etl dbt-run
