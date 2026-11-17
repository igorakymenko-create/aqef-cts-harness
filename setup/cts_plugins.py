"""The CTS test plugins (CTS 2.5 and Section 25), built for aqef-reference-engine's plugin
mechanism: each plugin is an external HTTP service (the engine's docs/PLUGINS.md).

Harness Contract 8.5: the test plugins run on the SUT's side, not in the harness. This
process is started next to the engine by start_reference_engine.sh. `cts-probe`,
`cts-reach`, and `cts-flaky` report to the harness through its session endpoint of kind `plugin`
(http://127.0.0.1:9100/plugin).

Every plugin reads `configuration.oracle` for its exact registration ID (`name@version`),
as the engine's protocol requires. `configuration.nonce` keeps `cts-flaky`'s call count
per registration, so a long-running process behaves the same in every run.

Run:  python3 cts_plugins.py [port]   (default 9200)
"""
import json
import random
import sys
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HARNESS = "http://127.0.0.1:9100/plugin"
PROBE = "repeatability-probe"     # the engine's registration probe identifiers (docs/PLUGINS.md)
LOCK = threading.Lock()
FLAKY = {}


def report(name, req, headers, extra=None):
    body = json.dumps({"plugin": name, "request": req, "headers": headers, **(extra or {})}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(HARNESS, body, {"Content-Type": "application/json"}),
                               timeout=5).read()
        return True
    except OSError:
        return False


def result(req, verdict, confidence="not_applicable", evidence=None, oracle_type="validator",
           drop=()):
    # Deterministic id and timestamp: the engine assigns its own on recording
    # (docs/PLUGINS.md), and a Result that differs only in these would fail the
    # registration probe for reasons that are not the plugin's verdict.
    key = f"{req.get('execution')}|{req.get('clause')}|{(req.get('configuration') or {}).get('oracle')}"
    r = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, key)), "execution": req.get("execution"), "clause": req.get("clause"),
         "oracle_type": oracle_type, "oracle": (req.get("configuration") or {}).get("oracle"),
         "verdict": verdict, "confidence": confidence, "disposition": "actionable",
         "supporting_evidence": evidence or {}, "recorded_at": "2026-01-01T00:00:00+00:00"}
    for k in drop:
        r.pop(k, None)
    return r


def cts_len(req, headers):
    ev = req.get("evidence")
    ok = isinstance(ev, str) and len(ev) >= 1
    return 200, result(req, "pass" if ok else "fail", evidence={"length": len(ev) if isinstance(ev, str) else None})


def cts_flaky(req, headers):
    report("cts-flaky", req, headers)     # so the harness log shows each call and its input
    key = (req.get("configuration") or {}).get("nonce")
    with LOCK:
        FLAKY[key] = FLAKY.get(key, 0) + 1
        n = FLAKY[key]
    return 200, result(req, "pass" if n == 1 else "fail", evidence={"call": n})


def cts_crash(req, headers):
    return 500, {"error": "cts-crash raises on every call"}


def cts_probe(req, headers):
    report("cts-probe", req, headers)
    cfg = req.get("configuration") or {}
    # `malformed: true` returns a Result with no `verdict` field. The engine validates the
    # replies to its registration probe, so the malformed reply is given only when a real
    # Execution is assessed (disclosed in the harness README).
    if cfg.get("malformed") and req.get("execution") != PROBE:
        return 200, result(req, None, evidence={"marker": (req.get("expected") or {}).get("marker")},
                           drop=("verdict",))
    return 200, result(req, "pass", evidence={"marker": (req.get("expected") or {}).get("marker")})


def cts_reach(req, headers):
    reached = {}
    try:
        clock_ms = int(time.time() * 1000)
        reached["clock"] = True
    except Exception:
        clock_ms, reached["clock"] = None, False
    try:
        rnd = random.randint(0, 10 ** 9)
        reached["random"] = True
    except Exception:
        rnd, reached["random"] = None, False
    # The network attempt is its own connection, made before the report, so that its
    # outcome is in the report and in the Result. (Harness 0.12.0 recorded the report's
    # own delivery as the only network attempt, and so left `network` out of the record.)
    try:
        urllib.request.urlopen(urllib.request.Request(HARNESS, b'{"plugin": "cts-reach", "network_probe": true}',
                                                      {"Content-Type": "application/json"}), timeout=5).read()
        reached["network"] = True
    except OSError:
        reached["network"] = False
    report("cts-reach", req, headers, {"reached": reached})
    basis = rnd if rnd is not None else clock_ms
    verdict = "pass" if basis is None or basis % 2 == 0 else "fail"
    return 200, result(req, verdict, confidence=0.5, evidence={"reached": reached})


def cts_judge_probe(req, headers):
    cfg = req.get("configuration") or {}
    r = result(req, "pass", confidence=0.90, oracle_type="judge",
               evidence={"criteria": req.get("criteria"), "reason": "cts-judge-probe always passes"},
               drop=("confidence",) if cfg.get("no_confidence") else ())
    return 200, r


def cts_dataset(req, headers):
    return 200, {"rows": [{"id": "row-1", "variables": {"query": "Plugin-1"}}]}


def cts_report(req, headers):
    results = req.get("results") or []
    low = [r for r in results if isinstance(r.get("confidence"), (int, float)) and r["confidence"] < 0.7]
    share = len(low) / len(results) if results else None
    # The engine's protocol takes exactly name, value, result_ids (docs/PLUGINS.md). The
    # Metric is computed from every Result in scope, so it links all of them.
    return 200, {"name": "cts-low-confidence-share", "value": share if share is not None else 0.0,
                 "result_ids": [r["id"] for r in results if r.get("id")]}


ROUTES = {"/cts-len": cts_len, "/cts-flaky": cts_flaky, "/cts-crash": cts_crash,
          "/cts-probe": cts_probe, "/cts-reach": cts_reach, "/cts-judge-probe": cts_judge_probe,
          "/cts-dataset": cts_dataset, "/cts-report": cts_report}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            req = {}
        fn = ROUTES.get(self.path.rstrip("/"))
        status, body = (404, {"error": f"no test plugin at {self.path}"}) if fn is None \
            else fn(req, dict(self.headers.items()))
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def urls(port=9200):
    return {k.lstrip("/"): f"http://127.0.0.1:{port}{k}" for k in ROUTES}


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9200
    if len(sys.argv) > 2 and sys.argv[2] == "--urls":
        print(json.dumps(urls(port)))
        sys.exit(0)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
