# n8n Automation Layer

Local n8n workflows, running natively (not Docker), automating InsightIQ's
data validation, ETL orchestration, and RFM-based retention alerting with
LLM-generated summaries via local Ollama.

## Setup

```bash
npm install -g n8n
# Required for Workflow 2's Code node, which calls execSync — n8n
# disables Node's child_process module by default as a security measure.
export NODE_FUNCTION_ALLOW_BUILTIN=child_process
n8n start
```

UI: `http://localhost:5678` (n8n's default port). Then see "Import"
below to load the three workflows and point their Postgres credential at
your local instance.

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

## Workflow 3: insightiq-rfm-alerts (Untested — built but not yet run in n8n)

Schedule Trigger (daily) → Postgres (top 10 `customer_key`s in the `At Risk`
or `Lost` RFM segments, by `monetary` descending) → IF (`$input.all().length
> 0`, so nothing downstream fires on an empty result) → Code node → Ollama
(llama3.2) generates a 2-3 sentence retention-focused summary.

The Postgres node can return up to 10 rows, but the goal is *one* summary
covering the whole list, not one Ollama call per customer — and n8n's HTTP
Request node otherwise executes once per input item. The Code node
(`Aggregate Customers`) collapses all rows into a single item
(`{ customers: [...] }`) before the HTTP Request node, the same
one-item-in-before-the-LLM-call shape `insightiq-etl-orchestration`
already uses for its Code → HTTP Request handoff, so there's exactly one
Ollama call per run regardless of how many at-risk customers come back.

## Setup notes

- n8n runs natively via npm — Docker-to-Docker networking to Postgres was
  unreliable; native install talks to localhost directly.
- Postgres credential: host 127.0.0.1 (avoids IPv6/IPv4 resolution
  mismatch), port 5544, database insightiq.
- Ollama used for local LLM calls during development to avoid Anthropic
  API costs; swap the HTTP Request node's target for production.
- The Python app layer (`llm/chatbot.py`, `llm/nl2sql.py`) mirrors this
  same choice via an `LLM_BACKEND` env var — `ollama` (default, calls
  `http://127.0.0.1:11434/api/generate` with `llama3.2`, same as these
  workflows) or `anthropic` (unchanged Claude code path, once credits are
  available). n8n's HTTP Request nodes call Ollama directly and aren't
  affected by this var.
- ETL pipeline output contains raw newlines that break naive JSON string
  interpolation; either sanitize in the Code node
  (`.replace(/\n/g, ' ')`) or wrap the expression in
  `JSON.stringify(...).slice(1, -1)` before inserting into a JSON body.

## Import

Import the .json files in n8n/workflows/ into a local n8n instance and
reconfigure the Postgres credential.
