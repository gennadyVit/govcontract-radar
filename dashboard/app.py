import os
import sys
import json
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

st.set_page_config(
    page_title="Contract Fit Engine",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .badge-pursue { background:#dcfce7; color:#166534; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
  .badge-watch  { background:#fef3c7; color:#92400e; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
  .badge-nobid  { background:#fee2e2; color:#991b1b; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
  .opp-card { border:1px solid #e2e5ec; border-radius:8px; padding:16px 20px; margin-bottom:12px; background:#fff; }
  .opp-title { font-size:15px; font-weight:600; margin-bottom:4px; }
  .opp-meta  { font-size:12px; color:#6b7280; }
  .score-big { font-size:28px; font-weight:700; color:#1b4fd8; }
</style>
""", unsafe_allow_html=True)


# ── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_opportunities():
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
            o.DESCRIPTION
        FROM GOVCONTRACT.AGENTS.AGENT_DECISIONS d
        LEFT JOIN GOVCONTRACT.RAW.STG_SAM_OPPORTUNITIES o ON o.NOTICE_ID = d.NOTICE_ID
        WHERE d.DECIDED_AT IS NOT NULL
        ORDER BY d.FIT_SCORE DESC NULLS LAST
    """)
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    conn.close()
    df = pd.DataFrame(rows, columns=cols)
    for col in ["FIT_SCORE"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def search_opportunities(query: str, top: int = 20) -> list[dict]:
    from search_index import search
    return search(query, top=top)


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎯 Contract Fit Engine")
    st.markdown("---")

    view = st.radio("View", ["Opportunity Feed", "Search", "Analytics"], label_visibility="collapsed")

    st.markdown("### Filters")
    decision_filter = st.multiselect(
        "Decision",
        ["PURSUE", "WATCH", "NO_BID"],
        default=["PURSUE", "WATCH"],
    )
    score_min = st.slider("Min Fit Score", 0, 100, 50)

    st.markdown("### Company Profile")
    profile_name = st.selectbox("Profile", ["technova", "startup", "apexeng", "cyberops"], format_func=lambda x: {
        "technova": "TechNova Solutions (8(a), $100K–$10M)",
        "startup": "BluePath Tech (SBA, $50K–$500K)",
        "apexeng": "Apex Engineering Group (SBA, $200K–$20M)",
        "cyberops": "CyberOps Federal Solutions (8(a), $500K–$50M)",
    }.get(x, x))

    st.markdown("---")
    if st.button("↻ Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── Load data ────────────────────────────────────────────────────────────────
try:
    df = load_opportunities()
    data_ok = True
except Exception as e:
    st.error(f"Could not connect to Snowflake: {e}")
    data_ok = False
    df = pd.DataFrame()


# ── Helpers ──────────────────────────────────────────────────────────────────
def badge(decision):
    cls = {"PURSUE": "pursue", "WATCH": "watch", "NO_BID": "nobid"}.get(decision, "nobid")
    return f'<span class="badge-{cls}">{decision}</span>'


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
    desc_raw = (row.get("DESCRIPTION") or "")
    description = desc_raw[:300] if not desc_raw.startswith("http") else ""

    decision_colors = {"PURSUE": "🟢", "WATCH": "🟡", "NO_BID": "🔴"}
    icon = decision_colors.get(decision, "⚪")

    with st.container(border=True):
        col_main, col_score = st.columns([5, 1])
        with col_main:
            st.markdown(f"**{title}**")
            st.caption(f"{agency} · NAICS {naics} {naics_desc} · Set-aside: {set_aside}")
            deadline_str = f"Deadline: {deadline}" if deadline else ""
            link_str = f"[View on SAM.gov →]({link})" if link else ""
            st.caption(f"{deadline_str}{'  ' if deadline_str and link_str else ''}{link_str}")
            if description:
                st.caption(description + "…")
        with col_score:
            st.markdown(f"### {score:.0f}")
            st.markdown(f"{icon} **{decision}**")


# ── Views ────────────────────────────────────────────────────────────────────
if view == "Opportunity Feed":
    st.markdown("## Opportunity Feed")

    if data_ok and not df.empty:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total scored", len(df))
        col2.metric("PURSUE", len(df[df.DECISION == "PURSUE"]))
        col3.metric("WATCH", len(df[df.DECISION == "WATCH"]))
        col4.metric("Avg score", f"{df.FIT_SCORE.mean():.1f}")

        st.markdown("---")

        # Filter
        filtered = df[
            df.DECISION.isin(decision_filter) &
            (df.FIT_SCORE >= score_min)
        ]

        if filtered.empty:
            st.info("No opportunities match the current filters.")
        else:
            st.caption(f"Showing {len(filtered)} opportunities")
            for _, row in filtered.iterrows():
                render_card(row)
    else:
        st.info("No data loaded.")

elif view == "Search":
    st.markdown("## Search Opportunities")
    query = st.text_input("Describe what you're looking for", placeholder="e.g. cloud DevSecOps modernization DoD")

    if query:
        with st.spinner("Searching…"):
            try:
                results = search_opportunities(query, top=20)
                if results:
                    st.caption(f"{len(results)} results")
                    for r in results:
                        render_card({
                            "TITLE": r.get("title"),
                            "AGENCY_NAME": r.get("agency"),
                            "NAICS_CODE": r.get("naics_code"),
                            "NAICS_DESCRIPTION": "",
                            "SET_ASIDE": r.get("set_aside"),
                            "FIT_SCORE": r.get("fit_score", 0),
                            "DECISION": r.get("decision"),
                            "RESPONSE_DEADLINE": r.get("deadline"),
                            "UI_LINK": r.get("ui_link"),
                            "DESCRIPTION": "",
                        })
                else:
                    st.info("No results found.")
            except Exception as e:
                st.error(f"Search error: {e}")

elif view == "Analytics":
    st.markdown("## Analytics")

    if data_ok and not df.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Decision breakdown")
            counts = df.DECISION.value_counts().reset_index()
            counts.columns = ["Decision", "Count"]
            st.bar_chart(counts.set_index("Decision"))

        with col2:
            st.markdown("#### Top agencies (PURSUE + WATCH)")
            top_df = df[df.DECISION.isin(["PURSUE", "WATCH"])]
            if not top_df.empty:
                agency_counts = top_df.AGENCY_NAME.value_counts().head(10).reset_index()
                agency_counts.columns = ["Agency", "Count"]
                st.bar_chart(agency_counts.set_index("Agency"))

        st.markdown("#### Score distribution")
        st.bar_chart(df.groupby(df.FIT_SCORE.round(-1)).size().rename("Count"))

        st.markdown("#### Top PURSUE opportunities")
        pursue_df = df[df.DECISION == "PURSUE"][["TITLE", "AGENCY_NAME", "FIT_SCORE", "RESPONSE_DEADLINE", "UI_LINK"]].copy()
        pursue_df.columns = ["Title", "Agency", "Score", "Deadline", "Link"]
        st.dataframe(pursue_df, use_container_width=True, hide_index=True)
    else:
        st.info("No data loaded.")
