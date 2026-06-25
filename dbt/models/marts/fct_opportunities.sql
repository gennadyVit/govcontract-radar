{{ config(materialized='table', schema='MARTS') }}

with source as (
    select * from GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES
),

cleaned as (
    select
        NOTICE_ID,
        TITLE,
        SOLICITATION_NUM,

        -- extract top-level agency from the full path
        SPLIT_PART(AGENCY, '.', 1)                          as AGENCY,
        SPLIT_PART(AGENCY, '.', 2)                          as SUB_AGENCY,

        TYPE                                                as NOTICE_TYPE,
        SET_ASIDE,
        NAICS_CODE,

        TRY_TO_DATE(POSTED_DATE)                            as POSTED_DATE,
        RESPONSE_DEADLINE,

        -- days until deadline from today
        DATEDIFF('day', CURRENT_DATE(), RESPONSE_DEADLINE) as DAYS_UNTIL_DEADLINE,

        OFFICE_CITY,
        OFFICE_STATE,
        UI_LINK,
        LOADED_AT

    from source
    where ACTIVE = 'Yes'
      and TYPE in ('Solicitation', 'Presolicitation', 'Sources Sought')
)

select * from cleaned
