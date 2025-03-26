import pandas as pd

# Load the new merged dataset
df = pd.read_csv("merged_df.csv")

# All major columns to evaluate
cols_to_check = [
    "Attack_Count",
    "GDP_USD",
    "GDP_per_capita_USD",
    "Internet_Penetration",
    "Cellular Subscription",
    "No. of Internet Users",
    "Broadband Subscription",
    "Population",
    "Population Growth",
    "Growth Rate (%)",
    "Penetration_Index",
    "Digital_Exposure_Index",
    "Economic_Exposure",
    "Connectivity_Score",
    "Attack_Density",
    "Growth_Adjusted_Risk"
]

# Count non-null fields per row
df["non_null_count"] = df[cols_to_check].notnull().sum(axis=1)

# Summary: how many rows have X non-null values
print("📊 Non-null value count per row:")
print(df["non_null_count"].value_counts().sort_index())

# Column-wise null summary
print("\n🧼 Column-wise missing value summary:")
print(df[cols_to_check].isnull().sum().sort_values(ascending=False))

# Dataset stats
print("\n📈 Dataset shape:", df.shape)
print("✅ Rows with at least 5 data points:", (df['non_null_count'] >= 5).sum())
print("🟠 Rows with 10+ data points:", (df['non_null_count'] >= 10).sum())
print("🟢 Fully enriched rows (all fields):", (df['non_null_count'] == len(cols_to_check)).sum())
print("🔴 Rows with ≤4 fields:", (df['non_null_count'] <= 4).sum())

# Year coverage
print("\n📅 Row count by year:")
print(df["Year"].value_counts().sort_index())

