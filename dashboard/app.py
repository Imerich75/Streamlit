import streamlit as st

# Set page config
st.set_page_config(
    page_title="Cyber Risk Intelligence Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main title
st.title("🌐 Cyber Risk Intelligence Dashboard")

# Intro text
st.markdown("""
Welcome to the EPAM probation task dashboard.

This interface integrates data engineering, enrichment, machine learning predictions, and strategic risk insight — all in one modular dashboard.

### 🧭 Use the sidebar to explore:

- 📊 Vanilla BI
- ⚠️ Risk Discrepancy (Predicted vs Actual Attacks)
- 🗺️ Transparency Map (Flagging suspicious underreporting)
- 🔥 Threat Index Explorer
- 🔍 Log-Scaled Visuals
- 📂 Raw Data Browser
- 📈 2025–2030 Forecast
- 🚗 Forgalmi térkép (Magyar Közút ÉÁNF 2025)
""")

# Optional: Add visual cue for data freshness
st.info("🔄 All insights are based on the enriched dataset: `merged_fully_enriched.csv`")

