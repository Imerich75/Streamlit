import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# === 1. Betöltés
df = pd.read_csv("merged_fully_enriched.csv")  # <- ezt állítsd be saját útvonaladra

# === 2. Feature lista (csak SAFE bemenetek!)
features = [
    "GDP_per_capita_USD",
    "GDP_USD",
    "Internet_Penetration",
    "Population",
    "Population Growth",
    "Growth Rate (%)",
    "No. of Internet Users",
    "Cellular Subscription",
    "Broadband Subscription",
    "Connectivity_Score",
    "Digital_Exposure_Index",
    "Economic_Exposure"
]

# === 3. Célváltozó és tisztítás
df = df.dropna(subset=["Attack_Count"]).copy()
X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1e9, 1e9)
y = df["Attack_Count"]

# === 4. Modell betanítása
X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=42)
model = RandomForestRegressor(n_estimators=200, random_state=42)
model.fit(X_train, y_train)

# === 5. Jövőbeli bemenetek előállítása (2025–2030)
recent_years = df[df["Year"] >= 2018]
future_rows = []

for iso in recent_years["ISO3"].unique():
    country_data = recent_years[recent_years["ISO3"] == iso].sort_values("Year")
    if len(country_data) < 2:
        continue

    feature_deltas = {}
    for feat in features:
        series = country_data[feat]
        delta = series.diff().mean()
        last_value = series.iloc[-1]
        feature_deltas[feat] = (last_value, delta)

    last_year = country_data["Year"].max()
    for year in range(2025, 2031):
        row = {"ISO3": iso, "Year": year}
        for feat in features:
            base, delta = feature_deltas[feat]
            projected = base + (year - last_year) * delta
            row[feat] = max(projected, 0)
        future_rows.append(row)

# === 6. Predikció futtatása
future_df = pd.DataFrame(future_rows)
X_future = future_df[features].replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1e9, 1e9)
future_df["Predicted_Attack_Count"] = model.predict(X_future)

# === 7. GDP_Risk_Ratio kiszámítása
future_df["GDP_Risk_Ratio"] = future_df["Predicted_Attack_Count"] / future_df["GDP_USD"]
future_df["GDP_Risk_Ratio"].replace([np.inf, -np.inf], np.nan, inplace=True)
future_df["GDP_Risk_Ratio"] = future_df["GDP_Risk_Ratio"].fillna(0)

# === 8. Mentés
future_df.to_csv("future_predictions.csv", index=False)
print("✅ Predikció mentve: future_predictions.csv")
