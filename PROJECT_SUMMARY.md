# InsightIQ — Interview Cheat Sheet

## 1. Elevator pitch
InsightIQ is an end-to-end analytics platform: a Python ETL pipeline loads Olist e-commerce data into a Postgres star schema, which feeds a Power BI dashboard and a RAG + NL2SQL chatbot for natural-language questions over the data. Apache Airflow (10 DAGs) and n8n orchestrate the pipeline, validation, and customer segmentation, with dbt handling in-warehouse transformation (staging model + marts) run and tested from its own Airflow DAG; everything was built and debugged with Claude Code, with the prompt log kept as evidence and GitHub Actions running CI on every push.

## 2. Architecture (one paragraph)
Raw CSVs (orders, customers, products, reviews, payments) are extracted, cleaned, and loaded by a Python/pandas/SQLAlchemy ETL pipeline into a Postgres star schema (`fact_orders` + `dim_*`). Airflow DAGs own the recurring work on top of that warehouse — the real ETL run itself, parallel data-quality checks (hand-written SQL + a Great Expectations suite), a pandas category-summary rollup, dynamic task-mapped deep dives, weekly RFM customer segmentation, an `insightiq_dbt_pipeline` DAG that runs and tests the `insightiq_dbt` project's staging model and marts, and an `insightiq_post_load_asset_consumer` DAG scheduled on a `fact_orders`-updated Asset rather than a cron/manual trigger — with one DAG chaining into another via `TriggerDagRunOperator` (explicit, point-to-point) or Asset scheduling (decoupled, consumer-declared), and LLM-generated (Ollama) failure alerts wired into every DAG that touches real data. n8n hosts an earlier, still-maintained visual-prototype version of the same ETL/validation/alerting/reporting ideas. On the consumption side, Power BI reads the warehouse directly for dashboards, and a Streamlit app routes natural-language questions through a chatbot that picks between NL2SQL (Postgres) and RAG (Chroma + LangChain) depending on the question, backed by either Claude or local Ollama depending on `LLM_BACKEND`.

## 3. Five best "bug you fixed" stories

1. **RFM frequency had zero variance.** Before writing the RFM DAG's scoring logic, queried the warehouse first and found every customer has exactly one order — `pd.qcut` on a constant frequency column would raise, not degrade, crashing the DAG on every run. Fixed by adding a documented fallback (constant middle score) in `score_quintile()` so a low-variance dimension degrades gracefully instead of blowing up.
2. **RFM segment labels collapsed to 2 buckets.** A rewritten 11-segment label scheme still only produced 4 labels; root cause wasn't the rules but that frequency (distinct order count) was still constant, so 8 of 11 rules could never fire. Redefined frequency as total items purchased instead — after testing and rejecting a rank-based quintile approach that produced "balanced" bins which were actually fabricated (4 of 5 bins were all identical values tie-broken by row order).
3. **`avg_review_score` was NULL for every row.** A quick `pd.to_numeric(errors="coerce")` patch fixed the immediate `.round()` crash but not the real bug: `etl/transform.py` hardcoded `review_score = None` for all 102,425 rows behind a stale "TODO: enrichment step" comment, even though real scores existed in the raw CSV and were already being extracted, just never joined. Fixed the join in `build_fact_orders()`, correcting the warehouse, not just the one DAG that surfaced it.
4. **A caught exception wasn't actually catching anything.** `run_query()` wrapped SQL execution in `except SQLAlchemyError`, but `pandas.read_sql()` re-wraps failures in its own `pandas.errors.DatabaseError`, which does *not* subclass `SQLAlchemyError` — a query against a nonexistent table slipped through as a raw traceback in the Streamlit UI. Fixed by catching both exception types.
5. **A routing bug found only through live testing.** `needs_sql()` used substring matching against keywords, so "what counts as a repeat customer?" false-matched "count" and got routed to NL2SQL instead of RAG. Fixed with word-boundary regex matching, verified against both the original false positive and a negative control ("accounting discrepancies").

## 4. Tech stack
Python, pandas, SQLAlchemy, PostgreSQL, dbt, Apache Airflow, n8n, Power BI/DAX, LangChain, Chroma, HuggingFace embeddings, Claude API (Anthropic), Ollama (llama3.2), Streamlit, pytest, Docker Compose, Great Expectations, GitHub Actions

## 5. Numbers that matter
- **fact_orders**: 102,425 rows · **dim_customer**: 99,441 · **dim_product**: 32,951 · **dim_seller**: 3,095 · **dim_date**: 799
- **customer_rfm_segments**: 98,666 rows · **category_summary**: 73 rows
- **Airflow DAGs**: 10
- **dbt**: 4 models (1 staging + 3 marts) · 9 data tests · 1 snapshot (SCD Type 2 on `customer_rfm_segments`) · 2 exposures · 7 sources
- **n8n workflows**: 6 committed (`n8n/workflows/*.json`), matching all 6 documented in `n8n/README.md`
- **Tests**: 14 Python passing (12 Airflow/`pytest tests/` in `airflow/`, 2 in root `tests/`) + 9 dbt data tests
- **Custom Claude Code commands/skills**: 16 (`.claude/commands/`)
- **Dev log entries**: 39 (`dev-logs/prompts.md`)

## 6. Three things to improve given more time
1. **Silent-wrong-answer detection in NL2SQL.** The pipeline gracefully handles SQL that *fails* to execute, but has no way to catch SQL that executes successfully and returns a confidently wrong or non-answer — the harder, more general NL2SQL correctness problem.
2. **Real alerting, not just log lines.** `notify_failure` produces a good LLM-generated failure summary, but it only ever reaches the task log — no Slack/email/PagerDuty integration, so a failure still requires someone to go looking for it.
3. **Root-cause the recurring stopped-Postgres-container issue** instead of restarting it every time it happened (3x in two days) — likely the Mac's sleep behavior bypassing Docker's `unless-stopped` policy, never actually investigated.
