import os
import requests
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

load_dotenv()


def load_private_key():
    with open("rsa_key.p8", "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def test_snowflake():
    print("\n--- Testing Snowflake Connection ---")
    try:
        conn = snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            user=os.getenv("SNOWFLAKE_USER"),
            private_key=load_private_key(),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA"),
        )
        cursor = conn.cursor()
        cursor.execute(f"USE WAREHOUSE {os.getenv('SNOWFLAKE_WAREHOUSE')}")
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()[0]
        print(f"[OK] Snowflake connected! Version: {version}")
        cursor.execute("SELECT SCHEMA_NAME FROM GOVCONTRACT.INFORMATION_SCHEMA.SCHEMATA")
        schemas = [row[0] for row in cursor.fetchall()]
        print(f"[OK] Schemas found: {schemas}")
        conn.close()
    except Exception as e:
        print(f"[FAIL] Snowflake connection failed: {e}")


def test_sam_gov():
    print("\n--- Testing SAM.gov API ---")
    try:
        api_key = os.getenv("SAM_GOV_API_KEY")
        url = "https://api.sam.gov/opportunities/v2/search"
        params = {
            "api_key": api_key,
            "limit": 5,
            "postedFrom": "01/01/2025",
            "postedTo": "12/31/2025",
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        count = len(data.get("opportunitiesData", []))
        print(f"[OK] SAM.gov API connected! Fetched {count} opportunities")
    except Exception as e:
        print(f"[FAIL] SAM.gov API failed: {e}")


def test_usaspending():
    print("\n--- Testing USASpending API ---")
    try:
        url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        payload = {
            "filters": {
                "keywords": ["software"],
                "award_type_codes": ["A", "B", "C", "D"],
            },
            "fields": ["Award ID", "Recipient Name", "Award Amount"],
            "limit": 5,
            "page": 1,
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        count = len(response.json().get("results", []))
        print(f"[OK] USASpending API connected! Fetched {count} awards")
    except Exception as e:
        print(f"[FAIL] USASpending API failed: {e}")


if __name__ == "__main__":
    test_snowflake()
    test_sam_gov()
    test_usaspending()
    print("\nDone!")
