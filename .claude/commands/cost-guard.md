Before running any code that calls the Anthropic API (generate_sql(),
chatbot.answer(), or anything using the Anthropic client), do a dry-run
safety check:
1. Scan the target file/function for loops that could call the API
   multiple times (e.g. iterating over a list of test questions without
   a limit or confirmation step)
2. Confirm max_tokens is set on every API call (uncapped calls can run
   longer/cost more than expected)
3. Report how many total API calls the current test/script would make if
   run as-is
4. If the count is more than 3, ask for explicit confirmation before
   proceeding, and suggest reducing to a smaller sample first

This is a safety check only — don't modify any files, just report findings
and ask before any code that matches this pattern is actually executed.
