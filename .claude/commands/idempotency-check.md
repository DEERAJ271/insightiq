Verify the ETL pipeline can be safely re-run without corrupting or
duplicating data:
1. Record current row counts for all tables (fact_orders, dim_customer,
   dim_product, dim_seller, dim_date)
2. Run python -m etl.run_pipeline a second time
3. Record row counts again
4. Compare — counts should be IDENTICAL after a re-run (the pipeline
   truncates before reloading, per the FK-safe truncation logic added
   earlier). Flag if any table's count changed, grew, or shrank
   unexpectedly
5. Also confirm surrogate keys reset correctly (RESTART IDENTITY worked)
   by checking that customer_key, product_key etc. start from 1 again
   after the re-run, not continuing from where they left off

Report: before/after counts per table, pass/fail on identical counts,
pass/fail on key reset.
