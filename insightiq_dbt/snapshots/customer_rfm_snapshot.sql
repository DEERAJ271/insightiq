{#
    SCD Type 2 snapshot of customer_rfm_segments.

    Every other table in this project is materialized with
    if_exists="replace" (Python/pandas loads) or TRUNCATE + re-insert
    (see insightiq_rfm_segmentation_dag.py) — each run overwrites prior
    state, so there is no history to query. A dbt snapshot works
    differently: on each `dbt snapshot` run it diffs the source rows
    against what's already in the snapshot table and, instead of
    overwriting a changed row, closes out the old version
    (dbt_valid_to = now) and inserts a new one (dbt_valid_from = now,
    dbt_valid_to = null). That makes this the one table in the project
    where "what was customer X's segment last month" is answerable —
    everywhere else that answer no longer exists once the next load
    truncates it away.

    Strategy: check (via check_cols) instead of timestamp, because
    customer_rfm_segments (written by insightiq_rfm_segmentation_dag)
    has no updated_at/modified_at column — it's a full truncate +
    append every run, so there's no reliable per-row timestamp to key
    off of. check_cols lists which columns to compare on each snapshot
    run; the row is versioned whenever segment_label or monetary changes.
#}

{% snapshot customer_rfm_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='customer_key',
      strategy='check',
      check_cols=['segment_label', 'monetary'],
    )
}}

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

{% endsnapshot %}
