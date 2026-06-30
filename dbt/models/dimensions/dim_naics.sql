{{ config(materialized='table', schema='DIMENSIONS') }}

select
    NAICS_CODE,
    NAICS_DESCRIPTION
from {{ ref('naics_codes') }}
