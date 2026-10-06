"""Minimal HTTP front end for a local Overpass database (instead of Apache + CGI).

Serves GET/POST /api/interpreter with the usual "data" parameter by piping the
query into osm3s_query, which talks to the running dispatcher.
"""
import argparse
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

parser = argparse.ArgumentParser()
parser.add_argument("--bin", required=True, help="Overpass bin directory")
parser.add_argument("--port", type=int, default=12346)
args = parser.parse_args()
QUERY = str(Path(args.bin) / "osm3s_query")


class Handler(BaseHTTPRequestHandler):
    def answer(self, params):
        query = params.get("data", [""])[0]
        if urlparse(self.path).path != "/api/interpreter" or not query:
            self.send_error(400, "POST data=<Overpass QL> to /api/interpreter")
            return
        run = subprocess.run([QUERY], input=query.encode(), capture_output=True)
        if run.returncode != 0 or not run.stdout:
            self.send_error(400, run.stderr.decode(errors="replace")[-2000:])
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(run.stdout)))
        self.end_headers()
        self.wfile.write(run.stdout)

    def do_GET(self):
        self.answer(parse_qs(urlparse(self.path).query))

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.answer(parse_qs(body.decode()))


ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
