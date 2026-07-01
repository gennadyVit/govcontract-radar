import os
import time
import requests
from dotenv import load_dotenv

from snowflake_conn import get_connection

load_dotenv()

SAM_URL = "https://api.sam.gov/opportunities/v2/search"


def create_staging_table(cursor):
    cursor.execute("""
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
            LOADED_AT          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)


def fetch_opportunities(posted_from="04/01/2026", posted_to="06/30/2026"):
    records = []
    offset = 0
    limit = 100

    while True:
        params = {
            "api_key": os.getenv("SAM_GOV_API_KEY"),
            "limit": limit,
            "offset": offset,
            "postedFrom": posted_from,
            "postedTo": posted_to,
        }
        response = requests.get(SAM_URL, params=params)
        if response.status_code == 429:
            print("  Rate limited — waiting 60s...")
            time.sleep(60)
            continue
        response.raise_for_status()
        data = response.json()
        batch = data.get("opportunitiesData", [])
        if not batch:
            break
        records.extend(batch)
        total = data.get("totalRecords", 0)
        print(f"  Fetched {len(records)}/{total}...")
        if len(records) >= total:
            break
        offset += limit
        time.sleep(1.0)

    return records


def load_to_snowflake(records, cursor):
    rows = []
    for r in records:
        office = r.get("officeAddress") or {}
        rows.append((
            r.get("noticeId"),
            r.get("title"),
            r.get("solicitationNumber"),
            r.get("fullParentPathName"),
            r.get("postedDate"),
            r.get("responseDeadLine") or None,
            r.get("type"),
            r.get("typeOfSetAsideDescription"),
            r.get("naicsCode"),
            r.get("active"),
            office.get("city"),
            office.get("state"),
            r.get("uiLink"),
        ))

    cursor.executemany("""
        INSERT INTO GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES (
            NOTICE_ID, TITLE, SOLICITATION_NUM, AGENCY, POSTED_DATE,
            RESPONSE_DEADLINE, TYPE, SET_ASIDE, NAICS_CODE, ACTIVE,
            OFFICE_CITY, OFFICE_STATE, UI_LINK
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, rows)
    return len(rows)


if __name__ == "__main__":
    print("Fetching SAM.gov opportunities (all, 2025)...")
    records = fetch_opportunities()
    print(f"Fetched {len(records)} records")

    print("Connecting to Snowflake...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE WAREHOUSE {os.getenv('SNOWFLAKE_WAREHOUSE')}")

    print("Creating staging table if not exists...")
    create_staging_table(cursor)

    print("Truncating staging table...")
    cursor.execute("TRUNCATE TABLE GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES")

    print("Loading records into Snowflake...")
    count = load_to_snowflake(records, cursor)
    conn.commit()
    conn.close()

    print(f"Done! {count} records loaded into GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES")
    print("Query it in Snowflake: SELECT * FROM GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES LIMIT 20;")
