import os
import sys
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

st.set_page_config(
    page_title="Contract Fit Engine",
    page_icon="🟦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global styles ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="collapsedControl"] { display: none; }
  section[data-testid="stSidebar"] { display: none; }

  .hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #1d4ed8 100%);
    border-radius: 16px;
    padding: 60px 48px;
    margin-bottom: 40px;
    color: white;
  }
  .hero-tag {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    color: #93c5fd;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 4px 14px;
    border-radius: 20px;
    margin-bottom: 20px;
  }
  .hero h1 {
    font-size: 42px;
    font-weight: 800;
    line-height: 1.15;
    margin: 0 0 16px 0;
    color: white;
  }
  .hero p {
    font-size: 18px;
    color: #cbd5e1;
    line-height: 1.6;
    max-width: 600px;
    margin: 0;
  }
  .stat-row {
    display: flex;
    gap: 32px;
    margin-top: 36px;
  }
  .stat { text-align: left; }
  .stat-num { font-size: 32px; font-weight: 800; color: white; }
  .stat-label { font-size: 13px; color: #94a3b8; margin-top: 2px; }

  .feature-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 28px 24px;
    height: 100%;
  }
  .feature-icon { font-size: 28px; margin-bottom: 12px; }
  .feature-title { font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
  .feature-desc { font-size: 14px; color: #64748b; line-height: 1.6; }

  .tech-pill {
    display: inline-block;
    background: #f1f5f9;
    color: #334155;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 14px;
    border-radius: 20px;
    margin: 4px;
  }
  .tech-category { font-size: 12px; font-weight: 700; color: #94a3b8; letter-spacing: 1px; text-transform: uppercase; margin: 20px 0 8px 0; }

  .step {
    display: flex;
    align-items: flex-start;
    gap: 20px;
    margin-bottom: 28px;
  }
  .step-num {
    min-width: 36px;
    height: 36px;
    background: #1d4ed8;
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 15px;
  }
  .step-content h4 { margin: 0 0 4px 0; font-size: 15px; color: #0f172a; }
  .step-content p  { margin: 0; font-size: 14px; color: #64748b; line-height: 1.5; }

  .section-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #1d4ed8;
    margin-bottom: 8px;
  }
  .section-title {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 8px;
  }
  .section-sub {
    font-size: 15px;
    color: #64748b;
    margin-bottom: 36px;
  }

  .nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0 24px 0;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 32px;
  }
  .nav-logo { font-size: 20px; font-weight: 800; color: #0f172a; }
  .nav-logo span { color: #1d4ed8; }

  .form-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 36px;
  }

  .result-header {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 24px;
  }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "home"
if "results_df" not in st.session_state:
    st.session_state.results_df = None
if "profile_used" not in st.session_state:
    st.session_state.profile_used = {}
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "chat_profile" not in st.session_state:
    st.session_state.chat_profile = None
if "chat_results" not in st.session_state:
    st.session_state.chat_results = None


# ── Data helpers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_scored_opportunities():
    from snowflake_conn import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("USE WAREHOUSE COMPUTE_WH")
    cursor.execute("""
        SELECT d.NOTICE_ID, d.TITLE, d.AGENCY_NAME, d.NAICS_CODE, d.NAICS_DESCRIPTION,
               d.SET_ASIDE, d.FIT_SCORE, d.DECISION, d.RESPONSE_DEADLINE, d.POSTED_DATE,
               o.UI_LINK, o.DESCRIPTION
        FROM GOVCONTRACT.AGENTS.AGENT_DECISIONS d
        LEFT JOIN GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES o ON o.NOTICE_ID = d.NOTICE_ID
        WHERE d.DECIDED_AT IS NOT NULL
        ORDER BY d.FIT_SCORE DESC NULLS LAST
    """)
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    conn.close()
    df = pd.DataFrame(rows, columns=cols)
    df["FIT_SCORE"] = pd.to_numeric(df["FIT_SCORE"], errors="coerce")
    return df


def score_custom_profile(profile: dict) -> pd.DataFrame:
    from scoring import embed_profile, compute_fit_score
    from snowflake_conn import get_connection
    import json as _json

    profile_embedding = embed_profile(profile)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("USE WAREHOUSE COMPUTE_WH")
    cursor.execute("""
        SELECT d.NOTICE_ID, d.TITLE, d.AGENCY_NAME, d.NAICS_CODE, d.NAICS_DESCRIPTION,
               d.SET_ASIDE, d.NAICS_SB_WIN_RATE_PCT, d.NAICS_MEDIAN_AWARD_AMOUNT,
               d.RESPONSE_DEADLINE, d.POSTED_DATE,
               m.EMBEDDING, o.UI_LINK, o.DESCRIPTION
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
            emb = _json.loads(emb)
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
            "TITLE": opp["TITLE"] or "",
            "AGENCY_NAME": opp["AGENCY_NAME"] or "",
            "NAICS_CODE": opp["NAICS_CODE"] or "",
            "NAICS_DESCRIPTION": opp["NAICS_DESCRIPTION"] or "",
            "SET_ASIDE": opp["SET_ASIDE"] or "",
            "FIT_SCORE": score,
            "DECISION": decision,
            "RESPONSE_DEADLINE": opp["RESPONSE_DEADLINE"],
            "UI_LINK": opp["UI_LINK"] or "",
            "DESCRIPTION": opp["DESCRIPTION"] or "",
        })

    df = pd.DataFrame(results)
    df["FIT_SCORE"] = pd.to_numeric(df["FIT_SCORE"], errors="coerce")
    return df.sort_values("FIT_SCORE", ascending=False)


def render_card(row):
    score = float(row.get("FIT_SCORE") or 0)
    title = row.get("TITLE") or "Untitled"
    agency = row.get("AGENCY_NAME") or ""
    naics = row.get("NAICS_CODE") or ""
    naics_desc = row.get("NAICS_DESCRIPTION") or ""
    set_aside = row.get("SET_ASIDE") or "None"
    deadline = str(row.get("RESPONSE_DEADLINE") or "")[:10]
    link = row.get("UI_LINK") or ""
    decision = row.get("DECISION") or "NO_BID"
    desc_raw = row.get("DESCRIPTION") or ""
    description = desc_raw[:300] if not desc_raw.startswith("http") else ""
    icons = {"PURSUE": "🟢", "WATCH": "🟡", "NO_BID": "🔴"}

    with st.container(border=True):
        col_main, col_score = st.columns([5, 1])
        with col_main:
            st.markdown(f"**{title}**")
            st.caption(f"{agency} · NAICS {naics} {naics_desc} · Set-aside: {set_aside or 'None'}")
            parts = []
            if deadline:
                parts.append(f"Deadline: {deadline}")
            if link:
                parts.append(f"[View on SAM.gov →]({link})")
            st.caption("  ".join(parts))
            if description:
                st.caption(description + "…")
        with col_score:
            st.markdown(f"### {score:.0f}")
            st.markdown(f"{icons.get(decision, '⚪')} **{decision}**")


# ── Nav helper ────────────────────────────────────────────────────────────────
def nav():
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        st.markdown('<div class="nav-logo">Contract<span>Fit</span> Engine</div>', unsafe_allow_html=True)
    with c2:
        if st.button("Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
    with c3:
        if st.button("Find Bids", use_container_width=True):
            st.session_state.page = "find"
            st.rerun()
    with c4:
        if st.button("How It Works", use_container_width=True):
            st.session_state.page = "tech"
            st.rerun()
    st.markdown("<hr style='margin:0 0 32px 0; border-color:#e2e8f0;'>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":
    nav()

    st.markdown("""
    <div class="hero">
      <div class="hero-tag">AI-Powered Federal Contract Intelligence</div>
      <h1>Find federal bids<br>worth pursuing</h1>
      <p>Contract Fit Engine scans thousands of publicly available federal contract opportunities from SAM.gov, scores each one against your company profile, and surfaces the bids most worth your time — so you focus on winning, not searching.</p>
      <div class="stat-row">
        <div class="stat"><div class="stat-num">1,387</div><div class="stat-label">Opportunities scored</div></div>
        <div class="stat"><div class="stat-num">5</div><div class="stat-label">Scoring dimensions</div></div>
        <div class="stat"><div class="stat-num">AI</div><div class="stat-label">Vector similarity matching</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("→ Find Opportunities for My Company", type="primary", use_container_width=False):
        st.session_state.page = "find"
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="section-label">What it does</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Built for small businesses that compete for federal contracts</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Stop manually reviewing hundreds of SAM.gov listings. Enter your company profile once and get a ranked, prioritized list in seconds.</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="feature-card">
          <div class="feature-icon">🎯</div>
          <div class="feature-title">Company-Fit Scoring</div>
          <div class="feature-desc">Every opportunity gets a 0–100 fit score based on your NAICS codes, past agency experience, contract size range, set-aside eligibility, and keywords — not just keyword matching.</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="feature-card">
          <div class="feature-icon">🔍</div>
          <div class="feature-title">Semantic Search</div>
          <div class="feature-desc">Describe what your company does in plain English. Our vector search finds semantically similar opportunities even when the exact words don't match.</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="feature-card">
          <div class="feature-icon">⚡</div>
          <div class="feature-title">Clear Decisions</div>
          <div class="feature-desc">Each opportunity is labeled PURSUE, WATCH, or NO BID — so your team knows immediately where to focus. Hard eligibility gates filter out bids you can't win.</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("→ Get Started", type="primary"):
        st.session_state.page = "find"
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# FIND BIDS PAGE — Single-column ChatGPT-style
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "find":
    nav()

    # ── Example cards (shown only before conversation starts) ─────────────────
    if not st.session_state.chat_messages:
        st.markdown('<div class="section-title" style="text-align:center;margin-bottom:8px;">Tell me about your company</div>', unsafe_allow_html=True)
        st.markdown('<div style="text-align:center;color:#64748b;margin-bottom:32px;">Describe what your company does — the agent will ask follow-up questions, then score 1,387 federal opportunities against your profile.</div>', unsafe_allow_html=True)

        examples = [
            ("🖥️ IT / Software", "8(a) · 541511 · $100K–$10M", "We're an 8(a) IT firm doing software development and cloud migration for DoD and VA."),
            ("⚙️ Engineering", "SBA · 541330 · $200K–$20M", "Small SBA engineering firm specializing in electrical systems and facility sustainment."),
            ("🔒 Cybersecurity", "8(a) · 541512 · $500K–$50M", "8(a) cybersecurity firm with SECRET clearance offering network security and PKI support."),
            ("🏗️ Construction", "SBA · 236220 · $500K–$15M", "SBA general contractor focused on federal facility renovation in the Southeast."),
        ]
        c1, c2, c3, c4 = st.columns(4, gap="small")
        for col, (title, meta, desc) in zip([c1, c2, c3, c4], examples):
            with col:
                st.markdown(
                    f"""<div style="border:1px solid #e2e8f0;border-radius:10px;padding:16px;background:#f8fafc;height:140px;">
                    <div style="font-weight:600;font-size:13px;margin-bottom:4px;">{title}</div>
                    <div style="font-size:11px;color:#64748b;margin-bottom:8px;">{meta}</div>
                    <div style="font-size:12px;color:#374151;line-height:1.4;">{desc}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Chat history ──────────────────────────────────────────────────────────
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Inline results inside chat ────────────────────────────────────────────
    if st.session_state.chat_results:
        profile = st.session_state.chat_profile or {}
        results = st.session_state.chat_results
        top = results["top_results"]

        with st.chat_message("assistant"):
            fc1, fc2 = st.columns([2, 1])
            with fc1:
                decision_filter = st.multiselect(
                    "Filter", ["PURSUE", "WATCH", "NO_BID"], default=["PURSUE", "WATCH"], key="chat_filter"
                )
            with fc2:
                score_min = st.slider("Min score", 0, 100, 50, key="chat_score_min")

            filtered = [r for r in top if r["decision"] in decision_filter and r["fit_score"] >= score_min]
            st.caption(f"Showing {len(filtered)} of top 20 results")

            for opp in filtered:
                with st.container(border=True):
                    badge_color = {"PURSUE": "#16a34a", "WATCH": "#d97706", "NO_BID": "#6b7280"}.get(opp["decision"], "#6b7280")
                    left, right = st.columns([5, 1])
                    with left:
                        st.markdown(f"**{opp['title'] or 'Untitled'}**")
                        st.caption(f"{opp['agency']} · NAICS {opp['naics_code']} · {opp.get('set_aside') or 'Open'} · Due {opp['deadline'] or 'TBD'}")
                        desc = opp.get("description", "")
                        if desc and not desc.startswith("http"):
                            st.markdown(f"<small>{desc[:250]}…</small>", unsafe_allow_html=True)
                    with right:
                        st.markdown(
                            f'<div style="text-align:center;background:{badge_color};color:white;border-radius:8px;padding:8px 4px;font-weight:700;">'
                            f'{opp["fit_score"]}<br><small>{opp["decision"]}</small></div>',
                            unsafe_allow_html=True,
                        )
                        if opp.get("ui_link"):
                            st.link_button("SAM.gov →", opp["ui_link"], use_container_width=True)

                    btn_key = f"explain_{opp['notice_id']}"
                    explain_key = f"explain_text_{opp['notice_id']}"
                    if explain_key not in st.session_state:
                        if st.button("Why does this fit me?", key=btn_key):
                            from agent import run_explain_fit
                            with st.spinner("Generating fit analysis…"):
                                try:
                                    explanation = run_explain_fit(
                                        {
                                            "notice_id": opp["notice_id"],
                                            "title": opp["title"],
                                            "description": opp["description"],
                                            "agency": opp["agency"],
                                            "naics_code": opp["naics_code"],
                                            "set_aside": opp["set_aside"],
                                            "fit_score": opp["fit_score"],
                                            "decision": opp["decision"],
                                        },
                                        profile,
                                    )
                                except Exception as e:
                                    explanation = f"Error: {e}"
                            st.session_state[explain_key] = explanation
                            st.rerun()
                    else:
                        st.markdown(st.session_state[explain_key])

        if st.button("← Start New Search", key="new_search"):
            st.session_state.chat_messages = []
            st.session_state.chat_profile = None
            st.session_state.chat_results = None
            st.rerun()

    # ── Chat input (always visible until results shown) ───────────────────────
    scoring_done = st.session_state.chat_results is not None
    placeholder = "Ask a follow-up question about scoring, results, or data…" if scoring_done else "Describe your company — industry, certifications, contract size, past agencies…"
    user_input = st.chat_input(placeholder)
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        try:
            from agent import chat as agent_chat
            with st.spinner("Thinking…"):
                response_text, updated_profile, scoring_results = agent_chat(
                    st.session_state.chat_messages,
                    st.session_state.chat_profile,
                    scoring_done=scoring_done,
                )
            st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
            if updated_profile:
                st.session_state.chat_profile = updated_profile
            if scoring_results:
                st.session_state.chat_results = scoring_results
        except Exception as e:
            st.session_state.chat_messages.append({"role": "assistant", "content": f"Agent error: {e}"})
        st.rerun()



# ════════════════════════════════════════════════════════════════════════════
# HOW IT WORKS / TECH PAGE — Option A layout
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "tech":
    nav()

    st.markdown('<div class="section-label">Under the Hood</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">How Contract Fit Engine works</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">From raw SAM.gov data to a ranked, scored opportunity feed. Fully automated, weekly refresh.</div>', unsafe_allow_html=True)

    # ── Stats bar ─────────────────────────────────────────────────────────────
    s1, s2, s3 = st.columns(3)
    s1.metric("Opportunities scored", "1,387")
    s2.metric("Scoring dimensions", "5")
    s3.metric("Pipeline refresh", "Weekly")

    st.markdown("---")

    # ── Two-column body ───────────────────────────────────────────────────────
    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("#### Pipeline")
        st.markdown("""
        <div class="step">
          <div class="step-num">1</div>
          <div class="step-content">
            <h4>Ingest from SAM.gov</h4>
            <p>Apache Airflow pulls active federal contract opportunities weekly from the SAM.gov public API. Raw data lands in Snowflake.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">2</div>
          <div class="step-content">
            <h4>Model with dbt</h4>
            <p>dbt transforms raw opportunity data into clean, analytics-ready models — opportunities, agencies, NAICS categories, and scoring features.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">3</div>
          <div class="step-content">
            <h4>Embed with Azure OpenAI</h4>
            <p>Each opportunity description is converted into a 1,536-dimension vector embedding using Azure OpenAI's text-embedding-3-small model.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">4</div>
          <div class="step-content">
            <h4>Score for fit</h4>
            <p>A conversational AI agent extracts your company profile from natural language, then a weighted scoring engine computes a FIT_SCORE (0–100) across 5 dimensions. As win/loss outcome data is captured from USASpending.gov, this rule-based engine will be replaced by an ML model trained on real award data.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">5</div>
          <div class="step-content">
            <h4>Index for search</h4>
            <p>Azure AI Search indexes all opportunities with their embeddings, enabling hybrid keyword + vector search across the full dataset.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">6</div>
          <div class="step-content">
            <h4>Surface in dashboard</h4>
            <p>Streamlit dashboard shows the ranked opportunity feed, semantic search, analytics, and AI-generated fit explanations.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("#### Scoring Model")
        st.markdown("""
        | Component | Weight | What it measures |
        |---|---|---|
        | Capability similarity | **35%** | Cosine similarity between opportunity and company profile embeddings |
        | Past performance | **25%** | NAICS code and past agency match |
        | Contract size fit | **15%** | Value within company's comfortable range |
        | Competition | **15%** | Small biz win rate + set-aside match |
        | Strategic alignment | **10%** | Keyword overlap with company focus |
        """)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Hard gates** cap scores for eligibility mismatches:")
        st.markdown("""
        - Set-aside mismatch → max score **40**
        - Clearance required → max score **50**
        - Contract 10× above max → max score **65**
        """)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Decision thresholds**")
        st.markdown("🟢 **PURSUE** — score ≥ 70  \n🟡 **WATCH** — score 50–69  \n🔴 **NO BID** — score < 50")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Roadmap: ML-based scoring**")
        st.markdown("Current rule-based weights will be replaced by an ML classifier trained on USASpending.gov award outcomes and user bid results (won/lost).")
        st.markdown('<span class="tech-pill">XGBoost</span><span class="tech-pill">Feature store in Snowflake</span><span class="tech-pill">USASpending.gov</span>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('[View full scoring methodology →](https://gennadyvit.github.io/contract-fit-engine/scoring-model.html)')

    # ── Tech stack ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Tech Stack")

    ts1, ts2, ts3 = st.columns(3)
    with ts1:
        st.markdown('<div class="tech-category">Data & Pipeline</div>', unsafe_allow_html=True)
        st.markdown('<span class="tech-pill">Apache Airflow</span><span class="tech-pill">Snowflake</span><span class="tech-pill">dbt</span><span class="tech-pill">Python</span><span class="tech-pill">SAM.gov API</span>', unsafe_allow_html=True)
    with ts2:
        st.markdown('<div class="tech-category">AI & Search</div>', unsafe_allow_html=True)
        st.markdown('<span class="tech-pill">Azure OpenAI GPT-4o</span><span class="tech-pill">text-embedding-3-small</span><span class="tech-pill">Azure AI Search</span><span class="tech-pill">RAG</span><span class="tech-pill">Function calling</span>', unsafe_allow_html=True)
    with ts3:
        st.markdown('<div class="tech-category">Infrastructure</div>', unsafe_allow_html=True)
        st.markdown('<span class="tech-pill">Azure Container Apps</span><span class="tech-pill">Azure Container Registry</span><span class="tech-pill">Streamlit</span><span class="tech-pill">Docker</span>', unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("→ Try It Now", type="primary"):
        st.session_state.page = "find"
        st.rerun()
