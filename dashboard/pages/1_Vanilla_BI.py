import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np


# --- CSV betöltése
df = pd.read_csv("predictions_enriched.csv")  # Update path if needed

st.title("🌍 Vanilla BI – GDP Insights")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Classic Bar", "🍩 Donut Tier", "📈 Scatter Retro", "🗺️ Choropleth Map"])

# --- TAB 1: Bar chart – Top 10 GDP per capita
with tab1:
    st.subheader("Top 10 Countries by GDP per Capita")
    
    years = sorted(df["Year"].unique())
    selected_year = st.selectbox("Select Year", years, index=len(years)-1)

    filtered = df[df["Year"] == selected_year]
    filtered_unique = filtered.drop_duplicates(subset="ISO3")  # csak egy sor per ország

    top10 = filtered_unique.sort_values("GDP_per_capita_USD", ascending=False).head(10)
    fig1 = px.bar(top10, x="ISO3", y="GDP_per_capita_USD", color="ISO3", text_auto=".2s")
    fig1.update_layout(template="plotly_white", showlegend=False)
    st.plotly_chart(fig1, use_container_width=True)


# --- TAB 2: Donut chart – GDP Tier megoszlás
with tab2:
    st.subheader("GDP Tier Distribution")
    
    selected_year_2 = st.selectbox("Select Year", years, index=len(years)-1, key="donut_year")
    filtered_2 = df[df["Year"] == selected_year_2]
    filtered_unique_2 = filtered_2.drop_duplicates(subset="ISO3")

    gdp_tier_counts = filtered_unique_2["GDP_Tier"].value_counts().reset_index()
    gdp_tier_counts.columns = ["GDP Tier", "Count"]

    fig2 = px.pie(
        gdp_tier_counts,
        values="Count",
        names="GDP Tier",
        hole=0.5,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig2.update_layout(template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)

# --- TAB 3: Scatter plot – GDP vs Threat Index
with tab3:
    st.subheader("GDP per Capita vs Threat Index")
    fig3 = px.scatter(
        df,
        x="GDP_per_capita_USD",
        y="Adjusted_Threat_Index",
        size="Attack_Count",
        color="GDP_Tier",
        hover_name="ISO3",
        template="ggplot2",
    )
    fig3.update_layout(xaxis_type="log", yaxis_type="log")
    st.plotly_chart(fig3, use_container_width=True)

# --- TAB 4: Choropleth Map – GDP per Capita világtérképen
with tab4:
    st.subheader("World Map – GDP per Capita (Log Scale)")

    # Távolítjuk a 0 vagy negatív értékeket, nehogy log hibát dobjon
    map_data = df[df["GDP_per_capita_USD"] > 0].copy()
    map_data["Log_GDP_per_capita"] = map_data["GDP_per_capita_USD"].apply(lambda x: np.log10(x))

    fig4 = px.choropleth(
        map_data,
        locations="ISO3",
        color="Log_GDP_per_capita",
        color_continuous_scale="Viridis",
        hover_name="ISO3",
        labels={"Log_GDP_per_capita": "Log₁₀ GDP per Capita"},
    )
    fig4.update_layout(template="plotly", geo=dict(showframe=False, showcoastlines=False))
    st.plotly_chart(fig4, use_container_width=True)


