"""
Azure AI Search indexer for GovContract opportunities.
Creates/updates the search index and uploads documents from Snowflake.
"""
import os
import json
from dotenv import load_dotenv

SEARCH_ENDPOINT = "https://govcontract-search.search.windows.net"
INDEX_NAME = "opportunities"

INDEX_SCHEMA = {
    "name": INDEX_NAME,
    "fields": [
        {"name": "id",          "type": "Edm.String", "key": True,  "filterable": True},
        {"name": "notice_id",   "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "title",       "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "agency",      "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True},
        {"name": "naics_code",  "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "naics_desc",  "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "set_aside",   "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "description", "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "fit_score",   "type": "Edm.Double", "sortable": True, "filterable": True, "retrievable": True},
        {"name": "decision",    "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "deadline",    "type": "Edm.String", "retrievable": True},
        {"name": "posted_date", "type": "Edm.String", "retrievable": True},
        {"name": "ui_link",     "type": "Edm.String", "retrievable": True},
        {"name": "embedding",   "type": "Collection(Edm.Single)",
         "searchable": True, "retrievable": False,
         "dimensions": 1536, "vectorSearchProfile": "hnsw-profile"},
    ],
    "vectorSearch": {
        "algorithms": [{"name": "hnsw-algo", "kind": "hnsw"}],
        "profiles": [{"name": "hnsw-profile", "algorithm": "hnsw-algo"}],
    },
    "semantic": {
        "configurations": [{
            "name": "semantic-config",
            "prioritizedFields": {
                "titleField": {"fieldName": "title"},
                "contentFields": [{"fieldName": "description"}],
                "keywordsFields": [{"fieldName": "naics_desc"}, {"fieldName": "agency"}],
            }
        }]
    }
}


def get_search_client():
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.core.credentials import AzureKeyCredential
    key = os.getenv("AZURE_SEARCH_KEY")
    cred = AzureKeyCredential(key)
    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=cred)
    search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=cred)
    return index_client, search_client


def create_or_update_index():
    from azure.search.documents.indexes.models import (
        SearchIndex, SearchField, SearchFieldDataType,
        VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
        SemanticConfiguration, SemanticSearch, SemanticPrioritizedFields, SemanticField,
    )
    index_client, _ = get_search_client()

    fields = [
        SearchField(name="id",          type=SearchFieldDataType.String, key=True,  filterable=True),
        SearchField(name="notice_id",   type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchField(name="title",       type=SearchFieldDataType.String, searchable=True, retrievable=True),
        SearchField(name="agency",      type=SearchFieldDataType.String, searchable=True, filterable=True, retrievable=True),
        SearchField(name="naics_code",  type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchField(name="naics_desc",  type=SearchFieldDataType.String, searchable=True, retrievable=True),
        SearchField(name="set_aside",   type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchField(name="description", type=SearchFieldDataType.String, searchable=True, retrievable=True),
        SearchField(name="fit_score",   type=SearchFieldDataType.Double, sortable=True, filterable=True, retrievable=True),
        SearchField(name="decision",    type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchField(name="deadline",    type=SearchFieldDataType.String, retrievable=True),
        SearchField(name="posted_date", type=SearchFieldDataType.String, retrievable=True),
        SearchField(name="ui_link",     type=SearchFieldDataType.String, retrievable=True),
        SearchField(name="embedding",   type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, retrievable=False, vector_search_dimensions=1536,
                    vector_search_profile_name="hnsw-profile"),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
        profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-algo")],
    )

    semantic_config = SemanticConfiguration(
        name="semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="description")],
            keywords_fields=[SemanticField(field_name="naics_desc"), SemanticField(field_name="agency")],
        )
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=SemanticSearch(configurations=[semantic_config]),
    )
    result = index_client.create_or_update_index(index)
    print(f"Index '{result.name}' ready.")


def upload_opportunities():
    from snowflake_conn import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("USE WAREHOUSE COMPUTE_WH")
    cursor.execute("""
        SELECT
            d.NOTICE_ID,
            d.TITLE,
            d.AGENCY_NAME,
            d.NAICS_CODE,
            d.NAICS_DESCRIPTION,
            d.SET_ASIDE,
            d.FIT_SCORE,
            d.DECISION,
            d.RESPONSE_DEADLINE,
            d.POSTED_DATE,
            o.UI_LINK,
            o.DESCRIPTION,
            m.EMBEDDING
        FROM GOVCONTRACT.AGENTS.AGENT_DECISIONS d
        LEFT JOIN GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES o ON o.NOTICE_ID = d.NOTICE_ID
        LEFT JOIN GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES m ON m.NOTICE_ID = d.NOTICE_ID
        WHERE d.DECIDED_AT IS NOT NULL
    """)
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    conn.close()

    _, search_client = get_search_client()

    docs = []
    for row in rows:
        r = dict(zip(cols, row))
        emb = r.get("EMBEDDING")
        if isinstance(emb, str):
            emb = json.loads(emb)

        docs.append({
            "id": r["NOTICE_ID"].replace(" ", "_").replace("/", "_"),
            "notice_id": r["NOTICE_ID"],
            "title": r["TITLE"] or "",
            "agency": r["AGENCY_NAME"] or "",
            "naics_code": r["NAICS_CODE"] or "",
            "naics_desc": r["NAICS_DESCRIPTION"] or "",
            "set_aside": r["SET_ASIDE"] or "",
            "description": (r["DESCRIPTION"] or "")[:4000],
            "fit_score": float(r["FIT_SCORE"]) if r["FIT_SCORE"] else 0.0,
            "decision": r["DECISION"] or "",
            "deadline": str(r["RESPONSE_DEADLINE"])[:10] if r["RESPONSE_DEADLINE"] else "",
            "posted_date": str(r["POSTED_DATE"])[:10] if r["POSTED_DATE"] else "",
            "ui_link": r["UI_LINK"] or "",
            "embedding": emb,
        })

    # Upload in batches of 100
    batch_size = 100
    total = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i+batch_size]
        result = search_client.upload_documents(documents=batch)
        total += len(batch)
        print(f"  Indexed {total}/{len(docs)}...")

    print(f"Done. {len(docs)} documents indexed.")


def search(query: str, top: int = 10, decision_filter: str = None) -> list[dict]:
    """Hybrid keyword + vector search."""
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    from openai import AzureOpenAI

    # Embed query
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2024-02-01",
    )
    resp = client.embeddings.create(
        input=query,
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
    )
    query_vector = resp.data[0].embedding

    from azure.search.documents.models import VectorizedQuery
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")),
    )

    vector_query = VectorizedQuery(vector=query_vector, k_nearest_neighbors=top, fields="embedding")
    filter_expr = f"decision eq '{decision_filter}'" if decision_filter else None

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        filter=filter_expr,
        select=["notice_id", "title", "agency", "naics_code", "set_aside",
                "fit_score", "decision", "deadline", "ui_link"],
        top=top,
    )
    return [dict(r) for r in results]


if __name__ == "__main__":
    load_dotenv()
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:]) or "cloud software modernization"
        print(f"Searching: {query}")
        results = search(query, top=5)
        for r in results:
            print(f"  [{r.get('fit_score',0):.0f}] {r['title'][:60]} — {r['agency'][:30]}")
    else:
        print("Creating index...")
        create_or_update_index()
        print("Uploading opportunities...")
        upload_opportunities()
