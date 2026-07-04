import os
import math

AZURE_ENABLED = bool(os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"))
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
_client = None


def _get_client():
    global _client
    if _client is None and AZURE_ENABLED:
        from openai import AzureOpenAI
        _client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-01",
        )
    return _client


def get_embedding(text: str) -> list[float] | None:
    client = _get_client()
    if client is None:
        return None
    response = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def get_profile_embedding(profile: dict) -> list[float] | None:
    """Compute profile embedding once to reuse across all opportunities."""
    if not AZURE_ENABLED or _get_client() is None:
        return None
    profile_text = (
        profile.get("company_summary", "") + " " +
        " ".join(profile.get("capabilities", [])) + " " +
        " ".join(profile.get("keywords_target", []))
    ).strip()
    if not profile_text:
        return None
    return get_embedding(profile_text)


def compute_capability_similarity(opportunity: dict, profile: dict, profile_embedding: list[float] | None = None) -> float | None:
    """
    Returns cosine similarity (0-1) between opportunity text and company profile,
    or None if Azure OpenAI is not configured (fit_score.py will use stub value).
    Pass profile_embedding to avoid recomputing it for every opportunity.
    """
    if not AZURE_ENABLED or _get_client() is None:
        return None

    opp_text = f"{opportunity.get('TITLE', '')} {opportunity.get('DESCRIPTION', '')}".strip()
    if not opp_text:
        return None

    if profile_embedding is None:
        profile_embedding = get_profile_embedding(profile)
    if not profile_embedding:
        return None

    opp_embedding = get_embedding(opp_text)
    if opp_embedding:
        return cosine_similarity(opp_embedding, profile_embedding)
    return None
