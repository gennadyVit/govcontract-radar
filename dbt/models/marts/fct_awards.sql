{{ config(materialized='table', schema='MARTS') }}

with source as (
    select * from GOVCONTRACT.RAW.STG_USASPENDING_AWARDS
),

dim_agency as (
    select * from GOVCONTRACT.DIMENSIONS.DIM_AGENCY
),

dim_vendor as (
    select * from GOVCONTRACT.DIMENSIONS.DIM_VENDOR
),

cleaned as (
    select
        s.AWARD_ID,
        s.INTERNAL_ID,

        -- FK to dim_agency (replaces raw agency text)
        a.AGENCY_ID,

        -- FK to dim_vendor (replaces raw recipient text)
        v.VENDOR_ID,

        s.AWARD_AMOUNT,
        case
            when s.AWARD_AMOUNT >= 1000000 then 'Large'
            when s.AWARD_AMOUNT >= 100000  then 'Medium'
            else 'Small'
        end as AWARD_SIZE_CATEGORY,

        s.DESCRIPTION,
        s.AWARD_TYPE,
        s.NAICS_CODE,
        s.IS_SMALL_BUSINESS_AWARD,
        s.SOURCE_ALL_MARKET_PULL,
        s.SOURCE_SMALL_BUSINESS_PULL,
        s.START_DATE,
        s.END_DATE,
        DATEDIFF('day', s.START_DATE, s.END_DATE) as CONTRACT_LENGTH_DAYS,
        s.POP_COUNTRY_CODE,
        s.POP_STATE_CODE,
        s.LOADED_AT

    from source s
    left join dim_agency a
        on a.AGENCY_NAME  = s.AWARDING_AGENCY
        and a.SUB_AGENCY_NAME = s.AWARDING_SUB_AGENCY
    left join dim_vendor v
        on v.VENDOR_NAME = s.RECIPIENT_NAME
    where s.AWARD_AMOUNT is not null
)

select * from cleaned
