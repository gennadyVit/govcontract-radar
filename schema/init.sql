-- Full schema initialization for GOVCONTRACT
-- Run this once in a new environment before any ingestion or dbt run.
-- dbt manages all table contents — this only creates the containers.

CREATE DATABASE IF NOT EXISTS GOVCONTRACT;

-- ── RAW layer ─────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS GOVCONTRACT.RAW;

-- SAM.gov opportunities (ingestion/sam_gov.py)
CREATE TABLE IF NOT EXISTS GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES (
    NOTICE_ID          VARCHAR,
    TITLE              VARCHAR,
    SOLICITATION_NUM   VARCHAR,
    AGENCY             VARCHAR,
    POSTED_DATE        DATE,
    RESPONSE_DEADLINE  TIMESTAMP_TZ,
    TYPE               VARCHAR,
    SET_ASIDE          VARCHAR,
    NAICS_CODE         VARCHAR,
    ACTIVE             VARCHAR,
    OFFICE_CITY        VARCHAR,
    OFFICE_STATE       VARCHAR,
    UI_LINK            VARCHAR,
    DESCRIPTION        VARCHAR,
    LOADED_AT          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- USASpending.gov awards (ingestion/usaspending.py)
CREATE TABLE IF NOT EXISTS GOVCONTRACT.RAW.STG_USASPENDING_AWARDS (
    AWARD_ID                       VARCHAR,
    INTERNAL_ID                    VARCHAR,
    RECIPIENT_NAME                 VARCHAR,
    AWARD_AMOUNT                   NUMBER(38, 2),
    DESCRIPTION                    VARCHAR,
    START_DATE                     DATE,
    END_DATE                       DATE,
    AWARDING_AGENCY                VARCHAR,
    AWARDING_SUB_AGENCY            VARCHAR,
    AWARD_TYPE                     VARCHAR,
    NAICS_CODE                     VARCHAR,
    POP_COUNTRY_CODE               VARCHAR,
    POP_STATE_CODE                 VARCHAR,
    IS_SMALL_BUSINESS_AWARD        BOOLEAN,
    SOURCE_ALL_MARKET_PULL         BOOLEAN,
    SOURCE_SMALL_BUSINESS_PULL     BOOLEAN,
    LOADED_AT                      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ── DIMENSIONS layer ──────────────────────────────────────────────────────────
-- Tables are populated by dbt. Schema must exist before `dbt run`.
CREATE SCHEMA IF NOT EXISTS GOVCONTRACT.DIMENSIONS;

-- ── MARTS layer ───────────────────────────────────────────────────────────────
-- Tables are populated by dbt. Schema must exist before `dbt run`.
CREATE SCHEMA IF NOT EXISTS GOVCONTRACT.MARTS;

-- EMBEDDING column — added after initial dbt run to store pre-computed vectors.
-- dbt preserves this column because mart_opportunity_features.sql selects it explicitly.
-- If rebuilding from scratch, run `dbt run` first, then this ALTER:
--   ALTER TABLE GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES ADD COLUMN IF NOT EXISTS EMBEDDING VARIANT;
