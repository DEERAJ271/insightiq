Generate a data quality profile for the warehouse, the kind a data analyst
would hand to a stakeholder before trusting a dashboard built on it:

For fact_orders, dim_customer, dim_product, dim_seller:
1. Row count and null rate per column (as a percentage)
2. For numeric columns (price, freight_value, review_score,
   payment_installments, item_count): min, max, mean, and flag any
   suspicious outliers (e.g. negative prices, review_score outside 1-5)
3. For categorical columns (category, state, city, payment_type):
   distinct value count, and the top 5 most frequent values with their
   share of total rows
4. For dim_date: confirm the date range covers what's expected (no gaps
   in the day sequence)

Present as a concise table per table, not raw dumps. End with a 3-bullet
summary of anything that looks like a genuine data quality concern versus
expected/benign (e.g. a 1.4% uncategorized product bucket is benign and
already explained; a column that's 40% null is not).
