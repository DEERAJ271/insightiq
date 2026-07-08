Compare the live Postgres schema against sql/schema.sql to catch drift:
1. Query information_schema.columns for each table defined in schema.sql
   (fact_orders, dim_customer, dim_product, dim_seller, dim_date,
   business_glossary)
2. Compare column names, types, and nullability against what schema.sql
   declares
3. Flag any column that exists in the live DB but not in schema.sql (or
   vice versa) — this catches manual ALTER TABLE calls that were never
   reflected back in the source file
4. Also check indexes: confirm idx_fact_orders_customer,
   idx_fact_orders_product, idx_fact_orders_order_date all exist

Report as a table: table.column, in schema.sql, in live DB, match/drift.
