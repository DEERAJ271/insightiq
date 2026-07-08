Run a full readiness check on the InsightIQ project before it's shown to
anyone. Go through each item, report PASS/FAIL/WARN, and don't fix
anything automatically — just report:

1. Security: re-run the checks from security-check.md (no exposed
   credentials anywhere in tracked files or git history)
2. Data integrity: summarize the latest validate.py results (referential
   integrity, duplicates, business rule violations)
3. RAG index: confirm it exists, has content indexed, and isn't stale
   relative to the latest schema.sql (flag if schema was edited after
   the index was last built)
4. Reproducibility: can a fresh clone of this repo actually be set up by
   following README.md alone? Check for any undocumented manual steps
   this session relied on that aren't written down anywhere
5. Dev log: confirm dev-logs/prompts.md has entries covering the major
   phases (ETL, RAG, NL2SQL, chatbot) — flag any major session that
   doesn't have a corresponding entry
6. Git hygiene: uncommitted changes, meaningful commit messages, no
   large data files accidentally tracked
7. Known gaps: list anything still marked TODO in code or the README
   status checklist that a recruiter might reasonably ask about

End with a short summary: is this demo-ready, and if not, what's the
single highest-priority fix before showing it to anyone.
