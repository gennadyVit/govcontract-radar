{{
    config(
        materialized='incremental',
        unique_key='NOTICE_ID',
        schema='AGENTS'
    )
}}

/*
  One row per opportunity per agent run.
  The agent worker populates DECISION and ACTION_TAKEN after this shell is created by dbt.
  dbt creates the table structure; the Python agent writes the decision columns.
*/

select
    o.NOTICE_ID,
    o.TITLE,
    o.NAICS_CODE,
    o.NAICS_DESCRIPTION,
    o.AGENCY_NAME,
    o.SET_ASIDE,
    o.DAYS_UNTIL_DEADLINE,
    o.DEADLINE_CATEGORY,
    o.RESPONSE_DEADLINE,
    o.POSTED_DATE,
    o.NAICS_SB_WIN_RATE_PCT,
    o.NAICS_MEDIAN_AWARD_AMOUNT,

    -- agent outputs (written by Python agent, NULL until agent runs)
    NULL::VARCHAR      as DECISION,           -- PURSUE | WATCH | NO_BID | HUMAN_REVIEW
    NULL::FLOAT        as FIT_SCORE,          -- 0-100
    NULL::VARCHAR      as ACTION_TAKEN,       -- archive_with_reason | generate_full_capture_package | generate_short_summary | flag_uncertain_extraction
    NULL::VARCHAR      as EXCLUSION_REASON,   -- populated when DECISION = NO_BID
    NULL::BOOLEAN      as REPORT_GENERATED,
    NULL::TIMESTAMP_NTZ as DECIDED_AT,
    NULL::VARCHAR      as AGENT_RUN_ID,

    o.LOADED_AT

from {{ ref('mart_opportunity_features') }} o

{% if is_incremental() %}
where o.LOADED_AT > (select MAX(LOADED_AT) from {{ this }})
{% endif %}
