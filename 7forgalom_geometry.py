"""Attach road geometry to the ÉÁNF sections (run after 6forgalom_prep.py).

Road lines come from the Overture Maps transportation theme (OpenStreetMap-derived),
read straight from its public S3 bucket. Only the row groups overlapping Hungary are
downloaded and cached in forgalom/cache/.

Each road number is assembled into one chain, oriented so that it runs from the
start of its chainage, and cut into sections by the "Kezdet_km"/"Veg_km" values.
The chainage is mapped onto the OSM line proportionally, so section boundaries are
approximate (typically within a few hundred metres).

Offline-only dependencies: pyarrow fsspec aiohttp shapely networkx
"""
import gzip
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from shapely import wkb
from shapely.geometry import LineString, Point, shape
from shapely.ops import substring, unary_union

OVERTURE_RELEASE = "2026-09-23.1"
BUCKET = "https://overturemaps-us-west-2.s3.amazonaws.com/"
HU_BBOX = (16.05, 22.95, 45.70, 48.62)  # xmin, xmax, ymin, ymax

SECTIONS_CSV = "dashboard/data/eanf_2025.csv"
COUNTIES = "dashboard/data/hu_megyek.geojson"
CACHE = Path("forgalom/cache/hu_route_segments.parquet")
OUT = "dashboard/data/eanf_2025_geom.json.gz"

# Local equirectangular projection (metres) – accurate enough inside Hungary
LAT0, LON0 = 47.2, 19.5
KX, KY = 111_320 * math.cos(math.radians(LAT0)), 110_574


def to_m(lon, lat):
    return (lon - LON0) * KX, (lat - LAT0) * KY


def to_deg(x, y):
    return x / KX + LON0, y / KY + LAT0


# === 1. Download Hungarian road segments that carry a route number (cached)
def fetch_segments():
    import fsspec

    fs = fsspec.filesystem("http", client_kwargs={"trust_env": True})
    prefix = f"release/{OVERTURE_RELEASE}/theme=transportation/type=segment/"
    listing = fs.cat(f"{BUCKET}?list-type=2&prefix={prefix}&max-keys=1000").decode()
    keys = re.findall(r"<Key>([^<]+\.parquet)</Key>", listing)

    def row_groups(key):
        md = pq.ParquetFile(fs.open(BUCKET + key, block_size=2**18)).metadata
        names = [md.schema.column(i).path for i in range(md.num_columns)]
        ix = {n: names.index(f"bbox.{n}") for n in ("xmin", "xmax", "ymin", "ymax")}
        hits = []
        for r in range(md.num_row_groups):
            st = {n: md.row_group(r).column(i).statistics for n, i in ix.items()}
            if (st["xmin"].min <= HU_BBOX[1] and st["xmax"].max >= HU_BBOX[0]
                    and st["ymin"].min <= HU_BBOX[3] and st["ymax"].max >= HU_BBOX[2]):
                hits.append((key, r))
        return hits

    def read(job):
        key, r = job
        t = pq.ParquetFile(fs.open(BUCKET + key, block_size=2**22)).read_row_group(
            r, columns=["id", "subtype", "class", "routes", "geometry", "bbox"])
        b = t["bbox"]
        inside = pc.and_(
            pc.and_(pc.less_equal(pc.struct_field(b, "xmin"), HU_BBOX[1]),
                    pc.greater_equal(pc.struct_field(b, "xmax"), HU_BBOX[0])),
            pc.and_(pc.less_equal(pc.struct_field(b, "ymin"), HU_BBOX[3]),
                    pc.greater_equal(pc.struct_field(b, "ymax"), HU_BBOX[2])),
        )
        keep = pc.and_(inside, pc.equal(t["subtype"], "road"))
        keep = pc.and_(keep, pc.greater(pc.fill_null(pc.list_value_length(t["routes"]), 0), 0))
        return t.filter(keep).drop_columns(["bbox"])

    with ThreadPoolExecutor(12) as ex:
        jobs = [job for hits in ex.map(row_groups, keys) for job in hits]
        print(f"⬇️  {len(jobs)} Overture row groups overlap Hungary")
        table = pa.concat_tables(list(ex.map(read, jobs)))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, CACHE)


if not CACHE.exists():
    fetch_segments()

segments = pq.read_table(CACHE, columns=["routes", "geometry"]).to_pandas()
sections = pd.read_csv(SECTIONS_CSV, dtype={"Ut": str})

with open(COUNTIES, encoding="utf-8") as f:
    counties = {feat["properties"]["megye"]: shape(feat["geometry"])
                for feat in json.load(f)["features"]}
hungary = unary_union(list(counties.values())).buffer(0.003)


def county_of(lon, lat):
    p = Point(lon, lat)
    return next((name for name, poly in counties.items() if poly.contains(p)), None)


# === 2. Group segment geometries by Hungarian route number (inside Hungary only)
by_ref = {}
for routes, geom in zip(segments["routes"], segments["geometry"]):
    refs = {r["ref"].strip() for r in routes
            if r["ref"] and (r["network"] or "").startswith("HU")}
    refs &= set(sections["Ut"])
    if not refs:
        continue
    line = wkb.loads(geom)
    if line.geom_type != "LineString" or not hungary.contains(line.interpolate(0.5, normalized=True)):
        continue
    coords = [to_m(x, y) for x, y in line.coords]
    for ref in refs:
        by_ref.setdefault(ref, []).append(coords)


def road_rank(ref):
    # Lower = more important (motorways first, then by number of digits / value)
    digits = re.sub(r"\D", "", ref) or "99999"
    return (0 if ref.startswith("M") else 1, len(digits), int(digits))


# Endpoints of every road, used to decide where a road "starts"
endpoint_refs = []
for ref, parts in by_ref.items():
    for coords in parts:
        endpoint_refs += [(coords[0], ref), (coords[-1], ref)]
ep_xy = np.array([p for p, _ in endpoint_refs])
ep_ref = np.array([r for _, r in endpoint_refs])


def junction_rank(xy, ref, radius=150):
    d = np.hypot(ep_xy[:, 0] - xy[0], ep_xy[:, 1] - xy[1])
    others = {r for r in ep_ref[d < radius] if r != ref}
    return min((road_rank(r) for r in others), default=(9, 9, 99999))


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

    # Bridge gaps between disconnected pieces (missing refs, roundabouts, towns)
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


def orient(chain, ref, road_sections):
    """Reverse the chain if its far end is where the chainage starts."""
    first = road_sections.loc[road_sections["Kezdet_km"].idxmin(), "Megye"]
    last = road_sections.loc[road_sections["Veg_km"].idxmax(), "Megye"]
    a, b = chain.coords[0], chain.coords[-1]
    ca, cb = county_of(*to_deg(*a)), county_of(*to_deg(*b))
    if first != last:
        if ca == last or cb == first:
            return LineString(chain.coords[::-1])
        if ca == first or cb == last:
            return chain
    # Same county at both ends: roads start at the junction with the more important road
    if junction_rank(b, ref) < junction_rank(a, ref):
        return LineString(chain.coords[::-1])
    return chain


geometries = {}
for ref, road_sections in sections.dropna(subset=["Kezdet_km", "Veg_km"]).groupby("Ut"):
    if ref not in by_ref:
        continue
    chain = build_chain(by_ref[ref])
    if chain is None or chain.length < 50:
        continue
    chain = orient(chain, ref, road_sections)

    k_min, k_max = road_sections["Kezdet_km"].min(), road_sections["Veg_km"].max()
    length = chain.length
    # Absolute chainage if the OSM line starts at km 0, else stretch over the covered range
    absolute = abs(length / (k_max * 1000) - 1)
    ranged = abs(length / ((k_max - k_min) * 1000) - 1)
    if absolute <= ranged:
        offset, scale = 0.0, length / (k_max * 1000)
    else:
        offset, scale = k_min, length / ((k_max - k_min) * 1000)

    for row in road_sections.itertuples():
        s0 = max(0.0, (row.Kezdet_km - offset) * 1000 * scale)
        s1 = min(length, (row.Veg_km - offset) * 1000 * scale)
        if s1 - s0 < 1:
            continue
        piece = substring(chain, s0, s1).simplify(15)
        coords = [to_deg(x, y) for x, y in piece.coords]
        geometries[int(row.Szakasz_id)] = [[round(x, 5), round(y, 5)] for x, y in coords]

with gzip.open(OUT, "wt", encoding="utf-8") as f:
    json.dump(geometries, f, separators=(",", ":"))

matched = sections["Szakasz_id"].isin(geometries)
km_share = sections.loc[matched, "Hossz_km"].sum() / sections["Hossz_km"].sum()
print(f"✅ {matched.sum()} / {len(sections)} sections with geometry "
      f"({km_share:.0%} of road length) saved to {OUT}")
print(sections[~matched].groupby("Utkategoria")["Hossz_km"].sum().round(0).to_string())
