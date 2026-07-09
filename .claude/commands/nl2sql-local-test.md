Create a temporary local-only variant to test the NL2SQL flow using Ollama
instead of the Anthropic API (no credits spent):
1. Write a scratch script (not committed, or clearly marked as a local
   dev tool) that mirrors generate_sql() in llm/nl2sql.py but calls
   http://localhost:11434/api/generate with model="llama3.2" instead of
   the Anthropic client, using the same SYSTEM_PROMPT and SCHEMA_SUMMARY
2. Run it against 3 questions: "What is the average order value by
   product category?", "How many orders had a delivery SLA breach?",
   "What is the repeat customer rate?"
3. For each: print the generated SQL, then actually run it through
   run_query() from nl2sql.py against the real database
4. Report whether the SQL was syntactically valid, whether it ran without
   error, and whether the result looks plausible

Note clearly that llama3.2 is a much weaker model than what production
will use — the goal here is testing the PIPELINE (prompt formatting,
schema context, execution, error handling), not judging final SQL
quality. Flag this distinction in the report.
