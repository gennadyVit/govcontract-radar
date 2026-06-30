{{ config(materialized='table', schema='MARTS') }}

with source as (
    select * from GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES
),

dim_agency as (
    select * from GOVCONTRACT.DIMENSIONS.DIM_AGENCY
),

cleaned as (
    select
        s.NOTICE_ID,
        s.TITLE,
        s.SOLICITATION_NUM,

        -- FK to dim_agency (replaces raw agency text)
        a.AGENCY_ID,

        -- keep raw agency fields for display/debugging
        SPLIT_PART(s.AGENCY, '.', 1) as AGENCY_NAME,
        SPLIT_PART(s.AGENCY, '.', 2) as SUB_AGENCY_NAME,

        s.TYPE                                                as NOTICE_TYPE,
        s.SET_ASIDE,
        s.NAICS_CODE,
        TRY_TO_DATE(s.POSTED_DATE)                           as POSTED_DATE,
        s.RESPONSE_DEADLINE,

        DATEDIFF('day', CURRENT_DATE(), s.RESPONSE_DEADLINE) as DAYS_UNTIL_DEADLINE,
        case
            when DATEDIFF('day', CURRENT_DATE(), s.RESPONSE_DEADLINE) < 7  then 'Closing Soon'
            when DATEDIFF('day', CURRENT_DATE(), s.RESPONSE_DEADLINE) < 30 then 'This Month'
            else 'Future'
        end as DEADLINE_CATEGORY,

        s.OFFICE_CITY,
        s.OFFICE_STATE,
        s.UI_LINK,
        s.LOADED_AT

    from source s
    left join dim_agency a
        on a.AGENCY_NAME    = SPLIT_PART(s.AGENCY, '.', 1)
        and a.SUB_AGENCY_NAME = SPLIT_PART(s.AGENCY, '.', 2)
    where s.ACTIVE = 'Yes'
      and s.TYPE in ('Solicitation', 'Presolicitation', 'Sources Sought')
)

select * from cleaned
