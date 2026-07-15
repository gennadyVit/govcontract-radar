import os
import time
import requests
from dotenv import load_dotenv

from snowflake_conn import get_connection

load_dotenv()

SAM_URL = "https://api.sam.gov/opportunities/v2/search"
MAX_RECORDS = 1000



def fetch_and_load(cursor, posted_from="04/01/2026", posted_to="06/30/2026"):
    """Fetch and load page by page so rate limits don't lose already-fetched data."""
    offset = 0
    limit = 100
    total_loaded = 0
    rate_limit_retries = 0
    MAX_RATE_LIMIT_RETRIES = 3

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
            rate_limit_retries += 1
            if rate_limit_retries >= MAX_RATE_LIMIT_RETRIES:
                print(f"  Rate limited {MAX_RATE_LIMIT_RETRIES}x in a row — stopping with {total_loaded} records loaded.")
                break
            print(f"  Rate limited (attempt {rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES}) — waiting 10s...")
            time.sleep(10)
            continue
        rate_limit_retries = 0
        response.raise_for_status()
        data = response.json()
        batch = data.get("opportunitiesData", [])
        if not batch:
            break
        count = load_to_snowflake(batch, cursor)
        total_loaded += count
        total = data.get("totalRecords", 0)
        print(f"  Loaded {total_loaded}/{total}...")
        if total_loaded >= total or total_loaded >= MAX_RECORDS:
            break
        offset += limit
        time.sleep(1.0)

    return total_loaded


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
            r.get("description"),
        ))

    cursor.executemany("""
        INSERT INTO GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES (
            NOTICE_ID, TITLE, SOLICITATION_NUM, AGENCY, POSTED_DATE,
            RESPONSE_DEADLINE, TYPE, SET_ASIDE, NAICS_CODE, ACTIVE,
            OFFICE_CITY, OFFICE_STATE, UI_LINK, DESCRIPTION
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, rows)
    return len(rows)


if __name__ == "__main__":
    print("Connecting to Snowflake...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE WAREHOUSE {os.getenv('SNOWFLAKE_WAREHOUSE')}")

    print("Truncating staging table...")
    cursor.execute("TRUNCATE TABLE GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES")
    conn.commit()

    print("Fetching and loading SAM.gov opportunities page by page (Apr-Jun 2026)...")
    count = fetch_and_load(cursor)
    conn.commit()
    conn.close()

    print(f"Done! {count} records loaded into GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES")
    print("Query it in Snowflake: SELECT * FROM GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES LIMIT 20;")
