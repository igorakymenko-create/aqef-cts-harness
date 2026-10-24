"""REST adapter: maps the operations the tests need to Appendix C of the AQEF
specification. Every exchange is returned as a record that the caller stores as
evidence. A rejection by the engine is an outcome, not an error (Harness Contract §5)."""
import json
import socket
import urllib.error
import urllib.request

import yaml

ADAPTER_VERSION = "0.1.0"


class Exchange(dict):
    """One request and its response. Keys: request, response, outcome
    (accepted | rejected | sut_error | transport_failed)."""

    @property
    def outcome(self):
        return self["outcome"]

    @property
    def status(self):
        return self["response"].get("status")

    @property
    def body(self):
        return self["response"].get("body")

    def text(self):
        b = self.body
        return b if isinstance(b, str) else json.dumps(b, ensure_ascii=False)


class RestAdapter:
    def __init__(self, cfg):
        self.cfg = cfg

    # ------------------------------------------------------------------ transport
    def call(self, method, path, actor, body=None, content_type="application/json", headers=None):
        url = self.cfg.base_url + path
        extra = dict(headers or {})
        headers = {"Accept": "application/json", **extra}
        data = None
        if body is not None:
            if content_type == "application/yaml":
                data = yaml.safe_dump(body, sort_keys=False, allow_unicode=True).encode()
            else:
                data = json.dumps(body, ensure_ascii=False).encode()
            headers["Content-Type"] = content_type
        token = self.cfg.tokens.get(actor)
        req_record = {"method": method, "path": path, "actor": actor,
                      "content_type": content_type if body is not None else None,
                      "body": body, "headers": extra or None}
        req = urllib.request.Request(url, data=data, method=method, headers=dict(headers))
        if token:
            req.add_header("Authorization", f"Bearer {token}")   # never recorded
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_s) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            return Exchange(request=req_record, response={"error": str(e)},
                            outcome="transport_failed")
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = raw.decode("utf-8", "replace")
        if 200 <= status < 300:
            outcome = "accepted"
        elif 400 <= status < 500:
            outcome = "rejected"
        else:
            outcome = "sut_error"
        return Exchange(request=req_record, response={"status": status, "body": parsed},
                        outcome=outcome)

    # ------------------------------------------------------------------ operations
    def to_engine_form(self, doc):
        """CTS fixtures write fixed Evidence as a list of {role, content} messages "in the
        implementation's own Conversation form" (CTS 13.1). Convert it to that form."""
        import copy
        if self.cfg.conversation_form != "turns":
            return doc
        d = copy.deepcopy(doc)
        for suite in d.get("suites", []) or []:
            for sc in suite.get("scenarios", []) or []:
                conv = (sc.get("evidence") or {}).get("conversation")
                if isinstance(conv, list):
                    turns, prompt = [], None
                    for m in conv:
                        if m.get("role") == "user":
                            prompt = m.get("content")
                        elif m.get("role") == "assistant":
                            turns.append({"prompt": prompt, "response": m.get("content")})
                    sc["evidence"]["conversation"] = {"turns": turns}
        return d

    def load_config(self, project_doc, actor=None):
        """Load a configuration: POST /projects (Appendix C §C.3). `project_doc` is the
        content of the `project:` key of an Appendix A file."""
        project_doc = self.to_engine_form(project_doc)
        body = {"project": project_doc} if self.cfg.wrap_project else project_doc
        ctype = "application/yaml" if self.cfg.config_format == "yaml" else "application/json"
        return self.call("POST", "/projects", actor or self.cfg.loader, body, ctype)

    def get_project(self, name, actor="P-RELEASE"):
        return self.call("GET", f"/projects/{name}", actor)

    def delete_project(self, name, actor="P-ADMIN"):
        """Cleanup. Appendix C §C.8 lets a Project with audit records be deleted only when
        the caller requests their retention; how is implementation-defined (delete_query)."""
        q = f"?{self.cfg.delete_query}" if self.cfg.delete_query else ""
        return self.call("DELETE", f"/projects/{name}{q}", actor)

    def execute(self, project, suite="cts-suite", environment="cts-env", actor="P-RELEASE"):  # noqa
        """Trigger Executions: POST /projects/{project}/executions (Appendix C §C.3)."""
        return self.call("POST", f"/projects/{project}/executions", actor,
                         {"suite": suite, "environment": environment})

    def put_project(self, name, doc, actor="P-APPROVER"):
        return self.call("PUT", f"/projects/{name}", actor, self.to_engine_form(doc))

    def post(self, path, body, actor):
        return self.call("POST", path, actor, body)

    def get(self, path, actor="P-RELEASE"):
        return self.call("GET", path, actor)
