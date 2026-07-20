-- Mart model: SLA delivery performance (delivered after estimated date) per state
with orders as (

    select *
    from {{ ref('stg_fact_orders') }}

),

customers as (

    select *
    from {{ source('insightiq', 'dim_customer') }}

),

orders_with_state as (

    select
        orders.order_key,
        orders.delivered_date_key,
        orders.estimated_date_key,
        customers.state
    from orders
    left join customers
        on orders.customer_key = customers.customer_key

)

select
    state,
    count(order_key) as total_orders,
    count(*) filter (
        where delivered_date_key > estimated_date_key
    ) as breach_count,
    round(
        100.0 * count(*) filter (where delivered_date_key > estimated_date_key)
        / nullif(count(order_key), 0),
        2
    ) as breach_percentage
from orders_with_state
group by state
