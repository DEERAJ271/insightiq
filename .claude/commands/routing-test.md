Test the needs_sql() routing logic in llm/chatbot.py WITHOUT calling the
Anthropic API. Read the function, then run it against a list of at least
10 sample questions covering:
- Clearly numeric (should route to NL2SQL): "how many orders were placed
  last month", "what is the average order value", "total revenue by state"
- Clearly definitional (should route to RAG): "what counts as a repeat
  customer", "what does SLA breach mean", "explain the AOV metric"
- Ambiguous/hybrid cases that could go either way: "what's our repeat
  customer rate and what counts as repeat", "how many products have no
  category and why does that happen"

For each question print: the question, which path it routed to, and
whether that routing seems correct. Summarize accuracy as a fraction
(e.g. 8/10 correct). Flag the hybrid cases specifically, since the
current router can only pick one path — note whether the current
NUMERIC_KEYWORDS list is too broad, too narrow, or missing obvious terms.
