{{
    config(
        materialized='table',
        schema='MARTS',
        post_hook="comment on table {{ this }} is 'Denormalized scoring-ready table: one row per opportunity with pre-computed market features from historical awards. Consumers (scoring engine, dashboard) read this instead of joining 5 tables at query time.'"
    )
}}

/*
  Denormalization intent: pre-join and pre-aggregate all features needed by the
  scoring engine so it reads one row per opportunity instead of re-deriving
  market stats at query time.

  Market stats are joined on NAICS_CODE only (not agency) because SAM.gov and
  USASpending use different agency name formats, making cross-source AGENCY_ID
  joins unreliable at this stage.
*/

with opportunities as (
    select * from {{ ref('fct_opportunities') }}
),

awards as (
    select * from {{ ref('fct_awards') }}
),

naics as (
    select * from {{ ref('dim_naics') }}
),

-- pre-aggregate market stats per NAICS code from historical awards
naics_market_stats as (
    select
        NAICS_CODE,
        COUNT(*)                                                    as TOTAL_AWARDS,
        COUNT(DISTINCT VENDOR_ID)                                   as UNIQUE_VENDORS,
        MEDIAN(AWARD_AMOUNT)                                        as MEDIAN_AWARD_AMOUNT,
        AVG(AWARD_AMOUNT)                                           as AVG_AWARD_AMOUNT,
        MIN(AWARD_AMOUNT)                                           as MIN_AWARD_AMOUNT,
        MAX(AWARD_AMOUNT)                                           as MAX_AWARD_AMOUNT,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY AWARD_AMOUNT) as P25_AWARD_AMOUNT,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY AWARD_AMOUNT) as P75_AWARD_AMOUNT,
        AVG(CONTRACT_LENGTH_DAYS)                                   as AVG_CONTRACT_LENGTH_DAYS,
        SUM(CASE WHEN IS_SMALL_BUSINESS_AWARD = TRUE THEN 1 ELSE 0 END) as SB_AWARD_COUNT,
        ROUND(
            SUM(CASE WHEN IS_SMALL_BUSINESS_AWARD = TRUE THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0) * 100, 1
        )                                                           as SB_WIN_RATE_PCT
    from awards
    where AWARD_AMOUNT is not null
    group by NAICS_CODE
)

-- one row per opportunity, enriched with market context
select
    -- opportunity identifiers
    o.NOTICE_ID,
    o.TITLE,
    o.SOLICITATION_NUM,
    o.UI_LINK,

    -- agency
    o.AGENCY_ID,
    o.AGENCY_NAME,
    o.SUB_AGENCY_NAME,

    -- classification
    o.NAICS_CODE,
    n.NAICS_DESCRIPTION,
    o.NOTICE_TYPE,
    o.SET_ASIDE,

    -- timing
    o.POSTED_DATE,
    o.RESPONSE_DEADLINE,
    o.DAYS_UNTIL_DEADLINE,
    o.DEADLINE_CATEGORY,

    -- location
    o.OFFICE_CITY,
    o.OFFICE_STATE,

    -- market features from historical awards (NAICS-level)
    m.TOTAL_AWARDS                  as NAICS_TOTAL_AWARDS,
    m.UNIQUE_VENDORS                as NAICS_UNIQUE_VENDORS,
    m.MEDIAN_AWARD_AMOUNT           as NAICS_MEDIAN_AWARD_AMOUNT,
    m.AVG_AWARD_AMOUNT              as NAICS_AVG_AWARD_AMOUNT,
    m.MIN_AWARD_AMOUNT              as NAICS_MIN_AWARD_AMOUNT,
    m.MAX_AWARD_AMOUNT              as NAICS_MAX_AWARD_AMOUNT,
    m.P25_AWARD_AMOUNT              as NAICS_P25_AWARD_AMOUNT,
    m.P75_AWARD_AMOUNT              as NAICS_P75_AWARD_AMOUNT,
    m.AVG_CONTRACT_LENGTH_DAYS      as NAICS_AVG_CONTRACT_LENGTH_DAYS,
    m.SB_AWARD_COUNT                as NAICS_SB_AWARD_COUNT,
    m.SB_WIN_RATE_PCT               as NAICS_SB_WIN_RATE_PCT,

    o.LOADED_AT

from opportunities o
left join naics_market_stats m on o.NAICS_CODE = m.NAICS_CODE
left join naics n on o.NAICS_CODE = n.NAICS_CODE
