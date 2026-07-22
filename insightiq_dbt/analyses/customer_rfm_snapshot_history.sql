-- Sample query: customers whose segment_label or monetary has changed
-- across snapshot runs (SCD Type 2 history), oldest version first.
-- A customer with only one row here has never had a tracked change —
-- dbt_valid_to = null means that row is the current version.
select
    customer_key,
    segment_label,
    monetary,
    dbt_valid_from,
    dbt_valid_to,
    dbt_valid_to is null as is_current
from {{ ref('customer_rfm_snapshot') }}
where customer_key in (
    select customer_key
    from {{ ref('customer_rfm_snapshot') }}
    group by customer_key
    having count(*) > 1
)
order by customer_key, dbt_valid_from
