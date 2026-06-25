import os
import requests
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

load_dotenv()

SAM_URL = "https://api.sam.gov/opportunities/v2/search"


def get_snowflake_conn():
    with open("rsa_key.p8", "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        private_key=private_key,
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )


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


def fetch_opportunities(posted_from="01/01/2025", posted_to="12/31/2025", limit=100):
    params = {
        "api_key": os.getenv("SAM_GOV_API_KEY"),
        "limit": limit,
        "postedFrom": posted_from,
        "postedTo": posted_to,
    }
    response = requests.get(SAM_URL, params=params)
    response.raise_for_status()
    return response.json().get("opportunitiesData", [])


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
    print("Fetching SAM.gov opportunities...")
    records = fetch_opportunities(limit=100)
    print(f"Fetched {len(records)} records")

    print("Connecting to Snowflake...")
    conn = get_snowflake_conn()
    cursor = conn.cursor()
    cursor.execute(f"USE WAREHOUSE {os.getenv('SNOWFLAKE_WAREHOUSE')}")

    print("Creating staging table if not exists...")
    create_staging_table(cursor)

    print("Loading records into Snowflake...")
    count = load_to_snowflake(records, cursor)
    conn.commit()
    conn.close()

    print(f"Done! {count} records loaded into GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES")
    print("Query it in Snowflake: SELECT * FROM GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES LIMIT 20;")
