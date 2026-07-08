Test the NL2SQL execution layer in llm/nl2sql.py WITHOUT calling the
Anthropic API (to avoid burning credits). Do this by:
1. Temporarily hardcoding 2-3 known-correct SQL queries (pulled from
   sql/analytical_queries.sql) in place of generate_sql() output
2. Running each through run_query() and printing the resulting DataFrame
3. Cross-checking the numeric results against directly running the same
   query via docker exec against insightiq-pg

Report: does run_query() correctly reject non-SELECT statements, does the
SQLAlchemy connection work, do results match the direct psql query. This
validates the database/execution path independent of the LLM's SQL
generation quality.
