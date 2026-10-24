"""A mock AQEF engine with known answers, for testing the harness itself (Harness
Contract, Stage C idea: check the instrument before trusting it). It is not an AQEF
implementation and validates nothing on its own.

Modes:
  accept-all   accepts every request and stores what it is given
  reject-all   rejects every request with 422, echoing the request
  refuse-auth  answers every request with 403
  golden       accepts exactly the configurations the CTS says load, and rejects every
               other one with an error naming what differs from the closest of them
"""
import copy
import json
import pathlib
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from aqef_harness import fixtures as F  # noqa: E402


def missing_keys(want, got, path=""):
    out = []
    if isinstance(want, dict) and isinstance(got, dict):
        for k, v in want.items():
            if k not in got:
                out.append(k)
            else:
                out += missing_keys(v, got[k], f"{path}.{k}")
    elif isinstance(want, list) and isinstance(got, list):
        for w, g in zip(want, got):
            out += missing_keys(w, g, path)
        if len(got) < len(want):
            out.append(path.split(".")[-1] or "list")
    return out


class Mock:
    def __init__(self, mode, cts_dir):
        self.mode = mode
        base = F.f_base(pathlib.Path(cts_dir))
        self.valid = [self._norm(v) for v in F.known_valid(base)]
        self.projects, self.datasets = {}, {}

    @staticmethod
    def _norm(doc):
        d = copy.deepcopy(doc)
        if isinstance(d, dict) and "name" in d:
            d["name"] = "cts-base"
        return d

    def handle(self, method, path, body):
        if self.mode == "refuse-auth":
            return 403, {"error": "forbidden"}
        if self.mode == "reject-all" and method in ("POST", "PUT"):
            return 422, {"error": "rejected", "request": body}
        parts = [p for p in path.split("/") if p]
        if method == "POST" and parts == ["projects"]:
            return self.load(body)
        if method == "GET" and len(parts) == 2 and parts[0] == "projects":
            p = self.projects.get(parts[1])
            return (200, p) if p else (404, {"error": "no such project"})
        if method == "GET" and len(parts) == 4 and parts[2] == "suites":
            p = self.projects.get(parts[1])
            s = next((s for s in (p or {}).get("suites", []) if s.get("name") == parts[3]), None)
            return (200, s) if s else (404, {"error": "no such suite"})
        if method == "DELETE" and len(parts) == 2:
            self.projects.pop(parts[1], None)
            return 204, None
        if method == "POST" and len(parts) == 3 and parts[2] == "datasets":
            return self.dataset(parts[1], body)
        if method == "GET" and len(parts) == 5 and parts[4] == "rows":
            rows = self.datasets.get((parts[1], parts[3]), {}).get("rows")
            return (200, {"items": rows}) if rows is not None else (404, {"error": "none"})
        if method == "POST" and len(parts) == 3 and parts[2] == "contracts":
            if self.mode == "golden" and not (isinstance(body, dict) and body.get("name")):
                return 422, {"error": "a Reusable Contract needs a name"}
            return 201, body
        return 404, {"error": f"mock has no {method} {path}"}

    def load(self, body):
        name = body.get("name") if isinstance(body, dict) else None
        if self.mode == "golden":
            n = self._norm(body)
            if n not in self.valid:
                closest = min(self.valid, key=lambda v: (len(missing_keys(v, n)) + len(missing_keys(n, v)),
                                                          len(missing_keys(n, v))))
                miss = missing_keys(closest, n)
                return 422, {"error": "configuration rejected", "missing": miss, "request": body}
        if name:
            self.projects[name] = body
            for d in body.get("datasets", []) or []:
                if isinstance(d, dict) and "name" in d:
                    self.datasets[(name, d["name"])] = d
        return 201, body

    def dataset(self, project, body):
        key = (project, body.get("name"))
        if self.mode == "golden":
            if "version" not in body:
                return 422, {"error": "a Dataset needs a version"}
            old = self.datasets.get(key)
            if old and old.get("version") == body.get("version") and old.get("rows") != body.get("rows"):
                return 409, {"error": "ds-1@1.0.0 already exists with other rows"}
        self.datasets.setdefault(key, body)
        return 201, body


def serve(mode, cts_dir, port=0):
    mock = Mock(mode, cts_dir)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _do(self, method):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            body = json.loads(raw) if raw else None
            status, out = mock.handle(method, self.path.split("?")[0], body)
            data = b"" if out is None else json.dumps(out).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self): self._do("GET")
        def do_POST(self): self._do("POST")
        def do_PUT(self): self._do("PUT")
        def do_DELETE(self): self._do("DELETE")

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["accept-all", "reject-all", "refuse-auth", "golden"])
    ap.add_argument("--cts", required=True)
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    s = serve(a.mode, a.cts, a.port)
    print(f"mock engine ({a.mode}) on http://127.0.0.1:{s.server_port}")
    threading.Event().wait()
