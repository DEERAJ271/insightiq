-- Sample analytical queries — good candidates to also expose via the NL2SQL layer.

-- 1. Monthly revenue trend
SELECT d.year, d.month, SUM(f.price) AS revenue
FROM fact_orders f
JOIN dim_date d ON f.order_date_key = d.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- 2. Average order value by product category
SELECT p.category, ROUND(AVG(f.price), 2) AS avg_order_value, COUNT(*) AS n_orders
FROM fact_orders f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY avg_order_value DESC;

-- 3. Delivery SLA breach rate by state
SELECT c.state,
       ROUND(100.0 * SUM(CASE WHEN f.delivered_date_key > f.estimated_date_key THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS sla_breach_pct
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.state
ORDER BY sla_breach_pct DESC;

-- 4. Repeat customer rate
-- NOTE: always returns 0% on this dataset. customer_id here is order-scoped
-- (one customer row per order), not a persistent shopper ID carried across
-- repeat purchases, so no customer_key can ever have order_count > 1. This
-- is a dataset limitation, not a query bug — see dev-logs/prompts.md and
-- airflow/README.md's RFM segmentation DAG for the same quirk.
SELECT
    COUNT(*) FILTER (WHERE order_count > 1) AS repeat_customers,
    COUNT(*) AS total_customers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE order_count > 1) / COUNT(*), 2) AS repeat_rate_pct
FROM (
    SELECT customer_key, COUNT(DISTINCT order_id) AS order_count
    FROM fact_orders
    GROUP BY customer_key
) t;

-- 5. Review score vs delivery delay
SELECT f.review_score,
       ROUND(AVG(d2.full_date - d1.full_date), 1) AS avg_delivery_days
FROM fact_orders f
JOIN dim_date d1 ON f.order_date_key = d1.date_key
JOIN dim_date d2 ON f.delivered_date_key = d2.date_key
WHERE f.review_score IS NOT NULL
GROUP BY f.review_score
ORDER BY f.review_score;

-- 6. RFM segment summary
SELECT segment_label,
       COUNT(*) AS customers,
       ROUND(AVG(recency_days)::numeric, 1) AS avg_recency,
       ROUND(AVG(frequency)::numeric, 2) AS avg_frequency,
       ROUND(AVG(monetary)::numeric, 2) AS avg_spend,
       ROUND(SUM(monetary)::numeric, 2) AS total_revenue
FROM customer_rfm_segments
GROUP BY segment_label
ORDER BY total_revenue DESC;
