# n8n Automation Layer

Local n8n workflows, running natively (not Docker), automating InsightIQ's
data validation and ETL orchestration with LLM-generated summaries via
local Ollama.

## Workflow 1: insightiq-data-validation (Published)

Schedule Trigger → Postgres (checks fact_orders.customer_key for NULLs) →
IF (threshold check) → on failure, Ollama (llama3.2) generates a
plain-English alert summary. Tested end-to-end with clean and simulated
failing data.

## Workflow 2: insightiq-etl-orchestration (Tested)

Manual Trigger → Code node executes the full ETL pipeline
(etl/run_pipeline.py) via execSync → Ollama (llama3.2) summarizes the run
(row counts loaded per table) in plain English for a stakeholder. Tested
end-to-end: pipeline runs, row counts are captured, and Ollama generates
the summary successfully.

Key fix: calling `source venv/bin/activate && python ...` via execSync
hung indefinitely in n8n's non-interactive shell context. Resolved by
calling the venv's Python binary directly by path instead:
`execSync('/path/to/venv/bin/python -m etl.run_pipeline', { cwd: ... })`.

Also required enabling Node's child_process module in the Code node,
disabled by default as a security measure:
`export NODE_FUNCTION_ALLOW_BUILTIN=child_process` before `n8n start`.

## Setup notes

- n8n runs natively via npm — Docker-to-Docker networking to Postgres was
  unreliable; native install talks to localhost directly.
- Postgres credential: host 127.0.0.1 (avoids IPv6/IPv4 resolution
  mismatch), port 5544, database insightiq.
- Ollama used for local LLM calls during development to avoid Anthropic
  API costs; swap the HTTP Request node's target for production.
- ETL pipeline output contains raw newlines that break naive JSON string
  interpolation; either sanitize in the Code node
  (`.replace(/\n/g, ' ')`) or wrap the expression in
  `JSON.stringify(...).slice(1, -1)` before inserting into a JSON body.

## Import

Import the .json files in n8n/workflows/ into a local n8n instance and
reconfigure the Postgres credential.
