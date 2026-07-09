Compare SQL generation quality between local Ollama (llama3.2) and, if
ANTHROPIC_API_KEY has available credits, Claude — using the exact same
SYSTEM_PROMPT from llm/nl2sql.py for both, no modifications.

1. First check if the Anthropic API call would succeed (a trivial 1-token
   test call). If it fails due to credits, run ONLY the Ollama side and
   clearly report that the comparison is one-sided until credits are
   available — don't skip the exercise, just note the gap.
2. For 3 questions ("average order value by category", "SLA breach rate
   by state", "repeat customer rate"), generate SQL with both models
   (or just Ollama if Anthropic isn't available)
3. Compare: does the SQL follow the same join pattern, does it use the
   correct aggregate functions, does it reference real column names
4. If both are available: report which model produced more correct SQL,
   and whether the SYSTEM_PROMPT needs to be more explicit/structured to
   help the weaker model (useful signal for prompt robustness generally)

This is a diagnostic exercise, not a benchmark to include in the
portfolio as-is — llama3.2 vs Claude Sonnet isn't a fair fight, the value
is in seeing WHERE the weaker model breaks down (ambiguous instructions,
missing few-shot examples) since that reveals prompt weaknesses that
would also affect edge cases in production.
