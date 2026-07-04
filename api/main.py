import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api.scoring.fit_score import score_opportunity
from api.scoring.embeddings import compute_capability_similarity, get_profile_embedding

load_dotenv()

app = FastAPI(title="GovContract Radar Scoring API")


class CompanyProfile(BaseModel):
    company_summary: str = ""
    capabilities: list[str] = []
    naics: list[str] = []
    psc: list[str] = []
    certifications: list[str] = []
    past_performance: list[dict] = []
    preferred_contract_size: dict = {"min": 0, "max": 10000000}
    locations: list[str] = []
    clearance: str = ""
    prime_or_sub: str = "either"
    contract_vehicles: list[str] = []
    avoid: list[str] = []
    keywords_target: list[str] = []
    keywords_avoid: list[str] = []
    agency_preferences: list[str] = []
    team_size: int = 1
    max_contract_executable: float = 1000000


def _get_snowflake_connection():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
    from snowflake_conn import get_connection
    return get_connection()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score")
def score_opportunities(profile: CompanyProfile, limit: int = 50, min_score: int = 0):
    """
    Score all active opportunities against the provided company profile.
    Returns opportunities ranked by fit score descending.
    """
    profile_dict = profile.model_dump()

    try:
        conn = _get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                NOTICE_ID, TITLE, AGENCY_NAME, SUB_AGENCY_NAME,
                NAICS_CODE, NAICS_DESCRIPTION, NOTICE_TYPE, SET_ASIDE,
                POSTED_DATE, DAYS_UNTIL_DEADLINE, DEADLINE_CATEGORY,
                OFFICE_STATE, UI_LINK,
                NAICS_MEDIAN_AWARD_AMOUNT, NAICS_AVG_AWARD_AMOUNT,
                NAICS_P25_AWARD_AMOUNT, NAICS_P75_AWARD_AMOUNT,
                NAICS_UNIQUE_VENDORS, NAICS_SB_WIN_RATE_PCT,
                NAICS_AVG_CONTRACT_LENGTH_DAYS
            FROM GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES
            LIMIT {limit * 3}
        """)
        columns = [col[0] for col in cursor.description]
        opportunities = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snowflake error: {str(e)}")

    profile_embedding = get_profile_embedding(profile_dict)

    results = []
    for opp in opportunities:
        similarity = compute_capability_similarity(opp, profile_dict, profile_embedding=profile_embedding)
        result = score_opportunity(opp, profile_dict, capability_similarity=similarity)
        if result.overall_fit_score >= min_score:
            results.append(result)

    results.sort(key=lambda r: r.overall_fit_score, reverse=True)

    return {
        "total": len(results),
        "azure_embeddings_enabled": bool(os.getenv("AZURE_OPENAI_ENDPOINT")),
        "opportunities": [
            {
                "notice_id": r.notice_id,
                "title": r.title,
                "agency_name": r.agency_name,
                "naics_code": r.naics_code,
                "days_until_deadline": r.days_until_deadline,
                "overall_fit_score": r.overall_fit_score,
                "confidence": r.confidence,
                "hard_gates": r.hard_gates,
                "components": r.components,
                "naics_median_award_amount": r.naics_median_award_amount,
                "naics_sb_win_rate_pct": r.naics_sb_win_rate_pct,
            }
            for r in results[:limit]
        ],
    }
