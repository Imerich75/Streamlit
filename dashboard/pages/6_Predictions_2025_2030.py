import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# === Load data
df = pd.read_csv("future_predictions.csv")

st.title("📈 2025–2030 Forecast")
st.markdown("This page uses only precomputed prediction data for future years. No recalculation is performed.")

# === Year selection
years = sorted(df["Year"].unique())
selected_year = st.selectbox("Select year", years, index=0)
filtered = df[df["Year"] == selected_year].copy()

# --- Remove duplicate countries (ISO3-wise)
filtered = filtered.drop_duplicates(subset="ISO3")

# === Tabs (3 only)
tab1, tab2, tab3 = st.tabs([
    "🌍 Global Trend",
    f"📊 Top 10 Countries ({selected_year})",
    f"🗺️ Forecast Map ({selected_year})",
])

# --- Tab 1: Global yearly total
with tab1:
    st.subheader("Global Predicted Attack Count (total by year)")
    trend = df.groupby("Year")["Predicted_Attack_Count"].sum().reset_index()
    fig1 = px.line(trend, x="Year", y="Predicted_Attack_Count", markers=True)
    fig1.update_layout(template="plotly_white", yaxis_title="Total Predicted Attack Count")
    st.plotly_chart(fig1, use_container_width=True)

# --- Tab 2: Top 10 countries
with tab2:
    st.subheader(f"Top 10 Countries – Predicted Attack Count ({selected_year})")
    top10 = filtered.sort_values("Predicted_Attack_Count", ascending=False).head(10)
    fig2 = px.bar(top10, x="ISO3", y="Predicted_Attack_Count", color="ISO3", text_auto=".2s")
    fig2.update_layout(template="plotly_dark", showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

# --- Tab 3: Choropleth map – log scale
with tab3:
    st.subheader(f"World Map – Predicted Attack Count (Log Scale, {selected_year})")
    map_df = filtered[filtered["Predicted_Attack_Count"] > 0].copy()
    map_df["Log_Predicted"] = map_df["Predicted_Attack_Count"].apply(lambda x: np.log10(x))

    fig3 = px.choropleth(
        map_df,
        locations="ISO3",
        color="Log_Predicted",
        color_continuous_scale="Blues",
        hover_name="ISO3",
        labels={"Log_Predicted": "Log₁₀ Predicted Attack Count"},
    )
    fig3.update_layout(template="plotly", geo=dict(showframe=False, showcoastlines=False))
    st.plotly_chart(fig3, use_container_width=True)

