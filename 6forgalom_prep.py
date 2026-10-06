import json
import re

import pandas as pd

# === Paths
SRC_XLSX = "forgalom/Elozetes-EANF-tablazat-2025.xlsx"
SRC_GEOJSON = "forgalom/hu_megyek_raw.geojson"
OUT_CSV = "dashboard/data/eanf_2025.csv"
OUT_GEOJSON = "dashboard/data/hu_megyek.geojson"

# === Load Magyar Közút preliminary 2025 traffic table (header is on row 2)
df = pd.read_excel(SRC_XLSX, header=1)

df = df.rename(columns={
    "Útkategória": "Utkategoria",
    "Út száma": "Ut",
    "Megye": "Megye",
    "Szelvény": "Szelveny",
    "Érv.eleje": "Kezdet",
    "Érv.vége": "Veg",
    "Fekvés": "Fekves",
    "Adatforrás": "Adatforras",
    "ÉÁNF (Ej)": "EANF",
    "MOF (Ej)": "MOF",
    "Személy-gépkocsi": "Szemelyauto",
    "Autóbusz (egyes)": "Busz_szolo",
    "Autóbusz (csuklós)": "Busz_csuklos",
    "Szóló teher-gépkocsi": "Teher_szolo",
    "Pótkocsis teher-gépkocsi": "Teher_potkocsis",
    "Nyerges szerelvény": "Nyerges",
    "Motor-kerékpár": "Motor",
    "Kerékpár": "Kerekpar",
})


# === Chainage "12+ 697" -> 12.697 km (also tolerates "44 + 046", "11_424")
def parse_km(value):
    m = re.search(r"(\d+)\s*[+_]\s*(\d+)", str(value))
    return int(m.group(1)) + int(m.group(2)) / 1000 if m else None


df["Kezdet_km"] = df["Kezdet"].map(parse_km)
df["Veg_km"] = df["Veg"].map(parse_km)
df["Hossz_km"] = (df["Veg_km"] - df["Kezdet_km"]).where(lambda s: s > 0)
# Source typos (e.g. road 8533 ends at "191+ 865") would dominate the totals
df.loc[df["Hossz_km"] > 60, "Hossz_km"] = None

# === Normalise county names to match the GeoJSON
df["Megye"] = (
    df["Megye"].astype(str).str.replace(" megye", "", regex=False).str.strip()
    .replace({"Csongrád": "Csongrád-Csanád", "3vagy13": "Ismeretlen"})
)

df["Ut"] = df["Ut"].astype(str).str.strip()
df["Fekves"] = df["Fekves"].map({"K": "Külterület", "L": "Belterület"}).fillna("Ismeretlen")

vehicle_cols = ["Szemelyauto", "Busz_szolo", "Busz_csuklos", "Teher_szolo",
                "Teher_potkocsis", "Nyerges", "Motor"]
for col in vehicle_cols + ["Kerekpar", "EANF", "MOF", "ÁNET"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# === Derived indicators
df["Jarmu_nap"] = df[vehicle_cols].sum(axis=1)
df["Nehez_nap"] = df[["Teher_szolo", "Teher_potkocsis", "Nyerges"]].sum(axis=1)
df["Nehez_arany"] = (df["Nehez_nap"] / df["Jarmu_nap"]).where(df["Jarmu_nap"] > 0)
# Daily traffic performance on the section (unit vehicle-km per day)
df["Ejkm_nap"] = df["EANF"] * df["Hossz_km"]

df = df.dropna(subset=["EANF"]).reset_index(drop=True)
df["Szakasz_id"] = df.index

keep = ["Szakasz_id", "Utkategoria", "Ut", "Megye", "Szelveny", "Kezdet_km", "Veg_km", "Hossz_km",
        "Fekves", "Adatforras", "EANF", "MOF", "Jarmu_nap", "Nehez_nap", "Nehez_arany",
        "Ejkm_nap"] + vehicle_cols + ["Kerekpar"]
df[keep].to_csv(OUT_CSV, index=False)
print(f"✅ {len(df)} road sections saved to {OUT_CSV}")

# === County boundaries: round coordinates to shrink the file
with open(SRC_GEOJSON, encoding="utf-8") as f:
    geo = json.load(f)


def round_coords(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 4), round(coords[1], 4)]
    return [round_coords(c) for c in coords]


def orient(ring, outer):
    # Plotly's d3-geo wants clockwise outer rings (counter-clockwise ones fill the whole
    # globe) and counter-clockwise holes, i.e. the reverse of the GeoJSON RFC 7946 order
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:]))
    return ring[::-1] if (area > 0) == outer else ring


for feature in geo["features"]:
    geom = feature["geometry"]
    polygons = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    polygons = [[orient(round_coords(ring), i == 0) for i, ring in enumerate(poly)]
                for poly in polygons]
    geom["coordinates"] = polygons[0] if geom["type"] == "Polygon" else polygons

with open(OUT_GEOJSON, "w", encoding="utf-8") as f:
    json.dump(geo, f, ensure_ascii=False, separators=(",", ":"))
print(f"✅ County boundaries saved to {OUT_GEOJSON}")
