import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(layout="wide")
st.title("📑 Prediction Log & Anomaly Insights")

# === Load dataset
@st.cache_data
def load_data():
    return pd.read_csv("predictions_enriched.csv")

df = load_data()

# === Sidebar filters
years = sorted(df["Year"].dropna().unique())
selected_year = st.sidebar.selectbox("Year", years, index=len(years)-1)

flag_types = ["All", "Suspicious Underreporting", "Normal"]
selected_flag = st.sidebar.selectbox("Transparency Flag", flag_types)

search_iso = st.sidebar.text_input("Search Country ISO3")

# === Filter
filtered_df = df[df["Year"] == selected_year]

if selected_flag != "All":
    filtered_df = filtered_df[filtered_df["Transparency_Flag"] == selected_flag]

if search_iso:
    filtered_df = filtered_df[filtered_df["ISO3"].str.contains(search_iso.upper())]

if filtered_df.empty:
    st.warning("No data found for the selected filters.")
    st.stop()

# === Top 10 Underreported (high error)
st.markdown("### ⚠️ Top 10 Underpredicted Cases")
under_df = filtered_df.sort_values("Prediction_Error").head(10)
st.dataframe(under_df[["ISO3", "Year", "Attack_Count", "Predicted_Attack_Count", "Prediction_Error", "Transparency_Flag"]])

under_chart = alt.Chart(under_df).mark_bar().encode(
    x=alt.X("ISO3:N", sort="-y"),
    y=alt.Y("Prediction_Error:Q"),
    color=alt.Color("Transparency_Flag:N"),
    tooltip=["Attack_Count", "Predicted_Attack_Count", "Prediction_Error"]
).properties(height=300)

st.altair_chart(under_chart, use_container_width=True)

# === Top 10 Overpredicted (opposite direction)
st.markdown("### ⚡ Top 10 Overpredicted Cases")
over_df = filtered_df.sort_values("Prediction_Error", ascending=False).head(10)
st.dataframe(over_df[["ISO3", "Year", "Attack_Count", "Predicted_Attack_Count", "Prediction_Error", "Transparency_Flag"]])

over_chart = alt.Chart(over_df).mark_bar().encode(
    x=alt.X("ISO3:N", sort="-y"),
    y=alt.Y("Prediction_Error:Q"),
    color=alt.Color("Transparency_Flag:N"),
    tooltip=["Attack_Count", "Predicted_Attack_Count", "Prediction_Error"]
).properties(height=300)

st.altair_chart(over_chart, use_container_width=True)

