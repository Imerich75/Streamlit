import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide")
st.title("🕵️ Transparency Heatmap – Reporting Honesty Index")

@st.cache_data
def load_data():
    df = pd.read_csv("predictions_enriched.csv").copy()

    required = ["Attack_Count", "Predicted_Attack_Count", "ISO3", "Year"]
    if not all(col in df.columns for col in required):
        st.error("Missing required columns in the dataset.")
        st.stop()

    # Compute Reporting Honesty Index: log10((Attack+1)/(Predicted+1))
    df["Honesty_Index"] = np.log10((df["Attack_Count"] + 1) / (df["Predicted_Attack_Count"] + 1))
    return df

df = load_data()

# Sidebar – year selector
st.sidebar.header("📅 Filter")
years = sorted(df["Year"].dropna().unique())
default_year = years[-1] if years else None
selected_year = st.sidebar.selectbox("Select Year", years, index=years.index(default_year) if default_year else 0)

filtered = df[df["Year"] == selected_year].copy()
if filtered.empty:
    st.warning("No data available for this year.")
    st.stop()

# Color range based on symmetric max
min_val = filtered["Honesty_Index"].min()
max_val = filtered["Honesty_Index"].max()
abs_max = max(abs(min_val), abs(max_val))
range_color = (-abs_max, abs_max)

# Heatmap
fig = px.choropleth(
    filtered,
    locations="ISO3",
    color="Honesty_Index",
    hover_name="ISO3",
    color_continuous_scale="RdBu_r",  # Red = underreporting, Blue = overreporting
    range_color=range_color,
    color_continuous_midpoint=0,
    title=f"Reporting Honesty Index (log10 ratio) — {selected_year}"
)
fig.update_geos(showcountries=True, projection_type="natural earth")
fig.update_layout(margin=dict(r=0, l=0, t=40, b=0))
st.plotly_chart(fig, use_container_width=True)

# Raw data table
with st.expander("📋 Show Raw Data"):
    st.dataframe(
        filtered[["ISO3", "Year", "Attack_Count", "Predicted_Attack_Count", "Honesty_Index"]],
        use_container_width=True
    )

