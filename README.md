# InsightIQ — AI-Augmented Sales Analytics Platform

[![CI](https://github.com/DEERAJ271/insightiq/actions/workflows/ci.yml/badge.svg)](https://github.com/DEERAJ271/insightiq/actions/workflows/ci.yml)

An end-to-end analytics stack: raw e-commerce data flows through a Python ETL
pipeline into a Postgres warehouse, which feeds a Power BI dashboard and a
RAG + LLM chatbot for natural-language questions over the data.

Built with Claude Code in VS Code — see `dev-logs/prompts.md` for the actual
prompts used to generate each layer, and what was hand-edited afterward.

## Architecture

```
Raw CSV --> Python ETL --> Postgres warehouse --> Power BI dashboard
                                   |
                                   v
                          RAG knowledge base ---> LLM chatbot (NL2SQL + RAG)
                                                          |
                                                          v
                                                   Streamlit UI
```

## Tech stack

| Layer          | Tools                                      |
|----------------|---------------------------------------------|
| ETL            | Python, pandas, SQLAlchemy                  |
| Warehouse      | PostgreSQL (star schema)                    |
| Transformation | dbt (staging model + marts, run/tested via Airflow) |
| Orchestration  | Apache Airflow (DAGs, retries, scheduling), n8n (visual prototyping) |
| BI             | Power BI, DAX                               |
| Retrieval      | LangChain, Chroma, HuggingFace embeddings   |
| LLM            | Claude API (Anthropic) or local Ollama (llama3.2) — switchable via `LLM_BACKEND`, default `ollama` |
| App layer      | Streamlit                                   |
| CI/CD          | GitHub Actions                              |
| Dev workflow   | Claude Code (VS Code)                       |

## Dataset

Default: [Olist Brazilian E-commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(orders, customers, products, reviews, payments). Swap in any relational
retail/sales dataset — the schema in `sql/schema.sql` is the thing to adapt.

## Setup

Requires [Ollama](https://ollama.com) running locally — `llm/chatbot.py`
and `llm/nl2sql.py` both default to `LLM_BACKEND=ollama`, calling
`http://127.0.0.1:11434`, so `streamlit run` will fail on the first
question without it (unless you switch `.env`'s `LLM_BACKEND` to
`anthropic` and supply `ANTHROPIC_API_KEY` instead).

```bash
# 0. Prerequisite: local LLM backend
# Install Ollama (https://ollama.com), then pull the model both
# llm/chatbot.py and llm/nl2sql.py call by default:
ollama pull llama3.2

# 1. Environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # fill in DATABASE_URL and ANTHROPIC_API_KEY

# 2. Database
# If your local Postgres isn't on the default port 5432 (e.g. this
# repo's own dev instance runs on 5544 — see .env.example), pass
# -p <port> to both commands below and match it in DATABASE_URL.
createdb insightiq
psql insightiq -f sql/schema.sql

# 3. Run ETL
python etl/run_pipeline.py

# 4. Build the RAG index (schema docs + business glossary)
python rag/build_index.py

# 5. Launch the app
streamlit run app/streamlit_app.py
```

Power BI: point a new report at the `insightiq` Postgres database
(Get Data > PostgreSQL database) and build visuals on top of the
`fact_orders` / `dim_*` tables. See `powerbi/README.md` for suggested
measures.

## Orchestration

- **`airflow/`** — Apache Airflow 3.3.0 via Docker Compose: 9 DAGs
  covering the real ETL pipeline (with DAG-to-DAG triggering into a
  validation DAG), parallel data-quality checks, dynamic task mapping,
  a sensor/reschedule-mode demo, a Great Expectations expectation
  suite, RFM customer segmentation, and an `insightiq_dbt_pipeline` DAG
  that runs and tests the `insightiq_dbt` project's staging model and
  marts inside the Airflow containers. See `airflow/README.md` for
  setup, the Postgres connection config, and container-networking notes.
- **`n8n/`** — n8n workflows for fast, visual prototyping of the same
  ETL-orchestration, data-validation, RFM-alerting, and category-revenue
  reporting ideas, built first and kept alongside Airflow rather than
  replaced by it. See `n8n/README.md`.

## Project structure

```
insightiq/
├── data/               # raw/ (gitignored) and processed/ CSVs
├── sql/                # schema DDL and analytical queries
├── etl/                # extract, transform, load scripts
├── rag/                # embedding + retrieval logic
├── llm/                # NL2SQL and chatbot orchestration
├── app/                # Streamlit UI
├── airflow/            # Airflow DAGs (Docker Compose) — see airflow/README.md
├── n8n/                # n8n workflows (visual orchestration) — see n8n/README.md
├── powerbi/            # dashboard notes (the .pbix itself isn't checked in)
├── tests/              # unit tests
└── dev-logs/           # Claude Code prompt log — the "how it was built" record
```

## Build phases

1. Setup — repo, Postgres, dataset
2. Python ETL — ingest, clean, load
3. SQL warehouse — star schema, analytical queries
4. Power BI — dashboard, DAX measures
5. RAG knowledge base — embed schema docs + glossary
6. LLM chatbot — hybrid NL2SQL + RAG
7. Integration — Streamlit UI tying dashboard + chatbot together
8. Documentation — architecture diagram, demo, dev-log writeup

## Status

- [x] ETL pipeline
- [x] Warehouse schema
- [ ] Power BI dashboard
- [x] RAG index
- [x] LLM chatbot
- [x] Streamlit integration
- [ ] Demo recording
