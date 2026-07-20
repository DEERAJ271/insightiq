-- Mart model: order and revenue performance aggregated per product category
with orders as (

    select *
    from {{ ref('stg_fact_orders') }}

),

products as (

    select *
    from {{ source('insightiq', 'dim_product') }}

),

orders_with_category as (

    select
        orders.order_key,
        orders.price,
        orders.freight_value,
        products.category
    from orders
    left join products
        on orders.product_key = products.product_key

)

select
    coalesce(category, 'unknown') as category,
    count(order_key) as order_count,
    avg(price) as avg_price,
    avg(freight_value) as avg_freight,
    sum(price) as total_revenue
from orders_with_category
group by category
