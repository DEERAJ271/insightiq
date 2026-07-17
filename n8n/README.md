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
below to load the four workflows and point their Postgres credential at
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

## Workflow 3: insightiq-rfm-alerts (Logic verified outside n8n — not yet run through the n8n engine)

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

**Verification status:** `n8n import:workflow` failed on this local install
(v2.29.9) with two unrelated internal errors (a bogus credential-ownership
error, then a `NOT NULL constraint failed: workflow_entity.id`) — a CLI
version-compat bug, not an issue with this workflow file; confirmed via
`PRAGMA integrity_check` that the existing `insightiq-data-validation` and
`insightiq-etl-orchestration` workflows were untouched. Rather than force
the CLI path, each stage was verified manually against real data instead:
the Postgres query ran against the live warehouse (10 real "At Risk" rows),
the `Aggregate Customers` JS logic was run in Node against that real result
(correctly collapsed to 1 item), and the resulting prompt was POSTed to the
real Ollama endpoint (returned a genuine, on-topic 3-sentence summary).
This confirms the query, aggregation, and Ollama call all work — it does
**not** confirm the n8n engine wiring the 5 nodes together via the GUI
import path documented above; that still needs a manual run.

## Workflow 4: insightiq-category-enrichment (Logic verified outside n8n — not yet run through the n8n engine)

Manual Trigger → Postgres (per-category order count and revenue, joining
`fact_orders` to `dim_product`) → Code node → Ollama (llama3.2) generates
a 3-sentence narrative.

The Postgres node returns one row per category (74, including a NULL
category the Code node labels `"Uncategorized"` — see
`data-profile.md`'s note on the ~1-2% uncategorized-product bucket). The
Code node (`Summarize Category Revenue`) computes each category's share
of total revenue *and* share of total orders in one pass over all 74
rows, then sorts by revenue descending — both shares are included, not
just revenue share, because a category with revenue share well above its
order share means unusually high average order value (and vice versa);
that divergence is what "surprisingly high/low revenue share" means, not
revenue share read in isolation. As with Workflow 3, this aggregation has
to happen before the HTTP Request node, once over the full category
list, or Ollama would be called once per category instead of once per run.

**Verification status:** not imported into n8n (same CLI import
version-compat issue noted under Workflow 3). Verified manually instead:
the Postgres query ran against the live warehouse (74 real category
rows, including the NULL/Uncategorized one), the `Summarize Category
Revenue` JS was run in Node against that real result (revenue shares
summed to ~100% across all categories, confirming the math; `health_beauty`
came out on top by revenue, and `watches_gifts` showed the largest
revenue-share-vs-order-share divergence — 8.87% of revenue from only
5.65% of orders), and the resulting prompt was POSTed to the real Ollama
endpoint and returned a 3-sentence narrative in ~3.5 min. Confirms the
query, aggregation, and Ollama call all work — the HTTP path, not the
content. The content itself showed a real instance of the same llama3.2
limitation documented elsewhere in this project (e.g. `dev-logs/prompts.md`):
it named `health_beauty`'s revenue as `$125,868,134.34`, a 100x
misread of the actual `$1,258,681.34`, and pointed to "electronics" and
"construction tools" as the divergent category rather than `watches_gifts`
(the one the Code node's own numbers actually flag as most divergent).
Pipeline correctness (query → aggregation → API call) is confirmed;
llama3.2's narrative accuracy over a 74-category prompt is not — expected,
consistent with this project's llama3.2-is-for-pipeline-testing-only
stance, not a new finding. Does not confirm the n8n engine wiring the 4
nodes together via the GUI import path.

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
