Run the project's pytest suite and report results cleanly:
1. Run pytest tests/ -v and capture full output
2. Report: total tests, passed, failed, skipped
3. For any failure, show the specific assertion that failed and a
   one-line diagnosis of the likely cause
4. Check test coverage gaps — scan etl/, rag/, llm/ for functions that
   have no corresponding test in tests/, and list the top 3 most
   important untested functions (prioritize by how much downstream logic
   depends on them, e.g. build_fact_orders matters more than a small
   helper)

End with a one-line verdict: is the test suite in good enough shape to
call this project "tested," or is it thin coverage that shouldn't be
oversold as such.
