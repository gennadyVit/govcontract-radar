import os
from dotenv import load_dotenv

from snowflake_conn import get_connection
import requests

load_dotenv()

BASE_URL = "https://api.usaspending.gov/api/v2"

FIELDS = [
    "Award ID",
    "Recipient Name",
    "Award Amount",
    "Description",
    "Start Date",
    "End Date",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Contract Award Type",
    "Place of Performance Country Code",
    "Place of Performance State Code",
]


def create_staging_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GOVCONTRACT.RAW.STG_USASPENDING_AWARDS (
            AWARD_ID            VARCHAR,
            INTERNAL_ID         VARCHAR,
            RECIPIENT_NAME      VARCHAR,
            AWARD_AMOUNT        NUMBER(38, 2),
            DESCRIPTION         VARCHAR,
            START_DATE          DATE,
            END_DATE            DATE,
            AWARDING_AGENCY     VARCHAR,
            AWARDING_SUB_AGENCY VARCHAR,
            AWARD_TYPE          VARCHAR,
            POP_COUNTRY_CODE    VARCHAR,
            POP_STATE_CODE      VARCHAR,
            LOADED_AT           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)


def fetch_awards(keyword: str, limit: int = 100) -> list[dict]:
    url = f"{BASE_URL}/search/spending_by_award/"
    payload = {
        "filters": {
            "keywords": [keyword],
            "award_type_codes": ["A", "B", "C", "D"],
        },
        "fields": FIELDS,
        "limit": limit,
        "page": 1,
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json().get("results", [])


def load_to_snowflake(records, cursor):
    rows = []
    for r in records:
        rows.append((
            r.get("Award ID"),
            str(r.get("internal_id")),
            r.get("Recipient Name"),
            r.get("Award Amount"),
            r.get("Description"),
            r.get("Start Date"),
            r.get("End Date"),
            r.get("Awarding Agency"),
            r.get("Awarding Sub Agency"),
            r.get("Contract Award Type"),
            r.get("Place of Performance Country Code"),
            r.get("Place of Performance State Code"),
        ))

    cursor.executemany("""
        INSERT INTO GOVCONTRACT.RAW.STG_USASPENDING_AWARDS (
            AWARD_ID, INTERNAL_ID, RECIPIENT_NAME, AWARD_AMOUNT, DESCRIPTION,
            START_DATE, END_DATE, AWARDING_AGENCY, AWARDING_SUB_AGENCY,
            AWARD_TYPE, POP_COUNTRY_CODE, POP_STATE_CODE
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, rows)
    return len(rows)


if __name__ == "__main__":
    print("Fetching USASpending awards...")
    records = fetch_awards("software", limit=100)
    print(f"Fetched {len(records)} records")

    print("Connecting to Snowflake...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE WAREHOUSE {os.getenv('SNOWFLAKE_WAREHOUSE')}")

    print("Creating staging table if not exists...")
    create_staging_table(cursor)

    print("Loading records into Snowflake...")
    count = load_to_snowflake(records, cursor)
    conn.commit()
    conn.close()

    print(f"Done! {count} records loaded into GOVCONTRACT.RAW.STG_USASPENDING_AWARDS")
    print("Query it in Snowflake: SELECT * FROM GOVCONTRACT.RAW.STG_USASPENDING_AWARDS LIMIT 20;")
