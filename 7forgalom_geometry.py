"""Attach road geometry to the ÉÁNF sections (run after 6forgalom_prep.py).

Road lines come from OpenStreetMap through our own Overpass API instance
(forgalom/overpass/setup_overpass.sh), set with OVERPASS_URL. Responses are cached
in forgalom/cache/.

1. Every road number is assembled into one chain from its OSM route relation
   (route=road, network=HU:*); roads without a relation (mostly 5-digit access
   roads) fall back to the highway ways carrying the same "ref".
2. The chainage is calibrated on the kilometre stones (highway=milestone) lying on
   the chain: they decide the direction of the road and give piecewise-linear
   anchors between OSM length and road km. Roads with fewer than two usable stones
   are oriented heuristically and stretched proportionally over their km range.
3. The chain is cut into sections by "Kezdet_km"/"Veg_km".

Offline-only dependencies: shapely networkx requests
"""
import gzip
import json
import math
import os
import re
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import requests
from shapely import STRtree
from shapely.geometry import LineString, Point, shape
from shapely.ops import substring, unary_union

OVERPASS_URL = os.environ.get("OVERPASS_URL", "http://localhost:12346/api/interpreter")
SECTIONS_CSV = "dashboard/data/eanf_2025.csv"
COUNTIES = "dashboard/data/hu_megyek.geojson"
CACHE = Path("forgalom/cache")
OUT = "dashboard/data/eanf_2025_geom.json.gz"

MILESTONE_RADIUS = 30   # m, kilometre stone to road chain
MAX_STRETCH = 1.6       # allowed OSM metres per chainage metre between two stones (and inverse)

# Local equirectangular projection (metres) – accurate enough inside Hungary
LAT0, LON0 = 47.2, 19.5
KX, KY = 111_320 * math.cos(math.radians(LAT0)), 110_574


def to_m(lon, lat):
    return (lon - LON0) * KX, (lat - LAT0) * KY


def to_deg(x, y):
    return x / KX + LON0, y / KY + LAT0


# === 1. Query the Overpass server (cached)
def overpass(name, query):
    path = CACHE / f"{name}.json.gz"
    if not path.exists():
        print(f"⬇️  Overpass: {name}")
        r = requests.post(OVERPASS_URL, data={"data": query}, timeout=3600,
                          proxies={"http": None, "https": None} if "localhost" in OVERPASS_URL else None)
        r.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wb") as f:
            f.write(r.content)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)["elements"]


relations = overpass("hu_route_relations", """
[out:json][timeout:1800];
relation["type"="route"]["route"="road"]["network"~"^HU:"];
out geom;
""")
ref_ways = overpass("hu_ref_ways", """
[out:json][timeout:1800];
way["highway"]["ref"]["highway"!~"^(footway|cycleway|path|track|bus_stop|platform)$"];
out geom;
""")
milestones = overpass("hu_milestones", """
[out:json][timeout:600];
node["highway"="milestone"]["distance"];
out;
""")

sections = pd.read_csv(SECTIONS_CSV, dtype={"Ut": str})
wanted = set(sections["Ut"])

with open(COUNTIES, encoding="utf-8") as f:
    counties = {feat["properties"]["megye"]: shape(feat["geometry"])
                for feat in json.load(f)["features"]}
hungary = unary_union(list(counties.values())).buffer(0.003)


def county_of(lon, lat):
    p = Point(lon, lat)
    return next((name for name, poly in counties.items() if poly.contains(p)), None)


def split_refs(value):
    return {r.strip().replace(" ", "") for r in re.split(r"[;,]", value or "") if r.strip()}


def to_coords(geometry):
    return [to_m(p["lon"], p["lat"]) for p in geometry if p]


# === 2. Line pieces per road number: route relation members, else ways with that ref
by_ref, source = {}, {}
for rel in relations:
    for ref in split_refs(rel["tags"].get("ref")) & wanted:
        for m in rel.get("members", []):
            if m["type"] == "way" and len(m.get("geometry") or []) > 1:
                by_ref.setdefault(ref, []).append(to_coords(m["geometry"]))
                source[ref] = "reláció"

for way in ref_ways:
    refs = (split_refs(way["tags"].get("ref")) & wanted) - set(source)
    geom = way.get("geometry") or []
    if not refs or len(geom) < 2:
        continue
    mid = geom[len(geom) // 2]
    if not hungary.contains(Point(mid["lon"], mid["lat"])):
        continue
    for ref in refs:
        by_ref.setdefault(ref, []).append(to_coords(geom))
for ref in set(by_ref) - set(source):
    source[ref] = "ref"


def road_rank(ref):
    # Lower = more important (motorways first, then by number of digits / value)
    digits = re.sub(r"\D", "", ref) or "99999"
    return (0 if ref.startswith("M") else 1, len(digits), int(digits))


# Endpoints of every road, used to decide where a road "starts" when no stones help
endpoint_refs = [(coords[i], ref) for ref, parts in by_ref.items()
                 for coords in parts for i in (0, -1)]
ep_xy = np.array([p for p, _ in endpoint_refs])
ep_ref = np.array([r for _, r in endpoint_refs])


def junction_rank(xy, ref, radius=150):
    d = np.hypot(ep_xy[:, 0] - xy[0], ep_xy[:, 1] - xy[1])
    others = {r for r in ep_ref[d < radius] if r != ref}
    return min((road_rank(r) for r in others), default=(9, 9, 99999))


# Kilometre stones: position (m) and chainage (km), plus the road ref if tagged
def parse_distance(value):
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)", value or "")
    return float(m.group(1).replace(",", ".")) if m else None


stones = [(to_m(n["lon"], n["lat"]), parse_distance(n["tags"]["distance"]),
           split_refs(n["tags"].get("ref")))
          for n in milestones]
stones = [s for s in stones if s[1] is not None]
stone_tree = STRtree([Point(xy) for xy, _, _ in stones])


# === 3. Build one chain per road
def build_chain(parts):
    g = nx.Graph()
    for coords in parts:
        nodes = [(round(x), round(y)) for x, y in coords]
        for a, b in zip(nodes, nodes[1:]):
            if a != b:
                g.add_edge(a, b, w=math.dist(a, b))
    if g.number_of_nodes() < 2:
        return None

    # Bridge gaps between disconnected pieces (unmapped stretches, ref gaps in towns)
    comps = list(nx.connected_components(g))
    if len(comps) > 1:
        ends = [np.array([n for n in c if g.degree(n) <= 1] or list(c)) for c in comps]
        cg = nx.Graph()
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                d = np.hypot(ends[i][:, None, 0] - ends[j][None, :, 0],
                             ends[i][:, None, 1] - ends[j][None, :, 1])
                k = np.unravel_index(d.argmin(), d.shape)
                cg.add_edge(i, j, w=d[k], a=tuple(ends[i][k[0]]), b=tuple(ends[j][k[1]]))
        for i, j, e in nx.minimum_spanning_edges(cg, weight="w", data=True):
            g.add_edge(e["a"], e["b"], w=e["w"])

    # Double sweep: the longest shortest path approximates the road's full run
    start = next(iter(g.nodes))
    dist = nx.single_source_dijkstra_path_length(g, start, weight="w")
    a = max(dist, key=dist.get)
    dist, paths = nx.single_source_dijkstra(g, a, weight="w")
    b = max(dist, key=dist.get)
    return LineString(paths[b])


def stone_anchors(chain, ref, k_min, k_max):
    """(position along chain in m, chainage in km) of the stones lying on the road."""
    anchors = []
    for i in stone_tree.query(chain, predicate="dwithin", distance=MILESTONE_RADIUS):
        xy, km, refs = stones[i]
        if refs and ref not in refs:
            continue
        if k_min - 1 <= km <= k_max + 1:
            anchors.append((chain.project(Point(xy)), km))
    return sorted(set(anchors))


def monotone_anchors(anchors):
    """Longest chain of stones increasing in both position and km at a sane ratio."""
    best = []
    for i, (s, k) in enumerate(anchors):
        cands = [best[j] for j in range(i)
                 if anchors[j][1] < k
                 and 1 / MAX_STRETCH <= (s - anchors[j][0]) / ((k - anchors[j][1]) * 1000) <= MAX_STRETCH]
        best.append(max(cands, key=len, default=[]) + [(s, k)])
    return max(best, key=len, default=[])


def orient_heuristic(chain, ref, road_sections):
    """Reverse the chain if its far end is where the chainage starts."""
    first = road_sections.loc[road_sections["Kezdet_km"].idxmin(), "Megye"]
    last = road_sections.loc[road_sections["Veg_km"].idxmax(), "Megye"]
    a, b = chain.coords[0], chain.coords[-1]
    ca, cb = county_of(*to_deg(*a)), county_of(*to_deg(*b))
    if first != last:
        if ca == last or cb == first:
            return True
        if ca == first or cb == last:
            return False
    # Same county at both ends: roads start at the junction with the more important road
    return junction_rank(b, ref) < junction_rank(a, ref)


def km_to_m_function(chain, ref, road_sections):
    """Return (chain, f) where f maps road km to metres along the (oriented) chain."""
    k_min, k_max = road_sections["Kezdet_km"].min(), road_sections["Veg_km"].max()
    length = chain.length
    anchors = stone_anchors(chain, ref, k_min, k_max)
    fwd = monotone_anchors(anchors)
    rev = monotone_anchors(sorted((length - s, k) for s, k in anchors))

    if max(len(fwd), len(rev)) >= 2:
        if len(rev) > len(fwd):
            chain, fwd = LineString(chain.coords[::-1]), rev
        s, k = np.array(fwd).T
        slope_lo = (s[1] - s[0]) / (k[1] - k[0])
        slope_hi = (s[-1] - s[-2]) / (k[-1] - k[-2])

        def f(km):
            if km < k[0]:
                return s[0] - (k[0] - km) * slope_lo
            if km > k[-1]:
                return s[-1] + (km - k[-1]) * slope_hi
            return float(np.interp(km, k, s))
        return chain, f, f"kilométerkő ({len(fwd)})"

    if orient_heuristic(chain, ref, road_sections):
        chain = LineString(chain.coords[::-1])
    # Absolute chainage if the OSM line starts at km 0, else stretch over the covered range
    absolute = abs(length / (k_max * 1000) - 1)
    ranged = abs(length / ((k_max - k_min) * 1000) - 1)
    offset = 0.0 if absolute <= ranged else k_min
    scale = length / ((k_max - offset) * 1000)
    return chain, lambda km: (km - offset) * 1000 * scale, "arányos"


def to_lonlat(line, tolerance):
    return [[round(x, 5), round(y, 5)] for x, y in
            (to_deg(*xy) for xy in line.simplify(tolerance).coords)]


geometries, methods, gaps = {}, {}, []
for ref, road_sections in sections.dropna(subset=["Kezdet_km", "Veg_km"]).groupby("Ut"):
    if ref not in by_ref:
        continue
    chain = build_chain(by_ref[ref])
    if chain is None or chain.length < 50:
        continue
    chain, km_to_m, method = km_to_m_function(chain, ref, road_sections)
    methods[ref] = (source[ref], method)

    # Chainage stretches missing from the table, with the sections on either side
    ordered = road_sections.sort_values("Kezdet_km")
    for prev, nxt in zip(ordered.itertuples(), ordered.iloc[1:].itertuples()):
        s0 = max(0.0, km_to_m(prev.Veg_km))
        s1 = min(chain.length, km_to_m(nxt.Kezdet_km))
        if nxt.Kezdet_km - prev.Veg_km > 0.05 and s1 - s0 >= 1:
            gaps.append({"ut": ref, "k0": prev.Veg_km, "k1": nxt.Kezdet_km,
                         "elozo": int(prev.Szakasz_id), "kovetkezo": int(nxt.Szakasz_id),
                         "vonal": to_lonlat(substring(chain, s0, s1), 15)})

    for row in road_sections.itertuples():
        s0 = max(0.0, km_to_m(row.Kezdet_km))
        s1 = min(chain.length, km_to_m(row.Veg_km))
        if s1 - s0 < 1:
            continue
        geometries[int(row.Szakasz_id)] = to_lonlat(substring(chain, s0, s1), 15)

with gzip.open(OUT, "wt", encoding="utf-8") as f:
    json.dump({"sections": geometries,
               "roads": {ref: {"forras": src, "kalibracio": m} for ref, (src, m) in methods.items()},
               "gaps": gaps},
              f, ensure_ascii=False, separators=(",", ":"))

# === 4. Coverage report
sections["Geometria"] = sections["Szakasz_id"].isin(geometries)
sections["Modszer"] = sections["Ut"].map(lambda r: " / ".join(methods[r]) if r in methods else "nincs")
sections["Modszer"] = sections["Modszer"].str.replace(r" \(\d+\)", "", regex=True)
km_share = sections.loc[sections["Geometria"], "Hossz_km"].sum() / sections["Hossz_km"].sum()
print(f"✅ {sections['Geometria'].sum()} / {len(sections)} sections with geometry "
      f"({km_share:.0%} of road length) saved to {OUT}")
print(f"   {len(gaps)} chainage gaps ({sum(g['k1'] - g['k0'] for g in gaps):,.0f} km) "
      "between neighbouring sections")
print(sections.pivot_table(index="Utkategoria", columns="Modszer", values="Hossz_km",
                           aggfunc="sum").round(0).fillna(0).to_string())
