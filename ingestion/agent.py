"""
Conversational AI agent for Contract Fit Engine.
Extracts company profile from natural language, identifies missing info,
scores opportunities, and generates RAG-based fit explanations.
"""
import os
import json
from openai import AzureOpenAI


SYSTEM_PROMPT = """You are a federal contract intelligence assistant helping small businesses find federal contract opportunities worth pursuing.

Your job is to:
1. Carefully extract ALL information already present in the user's message — NAICS codes, set-aside status, contract size range, keywords, agencies, states
2. Only ask follow-up questions for information that is genuinely missing and not inferable
3. Ask ONE focused follow-up question at a time
4. As soon as you have NAICS codes, set-aside eligibility, and contract size range, call the score_opportunities tool immediately
5. After scoring, help the user understand their results

Required information before scoring:
- NAICS code(s) — extract from message if present, or suggest based on industry description
- Set-aside eligibility — SBA, 8(a), WOSB, SDVOSB, HUBZone, or none
- Contract size range — min and max dollar values

If the user's message contains phrases like "541511 · SBA · $50K–$500K", extract: NAICS=541511, set_aside=SBA, min=50000, max=500000.
If the user mentions being SBA certified, set set_asides=["SBA"].
If the user gives a size range like "$50K–$500K", set min_contract_value=50000 and max_contract_value=500000.
Do NOT ask for information that is already in the user's message.

When you have all three required fields, call score_opportunities immediately without asking further questions.
Be conversational and helpful. Never ask for more than one thing at a time.

After scoring is complete, you can also answer general questions about:
- How scoring works: 5 weighted components — capability match (35%), past performance (25%), contract size fit (15%), competition favorability (15%), strategic keyword match (10%). Hard gates cap the score if set-aside eligibility doesn't match.
- Data freshness: opportunities are pulled weekly from SAM.gov. The last extract runs every Monday.
- What PURSUE/WATCH/NO_BID means: PURSUE = score ≥ 70, WATCH = 50–69, NO_BID = below 50.
- NAICS codes: 6-digit industry classification codes used by the federal government.
- Set-asides: contract reservations for certified small businesses (SBA, 8(a), WOSB, SDVOSB, HUBZone)."""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "score_opportunities",
            "description": "Score all federal opportunities against the extracted company profile. Call this when you have enough information about the company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name"},
                    "naics_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of NAICS codes e.g. ['541511', '541512']"
                    },
                    "set_asides": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Set-aside eligibilities e.g. ['SBA', '8(a)']"
                    },
                    "min_contract_value": {"type": "number", "description": "Minimum contract value in dollars"},
                    "max_contract_value": {"type": "number", "description": "Maximum contract value in dollars"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key capabilities and focus areas"
                    },
                    "past_agencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Federal agencies the company has worked with before"
                    },
                    "location_states": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "States where the company operates e.g. ['VA', 'MD', 'DC']"
                    },
                },
                "required": ["naics_codes", "set_asides", "min_contract_value", "max_contract_value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_fit",
            "description": "Generate a RAG-based explanation of why a specific opportunity fits (or doesn't fit) the company profile. Call when the user asks about a specific opportunity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notice_id": {"type": "string", "description": "The opportunity notice ID"},
                    "title": {"type": "string", "description": "Opportunity title"},
                    "description": {"type": "string", "description": "Full opportunity description"},
                    "agency": {"type": "string", "description": "Agency name"},
                    "naics_code": {"type": "string", "description": "NAICS code"},
                    "set_aside": {"type": "string", "description": "Set-aside type"},
                    "fit_score": {"type": "number", "description": "The computed fit score"},
                    "decision": {"type": "string", "description": "PURSUE, WATCH, or NO_BID"},
                },
                "required": ["title", "description", "fit_score", "decision"],
            },
        },
    },
]


def get_client():
    return AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2025-01-01-preview",
    )


def run_score_opportunities(args: dict) -> dict:
    """Execute scoring against the extracted profile."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from scoring import embed_profile, compute_fit_score
    from snowflake_conn import get_connection

    profile = {
        "name": args.get("company_name", "Your Company"),
        "naics_codes": args.get("naics_codes", []),
        "set_asides": args.get("set_asides", []),
        "clearances": [],
        "min_contract_value": args.get("min_contract_value", 0),
        "max_contract_value": args.get("max_contract_value", 10_000_000),
        "keywords": args.get("keywords", []),
        "past_agencies": args.get("past_agencies", []),
        "location_states": args.get("location_states", []),
        "embedding": None,
    }

    profile_embedding = embed_profile(profile)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("USE WAREHOUSE COMPUTE_WH")
    cursor.execute("""
        SELECT d.NOTICE_ID, d.TITLE, d.AGENCY_NAME, d.NAICS_CODE, d.NAICS_DESCRIPTION,
               d.SET_ASIDE, d.NAICS_SB_WIN_RATE_PCT, d.NAICS_MEDIAN_AWARD_AMOUNT,
               d.RESPONSE_DEADLINE, m.EMBEDDING, o.UI_LINK, o.DESCRIPTION
        FROM GOVCONTRACT.AGENTS.AGENT_DECISIONS d
        LEFT JOIN GOVCONTRACT.MARTS.MART_OPPORTUNITY_FEATURES m ON m.NOTICE_ID = d.NOTICE_ID
        LEFT JOIN GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES o ON o.NOTICE_ID = d.NOTICE_ID
    """)
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    conn.close()

    results = []
    for row in rows:
        opp = dict(zip(cols, row))
        emb = opp.get("EMBEDDING")
        if isinstance(emb, str):
            emb = json.loads(emb)
        opp["embedding"] = emb
        opp["naics_code"] = opp.get("NAICS_CODE")
        opp["agency"] = opp.get("AGENCY_NAME")
        opp["set_aside"] = opp.get("SET_ASIDE")
        opp["win_rate"] = float(opp["NAICS_SB_WIN_RATE_PCT"]) if opp.get("NAICS_SB_WIN_RATE_PCT") else None
        opp["median_award"] = float(opp["NAICS_MEDIAN_AWARD_AMOUNT"]) if opp.get("NAICS_MEDIAN_AWARD_AMOUNT") else None
        opp["title"] = opp.get("TITLE")
        opp["description"] = opp.get("DESCRIPTION")

        score, decision = compute_fit_score(opp, profile, profile_embedding)
        results.append({
            "notice_id": opp["NOTICE_ID"],
            "title": opp["TITLE"] or "",
            "agency": opp["AGENCY_NAME"] or "",
            "naics_code": opp["NAICS_CODE"] or "",
            "naics_description": opp["NAICS_DESCRIPTION"] or "",
            "set_aside": opp["SET_ASIDE"] or "",
            "fit_score": score,
            "decision": decision,
            "deadline": str(opp["RESPONSE_DEADLINE"] or "")[:10],
            "ui_link": opp["UI_LINK"] or "",
            "description": (opp["DESCRIPTION"] or "")[:500],
        })

    results.sort(key=lambda x: x["fit_score"], reverse=True)
    pursue = [r for r in results if r["decision"] == "PURSUE"]
    watch = [r for r in results if r["decision"] == "WATCH"]

    return {
        "profile": profile,
        "total": len(results),
        "pursue_count": len(pursue),
        "watch_count": len(watch),
        "top_results": results[:20],
    }


def run_explain_fit(args: dict, profile: dict) -> str:
    """Generate RAG explanation for a specific opportunity."""
    client = get_client()

    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5-mini")

    prompt = f"""You are a federal contracting advisor. Analyze whether this federal contract opportunity is a good fit for this company and explain your reasoning clearly and concisely.

COMPANY PROFILE:
- Name: {profile.get('name', 'The company')}
- NAICS codes: {', '.join(profile.get('naics_codes', []))}
- Set-aside eligibility: {', '.join(profile.get('set_asides', []))}
- Contract size range: ${profile.get('min_contract_value', 0):,.0f} – ${profile.get('max_contract_value', 0):,.0f}
- Keywords/capabilities: {', '.join(profile.get('keywords', []))}
- Past agencies: {', '.join(profile.get('past_agencies', []))}

OPPORTUNITY:
- Title: {args.get('title')}
- Agency: {args.get('agency', 'Unknown')}
- NAICS: {args.get('naics_code', 'Unknown')}
- Set-aside: {args.get('set_aside') or 'None'}
- Fit score: {args.get('fit_score')}/100
- Decision: {args.get('decision')}
- Description: {args.get('description', 'No description available')}

Provide a concise analysis with these sections:
✅ **Why this fits** — 2-3 specific reasons based on the opportunity and company profile
⚠️ **Watch out for** — 1-2 risks or gaps to investigate
📋 **Next steps** — 1-2 concrete actions if they want to pursue this

Keep it practical and specific. No generic advice."""

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a federal contracting advisor. Always respond with a detailed analysis."},
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=600,
    )
    msg = response.choices[0].message
    content = msg.content
    if not content or not content.strip():
        # Surface diagnostics so we can debug
        finish = response.choices[0].finish_reason
        return f"Model returned empty content (finish_reason={finish}). refusal={getattr(msg, 'refusal', None)}"
    return content


def chat(messages: list, profile: dict = None, scoring_done: bool = False) -> tuple[str, dict, dict]:
    """
    Run one turn of the agent.
    Returns (response_text, updated_profile, scoring_results)
    """
    client = get_client()
    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5-mini")

    system = SYSTEM_PROMPT
    if scoring_done and profile:
        system += f"\n\nSCORING IS ALREADY COMPLETE. Do NOT ask for company info or call score_opportunities again. The user's profile has been extracted: NAICS={profile.get('naics_codes')}, set-asides={profile.get('set_asides')}, size=${profile.get('min_contract_value'):,}–${profile.get('max_contract_value'):,}. Answer the user's question directly."

    full_messages = [{"role": "system", "content": system}] + messages

    response = client.chat.completions.create(
        model=deployment,
        messages=full_messages,
        tools=TOOLS,
        tool_choice="auto",
        max_completion_tokens=800,
    )

    msg = response.choices[0].message
    scoring_results = None

    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        fn_name = tool_call.function.name
        fn_args = json.loads(tool_call.function.arguments)

        if fn_name == "score_opportunities":
            scoring_results = run_score_opportunities(fn_args)
            profile = scoring_results["profile"]
            tool_result = json.dumps({
                "total": scoring_results["total"],
                "pursue_count": scoring_results["pursue_count"],
                "watch_count": scoring_results["watch_count"],
                "top_3": scoring_results["top_results"][:3],
            })
        elif fn_name == "explain_fit":
            tool_result = run_explain_fit(fn_args, profile or {})
        else:
            tool_result = "Tool not found."

        follow_up = client.chat.completions.create(
            model=deployment,
            messages=full_messages + [
                {"role": "assistant", "content": None, "tool_calls": msg.tool_calls},
                {"role": "tool", "tool_call_id": tool_call.id, "content": tool_result},
            ],
            max_completion_tokens=800,
        )
        response_text = follow_up.choices[0].message.content or ""
    else:
        response_text = msg.content or ""

    # Fallback if model returned nothing
    if not response_text.strip():
        if scoring_results:
            response_text = f"I've scored {scoring_results['total']} opportunities against your profile. Found {scoring_results['pursue_count']} to PURSUE and {scoring_results['watch_count']} to WATCH. See the results below — click 'Why does this fit me?' on any card for a detailed analysis."
        elif scoring_done:
            response_text = "Scoring uses 5 weighted components: capability match (35%), past performance (25%), contract size fit (15%), competition favorability (15%), and keyword match (10%). Hard eligibility gates cap the score if your set-aside status doesn't match the opportunity's requirements."
        else:
            response_text = "Got it. Could you tell me your NAICS code(s)? For example, 541511 for custom software development."

    return response_text, profile, scoring_results
