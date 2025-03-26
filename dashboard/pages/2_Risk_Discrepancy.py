import streamlit as st
import pandas as pd
import plotly.express as px

# Load dataset
df = pd.read_csv("predictions_enriched.csv")

st.title("📊 Risk Discrepancy")
st.markdown("Analyze where the model's predictions diverge from actual recorded cyber attacks.")

# Calculate standard deviation of absolute error
error_std = df["Abs_Error"].std()

# Define risk classification based on standard deviation
def classify_risk(row):
    if row["Abs_Error"] > error_std:
        return "Underpredicted" if row["Prediction_Error"] < 0 else "Overpredicted"
    return "Within Model Range"

df["Risk_Class"] = df.apply(classify_risk, axis=1)

# Sidebar filters
with st.sidebar:
    st.subheader("🔍 Filter Risk Patterns")
    selected_year = st.selectbox("Select Year", sorted(df["Year"].unique(), reverse=True))
    selected_classes = st.multiselect("Risk Class", df["Risk_Class"].unique(), default=df["Risk_Class"].unique())
    selected_tiers = st.multiselect("GDP Tier", df["GDP_Tier"].dropna().unique(), default=df["GDP_Tier"].dropna().unique())

# Apply filters
filtered_df = df[
    (df["Year"] == selected_year) &
    (df["Risk_Class"].isin(selected_classes)) &
    (df["GDP_Tier"].isin(selected_tiers))
]

# Plot 1: Histogram of Absolute Errors
st.markdown("### 📉 Prediction Error Distribution (Absolute)")
fig1 = px.histogram(
    filtered_df,
    x="Abs_Error",
    nbins=40,
    color_discrete_sequence=["#91C8F6"],
    height=400
)
fig1.update_layout(xaxis_title="Absolute Prediction Error", yaxis_title="Count of Records")
st.plotly_chart(fig1, use_container_width=True)

# Plot 2: Actual vs Predicted
st.markdown("### 🎯 Actual vs Predicted Attack Count")

if filtered_df["Attack_Count"].nunique() > 1 and filtered_df["Predicted_Attack_Count"].nunique() > 1:
    fig2 = px.scatter(
        filtered_df,
        x="Attack_Count",
        y="Predicted_Attack_Count",
        color="Risk_Class",
        hover_data=["ISO3", "GDP_Tier", "Prediction_Error"],
        title="Actual vs Predicted Attack Count",
        color_discrete_map={
            "Overpredicted": "#E74C3C",
            "Underpredicted": "#3498DB",
            "Within Model Range": "#2ECC71"
        },
        opacity=0.8,
        height=500
    )
    fig2.update_traces(marker=dict(size=10))
    fig2.update_layout(xaxis_title="Actual", yaxis_title="Predicted")
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.warning("⚠️ Not enough data to plot scatter — try changing filters.")

