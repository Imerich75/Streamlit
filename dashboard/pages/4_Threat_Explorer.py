import streamlit as st
import pandas as pd
import altair as alt
import numpy as np

st.set_page_config(layout="wide")
st.title("🔥 Threat Index Explorer")

@st.cache_data
def load_data():
    df = pd.read_csv("predictions_enriched.csv")
    # 1) Exclude rows where:
    #   - Attack_Count = 0
    #   - Adjusted_Threat_Index = 0
    #   - Growth_Adjusted_Risk < 0
    df = df[
        (df["Attack_Count"] > 0) &
        (df["Adjusted_Threat_Index"] > 0) &
        (df["Growth_Adjusted_Risk"] >= 0)
    ].copy()
    return df

df = load_data()

# === Determine available years
years = sorted(df["Year"].dropna().unique())

# === Default year is 2018, if present
if 2018 in years:
    default_year_index = list(years).index(2018)
else:
    default_year_index = 0

selected_year = st.sidebar.selectbox("Select Year", years, index=default_year_index)

index_options = [
    "Adjusted_Threat_Index",
    "Attack_Density",
    "Growth_Adjusted_Risk",
    "Digital_Exposure_Index",
    "Connectivity_Score"
]
selected_index = st.sidebar.selectbox("Select Threat Index", index_options)

# === Filter to chosen year & non-null index
filtered_df = df[(df["Year"] == selected_year) & (df[selected_index].notnull())]

if filtered_df.empty:
    st.warning(f"No data available for year={selected_year} or index={selected_index}.")
    st.stop()

# === Safely clip values for log scale
def clip_for_log(series):
    return np.where(series <= 0, 1e-9, series)

clipped_index = clip_for_log(filtered_df[selected_index])
clipped_pop = clip_for_log(filtered_df["Population"])

min_x = clipped_index.min()
max_x = clipped_index.max()
domain_x = [min_x * 0.8, max_x * 1.2] if min_x > 0 else [1e-9, max_x * 1.2]

min_y = clipped_pop.min()
max_y = clipped_pop.max()
domain_y = [min_y * 0.8, max_y * 1.2] if min_y > 0 else [1e-9, max_y * 1.2]

# === 1) Histogram
st.markdown(f"### 📊 Distribution of {selected_index} (clipped for log scale)")
hist_data = pd.DataFrame({selected_index: clipped_index})
hist = alt.Chart(hist_data).mark_bar().encode(
    x=alt.X(f"{selected_index}:Q", bin=alt.Bin(maxbins=40)),
    y="count()"
).properties(height=300)
st.altair_chart(hist, use_container_width=True)

# === 2) Bubble Chart
st.markdown("### 🧠 Log-Scaled Index vs Population (Bubble = Attack Count)")

bubble_data = filtered_df.copy()
bubble_data["clipped_index"] = clipped_index
bubble_data["clipped_pop"] = clipped_pop

# Custom color scale for GDP tier
color_scale = alt.Scale(
    domain=["High Income", "Upper-Middle Income", "Lower-Middle Income", "Low Income"],
    range=["#0000FF", "#87CEFA", "#FFA07A", "#FF0000"]
)

chart = alt.Chart(bubble_data).mark_circle(opacity=0.6).encode(
    x=alt.X("clipped_index:Q", title=f"{selected_index} (clipped)", scale=alt.Scale(type="log", domain=domain_x)),
    y=alt.Y("clipped_pop:Q", title="Population (clipped)", scale=alt.Scale(type="log", domain=domain_y)),
    size=alt.Size("Attack_Count:Q", legend=alt.Legend(title="Attack Count")),
    color=alt.Color("GDP_Tier:N", scale=color_scale, legend=alt.Legend(title="GDP Tier")),
    tooltip=["ISO3", selected_index, "Population", "Attack_Count", "GDP_Tier"]
).properties(height=500)

st.altair_chart(chart, use_container_width=True)

# === 3) Data Table
with st.expander("📋 Show Underlying Data"):
    st.dataframe(
        filtered_df[["ISO3", "Year", selected_index, "Attack_Count", "Population", "GDP_Tier"]],
        use_container_width=True
    )

