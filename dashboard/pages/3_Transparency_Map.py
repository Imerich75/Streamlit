import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(layout="wide")
st.title("🌍 Z-Error Choropleth (Log Distance from Zero)")

@st.cache_data
def load_data():
    df = pd.read_csv("predictions_enriched.csv").copy()
    # 1) Check we have Z_Error
    if "Z_Error" not in df.columns:
        st.error("`Z_Error` column not found. Please ensure your ML pipeline sets it.")
        st.stop()
    # 2) Create logZ = sign(Z_Error) * log10(1 + |Z_Error|)
    df["logZ"] = np.where(
        df["Z_Error"].isna(),
        np.nan,
        np.sign(df["Z_Error"]) * np.log10(1 + df["Z_Error"].abs())
    )
    return df

df = load_data()

# === Sidebar
st.sidebar.header("🗂 Filter")
years = sorted(df["Year"].dropna().unique())
default_year = years[-1] if len(years)>0 else None
selected_year = st.sidebar.selectbox("Select Year", years, index=years.index(default_year) if default_year else 0)

filtered_df = df[df["Year"] == selected_year].copy()
if filtered_df.empty:
    st.warning(f"No data for year {selected_year}.")
    st.stop()

# === Compute min/max of logZ to define color range
min_logz = filtered_df["logZ"].min()
max_logz = filtered_df["logZ"].max()

# We want symmetrical scale around 0, so:
abs_max = max(abs(min_logz), abs(max_logz))
range_color = (-abs_max, abs_max)

title = f"Z-Error Choropleth (Log Distance) — {selected_year}"

fig = px.choropleth(
    filtered_df,
    locations="ISO3",
    color="logZ",
    hover_name="ISO3",
    color_continuous_scale="RdBu",
    color_continuous_midpoint=0,      # zero-centered
    range_color=range_color,
    title=title
)
fig.update_geos(showcountries=True, projection_type="natural earth")
fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
st.plotly_chart(fig, use_container_width=True)

# === Table
with st.expander("📋 Show Raw Data"):
    st.dataframe(
        filtered_df[
            ["ISO3", "Year", "Attack_Count", "Predicted_Attack_Count", "Z_Error", "logZ"]
        ],
        use_container_width=True
    )

