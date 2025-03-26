import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🔎 Full Data Browser")

# === Load dataset
@st.cache_data
def load_data():
    return pd.read_csv("predictions_enriched.csv")

df = load_data()

# === Sidebar filters
st.sidebar.header("📋 Filters")

years = sorted(df["Year"].dropna().unique())
selected_year = st.sidebar.selectbox("Year", years, index=len(years)-1)

gdp_tiers = sorted(df["GDP_Tier"].dropna().unique())
selected_gdp = st.sidebar.multiselect("GDP Tier", gdp_tiers, default=gdp_tiers)

flags = ["All", "Suspicious Underreporting", "Normal"]
selected_flag = st.sidebar.selectbox("Transparency Flag", flags)

search_iso = st.sidebar.text_input("Search ISO3")

# === Filter data
filtered_df = df[df["Year"] == selected_year]
if selected_flag != "All":
    filtered_df = filtered_df[filtered_df["Transparency_Flag"] == selected_flag]

if selected_gdp:
    filtered_df = filtered_df[filtered_df["GDP_Tier"].isin(selected_gdp)]

if search_iso:
    filtered_df = filtered_df[filtered_df["ISO3"].str.contains(search_iso.upper())]

# === Show filtered table
st.markdown("### 📄 Filtered Dataset")

st.dataframe(
    filtered_df.sort_values("Prediction_Error", ascending=False),
    use_container_width=True
)

# === Optional: Export download
with st.expander("⬇️ Export Filtered Data as CSV"):
    st.download_button(
        "Download CSV",
        filtered_df.to_csv(index=False).encode("utf-8"),
        file_name=f"filtered_data_{selected_year}.csv",
        mime="text/csv"
    )

