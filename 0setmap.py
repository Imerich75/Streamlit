import os
import pandas as pd

base_path = "."
extensions = [".csv", ".xlsx"]

def describe_file(file_path):
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path, engine="openpyxl")
        else:
            return None
        return {
            "rows": len(df),
            "columns": df.columns.tolist(),
            "non_null_counts": df.notnull().sum().to_dict()
        }
    except Exception as e:
        return {"error": str(e)}

found_any = False

# Walk through datasets folder
for root, _, files in os.walk(base_path):
    for file in files:
        if any(file.endswith(ext) for ext in extensions):
            found_any = True
            full_path = os.path.join(root, file)
            print(f"\n📂 {file} — {full_path}")
            result = describe_file(full_path)
            if result is None:
                print("⚠️ Skipped (unsupported format)")
            elif "error" in result:
                print(f"❌ Error reading file: {result['error']}")
            else:
                print(f"📏 Rows: {result['rows']}")
                print("📊 Columns & Non-Null Counts:")
                for col in result["columns"]:
                    print(f"   • {col} — {result['non_null_counts'].get(col, 0)} non-null")

if not found_any:
    print("⚠️ No dataset files found in:", base_path)

