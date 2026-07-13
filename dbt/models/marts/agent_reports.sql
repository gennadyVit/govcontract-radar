{{
    config(
        materialized='incremental',
        unique_key='NOTICE_ID',
        schema='AGENTS'
    )
}}

/*
  Stores GPT-4o generated artifacts per opportunity.
  Populated by the agent worker after DECISION = PURSUE or WATCH.
  dbt creates the schema; Python agent writes the content columns.
*/

select
    d.NOTICE_ID,
    d.AGENT_RUN_ID,

    -- generated artifacts (written by Python agent)
    NULL::VARCHAR   as BID_NO_BID_MEMO,         -- full GPT-4o markdown memo
    NULL::VARCHAR   as COMPLIANCE_MATRIX,        -- JSON: [{requirement, status, gap}]
    NULL::VARCHAR   as MISSING_REQUIREMENTS,     -- JSON array of missing items
    NULL::VARCHAR   as CO_QUESTIONS,             -- suggested questions for contracting officer
    NULL::VARCHAR   as ACTION_ITEMS,             -- JSON array of next steps
    NULL::VARCHAR   as SHORT_SUMMARY,            -- 2-3 sentence summary (WATCH decisions)
    NULL::TIMESTAMP_NTZ as GENERATED_AT,

    d.DECIDED_AT,
    d.LOADED_AT

from {{ ref('agent_decisions') }} d
where d.DECISION in ('PURSUE', 'WATCH')

{% if is_incremental() %}
and d.LOADED_AT > (select MAX(LOADED_AT) from {{ this }})
{% endif %}
