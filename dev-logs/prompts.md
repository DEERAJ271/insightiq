# Claude Code prompt log

This file is the evidence trail for "built with Claude Code in VS Code."
Log real prompts as you go — include the ones where you had to correct
or redirect the output, not just the clean ones. That's what makes it
credible to an interviewer.

Suggested format per entry:

```
## [Date] — [Task]
**Prompt:** the actual prompt you gave Claude Code
**Output:** one-line summary of what it generated
**Edit:** what you changed by hand and why (or "used as-is")
```

---

## 2026-07-08 — RAG: extend build_index.py to pull from business_glossary

**Prompt:** "Read rag/build_index.py. Right now it only indexes the hardcoded
SCHEMA_DOCS string. Extend it to also pull all rows from the business_glossary
table in Postgres (term, definition columns) and index each row as a separate
document, tagged with metadata source="glossary". Use the DATABASE_URL from
.env via sqlalchemy, matching the pattern already used in etl/load.py."

**Output:** Added `get_engine()` and `load_glossary_docs()` to `rag/build_index.py`.
Each glossary row becomes a `Document(page_content="{term}: {definition}",
metadata={"source": "glossary"})`. Extended `build_index()` to call it and
append results before building the Chroma index. Print line updated to report
glossary count separately.

**Edit:** None — used as-is.

---

## 2026-07-08 — RAG: run build_index and resolve dependency conflicts

**Prompt:** "python -m rag.build_index" (then follow-up to pin versions in
requirements.txt with explanatory comments)

**Output:** Diagnosed and resolved three dependency conflicts to get the index
to build successfully (5 chunks: 2 from SCHEMA_DOCS, 3 from business_glossary):

- `psycopg2-binary` — listed in requirements.txt but not installed in the venv;
  installed it.
- `sentence-transformers` 5.6.0 pulled in torch 2.2.2, but 5.x requires
  torch >= 2.4 (no wheel available for Python 3.11 on x86_64 macOS); pinned to
  `>=3.0,<4.0`.
- `numpy` 2.x is incompatible with torch 2.2.2 (compiled against NumPy 1.x);
  pinned to `>=1.26,<2`.
- `chromadb` — listed in requirements.txt but not installed in the venv;
  installed it.

Updated `requirements.txt` with the upper-bound pins and comments explaining the
torch 2.2.2 compatibility constraint.

**Edit:** None — used as-is.

---

## Example entry (replace with your real ones)

## 2026-07-08 — ETL: fuzzy match for duplicate customer records
**Prompt:** "Write a function that deduplicates customer records in
etl/transform.py using difflib fuzzy matching on name + address, with a
configurable similarity threshold."
**Output:** Generated a `dedupe_customers()` function using
`difflib.SequenceMatcher`.
**Edit:** Tightened the default threshold from 0.8 to 0.9 after testing
against known duplicate pairs in the Olist dataset — 0.8 was merging
distinct customers with common names.

---

## 2026-07-09 — Local-testing cost strategy (summary)

**Verified this session:** `/prompt-comparison` ran the NL2SQL `SYSTEM_PROMPT`
against local Ollama (llama3.2) twice for the same 3 questions (6
`generate_sql()`-equivalent calls), after a trivial 1-token Anthropic API
call confirmed the account had no credits available. 6 Claude API calls
avoided.

**Evidence of prior local-testing (2026-07-08, from git history and scratch
file timestamps — not re-verified today, since `dev-logs/prompts.md` doesn't
log individual command invocations):**
- `nl2sql-local-test` (`scratch_nl2sql_local.py`): 3 questions → ~3
  `generate_sql()` calls avoided.
- `chatbot-local-test` (`scratch_chatbot_local.py`): 4 questions (3 routed
  to NL2SQL, 1 to RAG) → ~7 calls avoided — 2 per NL2SQL-routed question
  (`generate_sql` + compose) and 1 for the RAG-routed question (compose
  only), based on the actual call pattern in `llm/chatbot.py::answer()`.
- `nl2sql-test`-equivalent (commit `5253b01`): 3 hardcoded queries run
  through `run_query()` with zero generation calls.
- `rag-health`-equivalent (commit `440c446`): verified retrieval with no
  LLM call at all — RAG retrieval is local (Chroma) either way, so this
  doesn't substitute for a generation call, but it does catch bad context
  before it would reach a paid composition call downstream.
- No artifact or commit evidence of a `routing-test` run; `needs_sql()` is
  plain keyword matching, cheap enough to eyeball without a dedicated run.

**Total directly-evidenced Claude API calls avoided: ≥16** (6 today + 3 +
7 from the 2026-07-08 local-test runs). This is a lower bound from
available evidence (file timestamps, commit messages), not an exact
command log.

**What this validates, and what it doesn't:** local Ollama testing
validates PIPELINE correctness — routing logic, schema context injection,
join patterns, execution against the database, error handling — for zero
API cost. It does NOT validate final answer quality or SQL correctness at
production standard: llama3.2 is a materially weaker model than
claude-sonnet-5, and its output was never treated as a correctness signal.
`/prompt-comparison` on 2026-07-09 made this concrete — 1 of 3 llama3.2 SQL
outputs was fundamentally wrong (hallucinated column, missed business
logic). Answer-quality validation still requires the production model.

**README "Development approach" summary:**
> NL2SQL and chatbot pipeline changes were smoke-tested locally against
> Ollama (llama3.2) before touching the Anthropic API, validating routing
> logic, schema context injection, and SQL execution end-to-end at zero API
> cost. This caught pipeline-level issues — bad joins, unhandled query
> errors — without spending credits on generation calls that weren't needed
> to test plumbing. Ollama's SQL and answer quality were never treated as a
> correctness benchmark; final answer quality was validated separately
> against the production model once each pipeline change was confirmed to
> run end-to-end.

---

## 2026-07-10 — n8n: fix ETL orchestration workflow end-to-end

**Prompt:** "The etl-orchestration workflow's Code node hangs when it runs
the pipeline via execSync — debug why `source venv/bin/activate && python -m
etl.run_pipeline` never returns in n8n."

**Output:** Diagnosed and fixed three separate issues blocking the workflow
from completing end-to-end:

- `execSync('source venv/bin/activate && python ...')` hung indefinitely —
  `source` requires an interactive shell context that n8n's non-interactive
  child process doesn't provide. Fixed by calling the venv's Python binary
  directly by path instead: `execSync('/path/to/venv/bin/python -m
  etl.run_pipeline', { cwd: ... })`, skipping activation entirely.
- n8n's Code node disables Node's `child_process` module by default (a
  security measure), so `execSync` wasn't available at all until set via
  `export NODE_FUNCTION_ALLOW_BUILTIN=child_process` before `n8n start`.
- The HTTP Request node's JSON body broke because the ETL pipeline's raw
  stdout contains unescaped newlines, which aren't valid inside a JSON
  string literal. Fixed by sanitizing/escaping the captured stdout before
  interpolating it into the JSON body (stripping/replacing `\n` or using
  `JSON.stringify(...).slice(1, -1)`).

Both n8n workflows — `insightiq-data-validation` and
`insightiq-etl-orchestration` — now run fully end-to-end with local Ollama
(llama3.2) generating plain-English summaries at each workflow's tail.

**Edit:** None — used as-is.

---

## 2026-07-10 — Add LLM_BACKEND switch to llm/chatbot.py and llm/nl2sql.py

**Prompt:** "Add an LLM_BACKEND env var to llm/chatbot.py and
llm/nl2sql.py that switches between "anthropic" and "ollama" (calling
http://127.0.0.1:11434/api/generate with llama3.2 when set to "ollama").
Default to ollama. Keep the Anthropic code path intact and unchanged for
when credits are available — just gate which one runs based on the env
var."

**Output:** Added `LLM_BACKEND` (default `"ollama"`), `OLLAMA_URL`, and
`OLLAMA_MODEL` env vars to both files. `generate_sql()` in `nl2sql.py` and
the compose call in `chatbot.py::answer()` now branch on `LLM_BACKEND`:
`"ollama"` POSTs to `http://127.0.0.1:11434/api/generate` with `llama3.2`
using the same `SYSTEM_PROMPT`/schema context as the Anthropic path;
anything else falls through to the original, untouched
`client.messages.create()` call. Added `requests` and `tabulate` to
`requirements.txt` (both previously relied on transitively — `tabulate`
is needed by `df.to_markdown()` in `chatbot.py` and was missing
entirely) and documented `LLM_BACKEND`/`OLLAMA_URL`/`OLLAMA_MODEL` in
`.env.example` and `n8n/README.md`.

Verified end-to-end with the default `ollama` backend: `generate_sql()`
produced valid SQL for "average order value by product category" and
`chatbot.answer()` ran the full NL2SQL → Postgres → Ollama-compose path
and returned a real per-category breakdown — zero Anthropic API calls.

**Edit:** None — used as-is.
