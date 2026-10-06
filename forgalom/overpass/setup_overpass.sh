#!/usr/bin/env bash
# Own Overpass API instance with the Hungarian road network, for 7forgalom_geometry.py.
#
#   forgalom/overpass/setup_overpass.sh            # build, download, load, start
#   forgalom/overpass/setup_overpass.sh start      # only (re)start an existing instance
#   forgalom/overpass/setup_overpass.sh stop
#
# Needs: g++, make, libexpat1-dev, zlib1g-dev, liblz4-dev, osmium-tool (apt).
# Only roads (highway=*), road route relations and kilometre stones are loaded,
# which keeps the database at ~5 GB and the import at a few minutes.
# The query endpoint is http://localhost:${OVERPASS_PORT}/api/interpreter.
set -euo pipefail

ROOT="${OVERPASS_ROOT:-$HOME/osm}"
VERSION="${OVERPASS_VERSION:-0.7.62.9}"
# Geofabrik is the usual source; geo2day.com serves the same daily extract
PBF_URL="${PBF_URL:-https://download.geofabrik.de/europe/hungary-latest.osm.pbf}"
PORT="${OVERPASS_PORT:-12346}"
HERE="$(cd "$(dirname "$0")" && pwd)"

BIN="$ROOT/overpass/bin"
DB="$ROOT/db"

stop() {
    [ -x "$BIN/dispatcher" ] && "$BIN/dispatcher" --osm-base --terminate >/dev/null 2>&1 || true
    [ -f "$ROOT/http.pid" ] && kill "$(cat "$ROOT/http.pid")" 2>/dev/null || true
    rm -f "$ROOT/http.pid"
}

start() {
    stop
    rm -f /dev/shm/osm3s* "$DB/osm3s_osm_base"
    nohup "$BIN/dispatcher" --osm-base --db-dir="$DB/" > "$ROOT/dispatcher.log" 2>&1 &
    sleep 1
    nohup python3 "$HERE/overpass_http.py" --bin "$BIN" --port "$PORT" > "$ROOT/http.log" 2>&1 &
    echo $! > "$ROOT/http.pid"
    sleep 1
    echo "✅ Overpass: http://localhost:$PORT/api/interpreter"
}

case "${1:-all}" in
    stop) stop; exit 0 ;;
    start) start; exit 0 ;;
esac

mkdir -p "$ROOT"
cd "$ROOT"

# === 1. Build osm-3s
if [ ! -x "$BIN/dispatcher" ]; then
    curl -sSL -o osm-3s.tar.gz "https://dev.overpass-api.de/releases/osm-3s_v$VERSION.tar.gz"
    tar xzf osm-3s.tar.gz
    (cd "osm-3s_v$VERSION" && ./configure --prefix="$ROOT/overpass" --enable-lz4 \
        && make -j"$(nproc)" install) > build.log 2>&1
fi

# === 2. Download and filter the extract
[ -f hungary.osm.pbf ] || curl -sSL --retry 4 -o hungary.osm.pbf "$PBF_URL"
osmium tags-filter -O hungary.osm.pbf w/highway r/route=road n/highway=milestone -o roads.osm.pbf

# === 3. Load the database
stop
rm -rf "$DB" && mkdir -p "$DB"
osmium cat roads.osm.pbf -f osm -o - | "$BIN/update_database" --db-dir="$DB/" --meta=no \
    --compression-method=lz4 --map-compression-method=lz4 --flush-size=4 > load.log 2>&1
tail -1 load.log

start
