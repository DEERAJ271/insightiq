# n8n Automation Layer

Local n8n workflow, running natively (not Docker), validating InsightIQ's
Postgres warehouse and generating LLM alert summaries via local Ollama.

## Workflow: insightiq-data-validation (Published)

Schedule Trigger → Postgres (checks fact_orders.customer_key for NULLs) →
IF (threshold check) → on failure, Ollama (llama3.2) generates a
plain-English alert summary.

## Setup notes

- n8n runs natively via npm — Docker-to-Docker networking to Postgres was
  unreliable; native install talks to localhost directly.
- Postgres credential: host 127.0.0.1 (avoids IPv6/IPv4 resolution
  mismatch), port 5544, database insightiq.
- Ollama used for local LLM calls during development to avoid Anthropic
  API costs; swap the HTTP Request node's target for production.

## Import

Import n8n/workflows/insightiq-data-validation.json into a local n8n
instance and reconfigure the Postgres credential.
