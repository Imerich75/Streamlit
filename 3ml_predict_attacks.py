import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import matplotlib.pyplot as plt

# === Load the enriched dataset
df = pd.read_csv("merged_fully_enriched.csv")

# === Define your SAFE input features (no Attack_Count derived fields)
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

# 1. Drop rows missing the target
df = df.dropna(subset=["Attack_Count"]).copy()

# 2. Sanitize input data
X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1e9, 1e9)
y = df["Attack_Count"]

# 3. Train / Test Split + Model
X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=42)
model = RandomForestRegressor(n_estimators=200, random_state=42)
model.fit(X_train, y_train)

# 4. Evaluate on test set
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
print(f"📉 Mean Absolute Error: {mae:.2f}")

# 5. Feature importance
importances = pd.Series(model.feature_importances_, index=features).sort_values()
importances.plot(kind="barh", title="Feature Importance", figsize=(10, 6))
plt.tight_layout()
plt.savefig("feature_importance.png")
print("✅ Saved feature_importance.png")

# 6. Predict full dataset
df["Predicted_Attack_Count"] = model.predict(X)
df["Prediction_Error"] = df["Attack_Count"] - df["Predicted_Attack_Count"]
df["Abs_Error"] = df["Prediction_Error"].abs()

# 7. Compute standard deviation + create Z_Error
error_std = df["Abs_Error"].std()
df["Z_Error"] = df["Prediction_Error"] / error_std  # standardized error

def classify_risk(z):
    if pd.isna(z):
        return "Unknown"
    elif z < -1:   # less than -1 stdev → Underpredicted
        return "Underpredicted"
    elif z > 1:    # more than +1 stdev → Overpredicted
        return "Overpredicted"
    else:
        return "Within Model Range"

df["Risk_Class"] = df["Z_Error"].apply(classify_risk)

# 8. Save final dataset
df.to_csv("merged_with_predictions.csv", index=False)
print("✅ Saved predictions to merged_with_predictions.csv")

# 9. Anomaly Reporting
print("\n⚠️ Top 10 underpredicted (lowest Z_Error):")
under_df = df.sort_values("Z_Error").head(10)[["ISO3", "Year", "Attack_Count", "Predicted_Attack_Count", "Prediction_Error", "Z_Error"]]
print(under_df)

print("\n⚡ Top 10 overpredicted (highest Z_Error):")
over_df = df.sort_values("Z_Error", ascending=False).head(10)[["ISO3", "Year", "Attack_Count", "Predicted_Attack_Count", "Prediction_Error", "Z_Error"]]
print(over_df)

