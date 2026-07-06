import json
import streamlit as st

st.set_page_config(page_title="Company Profile — GovContract Radar", layout="wide")
st.title("Company Profile")
st.caption("Define your company so the system can score opportunities against it.")

if "profile" not in st.session_state:
    st.session_state.profile = {}

with st.form("profile_form"):
    st.subheader("About your company")
    company_summary = st.text_area(
        "Company summary",
        value=st.session_state.profile.get("company_summary", ""),
        placeholder="Brief description of what your company does for federal clients...",
        height=100,
    )

    st.subheader("Capabilities")
    capabilities_raw = st.text_area(
        "Core capabilities (one per line)",
        value="\n".join(st.session_state.profile.get("capabilities", [])),
        placeholder="Cloud migration\nDevSecOps\nSoftware development\nCybersecurity",
        height=120,
    )

    col1, col2 = st.columns(2)
    with col1:
        naics_raw = st.text_input(
            "NAICS codes (comma-separated)",
            value=", ".join(st.session_state.profile.get("naics", [])),
            placeholder="541511, 541512, 541519",
        )
        certifications_raw = st.text_input(
            "Certifications (comma-separated)",
            value=", ".join(st.session_state.profile.get("certifications", [])),
            placeholder="8a, SDVOSB, WOSB",
        )
        clearance_options = ["None", "Public Trust", "Secret", "Top Secret", "Top Secret/SCI"]
        saved_clearance = st.session_state.profile.get("clearance", "None") or "None"
        clearance = st.selectbox(
            "Clearance level",
            clearance_options,
            index=clearance_options.index(saved_clearance),
        )

    with col2:
        min_size = st.number_input(
            "Preferred contract min ($)",
            value=st.session_state.profile.get("preferred_contract_size", {}).get("min", 100000),
            step=50000,
            format="%d",
        )
        max_size = st.number_input(
            "Preferred contract max ($)",
            value=st.session_state.profile.get("preferred_contract_size", {}).get("max", 5000000),
            step=100000,
            format="%d",
        )
        locations_raw = st.text_input(
            "Preferred locations (comma-separated states)",
            value=", ".join(st.session_state.profile.get("locations", [])),
            placeholder="VA, MD, DC, TX",
        )

    st.subheader("Targeting")
    col3, col4 = st.columns(2)
    with col3:
        keywords_target_raw = st.text_area(
            "Keywords to target (one per line)",
            value="\n".join(st.session_state.profile.get("keywords_target", [])),
            placeholder="cloud\nAWS\nzero trust\nfedRAMP",
            height=100,
        )
        agency_prefs_raw = st.text_input(
            "Preferred agencies (comma-separated)",
            value=", ".join(st.session_state.profile.get("agency_preferences", [])),
            placeholder="DEPT OF DEFENSE, DHS",
        )
    with col4:
        keywords_avoid_raw = st.text_area(
            "Keywords to avoid (one per line)",
            value="\n".join(st.session_state.profile.get("keywords_avoid", [])),
            placeholder="construction\nhardware\nlogistics",
            height=100,
        )
        prime_sub_options = ["either", "prime", "sub"]
        saved_prime_or_sub = st.session_state.profile.get("prime_or_sub", "either") or "either"
        prime_or_sub = st.selectbox(
            "Prime or sub?",
            prime_sub_options,
            index=prime_sub_options.index(saved_prime_or_sub),
        )

    submitted = st.form_submit_button("Save Profile & Score", type="primary")

if submitted:
    profile = {
        "company_summary": company_summary.strip(),
        "capabilities": [c.strip() for c in capabilities_raw.splitlines() if c.strip()],
        "naics": [n.strip() for n in naics_raw.split(",") if n.strip()],
        "certifications": [c.strip() for c in certifications_raw.split(",") if c.strip()],
        "clearance": clearance if clearance != "None" else "",
        "preferred_contract_size": {"min": int(min_size), "max": int(max_size)},
        "locations": [l.strip() for l in locations_raw.split(",") if l.strip()],
        "keywords_target": [k.strip() for k in keywords_target_raw.splitlines() if k.strip()],
        "keywords_avoid": [k.strip() for k in keywords_avoid_raw.splitlines() if k.strip()],
        "agency_preferences": [a.strip() for a in agency_prefs_raw.split(",") if a.strip()],
        "prime_or_sub": prime_or_sub,
        "psc": [],
        "past_performance": [],
        "contract_vehicles": [],
        "avoid": [],
        "team_size": 1,
        "max_contract_executable": float(max_size),
    }
    st.session_state.profile = profile
    st.success("Profile saved. Go to **Opportunity Feed** to see your matches.")
    with st.expander("Profile JSON"):
        st.json(profile)
