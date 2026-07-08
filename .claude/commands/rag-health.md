Sanity-check the RAG index without needing an LLM call:
1. Read rag/build_index.py and rag/query_engine.py to confirm the
   persist directory (CHROMA_PERSIST_DIR) matches between build and query
2. Load the Chroma vectorstore directly and report: total chunk count,
   breakdown by metadata source (schema_docs vs glossary), and print the
   first ~100 chars of each chunk so content can be eyeballed
3. Run retrieve_context() against 3 sample questions that should map to
   different chunks: one clearly schema-related ("what columns does
   fact_orders have"), one clearly glossary-related ("what is AOV"), and
   one ambiguous one ("what does SLA breach mean for delivery")
4. Flag if any query returns 0 results, returns near-duplicate chunks, or
   returns content that doesn't match the question at all

Report as a table: query, top result source, top result snippet, verdict
(relevant / irrelevant / empty).
