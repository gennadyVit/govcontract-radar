"""
Opportunity scoring engine.
Computes FIT_SCORE (0-100) and DECISION for each opportunity against a company profile.
Company-agnostic components are precomputed; company-specific components run at score time.
"""
import os
import json
import math
import numpy as np
import snowflake.connector
from snowflake_conn import get_connection

# Weights from spec
W_CAPABILITY   = 0.35
W_PAST_PERF    = 0.25
W_SIZE         = 0.15
W_COMPETITION  = 0.15
W_STRATEGIC    = 0.10

# Hard gate caps
CAP_SET_ASIDE   = 40
CAP_CLEARANCE   = 50
CAP_LOCATION    = 60
CAP_SIZE        = 65

PURSUE_THRESHOLD = 70
WATCH_THRESHOLD  = 50


PROFILES = {
    "technova": {
        "name": "TechNova Solutions LLC",
        "naics_codes": ["541511", "541512", "541519", "541330", "518210"],
        "set_asides": ["SBA", "8(a)"],
        "clearances": [],
        "min_contract_value": 100_000,
        "max_contract_value": 10_000_000,
        "keywords": ["software", "cloud", "cybersecurity", "data analytics", "IT modernization",
                     "DevSecOps", "machine learning", "artificial intelligence", "API"],
        "past_agencies": ["Department of Defense", "Department of Veterans Affairs",
                          "General Services Administration", "Department of Homeland Security"],
        "location_states": ["VA", "MD", "DC", "TX", "FL"],
        "embedding": None,
    },
    "startup": {
        "name": "BluePath Tech Inc",
        "naics_codes": ["541511"],
        "set_asides": ["SBA"],
        "clearances": [],
        "min_contract_value": 50_000,
        "max_contract_value": 500_000,
        "keywords": ["software", "web", "database", "support"],
        "past_agencies": [],
        "location_states": ["TX"],
        "embedding": None,
    },
}


def load_company_profile(profile_name: str = None) -> dict:
    """Load company profile from env var JSON, named profile, or default."""
    raw = os.getenv("COMPANY_PROFILE")
    if raw:
        return json.loads(raw)
    if profile_name and profile_name in PROFILES:
        return PROFILES[profile_name]
    return PROFILES["technova"]


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def score_capability(opp_embedding, profile_embedding) -> float:
    """Semantic similarity between opportunity and company profile. 0-100."""
    if opp_embedding is None or profile_embedding is None:
        return 50.0
    sim = cosine_similarity(opp_embedding, profile_embedding)
    return round(((sim + 1) / 2) * 100, 1)


def score_past_performance(opp_naics, opp_agency, profile) -> float:
    """How well company's past work matches this opportunity. 0-100."""
    score = 0.0
    # NAICS match
    if opp_naics and opp_naics in profile.get("naics_codes", []):
        score += 60.0
    elif opp_naics and any(opp_naics[:3] == n[:3] for n in profile.get("naics_codes", [])):
        score += 30.0
    # Agency match
    agency = (opp_agency or "").lower()
    for past in profile.get("past_agencies", []):
        if past.lower() in agency or agency in past.lower():
            score += 40.0
            break
    return min(score, 100.0)


def score_contract_size(median_award, profile) -> float:
    """How well contract size fits company capacity. 0-100."""
    if not median_award:
        return 50.0
    lo = profile.get("min_contract_value", 0)
    hi = profile.get("max_contract_value", float("inf"))
    if lo <= median_award <= hi:
        return 100.0
    if median_award < lo:
        ratio = median_award / lo
        return round(50 + 50 * ratio, 1)
    # Too large
    ratio = hi / median_award
    return round(100 * ratio, 1)


def score_competition(win_rate_pct, set_aside, profile) -> float:
    """Competition favorability. 0-100."""
    score = win_rate_pct if win_rate_pct else 50.0
    # Bonus if set-aside matches
    opp_sa = (set_aside or "").upper()
    for sa in profile.get("set_asides", []):
        if sa.upper() in opp_sa or opp_sa in sa.upper():
            score = min(score + 20, 100)
            break
    return round(score, 1)


def score_strategic(title, description, profile) -> float:
    """Keyword match against company focus areas. 0-100."""
    text = f"{title or ''} {description or ''}".lower()
    keywords = profile.get("keywords", [])
    if not keywords:
        return 50.0
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return round(min(hits / max(len(keywords), 1) * 150, 100), 1)


def apply_hard_gates(raw_score, opp, profile) -> float:
    """Apply caps for eligibility gates. Returns capped score."""
    score = raw_score
    set_aside = (opp.get("set_aside") or "").upper()
    profile_setasides = [s.upper() for s in profile.get("set_asides", [])]

    # Set-aside gate
    if set_aside and set_aside not in ("NONE", "N/A", ""):
        eligible = any(s in set_aside or set_aside in s for s in profile_setasides)
        if not eligible and profile_setasides:
            score = min(score, CAP_SET_ASIDE)

    # Contract size gate (10x above max)
    median = opp.get("median_award") or 0
    max_val = profile.get("max_contract_value", float("inf"))
    if median > max_val * 10:
        score = min(score, CAP_SIZE)

    return round(score, 1)


def compute_fit_score(opp: dict, profile: dict, profile_embedding) -> tuple[float, str]:
    """Returns (fit_score, decision)."""
    cap = score_capability(opp.get("embedding"), profile_embedding)
    pp  = score_past_performance(opp.get("naics_code"), opp.get("agency"), profile)
    sz  = score_contract_size(opp.get("median_award"), profile)
    co  = score_competition(opp.get("win_rate"), opp.get("set_aside"), profile)
    st  = score_strategic(opp.get("title"), opp.get("description"), profile)

    raw = (W_CAPABILITY * cap + W_PAST_PERF * pp + W_SIZE * sz +
           W_COMPETITION * co + W_STRATEGIC * st)

    score = apply_hard_gates(raw, opp, profile)

    if score >= PURSUE_THRESHOLD:
        decision = "PURSUE"
    elif score >= WATCH_THRESHOLD:
        decision = "WATCH"
    else:
        decision = "NO_BID"

    return round(score, 1), decision


def embed_profile(profile: dict) -> list:
    """Embed the company profile using Azure OpenAI."""
    from openai import AzureOpenAI
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2024-02-01",
    )
    text = " ".join([
        profile.get("name", ""),
        " ".join(profile.get("keywords", [])),
        " ".join(profile.get("past_agencies", [])),
        " ".join(profile.get("naics_codes", [])),
    ])
    resp = client.embeddings.create(
        input=text,
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
    )
    return resp.data[0].embedding


def main():
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    profile_name = sys.argv[1] if len(sys.argv) > 1 else "technova"
    print(f"Loading company profile: {profile_name}...")
    profile = load_company_profile(profile_name)

    print("Embedding company profile...")
    profile_embedding = embed_profile(profile)

    print("Connecting to Snowflake...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("USE WAREHOUSE COMPUTE_WH")

    print("Loading opportunities...")
    cursor.execute("""
        SELECT
            d.NOTICE_ID,
            d.TITLE,
            d.NAICS_CODE,
            d.AGENCY_NAME,
            d.SET_ASIDE,
            d.NAICS_SB_WIN_RATE_PCT,
            d.NAICS_MEDIAN_AWARD_AMOUNT,
            m.EMBEDDING,
            o.DESCRIPTION
        FROM GOVCONTRACT.AGENTS.AGENT_DECISIONS d
        LEFT JOIN GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES m ON m.NOTICE_ID = d.NOTICE_ID
        LEFT JOIN GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES o ON o.NOTICE_ID = d.NOTICE_ID
    """)
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    print(f"Scoring {len(rows)} opportunities...")

    updates = []
    import uuid
    run_id = str(uuid.uuid4())[:8]

    for row in rows:
        opp = dict(zip(cols, row))
        emb = opp.get("EMBEDDING")
        if isinstance(emb, str):
            import json as _json
            emb = _json.loads(emb)
        opp["embedding"] = emb
        opp["naics_code"] = opp.get("NAICS_CODE")
        opp["agency"] = opp.get("AGENCY_NAME")
        opp["set_aside"] = opp.get("SET_ASIDE")
        opp["win_rate"] = float(opp["NAICS_SB_WIN_RATE_PCT"]) if opp.get("NAICS_SB_WIN_RATE_PCT") is not None else None
        opp["median_award"] = float(opp["NAICS_MEDIAN_AWARD_AMOUNT"]) if opp.get("NAICS_MEDIAN_AWARD_AMOUNT") is not None else None
        opp["title"] = opp.get("TITLE")
        opp["description"] = opp.get("DESCRIPTION")

        score, decision = compute_fit_score(opp, profile, profile_embedding)
        updates.append((score, decision, run_id, opp["NOTICE_ID"]))

    print(f"Writing scores to Snowflake...")
    cursor.executemany("""
        UPDATE GOVCONTRACT.AGENTS.AGENT_DECISIONS
        SET FIT_SCORE = %s,
            DECISION = %s,
            AGENT_RUN_ID = %s,
            DECIDED_AT = CURRENT_TIMESTAMP()
        WHERE NOTICE_ID = %s
    """, updates)
    conn.commit()

    pursue = sum(1 for _, d, _, _ in updates if d == "PURSUE")
    watch  = sum(1 for _, d, _, _ in updates if d == "WATCH")
    nobid  = sum(1 for _, d, _, _ in updates if d == "NO_BID")
    print(f"Done. PURSUE={pursue}, WATCH={watch}, NO_BID={nobid}")
    conn.close()


if __name__ == "__main__":
    main()
