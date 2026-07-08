# InsightIQ — AI-Augmented Sales Analytics Platform

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
| BI             | Power BI, DAX                               |
| Retrieval      | LangChain (or LlamaIndex), Chroma           |
| LLM            | Claude API (Anthropic)                      |
| App layer      | FastAPI + Streamlit                         |
| Dev workflow   | Claude Code (VS Code)                       |

## Dataset

Default: [Olist Brazilian E-commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(orders, customers, products, reviews, payments). Swap in any relational
retail/sales dataset — the schema in `sql/schema.sql` is the thing to adapt.

## Setup

```bash
# 1. Environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # fill in DATABASE_URL and ANTHROPIC_API_KEY

# 2. Database
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

## Project structure

```
insightiq/
├── data/               # raw/ (gitignored) and processed/ CSVs
├── sql/                # schema DDL and analytical queries
├── etl/                # extract, transform, load scripts
├── rag/                # embedding + retrieval logic
├── llm/                # NL2SQL and chatbot orchestration
├── app/                # Streamlit UI
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

- [ ] ETL pipeline
- [ ] Warehouse schema
- [ ] Power BI dashboard
- [ ] RAG index
- [ ] LLM chatbot
- [ ] Streamlit integration
- [ ] Demo recording
