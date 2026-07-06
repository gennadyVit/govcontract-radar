import os
import requests

API_BASE = os.getenv("SCORING_API_URL", "http://localhost:8000")


def score_opportunities(profile: dict, limit: int = 50) -> dict:
    resp = requests.post(
        f"{API_BASE}/score",
        json=profile,
        params={"limit": limit},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()
