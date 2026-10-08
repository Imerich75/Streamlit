import gzip
import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
import streamlit as st

st.set_page_config(page_title="Forgalmi térkép", page_icon="🚗", layout="wide")
st.title("🚗 Forgalmi térkép – országos közutak, 2025")
st.markdown(
    "Magyar Közút **előzetes 2025-ös évi átlagos napi forgalom** (ÉÁNF, egységjármű/nap) "
    "adatai útszakaszonként, megyei összesítéssel."
)

DATA_DIR = Path(__file__).resolve().parent / "data"
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
BAR_BLUE = "#2a78d6"
# Traffic-map convention: light yellow (quiet) through red to dark purple (busy)
LINE_SCALE = ["#ffe680", "#fdb44b", "#f7782a", "#e2401f", "#bb1428", "#860632", "#4b0a3c"]
# On the dark basemap brightness runs the other way: dim purple (quiet) to glowing yellow (busy)
LINE_SCALE_DARK = ["#5c2a8a", "#9b2f7f", "#d6456c", "#f6734f", "#fdab53", "#fde26b", "#fffbd0"]
# Lower class bounds; the last class is open-ended
LINE_METRICS = {
    "ÉÁNF (Ej/nap)": ("EANF", [0, 500, 1_000, 2_000, 3_000, 5_000, 7_500, 10_000, 15_000,
                               20_000, 30_000, 45_000, 60_000, 80_000], "{:,.0f}"),
    "Nehézgépjármű-arány (%)": ("Nehez_szazalek", [0, 2, 4, 6, 8, 10, 12, 15, 20, 25, 30, 40],
                                "{:.0f}"),
}

VEHICLE_LABELS = {
    "Szemelyauto": "Személygépkocsi",
    "Busz_szolo": "Autóbusz (szóló)",
    "Busz_csuklos": "Autóbusz (csuklós)",
    "Teher_szolo": "Szóló tehergépkocsi",
    "Teher_potkocsis": "Pótkocsis tehergépkocsi",
    "Nyerges": "Nyerges szerelvény",
    "Motor": "Motorkerékpár",
}
CATEGORY_ORDER = ["autópálya", "autóút", "I. rendű főút", "II. rendű főút",
                  "összekötőút", "bekötőút"]


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_DIR / "eanf_2025.csv", dtype={"Ut": str})
    with open(DATA_DIR / "hu_megyek.geojson", encoding="utf-8") as f:
        geo = json.load(f)
    return df, geo


@st.cache_data
def load_geometry():
    path = DATA_DIR / "eanf_2025_geom.json.gz"
    if not path.exists():
        return {}, {}, [], {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    return ({int(k): v for k, v in data["sections"].items()}, data["roads"], data.get("gaps", []),
            {int(k): v for k, v in data.get("lanes", {}).items()})


def gap_sections(gaps):
    """Stretches missing from the table, valued as the mean of the two neighbouring sections."""
    by_id = df.set_index("Szakasz_id")
    rows, geom = [], {}
    for i, gap in enumerate(gaps):
        prev, nxt = by_id.loc[gap["elozo"]], by_id.loc[gap["kovetkezo"]]
        sid = -1 - i  # negative ids never clash with real sections
        geom[sid] = gap["vonal"]
        rows.append({
            "Szakasz_id": sid, "Ut": gap["ut"], "Utkategoria": prev["Utkategoria"],
            "Megye": prev["Megye"], "Fekves": prev["Fekves"],
            "Kezdet_km": gap["k0"], "Veg_km": gap["k1"], "Hossz_km": gap["k1"] - gap["k0"],
            "EANF": (prev["EANF"] + nxt["EANF"]) / 2,
            "Nehez_arany": (prev["Nehez_arany"] + nxt["Nehez_arany"]) / 2,
            "Savok": min(prev["Savok"], nxt["Savok"]),
            "Adatforras": "becsült (két szomszéd átlaga)",
            "Szomszedok": (gap["elozo"], gap["kovetkezo"]),
        })
    return pd.DataFrame(rows), geom


df, geo = load_data()
section_geom, road_info, gaps, lanes = load_geometry()
# Lanes per direction from OpenStreetMap (2 = "2×2"), and whether the carriageways are separate
df["Savok"] = df["Szakasz_id"].map(lambda i: lanes[i][0] if i in lanes else None)
df["Osztott"] = df["Szakasz_id"].map(lambda i: lanes[i][1] if i in lanes else None)

# === Sidebar filters
st.sidebar.header("🔎 Szűrők")
categories = st.sidebar.multiselect(
    "Útkategória", CATEGORY_ORDER, default=CATEGORY_ORDER
)
location = st.sidebar.radio("Fekvés", ["Mind", "Külterület", "Belterület"], horizontal=True)
EXPRESSWAYS = ["autópálya", "autóút"]
LANE_FILTERS = {
    "Mind": None,
    "Gyorsforgalmi + 2×2 vagy több": lambda d: d["Utkategoria"].isin(EXPRESSWAYS) | (d["Savok"] >= 2),
    "2×2 vagy több": lambda d: d["Savok"] >= 2,
    "2×3 vagy több": lambda d: d["Savok"] >= 3,
    "Csak 2×1": lambda d: d["Savok"] == 1,
}
lane_choice = st.sidebar.selectbox(
    "Sávszám", list(LANE_FILTERS),
    help="Forgalmi sávok irányonként az OpenStreetMap alapján (pl. 2×2 = irányonként 2 sáv). "
         "A „Gyorsforgalmi” opció az összes autópályát és autóutat is mutatja, sávszámtól "
         "függetlenül. "
         "Csomópontoknál a gyorsító-lassító sávok miatt egy szakasz többnek látszhat.",
)

filtered = df[df["Utkategoria"].isin(categories)]
if location != "Mind":
    filtered = filtered[filtered["Fekves"] == location]
if LANE_FILTERS[lane_choice]:
    filtered = filtered[LANE_FILTERS[lane_choice](filtered)]

# Traffic range on a logarithmic scale (1–1.5–2–3–5–7 steps per decade), 0 = no lower limit
EANF_STEPS = [0] + [m * 10 ** e for e in range(1, 6) for m in (1, 1.5, 2, 3, 5, 7)
                    if m * 10 ** e <= 200_000]
EANF_STEPS = [int(v) for v in EANF_STEPS]
eanf_lo, eanf_hi = st.sidebar.select_slider(
    "ÉÁNF (Ej/nap)", options=EANF_STEPS, value=(EANF_STEPS[0], EANF_STEPS[-1]),
    format_func=lambda v: f"{v:,}".replace(",", " "),
    help="Logaritmikus skála: a csúszka minden tizedes nagyságrendre ugyanannyi helyet ad.",
)
EANF_FILTER = (eanf_lo, eanf_hi) != (EANF_STEPS[0], EANF_STEPS[-1])
if EANF_FILTER:
    filtered = filtered[filtered["EANF"].between(eanf_lo, eanf_hi)]

if filtered.empty:
    st.warning("Nincs adat a kiválasztott szűrőkkel.")
    st.stop()

# === KPI row
with_length = filtered.dropna(subset=["Hossz_km"])
total_km = with_length["Hossz_km"].sum()
weighted_eanf = with_length["Ejkm_nap"].sum() / total_km if total_km else 0
measured_share = (filtered["Adatforras"] == "mért").mean()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Útszakaszok", f"{len(filtered):,}".replace(",", " "))
k2.metric("Úthossz", f"{total_km:,.0f} km".replace(",", " "))
k3.metric("Átlagos ÉÁNF (hosszal súlyozva)", f"{weighted_eanf:,.0f} Ej/nap".replace(",", " "))
k4.metric("Mért szakaszok aránya", f"{measured_share:.0%}")

tab_lines, tab_map, tab_roads, tab_profile, tab_mix, tab_data = st.tabs([
    "🛣️ Útszakasz-térkép",
    "🗺️ Megyei térkép",
    "🏆 Legforgalmasabb utak",
    "📈 Útprofil",
    "🚚 Járműösszetétel",
    "📋 Adatok",
])

# --- Tab 1: Road sections drawn on the map, coloured by traffic
with tab_lines:
    if not section_geom:
        st.info("Az útszakaszok geometriája hiányzik – futtasd a 7forgalom_geometry.py-t.")
    else:
        c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
        line_label = c1.selectbox("Színezés", list(LINE_METRICS))
        county_names = sorted(m for m in filtered["Megye"].unique() if m != "Ismeretlen")
        county = c2.selectbox("Megye", ["Teljes ország"] + county_names)
        road_names = sorted(filtered["Ut"].unique(),
                            key=lambda r: (not r.startswith("M"), len(r), r))
        picked = c3.multiselect("Csak ezek az utak", road_names, placeholder="Összes út")
        fill_gaps = c4.checkbox(
            "Hiányzó szakaszok kitöltése", value=True,
            help="Ahol a Magyar Közút táblázatából kimarad egy szelvényszakasz, ott a két "
                 "szomszédos szakasz átlagát mutatjuk (a tooltipben „becsült”).",
        )
        # Follow the viewer's light/dark theme until they flip the switch themselves
        system_dark = getattr(st.context.theme, "type", None) == "dark"
        if not st.session_state.get("dark_map_touched"):
            st.session_state["dark_map"] = system_dark
        dark = c4.toggle(
            "🌙 Sötét térkép", key="dark_map",
            on_change=lambda: st.session_state.update(dark_map_touched=True),
            help="Sötét OpenStreetMap-alaptérkép (CARTO Dark Matter). Alapból a böngésző / "
                 "rendszer világos vagy sötét módját követi.",
        )

        line_col, bins, fmt = LINE_METRICS[line_label]
        shown = filtered[filtered["Szakasz_id"].isin(section_geom)].assign(
            Nehez_szazalek=lambda d: 100 * d["Nehez_arany"])
        if county != "Teljes ország":
            shown = shown[shown["Megye"] == county]
        if picked:
            shown = shown[shown["Ut"].isin(picked)]
        geom = section_geom
        if fill_gaps and gaps:
            estimated, gap_geom = gap_sections(gaps)
            shown_ids = set(shown["Szakasz_id"])
            # Fill a gap when either neighbour passes the filters
            keep = estimated["Szomszedok"].map(lambda ids: bool(shown_ids & set(ids)))
            shown = pd.concat([shown, estimated[keep].assign(
                Nehez_szazalek=lambda d: 100 * d["Nehez_arany"])], ignore_index=True)
            geom = section_geom | gap_geom
        if EANF_FILTER:
            shown = shown[shown["EANF"].between(eanf_lo, eanf_hi)]
        shown = shown.dropna(subset=[line_col])

        fig_lines = go.Figure()
        lons_all, lats_all = [], []
        # One trace per colour class: lines separated by None gaps keep the figure light
        edges = [-math.inf] + bins[1:] + [math.inf]
        classes = pd.cut(shown[line_col], edges, labels=False, right=False)
        colors = sample_colorscale(LINE_SCALE_DARK if dark else LINE_SCALE,
                                   [i / (len(bins) - 1) for i in range(len(bins))])
        traces = []
        for i, color in enumerate(colors):
            part = shown[classes == i]
            lons, lats, hover = [], [], []
            for row in part.itertuples():
                coords = geom[row.Szakasz_id]
                info = road_info.get(row.Ut, {})
                text = (f"<b>{row.Ut}</b> ({row.Utkategoria}), {row.Megye}<br>"
                        f"{row.Kezdet_km:.3f}–{row.Veg_km:.3f} km<br>"
                        f"ÉÁNF: {row.EANF:,.0f} Ej/nap · nehéz: {row.Nehez_szazalek:.1f}%<br>"
                        f"Sávok: {f'2×{row.Savok:.0f}' if pd.notna(row.Savok) else '?'} · "
                        f"adat: {row.Adatforras} · hely: {info.get('kalibracio', '?')}")
                lons += [c[0] for c in coords] + [None]
                lats += [c[1] for c in coords] + [None]
                hover += [text] * len(coords) + [None]
            lons_all += lons
            lats_all += lats
            if i == 0:
                name = f"< {fmt.format(bins[1])}"
            elif i == len(colors) - 1:
                name = f"≥ {fmt.format(bins[-1])}"
            else:
                name = f"{fmt.format(bins[i])} – {fmt.format(bins[i + 1])}"
            traces.append(go.Scattermap(
                lon=lons, lat=lats, mode="lines", name=name.replace(",", " "),
                line=dict(color=color, width=1.3 + 4.2 * i / (len(colors) - 1)),
                hovertext=hover, hoverinfo="text",
            ))

        lon_vals = [x for x in lons_all if x is not None]
        lat_vals = [y for y in lats_all if y is not None]
        for trace in traces:
            fig_lines.add_trace(trace)
        if lon_vals:
            span = max(max(lon_vals) - min(lon_vals), 1.6 * (max(lat_vals) - min(lat_vals)), 0.05)
            center = {"lon": (min(lon_vals) + max(lon_vals)) / 2,
                      "lat": (min(lat_vals) + max(lat_vals)) / 2}
            zoom = max(5.5, min(12.0, math.log2(360 / span) + 0.6))
        else:
            center, zoom = {"lat": 47.16, "lon": 19.5}, 6
        fig_lines.update_layout(
            map=dict(style="carto-darkmatter" if dark else "carto-positron",
                     center=center, zoom=zoom),
            height=640, margin=dict(r=0, l=0, t=10, b=0),
            legend=dict(title=line_label, yanchor="top", y=0.98, xanchor="left", x=0.01,
                        bgcolor="rgba(20,20,24,0.85)" if dark else "rgba(255,255,255,0.85)",
                        font=dict(color="#e8e8e8" if dark else "#262730")),
        )
        st.plotly_chart(fig_lines, use_container_width=True)

        drawn = filtered["Szakasz_id"].isin(section_geom)
        km_drawn = filtered.loc[drawn, "Hossz_km"].sum() / filtered["Hossz_km"].sum()
        stones = shown["Ut"].map(lambda r: road_info.get(r, {}).get("kalibracio", ""))
        stone_share = shown.loc[stones.str.startswith("kilométerkő"), "Hossz_km"].sum() / \
            max(shown["Hossz_km"].sum(), 1e-9)
        st.caption(
            f"A szűrt úthossz {km_drawn:.0%}-a van a térképen; a megjelenített hossz "
            f"{stone_share:.0%}-ánál a szelvényezést OSM-kilométerkövekhez kalibráltuk, a többinél "
            "az út hossza mentén arányosan osztottuk fel (néhány száz méteres eltérés lehet). "
            f"{shown.loc[shown['Szakasz_id'] < 0, 'Hossz_km'].sum():,.0f} km a táblázatból hiányzó, "
            "a két szomszédos szakasz átlagával becsült rész. "
            "Útvonalak: © OpenStreetMap-közreműködők (ODbL), saját Overpass szerverről."
        )

# --- Tab 2: County choropleth
with tab_map:
    metrics = {
        "Átlagos ÉÁNF (Ej/nap, hosszal súlyozva)": "Atlag_EANF",
        "Forgalmi teljesítmény (millió Ej·km/nap)": "Teljesitmeny_M",
        "Nehézgépjármű-arány (%)": "Nehez_szazalek",
        "Úthossz (km)": "Hossz_km",
    }
    c1, c2 = st.columns([3, 2])
    metric_label = c1.selectbox("Megjelenített mutató", list(metrics))
    metric = metrics[metric_label]
    clip_budapest = c2.checkbox(
        "Színskála Budapest nélkül", value=True,
        help="Budapest kiugró értéke elnyomná a megyék közti különbségeket; "
             "a tényleges érték a tooltipben látszik.",
    )

    counties = with_length[with_length["Megye"] != "Ismeretlen"].assign(
        Nehez_km=lambda d: d["Nehez_nap"] * d["Hossz_km"],
        Jarmu_km=lambda d: d["Jarmu_nap"] * d["Hossz_km"],
    )
    agg = counties.groupby("Megye").agg(
        Hossz_km=("Hossz_km", "sum"),
        Ejkm_nap=("Ejkm_nap", "sum"),
        Nehez_km=("Nehez_km", "sum"),
        Jarmu_km=("Jarmu_km", "sum"),
        Szakaszok=("Ut", "size"),
    ).reset_index()
    agg["Atlag_EANF"] = agg["Ejkm_nap"] / agg["Hossz_km"]
    agg["Teljesitmeny_M"] = agg["Ejkm_nap"] / 1e6
    agg["Nehez_szazalek"] = 100 * agg["Nehez_km"] / agg["Jarmu_km"]

    scale_base = agg[agg["Megye"] != "Budapest"] if clip_budapest else agg
    range_color = (scale_base[metric].min(), scale_base[metric].max())

    fig_map = px.choropleth_map(
        agg,
        geojson=geo,
        locations="Megye",
        featureidkey="properties.megye",
        color=metric,
        color_continuous_scale=SEQ_BLUE,
        range_color=range_color,
        map_style="white-bg",
        center={"lat": 47.16, "lon": 19.5},
        zoom=6,
        opacity=0.9,
        hover_name="Megye",
        hover_data={
            "Megye": False,
            "Atlag_EANF": ":,.0f",
            "Teljesitmeny_M": ":.2f",
            "Nehez_szazalek": ":.1f",
            "Hossz_km": ":,.0f",
            "Szakaszok": True,
        },
        labels={
            "Atlag_EANF": "Átlagos ÉÁNF (Ej/nap)",
            "Teljesitmeny_M": "Teljesítmény (M Ej·km/nap)",
            "Nehez_szazalek": "Nehézgépjármű (%)",
            "Hossz_km": "Úthossz (km)",
            "Szakaszok": "Szakaszok",
        },
    )
    fig_map.update_traces(marker_line_color="white", marker_line_width=1)
    fig_map.update_layout(
        height=560,
        margin=dict(r=0, l=0, t=10, b=0),
        coloraxis_colorbar=dict(title=metric_label.split(" (")[0]),
    )
    st.plotly_chart(fig_map, use_container_width=True)
    st.caption(
        "Budapesten csak az országos közúthálózat (pl. M0, bevezető szakaszok) szerepel, "
        "a fővárosi utak nem, ezért a budapesti átlag felfelé torzít."
    )

# --- Tab 3: Busiest roads
with tab_roads:
    roads = with_length.groupby(["Ut", "Utkategoria"]).agg(
        Hossz_km=("Hossz_km", "sum"),
        Ejkm_nap=("Ejkm_nap", "sum"),
        Max_EANF=("EANF", "max"),
    ).reset_index()
    roads["Atlag_EANF"] = roads["Ejkm_nap"] / roads["Hossz_km"]
    top_n = st.slider("Megjelenített utak száma", 5, 30, 15)
    top = roads.nlargest(top_n, "Atlag_EANF").sort_values("Atlag_EANF")
    top["Cimke"] = top["Ut"] + " (" + top["Utkategoria"] + ")"

    fig_top = px.bar(
        top, x="Atlag_EANF", y="Cimke", orientation="h",
        hover_data={"Cimke": False, "Hossz_km": ":,.1f", "Max_EANF": ":,.0f",
                    "Atlag_EANF": ":,.0f"},
        labels={"Atlag_EANF": "Átlagos ÉÁNF (Ej/nap, hosszal súlyozva)", "Cimke": "",
                "Hossz_km": "Hossz (km)", "Max_EANF": "Max. ÉÁNF"},
    )
    fig_top.update_traces(marker_color=BAR_BLUE, marker_line_width=0)
    fig_top.update_layout(height=max(350, 28 * top_n), margin=dict(t=10), bargap=0.35)
    st.plotly_chart(fig_top, use_container_width=True)

# --- Tab 4: Traffic profile along a single road
with tab_profile:
    road_lengths = with_length.groupby("Ut")["Hossz_km"].sum()
    road_options = sorted(
        road_lengths.index,
        key=lambda r: (not r.startswith("M"), int("".join(c for c in r if c.isdigit()) or 0), r),
    )
    default_road = road_options.index("M1") if "M1" in road_options else 0
    road = st.selectbox("Út kiválasztása", road_options, index=default_road)

    sections = with_length[with_length["Ut"] == road].sort_values("Kezdet_km")
    # Step line: each section is a flat run from its start to its end chainage
    xs, ys, hover = [], [], []
    for _, row in sections.iterrows():
        text = (f"{row['Megye']}<br>{row['Kezdet_km']:.3f}–{row['Veg_km']:.3f} km"
                f"<br>ÉÁNF: {row['EANF']:,.0f} Ej/nap<br>{row['Adatforras']}")
        xs += [row["Kezdet_km"], row["Veg_km"]]
        ys += [row["EANF"], row["EANF"]]
        hover += [text, text]

    fig_profile = go.Figure(go.Scatter(
        x=xs, y=ys, mode="lines", line=dict(color=BAR_BLUE, width=2),
        fill="tozeroy", fillcolor="rgba(42, 120, 214, 0.15)",
        hovertext=hover, hoverinfo="text", name=road,
    ))
    fig_profile.update_layout(
        height=420, margin=dict(t=10),
        xaxis_title="Szelvény (km)", yaxis_title="ÉÁNF (Ej/nap)",
        hovermode="closest", showlegend=False,
    )
    st.plotly_chart(fig_profile, use_container_width=True)
    st.caption(
        f"{road}: {len(sections)} szakasz, {sections['Hossz_km'].sum():,.1f} km, "
        f"érintett megyék: {', '.join(sections['Megye'].unique())}."
    )

# --- Tab 5: Vehicle mix (vehicle-km weighted)
with tab_mix:
    mix = pd.DataFrame({
        "Járműkategória": list(VEHICLE_LABELS.values()),
        "Jarmukm": [(with_length[c] * with_length["Hossz_km"]).sum() for c in VEHICLE_LABELS],
    })
    mix["Arany"] = 100 * mix["Jarmukm"] / mix["Jarmukm"].sum()
    mix = mix.sort_values("Arany")

    fig_mix = px.bar(
        mix, x="Arany", y="Járműkategória", orientation="h", text="Arany",
        labels={"Arany": "Arány a járműkilométerekből (%)", "Járműkategória": ""},
        hover_data={"Jarmukm": ":,.0f", "Arany": ":.1f"},
    )
    fig_mix.update_traces(marker_color=BAR_BLUE, texttemplate="%{text:.1f}%",
                          textposition="outside", cliponaxis=False)
    fig_mix.update_layout(height=380, margin=dict(t=10, r=40), bargap=0.35)
    st.plotly_chart(fig_mix, use_container_width=True)
    st.caption("A kerékpáros forgalom nem szerepel a gépjármű-összetételben.")

# --- Tab 6: Raw data
with tab_data:
    columns = {
        "Utkategoria": "Útkategória", "Ut": "Út", "Megye": "Megye",
        "Kezdet_km": "Kezdet (km)", "Veg_km": "Vég (km)", "Hossz_km": "Hossz (km)",
        "Fekves": "Fekvés", "Adatforras": "Adatforrás", "EANF": "ÉÁNF (Ej/nap)",
        "MOF": "MOF (Ej/óra)", "Jarmu_nap": "Jármű/nap", "Nehez_arany": "Nehézgépjármű-arány",
        "Savok": "Sáv/irány",
    }
    table = filtered[list(columns)].assign(
        Nehez_arany=lambda d: (100 * d["Nehez_arany"]).round(1)
    ).rename(columns=columns | {"Nehez_arany": "Nehézgépjármű (%)"})
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Letöltés CSV-ben",
        table.to_csv(index=False).encode("utf-8"),
        file_name="eanf_2025_szurt.csv",
        mime="text/csv",
    )

st.caption(
    "Forrás: Magyar Közút Nonprofit Zrt., Előzetes ÉÁNF táblázat 2025 (2026.10.01.). "
    "Az értékek előzetesek; a szakaszok többsége korábbi mérésekből felszorzott becslés."
)
