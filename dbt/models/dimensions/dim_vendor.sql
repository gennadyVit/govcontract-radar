{{ config(materialized='table', schema='DIMENSIONS') }}

with source as (
    select distinct
        RECIPIENT_NAME
    from GOVCONTRACT.RAW.STG_USASPENDING_AWARDS
    where RECIPIENT_NAME is not null
),

normalized as (
    select
        RECIPIENT_NAME,
        UPPER(TRIM(RECIPIENT_NAME)) as RECIPIENT_NAME_NORMALIZED
    from source
)

select
    MD5(RECIPIENT_NAME_NORMALIZED) as VENDOR_ID,
    RECIPIENT_NAME as VENDOR_NAME,
    RECIPIENT_NAME_NORMALIZED
from normalized
