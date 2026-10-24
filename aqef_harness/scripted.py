"""The scripted subject and Judge (CTS 2.2, 2.3, 13.1, 22): an HTTP service that the
engine's provider interface calls. The engine maps model identifiers to URLs at its
startup; this service answers on /subject and /judge and behaves as the code the
current case set. Every call is logged with the time it arrived and the time it was
answered, so tests can compare what the engine sent and recorded with what happened."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SUBJECT = {
    "SR-OK": lambda req, n: (200, {"response": "Hello! How can I help?"}),
    "SR-EMPTY": lambda req, n: (200, {"response": ""}),
    "SR-503-THEN-OK": lambda req, n: (503, {"error": "unavailable"}) if n == 1
    else (200, {"response": "Hello! How can I help?"}),
    # CT-REL-035: "SR-ECHO, except that its first call ... fails as in SR-503-THEN-OK"
    "SR-503-THEN-ECHO": lambda req, n: (503, {"error": "unavailable"}) if n == 1
    else (200, {"response": req.get("prompt", "")}),
    "SR-ECHO": lambda req, n: (200, {"response": req.get("prompt", "")}),
    "SR-SLOW-200": lambda req, n: (time.sleep(0.2), (200, {"response": "Hello! How can I help?"}))[1],
    "SR-BYE": lambda req, n: (200, {"response": "Goodbye."}),
    "SR-HI": lambda req, n: (200, {"response": "Hi there! What do you need?"}),
}


def _j(verdict, conf, assertions=1):
    return lambda resp, n: (200, {"verdict": verdict, "confidence": conf,
                                  "explanation": f"scripted {verdict}", "assertions": assertions})


DOWN = "DOWN"   # close the connection without answering (CTS 2.3, J-DOWN)
JUDGE = {
    "J-PASS-90": _j("pass", 0.9),
    "J-PASS-60": _j("pass", 0.6),
    "J-PASS-90-A3": _j("pass", 0.9, 3),   # CTS WD9 2.3
    "J-FAIL-90": _j("fail", 0.9),
    "J-DOWN": lambda resp, n: DOWN,
    "J-DOWN-THEN-PASS-90": lambda resp, n: DOWN if n == 1 else _j("pass", 0.9)(resp, n),
    "J-FAIL-THEN-PASS-90": lambda resp, n: _j("fail", 0.9)(resp, n) if n == 1 else _j("pass", 0.9)(resp, n),
    # first call J-PASS-60, every later call J-PASS-90 (CT-DEC-013's fixture)
    "J-PASS-60-THEN-90": lambda resp, n: _j("pass", 0.6)(resp, n) if n == 1 else _j("pass", 0.9)(resp, n),
    "J-CATCH": lambda resp, n: _j("fail", 0.9)(resp, n) if resp in ("Goodbye.", "Bye now.")
    else _j("pass", 0.9)(resp, n),
    "J-ALARM": lambda resp, n: _j("fail", 0.9)(resp, n) if resp == "Hi there! What do you need?"
    else _j("pass", 0.9)(resp, n),
}


def last_response(req):
    """The Response being assessed, from the Evidence the engine sent."""
    ev = req.get("evidence") or {}
    conv = ev.get("conversation") or {}
    t = conv.get("turns") if isinstance(conv, dict) else conv
    if t:
        last = t[-1]
        return last.get("response", last.get("content"))
    return req.get("response")


class Scripted:
    def __init__(self, port):
        self.port = port
        self.lock = threading.Lock()
        self.reset()
        self.srv = None

    def reset(self, subject="SR-OK", subject_by_prompt=None, judge="J-PASS-90",
              judge_by_model=None, judge_map=None):
        """`judge_map` is J-MAP(a, b, c) (CTS 13.1): a behavior per Response."""
        with self.lock:
            self.subject = subject
            self.subject_by_prompt = subject_by_prompt or {}
            self.judge = judge
            self.judge_by_model = judge_by_model or {}
            self.judge_map = judge_map or {}
            self.calls = []
            self.n = {}

    def handle(self, path, req):
        t0 = time.time()
        if path.rstrip("/").endswith("/subject"):
            code = self.subject_by_prompt.get(req.get("prompt"), self.subject)
            with self.lock:
                self.n[code] = self.n.get(code, 0) + 1
                n = self.n[code]
            status, body = SUBJECT[code](req, n)
            role = "subject"
        elif path.rstrip("/").endswith("/judge"):
            resp = last_response(req)
            code = self.judge_map.get(resp) or self.judge_by_model.get(req.get("model"), self.judge)
            key = (code, req.get("model"))
            with self.lock:
                self.n[key] = self.n.get(key, 0) + 1
                n = self.n[key]
            out = JUDGE[code](resp, n)
            status, body = (None, None) if out == DOWN else out
            role = "judge"
        else:
            status, body, code, role = 404, {"error": f"no scripted service at {path}"}, None, "?"
        t1 = time.time()
        with self.lock:
            self.calls.append({"role": role, "path": path, "behavior": code, "request": req,
                               "status": status, "response": body,
                               "received_at": t0, "answered_at": t1,
                               "harness_ms": round((t1 - t0) * 1000, 1)})
        return status, body

    def judge_calls(self):
        with self.lock:
            return [c for c in self.calls if c["role"] == "judge"]

    def subject_calls(self):
        with self.lock:
            return [c for c in self.calls if c["role"] == "subject"]

    def start(self):
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    req = json.loads(self.rfile.read(n) or b"{}")
                except json.JSONDecodeError:
                    req = {}
                status, body = outer.handle(self.path, req)
                if status is None:            # J-DOWN: drop the connection unanswered
                    self.close_connection = True
                    try:
                        self.connection.shutdown(2)
                    except OSError:
                        pass
                    return
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.srv = ThreadingHTTPServer(("127.0.0.1", self.port), H)
        self.port = self.srv.server_port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return self

    def stop(self):
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()

    def provider_map(self, models):
        base = f"http://127.0.0.1:{self.port}"
        return {m: f"{base}/judge" if "judge" in m else f"{base}/subject" for m in models}
