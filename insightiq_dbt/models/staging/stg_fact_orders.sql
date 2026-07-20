-- Staging model: light cleaning/renaming, one-to-one with the source table
select
    order_key,
    order_id,
    customer_key,
    product_key,
    seller_key,
    order_date_key,
    delivered_date_key,
    estimated_date_key,
    order_status,
    price,
    freight_value,
    payment_type,
    payment_installments,
    review_score,
    item_count
from {{ source('insightiq', 'fact_orders') }}
