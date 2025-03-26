import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

# === Load raw merged dataset
df = pd.read_csv("merged_df.csv")
df.replace([np.inf, -np.inf], np.nan, inplace=True)

# === Derived Indicators

# Economic Exposure
df["Economic_Exposure"] = df["GDP_USD"] / df["Population"]
df["Log_Economic_Exposure"] = np.log10(df["Economic_Exposure"].replace(0, np.nan))

# Digital Exposure
df["Digital_Exposure_Index"] = (
    df["Internet_Penetration"] * df["Cellular Subscription"] * df["Broadband Subscription"]
)
df["Digital_Exposure_Index_B"] = df["Digital_Exposure_Index"] / 1e9

# Population log scale
df["Log_Population"] = np.log10(df["Population"].replace(0, np.nan))

# Attack Density per million
df["Attack_Density"] = (df["Attack_Count"] / df["Population"]) * 1_000_000

# Growth-Adjusted Risk
df["Growth_Adjusted_Risk"] = df["Attack_Density"] * df["Population Growth"]

# Connectivity Score
df["Connectivity_Score"] = (
    df["Broadband Subscription"] + df["Cellular Subscription"] + df["Internet_Penetration"]
) / 3

# Adjusted Threat Index
df["Adjusted_Threat_Index"] = df["Attack_Density"] * (df["Internet_Penetration"] / 100)

# Log transforms
df["Log_Attack_Count"] = np.log10(df["Attack_Count"].replace(0, np.nan))
df["Log_GDP_USD"] = np.log10(df["GDP_USD"].replace(0, np.nan))
df["Log_Internet_Users"] = np.log10(df["No. of Internet Users"].replace(0, np.nan))

# === Groupings

def gdp_tier(gdp):
    if pd.isna(gdp): return "Unknown"
    if gdp >= 40000: return "High Income"
    if gdp >= 12000: return "Upper-Middle Income"
    if gdp >= 4000: return "Lower-Middle Income"
    return "Low Income"

df["GDP_Tier"] = df["GDP_per_capita_USD"].apply(gdp_tier)

def net_group(pen):
    if pd.isna(pen): return "Unknown"
    if pen < 30: return "Emerging"
    if pen < 70: return "Developing"
    return "Advanced"

df["Net_Group"] = df["Internet_Penetration"].apply(net_group)

# === Normalize selected features

scaler = MinMaxScaler()
for col in [
    "Adjusted_Threat_Index",
    "Attack_Density",
    "Growth_Adjusted_Risk",
    "Connectivity_Score",
    "Digital_Exposure_Index",
    "GDP_USD",
    "Internet_Penetration"
]:
    if col in df.columns:
        df[f"{col}_Norm"] = scaler.fit_transform(df[[col]].fillna(0))

# === Save
df.to_csv("merged_fully_enriched.csv", index=False)
print("✅ Enrichment complete → saved as merged_fully_enriched.csv")

