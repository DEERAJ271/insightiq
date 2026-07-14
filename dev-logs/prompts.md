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

---

## 2026-07-10 — Attempted anthropic-backend comparison run (no credits)

**Prompt:** "run the chatbot with LLM_BACKEND=anthropic to compare"

**Output:** `/cost-guard` dry-run check first: single question, no loops,
`max_tokens` set on both calls (`generate_sql`=500, compose=600), 2 total
API calls if run — under the 3-call confirmation threshold, but flagged
that the account had zero credits as of 2026-07-09 and asked before
spending the account's only test calls on it. Confirmed, then ran
`LLM_BACKEND=anthropic chatbot.answer(...)` for the same AOV-by-category
question already answered via Ollama.

**Result:** confirmed `LLM_BACKEND=anthropic` correctly routes to the
untouched Anthropic code path (traceback shows it reached
`generate_sql()`'s `client.messages.create()`, not the Ollama branch), but
the call failed with `anthropic.BadRequestError: 400 invalid_request_error
— "Your credit balance is too low to access the Anthropic API."` Same
zero-credit state noted on 2026-07-09, still true today. A rejected
request isn't billed, so no cost was incurred. Live side-by-side answer
quality comparison (Ollama vs. Claude) is still blocked on adding credits;
only the routing logic itself was verified.

**Edit:** None — used as-is.

---

## 2026-07-10 — Gracefully handle failed generated SQL

**Prompt:** "In llm/nl2sql.py's run_query() or answer_numeric_question(),
catch SQLAlchemy errors from a failed query. On failure, don't crash —
instead return a graceful message like 'The generated SQL was invalid.
This is a known limitation of the local Ollama model (llama3.2) used for
zero-cost development testing; production Claude generates more reliable
SQL.' Log the failed SQL and error for debugging, but never show a raw
traceback to the end user in the Streamlit app."

**Output:** `run_query()` in `nl2sql.py` now wraps execution in
`try/except (SQLAlchemyError, DatabaseError)`, logs the failed SQL and
error via `logger.error()`, then raises a new `SQLExecutionError` with
the requested user-facing message. `chatbot.answer()` catches
`SQLExecutionError` around `answer_numeric_question()` and returns the
message directly, skipping the LLM compose call entirely since there's
no data to compose from. Since `streamlit_app.py` just calls
`chatbot.answer()` and `st.write()`s the result, a failed query now
surfaces the friendly message instead of a raw traceback in the UI.

Caught a real bug while testing: `pandas.read_sql()` wraps SQLAlchemy
errors in its own `pandas.errors.DatabaseError`, which is **not** a
`SQLAlchemyError` subclass (confirmed via `DatabaseError.__mro__` —
inherits from `OSError`/`Exception`, not `SQLAlchemyError`). Catching
only `SQLAlchemyError` as the prompt suggested let a real
`SELECT * FROM nonexistent_table_xyz` failure slip through as an
unhandled traceback. Fixed by catching both exception types.

Verified: (1) `run_query()` directly against a query on a nonexistent
table — caught, logged the SQL + error, raised `SQLExecutionError` with
the friendly message; (2) `chatbot.answer()` with
`answer_numeric_question` mocked to raise `SQLExecutionError` — returned
the message directly, no compose call attempted; (3) existing
`nl2sql.py` `__main__` smoke tests (3 valid queries + non-SELECT
rejection) still pass unaffected.

**Edit:** Broadened the except clause from `SQLAlchemyError` alone to
`(SQLAlchemyError, DatabaseError)` after the nonexistent-table test
proved the first version didn't actually catch the failure it was meant
to catch — pandas re-wraps the underlying SQLAlchemy exception before it
reaches `run_query()`'s except block.

---

## 2026-07-10 — Live UI testing surfaces a routing bug + a router limitation

**Prompt:** Live-tested the chatbot with 8 real questions through the
Streamlit UI (`streamlit run app/streamlit_app.py`).

**Output:** Found and fixed a routing bug in `needs_sql()`
(`llm/chatbot.py`): substring matching against `NUMERIC_KEYWORDS` made
"counts" (as in "what counts as a repeat customer?") false-match the
"count" keyword, misrouting a definitional question to NL2SQL instead of
RAG. Fixed by switching to word-boundary regex matching
(`re.search(rf"\b{re.escape(kw)}\b", q)` per keyword) so "counts" no
longer matches "count" while "how many orders" and "discounted rate"
still correctly match "how many" and "rate". Verified against 6 cases
including the reported false positive and a negative control
("accounting discrepancies" no longer false-matches "count").

Also confirmed, rather than "fixed," a separate limitation: genuinely
hybrid questions (e.g. "explain X and how many Y") only get the numeric
half answered, since `needs_sql()` returns a single boolean and
`answer()` picks exactly one path (NL2SQL or RAG), never both. This
matches the TODO already at the top of `chatbot.py` ("support questions
that need BOTH paths") — it's a known architectural tradeoff of the
current single-path router, not a regression to patch alongside the
keyword-matching bug.

**Edit:** None — used as-is.

---

## 2026-07-10 — Re-test 8 questions; found and fixed venv drift breaking RAG

**Prompt:** "test the other 8 questions again in the UI" (re-running the
same 8 questions from the earlier live-testing session, this time
through `chatbot.answer()` directly since no browser automation is
available; then "pip install -r requirements.txt to fix the drift").

**Output:** Routing was 8/8 correct, confirming the `needs_sql()`
word-boundary fix holds, including both edge cases it targeted ("what
counts as..." → RAG, "recount the steps..." → RAG). NL2SQL answers were
1 valid / 4 invalid-but-gracefully-handled (llama3.2 hallucinated tables
like `dimension_sla` and produced ambiguous/undefined columns — the
`SQLExecutionError` fallback from the earlier fix returned the friendly
message instead of crashing, exactly as designed).

All 3 RAG-routed questions crashed with `NameError: name 'nn' is not
defined`. Root cause: `venv/bin/pip show` revealed `numpy==2.4.6` and
`sentence-transformers==5.6.0` installed, despite `requirements.txt`
pinning `numpy<2` and `sentence-transformers<4.0` specifically because
torch 2.2.2 isn't ABI-compatible with either (the exact scenario the
2026-07-08 pin comments warn about) — the installed venv had drifted
from the pins at some point after they were set.

Fixed via `pip install -r requirements.txt`, which downgraded
`numpy` 2.4.6→1.26.4 and `sentence-transformers` 5.6.0→3.4.1 (pulling
compatible `transformers`/`huggingface-hub` versions along with it).
Re-ran all 3 previously-crashing RAG questions — all now return real
answers (only harmless `HuggingFaceEmbeddings`/`Chroma` import-path
deprecation warnings remain, not errors).

**Edit:** None — used as-is. `requirements.txt` itself was already
correct; only the installed venv needed to be brought back in line with
it.

---

## 2026-07-10 — Full 8-question regression test, post venv-drift fix

**Prompt:** Restart Streamlit to pick up the venv fix, then re-run the
same 8 questions through `chatbot.answer()` as a full regression test.

**Output:** Routing was 100% correct across all 8 — including "Can you
recount the steps for the ETL pipeline?", which confirms the
word-boundary fix generalized beyond the original "what counts as X"
bug it was written for, not just the one reported case.

NL2SQL results (4 numeric questions, after excluding the SLA-breach-count
question counted separately below): 1/4 succeeded cleanly (AOV by
category, real per-category breakdown), 3/4 failed gracefully via the
`SQLExecutionError` fallback message — no crash — due to llama3.2
generating invalid SQL (hallucinated aliases, wrong column references,
malformed date comparisons).

One question ("How many orders had a delivery SLA breach?") surfaced a
different and more concerning failure mode: the generated SQL executed
successfully (no error to catch) but didn't actually compute the SLA
breach count — the model answered with a vague hedge instead of a wrong
number, but the underlying pattern is the same. This is qualitatively
harder than the loud/caught failures above: there's no exception to
catch and no signal to the user that the answer might be wrong. Silent
wrong-or-non-answers are the general hard problem in NL2SQL correctness
regardless of which model generates the SQL — the graceful-failure
handling built earlier this session only covers SQL that fails to
execute, not SQL that executes but answers the wrong question.

**Edit:** None — used as-is.

---

## 2026-07-10 — Guard compose step against hallucinated raw SQL leaking

**Prompt:** "When I ask 'What is the average order value by product
category?' in the Streamlit app, the output shows raw SQL text
(SELECT AVG(order_value), product_category FROM data GROUP BY
product_category;) instead of an actual answer... Trace through
chatbot.answer() and nl2sql.py to find where this raw SQL string is
being returned/displayed instead of being executed and replaced with
real results or a graceful error."

**Output:** Traced both files. Reproduced the exact reported SQL
directly against `run_query()` and confirmed the existing
`SQLExecutionError` handling (from the earlier graceful-failure fix)
already catches it correctly — that specific failure mode was not
live-reproducible with the current code. While probing further,
surfaced a second, distinct leak path: the **compose step itself**
(the Ollama/Anthropic call that turns query results into prose) has no
output validation at all, and a weak local model can hallucinate a
SQL-shaped response as its "answer" even when the underlying query
succeeded — observed this directly in a test run where llama3.2
produced a rambling, SQL-flavored non-answer instead of prose.

Added `RAW_SQL_PATTERN` in `chatbot.py` (matches a leading
`SELECT/INSERT/UPDATE/DELETE` keyword) applied to the compose output
for both backends. On match, logs the leaked question/backend/response
for debugging and returns the same graceful fallback message instead —
extracted as a shared `SQL_GENERATION_FAILURE_MESSAGE` constant in
`nl2sql.py` so both failure paths (execution failure and compose
hallucination) show identical messaging.

Verified 3 cases via mocking: (1) the original run_query-failure path
still returns the graceful message, (2) a simulated compose-step
hallucination of raw SQL is now caught and replaced, (3) a normal prose
answer passes through unaffected (no false positives). Re-ran
`nl2sql.py`'s existing smoke tests — unaffected.

**Edit:** None — used as-is.

---

## 2026-07-10 — Permanent sys.path fix for streamlit_app.py

**Prompt:** "Fix this permanently by adding this to the top of
app/streamlit_app.py, before any other imports: `import sys` /
`from pathlib import Path` / `sys.path.insert(0,
str(Path(__file__).resolve().parent.parent))`. This ensures the
project root is always on the import path regardless of how streamlit
is launched, so PYTHONPATH never needs to be set manually again."

**Output:** Added the three lines as specified, before the `streamlit`
and `llm.chatbot` imports. Verified by stopping and restarting the
Streamlit server — came back up cleanly and the chat tab still resolved
`llm.chatbot` correctly.

**Edit:** None — used as-is.

---

## 2026-07-13 — Set up Apache Airflow 3.3.0 via Docker Compose

**Prompt:** Set up Apache Airflow 3.3.0 via Docker Compose alongside
the existing n8n/Postgres/Ollama stack.

**Output:** Added `airflow/docker-compose.yaml` and a `hello_world_dag.py`
under `airflow/dags/`. Set `AIRFLOW__CORE__LOAD_EXAMPLES` (`LOAD_EXAMPLES`)
to `false` to disable the 115 default example DAGs — since they'd already
been loaded into the metadata database on first boot, disabling the flag
alone wasn't enough and required a full volume reset (`docker compose down
-v`) to take effect. Confirmed working end-to-end with a two-task
`hello_world` DAG (BashOperator tasks with an explicit dependency via
`>>`), verified via the Graph view and task logs in the Airflow UI.

**Edit:** None — used as-is.

---

## 2026-07-13 — Rotate Airflow fernet_key and secret_key

**Prompt:** "rotate the fernet_key and secret_key just in case" (after
confirming `airflow/config/airflow.cfg` had never been committed to
git history).

**Output:** Generated a new `fernet_key` (via
`cryptography.fernet.Fernet.generate_key()`) and `secret_key` (via
`secrets.token_urlsafe`) and wrote them into the local
`airflow/config/airflow.cfg`. While rotating, discovered that file
isn't actually wired into the running stack: no `airflow.cfg` exists
inside the containers at all, and `docker-compose.yaml` reads
`AIRFLOW__CORE__FERNET_KEY` from `${FERNET_KEY}` in `airflow/.env`,
which only had `AIRFLOW_UID` set — so connection-password encryption
was silently off in the live containers regardless of what was in the
local cfg file.

Added `FERNET_KEY=<new key>` to `airflow/.env` (gitignored) and ran
`docker compose down` / `up -d` (no `-v`, so metadata/DAG history was
preserved) to pick it up. Verified via `docker exec ... printenv` that
`AIRFLOW__CORE__FERNET_KEY` is now live inside the scheduler container
with the new key, and all 7 services (`postgres`, `redis`,
`airflow-init`, `scheduler`, `dag-processor`, `apiserver`, `triggerer`,
`worker`) came back healthy.

**Edit:** None — used as-is.

---

## 2026-07-13 — Audit webserver_config, Postgres, and n8n configs for secrets

**Prompt:** "check the webserver_config.py for any hardcoded secrets
too" followed by "check the postgres and n8n configs for hardcoded
secrets too."

**Output:** No `webserver_config.py` exists locally or inside the
running Airflow containers — Airflow never generated one for this
setup, and the FAB auth manager's `secret_key` is already sourced from
`airflow.cfg`/env (rotated in the previous entry). The only match
anywhere in the containers was Airflow's own shipped
`default_webserver_config.py` template, which contains only commented-out
placeholder lines, not live credentials.

There's no dedicated Postgres or n8n docker-compose/config file in the
repo — n8n is represented only by two exported workflow JSONs under
`n8n/workflows/`, and the sole compose file in the project is
`airflow/docker-compose.yaml` (already audited). Grepped the workflow
JSONs for passwords/keys/tokens/connection strings — clean; the one
`credentials` block found is just an n8n internal credential-store
reference (id/name), not an embedded secret.

The root `.env` (gitignored, confirmed never committed via full git
history search) does contain a live `ANTHROPIC_API_KEY` and a
default/weak local Postgres credential
(`postgresql://postgres:postgres@localhost:5544/insightiq`). Flagged
both to the user; decided to leave as-is since the file is gitignored
and the Postgres instance is local-only.

**Edit:** None — used as-is.

---

## 2026-07-13 — Audit etl and llm directories for hardcoded secrets

**Prompt:** "check the etl and llm directories for hardcoded secrets
too."

**Output:** Grepped both directories for API-key patterns, password/
secret assignments, connection strings, and auth headers. No hardcoded
secrets found — `CLAUDE_MODEL`, `LLM_BACKEND`, `OLLAMA_URL`,
`OLLAMA_MODEL`, and `DATABASE_URL` in `llm/chatbot.py` and
`llm/nl2sql.py` are all pulled via `os.getenv(...)`. The one literal
match, `etl/load.py:14`'s `os.getenv("DATABASE_URL",
"postgresql://postgres:postgres@localhost:5432/insightiq")`, is just
the same local-dev fallback default already documented in
`.env.example`, not a real secret, and only used when `DATABASE_URL`
isn't set.

**Edit:** None — used as-is.

---

## 2026-07-13 — Audit app and rag directories for hardcoded secrets

**Prompt:** "check the app and rag directories for hardcoded secrets
too."

**Output:** Grepped both directories for the same set of patterns
(API-key formats, password/secret assignments, connection strings,
auth headers). No hardcoded secrets found — `app/streamlit_app.py` is
just the `sys.path` fix plus Streamlit UI wiring, no credentials at
all. `rag/query_engine.py` and `rag/build_index.py` pull
`CHROMA_PERSIST_DIR` and `DATABASE_URL` via `os.getenv(...)`; the one
literal match, `rag/build_index.py:24`'s fallback
`postgresql://postgres:postgres@localhost:5432/insightiq`, is the same
local-dev default already flagged in `etl/load.py`, not a real secret.

This closes out the full-codebase secrets sweep — `airflow`, `etl`,
`llm`, `app`, and `rag` have now all been audited and are clean.

**Edit:** None — used as-is.

---

## 2026-07-13 — Audit sql and tests directories for hardcoded secrets

**Prompt:** "check the sql and tests directories too."

**Output:** Grepped both directories for the same set of patterns
(API-key formats, password/secret assignments, connection strings,
auth headers). No hardcoded secrets found — `sql/schema.sql` and
`sql/analytical_queries.sql` are pure DDL/queries with no connection
strings or credentials, and `tests/test_transform.py` doesn't touch
the database or any credentials at all (no `getenv`, `environ`, or
`connect()` calls).

Extends the full-codebase secrets sweep — `airflow`, `etl`, `llm`,
`app`, `rag`, `sql`, and `tests` have now all been audited and are
clean.

**Edit:** None — used as-is.

---

## 2026-07-13 — Fix TypeError in insightiq_category_summary_dag.py

**Prompt:** "Fix the TypeError in
dags/insightiq_category_summary_dag.py line 36 — 'Expected numeric
dtype, got object instead' on `.round()`. This happens in the groupby
aggregation step. Before calling `.round()`, explicitly cast the
relevant columns (avg_price, avg_freight, avg_review_score) to numeric
using `pd.to_numeric(..., errors='coerce')` to handle any non-numeric
or NULL values that might be causing pandas to infer an object dtype.
Also add a print statement showing `df.dtypes` right after the
`read_sql()` call so future debugging is faster."

**Output:** In `airflow/dags/insightiq_category_summary_dag.py`, added
`print(df.dtypes)` immediately after the `read_sql()` call, and wrapped
`avg_price`, `avg_freight`, and `avg_review_score` in
`pd.to_numeric(..., errors="coerce")` before each `.round(2)` call so
non-numeric/NULL-tainted values no longer raise on `.round()`.

**Edit:** None — used as-is.

---

## 2026-07-13 — Commit data validation DAG and image build changes

**Prompt:** "yes, commit those too" (referring to pre-existing, not
Claude-authored, uncommitted changes found while committing the
category-summary DAG fix: a modified `airflow/docker-compose.yaml` and
two untracked files).

**Output:** Reviewed the three files before staging (checked for
secrets, matching the ongoing audit) — all clean. Committed
`airflow/dags/insightiq_data_validation_dag.py` (null foreign-key,
duplicate order-product, review-score-range, and freight-outlier
checks against `fact_orders`), `airflow/requirements.txt` (pandas,
sqlalchemy, psycopg2-binary, python-dotenv, great-expectations), and
the `airflow/docker-compose.yaml` change that builds the Airflow image
inline with `requirements.txt` installed, so both the validation DAG
and the category summary DAG have their pandas dependency available at
runtime.

**Edit:** None — used as-is.

---

## 2026-07-13 — Pin airflow/requirements.txt versions

**Prompt:** "check the airflow requirements.txt for pinned versions"
followed by "yes, align it with the root file's versions" and "yes,
rebuild and commit it."

**Output:** Found `airflow/requirements.txt`'s 5 packages (pandas,
sqlalchemy, psycopg2-binary, python-dotenv, great-expectations) were
all unpinned, unlike the root `requirements.txt` which pins the same
packages with version floors and explanatory comments. Aligned
`airflow/requirements.txt` to the same floors (`pandas>=2.2`,
`sqlalchemy>=2.0`, `psycopg2-binary>=2.9`, `python-dotenv>=1.0`,
`great-expectations>=0.18`). Ran `docker compose build` to verify —
all 6 services (`scheduler`, `worker`, `triggerer`, `apiserver`,
`dag-processor`, `init`) built cleanly; already-installed versions in
the base image satisfied every new floor.

**Edit:** None — used as-is.

---

## 2026-07-13 — Check root requirements.txt for pinned versions

**Prompt:** "check the requirements.txt for the rest of the project."

**Output:** Confirmed only two `requirements.txt` files exist in the
project — the root one and `airflow/requirements.txt` (just fixed in
the previous entry). The root file was already in good shape: all 21
packages have a version floor (`>=`), and two carry documented upper
bounds — `numpy>=1.26,<2` (avoids an `_ARRAY_API` import error from a
NumPy 2.x/torch ABI mismatch) and `sentence-transformers>=3.0,<4.0`
(torch>=2.4, required by 4.x, has no wheel for Python 3.11 on x86_64
macOS). No unpinned packages found; no changes needed.

**Edit:** None — used as-is.

---

## 2026-07-13 — Fix category_summary NULL avg_review_score

**Prompt:** "The category_summary table has NULL avg_review_score for
every row. The earlier fix used pd.to_numeric(errors='coerce') which
likely converted problematic values to NaN instead of preserving valid
scores. Check what review_score actually contains in fact_orders (run
the diagnostic query first), then fix the aggregation so
avg_review_score correctly computes the mean of valid (non-null)
review scores, using .mean(skipna=True) rather than losing all values
to a blanket coercion."

**Output:** Ran the diagnostic query first, per the instruction, and
it overturned the premise: `fact_orders.review_score` was `NULL` for
all 102,425 rows already, at the Postgres level, before pandas ever
touched it. The `pd.to_numeric(errors='coerce')` fix from the earlier
entry wasn't the cause — `.mean(skipna=True)` on an all-null column is
still `NaN` regardless of aggregation method.

Traced the real root cause to `etl/transform.py`, which hardcoded
`fact["review_score"] = None` for every row with a comment noting it
was a placeholder "to be filled by a later enrichment step" that was
never built — even though `data/raw/olist_order_reviews_dataset.csv`
has real scores (mean ~4.09, 0 nulls) and was already being extracted
into a `"reviews"` key by `etl/extract.py`, just never joined in.

Presented this finding to the user (via AskUserQuestion) instead of
applying the originally-requested DAG-only fix, since it wouldn't have
changed anything. User chose to fix the ETL join now. Updated
`build_fact_orders()` in `etl/transform.py` to accept a `reviews`
dataframe and left-join `review_score` by `order_id`. Found 551 orders
have multiple review submissions with genuinely different scores
(resubmissions) — averaging them would produce fractional values that
don't fit the `SMALLINT` schema column, so kept the most recent
submission per order_id (by `review_creation_date`, tie-broken by
`review_answer_timestamp`) instead. Updated `etl/run_pipeline.py` to
pass `raw["reviews"]` through.

Re-ran the full ETL pipeline (`python -m etl.run_pipeline`) — 102,425
fact rows reloaded, 101,628 now have a non-null review_score (mean
4.08). Re-ran the `category_summary` DAG task directly (`airflow tasks
test insightiq_category_summary build_category_summary`) inside the
scheduler container and confirmed all 73 category rows in
`category_summary` now have a valid `avg_review_score` — zero NULLs.
The earlier `pd.to_numeric` coercion was left in place as a harmless
defensive cast.

**Edit:** None — used as-is.

---

## 2026-07-13 — Add LLM-generated failure alerts to data validation DAG

**Prompt:** "Add on_failure_callback=notify_failure (imported from
dags.utils.alerting) to the default_args of
dags/insightiq_data_validation_dag.py, so any task failure triggers an
LLM-generated alert summary printed to the task log. Test it by
temporarily changing one check (e.g. check_null_foreign_keys) to query
a nonexistent table like 'nonexistent_table_xyz' to force a real
failure, verify the alert prints in the task logs, then revert the
query back to fact_orders."

**Output:** `dags/utils/alerting.py` (a `notify_failure(context)` that
calls the local Ollama instance for a 1-2 sentence summary, with a
fallback message if unreachable) already existed. Added
`default_args={"on_failure_callback": notify_failure}` to
`insightiq_data_validation_dag.py` and imported it via `from
dags.utils.alerting import notify_failure`, exactly as specified.

That exact import failed at real DAG-parse time
(`ModuleNotFoundError: No module named 'dags'`) — it only worked in an
interactive `python3 -c` check because that implicitly adds cwd to
`sys.path`; Airflow's actual DAG processor only adds the DAG file's own
directory, not its parent. Fixed at the environment level rather than
changing the import: added `PYTHONPATH: '/opt/airflow'` to
`docker-compose.yaml`'s `airflow-common-env` and recreated the
containers, so `dags.utils.alerting` resolves as intended.

Forced a real failure by pointing `check_null_foreign_keys` at
`nonexistent_table_xyz` and ran `airflow tasks test`. First attempt hit
an Ollama cold-start timeout and fell back to the existing error
message; confirmed Ollama was reachable locally, retried, and got a
real LLM-generated alert correctly diagnosing the missing table.
Reverted the query back to `fact_orders` and re-ran the task — passes
cleanly with no alert.

**Edit:** None — used as-is.

---

## 2026-07-13 — Add pytest-based DAG integrity tests

**Prompt:** "added pytest-based DAG integrity tests run via DagBag
inside the Airflow worker container (required adding a tests/ volume
mount to docker-compose.yaml and pytest to requirements.txt). Fixed a
DagBag API signature change in Airflow 3.x — include_examples parameter
was removed, example loading is now config-only via
AIRFLOW__CORE__LOAD_EXAMPLES. All 6 tests pass: no import errors,
expected DAGs present, correct tagging, no cycles, and expected task
structure in insightiq_data_validation."

**Output:** Added `airflow/tests/test_dag_integrity.py`, running
`DagBag(dag_folder="dags/")` against all DAG files inside the Airflow
containers. Required adding `pytest` to `airflow/requirements.txt` and
a `tests/` volume mount (`${AIRFLOW_PROJ_DIR:-.}/tests:/opt/airflow/tests`)
to `docker-compose.yaml`. Fixed a `DagBag` API signature change in
Airflow 3.x — the `include_examples` parameter was removed; example DAG
loading is now controlled entirely via the
`AIRFLOW__CORE__LOAD_EXAMPLES` config/env var instead. Also updated all
4 DAG files to import `PythonOperator`/`BashOperator` from
`airflow.providers.standard.operators.*` instead of the deprecated
`airflow.operators.*` paths.

Verified via `pytest tests/` inside the scheduler container — all 6
tests pass: no import errors, expected DAGs present
(`hello_world`, `insightiq_data_validation`, `insightiq_category_summary`,
`insightiq_category_deep_dive`), correct tagging, no cycles, and the
expected task structure in `insightiq_data_validation`. Also ran with
`-W error::DeprecationWarning` to confirm no deprecation warnings
remain after the operator import fix.

**Edit:** None — used as-is.

---

## 2026-07-13 — Check remaining DAGs for deprecated imports

**Prompt:** "check the other DAGs for any remaining deprecated
imports."

**Output:** Grepped all import lines across the 4 DAG files.
`PostgresHook` already used the correct
`airflow.providers.postgres.hooks.postgres` path, and
`PythonOperator`/`BashOperator` were already fixed to
`airflow.providers.standard.operators.*` in the previous entry — no
other legacy paths (`airflow.contrib.*`, `airflow.operators.dummy`,
`airflow.hooks.postgres_hook`, etc.) found anywhere. Confirmed by
loading a `DagBag` over `dags/` inside the scheduler container under
`-W error::DeprecationWarning` — zero import errors, all 4 DAGs
(`hello_world`, `insightiq_data_validation`, `insightiq_category_summary`,
`insightiq_category_deep_dive`) load cleanly. No changes needed.

**Edit:** None — used as-is.

---

## 2026-07-14 — Add real ETL DAG and fix its DATABASE_URL inside Docker

**Prompt:** "Create `airflow/dags/insightiq_real_etl_dag.py` with 4
PythonOperator tasks (extract, transform+load, validate, LLM summary),
`extract_task` returning only row counts via XCom since DataFrames are
too large for it, `on_failure_callback=notify_failure`, `schedule=None`,
and tags `["insightiq", "etl", "real-pipeline"]`. Then, after a real run
failed with 'Connection refused' on `localhost:5544`: `transform_task`
calls `etl.load.get_engine()`, which reads `DATABASE_URL` from `.env` —
correctly `localhost:5544` for running outside Docker, but wrong inside
the Airflow containers where `localhost` refers to the container
itself. Fix by setting `DATABASE_URL` explicitly inside `transform_task`
before calling any `etl` functions, pointing at
`host.docker.internal:5544`."

**Output:** Added the DAG with `extract_task` (calls
`etl.extract.extract_all()`, returns only `{name: row_count}` via
XCom) and `transform_task` (re-extracts, since DataFrames can't cross
the XCom boundary, then runs `etl.transform` + `etl.load` in the same
task since those cleaned DataFrames never need to leave it, reusing
`_assign_key`/`_truncate_all` from `etl/run_pipeline.py`).
`validate_task` mirrors the row-count and orphaned-FK checks from
`insightiq_data_validation_dag.py` via `PostgresHook`. `summary_task`
calls Ollama the same way `dags/utils/alerting.py` does, summarizing
extract vs. loaded counts pulled from XCom. Required adding the
`/opt/insightiq` volume mount to `docker-compose.yaml` and `numpy` to
`requirements.txt`, plus test coverage for `notify_failure` itself
(`tests/test_alerting.py`) and a DAG-integrity check that it's wired
correctly (`test_failure_alerting_wired`).

Fixed the `DATABASE_URL` bug by setting
`os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@host.docker.internal:5544/insightiq"`
as the first line of `transform_task`, before any `etl.*` import —
`etl.load` resolves `DATABASE_URL` at module-import time via
`os.getenv`, and `python-dotenv`'s `load_dotenv()` doesn't override
already-set env vars, so the explicit override wins over `.env`'s
`localhost:5544`. `validate_task` needed no change since it only goes
through `PostgresHook`, never `etl.load`. Verified inside the running
worker container that `get_engine()` now resolves to
`host.docker.internal:5544`, and the full `pytest tests/` suite (10
tests) still passes.

**Edit:** None — used as-is.

---

## 2026-07-14 — Increase notify_failure's Ollama timeout

**Prompt:** "increase the timeout in `dags/utils/alerting.py`'s
`notify_failure()` from 15 to 30 seconds, since it timed out under
real load."

**Output:** Changed the `requests.post` call's `timeout` from `15` to
`30` in `dags/utils/alerting.py`. Ran `pytest tests/` inside the
worker container to confirm nothing else depended on the old value —
all 10 tests still pass.

**Edit:** None — used as-is.

---

## 2026-07-14 — Build insightiq_real_etl_dag.py against the real etl/ pipeline

**Prompt:** "Create `insightiq_real_etl_dag.py`, the first Airflow DAG
that calls the project's actual `etl/` pipeline code rather than
reimplementing that logic, with extract, transform+load, validate, and
LLM-summary tasks — then verify the full pipeline actually runs
end-to-end via direct task execution."

**Output:** Built `insightiq_real_etl_dag.py` as the first DAG that
calls the project's actual `etl/` pipeline code (`extract_all`,
`clean_orders`/`clean_customers`/`clean_sellers`/`clean_products`,
`build_fact_orders`, `_truncate_all`, `load_table`) instead of
reimplementing that logic inline. Solved the XCom dataframe-passing
limitation by having `extract_task` report only row counts (cheap XCom
metadata) while `transform_task` re-extracts locally and performs
transform+load in one task, since the large DataFrames it builds never
need to leave that task.

Hit and fixed a real bug: `etl.load.get_engine()` reads `DATABASE_URL`
from `.env` (`localhost:5544`, correct for running outside Docker),
which resolves incorrectly inside the Airflow container since
"localhost" there refers to the container itself. Fixed by overriding
`DATABASE_URL` to `host.docker.internal:5544` at task runtime, before
any `etl.*` import.

Also hit the same recurring stopped-Postgres-container issue seen in
earlier sessions — the third occurrence today — suggesting the Mac's
sleep behavior is bypassing the `unless-stopped` restart policy
regardless of container config; worth investigating separately from
the DAG itself.

Verified the full pipeline (102,425 `fact_orders` rows) via direct
execution as Airflow tasks: extract -> transform+load -> validate
(referential integrity) -> LLM-generated run summary.

**Edit:** None — used as-is.

---

## 2026-07-14 — Chain insightiq_real_etl into insightiq_data_validation

**Prompt:** "Chain `insightiq_real_etl_dag.py` to
`insightiq_data_validation_dag.py` using `TriggerDagRunOperator`, so a
successful ETL run automatically triggers downstream validation instead
of relying on separate schedules or manual triggers."

**Output:** Added a `trigger_validation` task to
`insightiq_real_etl_dag.py` using
`airflow.providers.standard.operators.trigger_dagrun.TriggerDagRunOperator`
with `trigger_dag_id="insightiq_data_validation"`, appended to the end
of the existing chain: `extract >> transform >> validate >> summary >>
trigger_validation`. Left it fire-and-forget (no
`wait_for_completion`/`failed_states`) — the ETL run is considered
successful once validation has been *triggered*, not once it has
*passed*.

Chose `TriggerDagRunOperator` over merging validation's checks directly
into the ETL DAG because it keeps `insightiq_data_validation`
independently schedulable and testable (it already has its own
`schedule=None`/manual-trigger history and its own DagBag/pytest
coverage) rather than folding those checks into one growing monolithic
DAG. It also leaves the door open for validation to run on its own
cadence later — e.g. a periodic schedule in addition to the ETL-triggered
run — without restructuring the ETL DAG again.

Verified by triggering `insightiq_real_etl` and confirming a new
automatic run appeared in `insightiq_data_validation`'s Dag Runs
immediately after the ETL run's `summary_task` completed.

**Edit:** None — used as-is.

---

## 2026-07-14 — Add execution_timeout and doc_md across all DAGs

**Prompt:** "Add `execution_timeout=timedelta(minutes=15)` to the
`extract_task` and `transform_task` in `insightiq_real_etl_dag.py` as a
safety net against runaway tasks. Add `doc_md` to the top of every DAG
in `airflow/dags/` — a short markdown description of what each DAG
does, its schedule, and any notable design decisions — so it renders in
the Airflow UI's DAG details page."

**Output:** Added `execution_timeout=timedelta(minutes=15)` to both
`extract_task` and `transform_task` in `insightiq_real_etl_dag.py`
(the two tasks that touch the CSV extract and the Postgres load, the
most likely places for a hang) — `validate_task` and `summary_task`
were left without one since they're bounded, cheap operations.

Added a `doc_md` to all 6 DAGs' `DAG(...)` constructors, each covering
purpose, trigger/schedule, and the one or two design decisions worth
calling out for a reader in the UI rather than the source: dynamic
task mapping in `insightiq_category_deep_dive`, `mode="reschedule"` in
`insightiq_sensor_demo`, the DAG-to-DAG `TriggerDagRunOperator` chain
between `insightiq_real_etl` and `insightiq_data_validation`, and the
defensive `pd.to_numeric` cast in `insightiq_category_summary`.

Verified via `pytest tests/` inside the worker container — all 10
tests pass (DagBag import errors, DAG presence, tagging, no cycles,
task structure), confirming every DAG still parses cleanly with the
added `doc_md` and `execution_timeout` kwargs.

**Edit:** None — used as-is.

---

## 2026-07-13 to 2026-07-14 — Airflow build, two-day summary

**Scope:** Stood up Apache Airflow 3.3.0 via Docker Compose alongside the
existing n8n/Postgres/Ollama stack and built out 6 DAGs, each
demonstrating a distinct orchestration pattern rather than duplicating
the same kind of task:

- `hello_world` — proof of concept confirming the Compose stack itself
  works.
- `insightiq_data_validation` — 4 independent checks (null FKs,
  duplicate order-product rows, review-score range, freight outliers)
  run in parallel with results pushed to XCom.
- `insightiq_category_summary` — pandas transformation (groupby
  aggregation over `fact_orders`/`dim_product`, written back via
  `to_sql`).
- `insightiq_category_deep_dive` — dynamic task mapping,
  `PythonOperator.partial(...).expand(...)` over a runtime-determined
  list of top categories.
- `insightiq_sensor_demo` — `PythonSensor` in `mode="reschedule"`,
  demonstrating the poll/release pattern that avoids starving other DAGs
  of worker slots.
- `insightiq_real_etl` — the real pipeline, the first DAG to call the
  project's actual `etl/` package instead of reimplementing it, ending
  in a `TriggerDagRunOperator` that chains into
  `insightiq_data_validation` as its own DagRun.

Added `tests/test_dag_integrity.py` (`DagBag`-based: import errors, DAG
presence, tagging, no cycles, failure-alerting wiring, task structure) —
10 tests passing by the end of the two days. Wired LLM-based failure
alerting (`dags/utils/alerting.py::notify_failure`, calling local
Ollama for a 1-2 sentence plain-English alert) onto every DAG handling
real data, reusing the same Ollama-summary pattern already proven out in
the n8n workflows rather than inventing a second alerting approach.
Closed out with `airflow/README.md`, documenting all 6 DAGs, the
`insightiq_postgres` Connection setup, the `host.docker.internal`
container-networking pattern, and known limitations honestly (unused
`great-expectations` dependency, alerting that only reaches task logs
rather than a real notification channel, fire-and-forget DAG triggering).

**Real bugs found and fixed along the way, not just features added:**

- **Recurring stopped-Postgres-container issue (3 occurrences across the
  two days).** The project's Postgres container kept coming up stopped,
  breaking any DAG that touched `insightiq_postgres`. Worked around each
  time by restarting it; root cause suspected to be the Mac's sleep
  behavior bypassing Docker's `unless-stopped` restart policy, flagged
  as worth a dedicated investigation rather than patched blindly three
  times.
- **`pd.to_numeric(errors="coerce")` masked a deeper issue.** A
  `TypeError` on `.round()` in `insightiq_category_summary` was first
  patched by coercing to numeric before rounding — which fixed the
  crash but not the actual problem: `avg_review_score` was `NULL` for
  every row. Chasing that down (rather than accepting the coercion fix
  as sufficient) surfaced the real bug below.
- **Root-cause missing join in `etl/transform.py`.** `fact_orders.review_score`
  was hardcoded to `None` for all 102,425 rows, per a comment noting it
  was a placeholder "to be filled by a later enrichment step" that was
  never built — even though the real review scores were already being
  extracted from `olist_order_reviews_dataset.csv` and just never joined
  in. Fixed by joining `reviews` into `build_fact_orders()` (most-recent
  submission per `order_id` for the 551 orders with multiple reviews),
  which corrected `avg_review_score` warehouse-wide, not just in the one
  DAG that surfaced it.
- **`DATABASE_URL` host-resolution mismatch, host vs. container.**
  `etl.load.get_engine()` reads `DATABASE_URL` from `.env`
  (`localhost:5544`), correct when running the ETL pipeline on the host
  but wrong inside the Airflow containers, where `localhost` resolves to
  the container itself. Fixed in `insightiq_real_etl_dag.py`'s
  `transform_task` by overriding `DATABASE_URL` to
  `host.docker.internal:5544` before any `etl.*` module is imported —
  documented in `airflow/README.md` as a networking gotcha rather than
  left as a one-off code comment.

**Edit:** None — used as-is.
