{{ config(materialized='table', schema='DIMENSIONS') }}

with sam_agencies as (
    select distinct
        SPLIT_PART(AGENCY, '.', 1) as AGENCY_NAME,
        SUB_AGENCY as SUB_AGENCY_NAME
    from GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES
    where AGENCY is not null
),

award_agencies as (
    select distinct
        AWARDING_AGENCY as AGENCY_NAME,
        AWARDING_SUB_AGENCY as SUB_AGENCY_NAME
    from GOVCONTRACT.RAW.STG_USASPENDING_AWARDS
    where AWARDING_AGENCY is not null
),

combined as (
    select * from sam_agencies
    union
    select * from award_agencies
),

deduped as (
    select distinct
        AGENCY_NAME,
        SUB_AGENCY_NAME
    from combined
)

select
    MD5(COALESCE(AGENCY_NAME, '') || '|' || COALESCE(SUB_AGENCY_NAME, '')) as AGENCY_ID,
    AGENCY_NAME,
    SUB_AGENCY_NAME
from deduped
