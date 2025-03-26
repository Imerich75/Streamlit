import pandas as pd
import numpy as np

# === Load file from ML prediction step
df = pd.read_csv("merged_with_predictions.csv")

# === GDP Risk Ratio
df["GDP_Risk_Ratio"] = df["Prediction_Error"] / df["GDP_per_capita_USD"]

# === Transparency Flag
df["Transparency_Flag"] = np.where(
    (df["Prediction_Error"] < -25) & (df["Internet_Penetration"] > 60),
    "Suspicious Underreporting",
    "Normal"
)

# === Risk Class based on absolute error bands
def classify_risk(error):
    if pd.isna(error):
        return "Unknown"
    elif error < -50:
        return "Underpredicted"
    elif error > 50:
        return "Overpredicted"
    else:
        return "Within Model Range"

df["Risk_Class"] = df["Prediction_Error"].apply(classify_risk)

# === Log Transform Safely (Clip or set invalid to NaN)
def safe_log(series):
    # Convert <=0 to NaN, so log10 doesn't break
    return np.where(
        (series <= 0) | (series.isna()),
        np.nan,
        np.log10(series)
    )

df["Log_Predicted_Attack_Count"] = safe_log(df["Predicted_Attack_Count"])
df["Log_GDP_Risk_Ratio"] = safe_log(df["GDP_Risk_Ratio"])

# === Save the enhanced version to a new file
output_file = "predictions_enriched.csv"
df.to_csv(output_file, index=False)
print(f"✅ Custom metrics added → saved to {output_file}")

