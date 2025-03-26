import pandas as pd
import pycountry

def safe_iso3(name):
    try:
        return pycountry.countries.lookup(name).alpha_3
    except:
        return None

# === Load UMD
print("📂 Loading UMD dataset...")
df = pd.read_excel("cyberattacks/UMD Cyber Attacks Dataset.xlsx", engine="openpyxl")
df = df[["country", "year"]].dropna()
df = df.rename(columns={"country": "Country", "year": "Year"})
df["ISO3"] = df["Country"].apply(safe_iso3)
df = df.dropna(subset=["ISO3", "Year"])
df["Year"] = df["Year"].astype(int)
cyber = df.groupby(["ISO3", "Year"]).size().reset_index(name="Attack_Count")

# === GDP
print("💰 Loading GDP...")
gdp = pd.read_csv("gdp/world_country_gdp_usd.csv")
gdp = gdp.rename(columns={"Country Code": "ISO3", "year": "Year"})
gdp = gdp[["ISO3", "Year", "GDP_USD", "GDP_per_capita_USD"]]

# === Internet
print("🌐 Loading Internet...")
net = pd.read_csv("internetusers/Final.csv")
net = net.rename(columns={
    "Code": "ISO3",
    "Year": "Year",
    "Internet Users(%)": "Internet_Penetration"
})
net = net[[
    "ISO3", "Year", "Internet_Penetration",
    "Cellular Subscription", "No. of Internet Users", "Broadband Subscription"
]]

# === Population
print("👥 Loading Population...")
pop = pd.read_csv("population/countries_population.csv")
pop = pop[[
    "ISO3", "Year", "Population",
    "Population Growth", "Growth Rate (%)", "Decade"
]]

# === Merge
print("🔗 Merging datasets...")
df = cyber.merge(gdp, on=["ISO3", "Year"], how="outer")
df = df.merge(net, on=["ISO3", "Year"], how="outer")
df = df.merge(pop, on=["ISO3", "Year"], how="outer")

# === Filter timeframe
df = df[df["Year"].between(2005, 2024)]

# === Fill missing attack counts post-2014
df.loc[(df["Year"] >= 2014) & (df["Attack_Count"].isna()), "Attack_Count"] = 0

# === Clean up
df["non_null_count"] = df[[
    "Attack_Count", "GDP_per_capita_USD", "Internet_Penetration", "Population"
]].notnull().sum(axis=1)
df = df[df["non_null_count"] >= 3].drop(columns=["non_null_count"])
df.reset_index(drop=True, inplace=True)

# === Calculated Columns
print("🧠 Generating calculated fields...")
df["Penetration_Index"] = df["Attack_Count"] / (
    (df["GDP_per_capita_USD"].fillna(1)) * ((df["Internet_Penetration"].fillna(50) / 100) + 0.01)
)

df["Digital_Exposure_Index"] = df["Internet_Penetration"] * df["No. of Internet Users"]
df["Economic_Exposure"] = df["GDP_USD"] / df["No. of Internet Users"]
df["Connectivity_Score"] = df["Broadband Subscription"] + df["Cellular Subscription"]
df["Attack_Density"] = df["Attack_Count"] / df["Population"]
df["Growth_Adjusted_Risk"] = df["Attack_Count"] * df["Growth Rate (%)"]

# === Save
print("💾 Saving full enriched dataset...")
df.to_csv("merged_df.csv", index=False)
print(f"✅ Saved {df.shape[0]} rows to merged_df.csv")

