{{ config(materialized='table', schema='MARTS') }}

with source as (
    select * from GOVCONTRACT.RAW.STG_USASPENDING_AWARDS
),

cleaned as (
    select
        AWARD_ID,
        INTERNAL_ID,
        RECIPIENT_NAME,
        AWARD_AMOUNT,
        DESCRIPTION,
        AWARDING_AGENCY,
        AWARDING_SUB_AGENCY,
        AWARD_TYPE,
        START_DATE,
        END_DATE,
        DATEDIFF('day', START_DATE, END_DATE) as CONTRACT_LENGTH_DAYS,
        POP_COUNTRY_CODE,
        POP_STATE_CODE,
        LOADED_AT

    from source
    where AWARD_AMOUNT is not null
)

select * from cleaned
