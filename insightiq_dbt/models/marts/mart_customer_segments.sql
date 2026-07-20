-- Mart model: RFM customer segments, exposed as-is for lineage/testing
-- (already aggregated per customer by the insightiq_rfm_segmentation DAG)
select
    customer_key,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    rfm_segment,
    segment_label
from {{ source('insightiq', 'customer_rfm_segments') }}
