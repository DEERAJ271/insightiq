Summarize the local-testing strategy used during development, for
inclusion in the portfolio README or an interview answer:

1. Count how many distinct test runs happened via nl2sql-test, rag-health,
   routing-test, nl2sql-local-test, and chatbot-local-test commands this
   session (check terminal history / dev-logs/prompts.md if available)
2. Estimate how many of those would have been real Anthropic API calls
   if local/offline testing hadn't been used instead (roughly: each
   nl2sql-local-test run = 3 calls avoided, each chatbot-local-test run
   = 4 calls avoided, etc.)
3. State plainly: local Ollama testing validates PIPELINE correctness
   (routing logic, schema context, execution, error handling) for free;
   it does NOT validate final answer quality, which still requires the
   production model. Be explicit that this is a development-cost
   optimization, not a claim that Ollama output was verified as correct.
4. Write a 3-sentence summary suitable for a README section titled
   "Development approach" — plain, factual, no overselling.

Append this summary to dev-logs/prompts.md as a dedicated entry.
