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
