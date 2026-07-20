-- Custom singular test (dbt_utils not installed): breach_percentage must
-- fall within the valid 0-100 percentage range. Passes when it returns
-- zero rows.
select *
from {{ ref('mart_delivery_performance') }}
where breach_percentage < 0
   or breach_percentage > 100
