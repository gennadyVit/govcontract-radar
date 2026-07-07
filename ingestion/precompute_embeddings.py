"""
Pre-compute Azure OpenAI embeddings for new opportunities and store in Snowflake.
Called by the Airflow DAG after each dbt run (only rows where EMBEDDING IS NULL).

Embedding model: text-embedding-3-small (Azure OpenAI)
Chosen over Snowflake Cortex (e5-base-v2) because:
  - Newer architecture — OpenAI's 3rd-gen models outperform e5-base-v2 on MTEB benchmarks
  - Higher dimensionality (1536-d vs 768-d) → finer-grained similarity for niche NAICS codes
"""
import os
import json
import time
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from snowflake_conn import get_connection
from openai import AzureOpenAI

EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
BATCH_SIZE = 20  # embeddings per API call (Azure supports up to 2048 inputs)

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
)


def get_embedding_batch(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def main():
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch opportunities that don't have embeddings yet
    cursor.execute("""
        SELECT NOTICE_ID, TITLE, NAICS_DESCRIPTION
        FROM GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES
        WHERE EMBEDDING IS NULL
        ORDER BY POSTED_DATE DESC
    """)
    rows = cursor.fetchall()
    print(f"Found {len(rows)} opportunities without embeddings")

    if not rows:
        print("All embeddings already computed.")
        return

    # Process in batches
    total = len(rows)
    processed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        notice_ids = [r[0] for r in batch]
        texts = [f"{r[1]} {r[2] or ''}".strip() for r in batch]

        try:
            embeddings = get_embedding_batch(texts)
        except Exception as e:
            print(f"Error on batch {i}: {e}")
            time.sleep(5)
            continue

        # Update each row
        for notice_id, embedding in zip(notice_ids, embeddings):
            cursor.execute("""
                UPDATE GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES
                SET EMBEDDING = PARSE_JSON(%s)
                WHERE NOTICE_ID = %s
            """, (json.dumps(embedding), notice_id))

        conn.commit()
        processed += len(batch)
        print(f"Processed {processed}/{total}")
        time.sleep(0.5)  # rate limit buffer

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
