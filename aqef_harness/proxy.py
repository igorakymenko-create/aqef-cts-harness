"""A recording reverse proxy (CT-SDK-001: "The tester routes the CLI's traffic through a
recording proxy"). It forwards every request to the engine unchanged and records the
method, path, query, status and request body of each. Request and response headers are
not recorded, so a bearer token never reaches the log."""
import http.client
import http.server
import json
import threading
import urllib.parse

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
       "trailers", "transfer-encoding", "upgrade", "host", "content-length"}


class RecordingProxy:
    def __init__(self, upstream, port=0):
        self.upstream = urllib.parse.urlsplit(upstream)
        self.log = []
        self._lock = threading.Lock()
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _forward(self):
                n = int(self.headers.get("Content-Length") or 0)
                data = self.rfile.read(n) if n else None
                headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
                u = proxy.upstream
                conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=120)
                try:
                    conn.request(self.command, self.path, body=data, headers=headers)
                    r = conn.getresponse()
                    raw = r.read()
                    status, rheaders = r.status, r.getheaders()
                finally:
                    conn.close()
                split = urllib.parse.urlsplit(self.path)
                try:
                    body = json.loads(data) if data else None
                except ValueError:
                    body = "<non-JSON body>"
                with proxy._lock:
                    proxy.log.append({"method": self.command, "path": split.path,
                                      "query": split.query or None, "status": status,
                                      "request_body": body})
                self.send_response(status)
                for k, v in rheaders:
                    if k.lower() not in HOP:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _forward

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def entries(self):
        with self._lock:
            return list(self.log)
