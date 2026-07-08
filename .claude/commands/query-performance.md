Run EXPLAIN ANALYZE on each query in sql/analytical_queries.sql against
the live database to check performance and index usage:
1. For each of the 5 queries, run EXPLAIN ANALYZE and capture execution
   time and whether it used an index scan or fell back to a sequential
   scan on fact_orders (112k+ rows — seq scans here are a red flag)
2. Cross-reference against the indexes defined in sql/schema.sql
   (idx_fact_orders_customer, idx_fact_orders_product,
   idx_fact_orders_order_date) — confirm they're actually being used
   where relevant
3. Flag any query taking more than ~200ms or doing a full seq scan when
   an index exists that should have been used
4. If a query would benefit from an index that doesn't exist yet, suggest
   the exact CREATE INDEX statement (but don't run it without confirmation)

Report as a table: query #, execution time, scan type, verdict, suggested
fix if any.
