Create a temporary local-only variant of llm/chatbot.py's answer() function
that swaps the Anthropic client for a call to
http://localhost:11434/api/generate with model="llama3.2" — keep the
routing logic (needs_sql), the RAG retrieval call, and the NL2SQL call
exactly as-is, just swap the final composition LLM call.

Run it against 4 questions covering all routing paths:
1. "What is the average order value by product category?" (numeric → NL2SQL)
2. "What counts as a repeat customer?" (definitional → RAG)
3. "What's our repeat customer rate?" (numeric, tests if RAG-sounding
   phrasing routes correctly)
4. "How many orders were delivered late?" (numeric, tests SLA breach path)

For each: print which path it routed to, the context it retrieved/
generated, and the final composed answer. Flag anything where the answer
doesn't actually reflect the context it was given (a sign of poor
grounding), or where routing sent it down the wrong path.

Note this tests PIPELINE correctness (routing, data flow, composition),
not final answer quality — llama3.2 is much weaker than the production
model. Don't commit the scratch script; treat it as disposable.
