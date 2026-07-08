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
