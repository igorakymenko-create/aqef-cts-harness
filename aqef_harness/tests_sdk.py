"""CTS Section 26: CT-SDK-001 (a CLI command is a REST API call) and CT-SDK-002 (an SDK
behaves as the REST API does).

Both tests are generic. They know the engine through Appendix C, and the CLI or SDK only
through a driver module named in harness.yaml (`cli.driver`, `sdk.<language>`). A driver
failure is a harness or adapter fault (NOT_RUN), never a FAIL of the implementation.
Tokens reach the CLI only through its environment and the SDK only as an argument; they
are never recorded."""
import copy
import importlib.util
import json
import os
import re
import subprocess
import tempfile

from .adapter_rest import Exchange, RestAdapter
from .core import CaseContext, Stop
from .proxy import RecordingProxy
from .tests_inspect import pending


def driver(path, what):
    spec = importlib.util.spec_from_file_location(f"aqef_cts_{what}_driver", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def redact(text, cfg):
    for t in cfg.tokens.values():
        if t:
            text = text.replace(t, "<redacted>")
    return text


# ===================================================================== CT-SDK-001
# The three commands of the Action, and the Appendix C §C.3 operation each must be.
EXPECTED = (
    ("load F-BASE", "POST", r"^/projects$"),
    ("execute cts-suite", "POST", r"^/projects/[^/]+/executions$"),
    ("evaluate the Gates", "POST", r"^/projects/[^/]+/gates/check$"),
)


def sdk001(ctx, b):
    cfg = ctx.a.cfg
    if not cfg.cli_driver or not cfg.cli_driver.is_file():
        ctx.stop("NOT_RUN", "ADAPTER_GAP", "no CLI driver configured (cli.driver in harness.yaml)")
    try:
        d = driver(cfg.cli_driver, "cli")
    except Exception as e:
        ctx.stop("NOT_RUN", "ADAPTER_GAP", f"the CLI driver did not load: {type(e).__name__}: {e}")
    proxy = RecordingProxy(cfg.base_url).start()
    try:
        return _sdk001(ctx, b, cfg, d, proxy)
    finally:
        proxy.stop()


def _cli(ctx, cfg, proxy, argv, actor, note):
    env = {**os.environ, "AQEF_URL": proxy.url, "AQEF_TOKEN": cfg.tokens.get(actor) or ""}
    before = len(proxy.entries())
    try:
        p = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=cfg.timeout_s * 4)
    except (OSError, subprocess.TimeoutExpired) as e:
        ctx.stop("NOT_RUN", "ADAPTER_GAP", f"{note}: the CLI could not be run: {type(e).__name__}: {e}")
    calls = proxy.entries()[before:]
    rec = {"note": note, "argv": argv, "actor": actor, "exit_code": p.returncode,
           "stdout": redact(p.stdout, cfg)[:20000], "stderr": redact(p.stderr, cfg)[:5000],
           "proxy_log": calls}
    ctx.refs.append(ctx.store.add(ctx.case_id, "harness_call", rec))
    try:
        out = json.loads(p.stdout) if p.stdout.strip() else None
    except ValueError:
        out = None
    return p, calls, out


def reachable(ctx):
    """Whether the engine answers the harness directly, without the CLI. A command that made
    no call while the engine was unreachable says nothing about the CLI."""
    return ctx.a.get("/projects", "P-RELEASE").outcome != "transport_failed"


def no_call(ctx, what):
    if not reachable(ctx):
        ctx.stop("NOT_RUN", "TRANSPORT_FAILED", f"{what}: the engine did not answer the harness either")
    return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{what} made no REST call")


def _sdk001(ctx, b, cfg, d, proxy):
    if not reachable(ctx):
        ctx.stop("NOT_RUN", "TRANSPORT_FAILED", "the engine did not answer the harness")
    doc = ctx.named(b)
    name = doc["name"]
    body = {"project": doc} if cfg.wrap_project else ctx.a.to_engine_form(doc)
    tmp = tempfile.mkdtemp(prefix="cts-sdk001-")
    cfile = os.path.join(tmp, "f-base.json")
    with open(cfile, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)

    seen = []
    p, calls, _ = _cli(ctx, cfg, proxy, d.load(cfile), cfg.loader, "CLI: load F-BASE")
    seen.append(calls)
    if p.returncode == 0:
        ctx.created.append(name)
    else:
        ctx.setup_status = "failed"
        if not calls:
            return no_call(ctx, "load F-BASE")
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"F-BASE was not loaded through the CLI (exit {p.returncode})")
    ctx.setup_status = "ready"

    ctx.behave("SR-OK", judge="J-PASS-90")
    p, calls, out = _cli(ctx, cfg, proxy, d.execute(name, "cts-suite", "cts-env"), "P-RELEASE",
                         "CLI: execute cts-suite against cts-env")
    seen.append(calls)
    batch = (out or {}).get("execution_batch_id") if isinstance(out, dict) else None
    if not batch:
        if not calls:
            return no_call(ctx, "execute")
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"the execution returned no batch (exit {p.returncode})")

    gfile = os.path.join(tmp, "gates.json")
    with open(gfile, "w", encoding="utf-8") as f:
        json.dump({"execution_batch_id": batch}, f)
    p, calls, _ = _cli(ctx, cfg, proxy, d.check_gates(name, gfile), "P-RELEASE", "CLI: evaluate the Gates")
    seen.append(calls)

    if not seen[2] and not reachable(ctx):
        ctx.stop("NOT_RUN", "TRANSPORT_FAILED", "evaluate the Gates: the engine did not answer the harness either")
    problems = []
    for (what, method, rx), calls in zip(EXPECTED, seen):
        if not any(c["method"] == method and re.match(rx, c["path"]) for c in calls):
            got = ", ".join(f"{c['method']} {c['path']}" for c in calls) or "no call"
            problems.append(f"{what}: expected {method} {rx.strip('^$')}, the proxy saw {got}")
    if problems:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "; ".join(problems))

    # Inspection part: the documented commands and the Appendix C operations.
    helps = []
    for argv in d.help_commands():
        try:
            h = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            helps.append({"argv": argv, "stdout": h.stdout, "exit_code": h.returncode})
        except (OSError, subprocess.TimeoutExpired) as e:
            helps.append({"argv": argv, "error": str(e)})
    docs = cfg.cli_docs.read_text(encoding="utf-8") if cfg.cli_docs and cfg.cli_docs.is_file() else None
    appc = (cfg.aqef_repo / "appendices" / "appendix-c-rest-api-specification.md")
    ops = [l for l in appc.read_text(encoding="utf-8").splitlines()
           if re.match(r"^\| (GET|POST|PUT|DELETE|PATCH) \|", l)] if appc.is_file() else None
    api = {str(p.name): p.read_text(encoding="utf-8") for p in cfg.api_docs if p.is_file()}
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "for the reviewer: the CLI's documented commands, the REST operations of Appendix C, "
                "and the implementation's own documentation of its REST API",
        "cli_help": helps, "cli_documentation": docs, "appendix_c_operations": ops,
        "implementation_api_documentation": api or None}))
    return pending(ctx, "the three commands made the matching Appendix C calls (Harness); "
                        "the mapping of every documented command is for Inspection")


# ===================================================================== CT-SDK-002
TESTS = ("CT-CFG-002", "CT-DEC-006", "CT-REL-002")


class SdkAdapter(RestAdapter):
    """The harness's REST adapter, with every request carried out through an SDK, whose
    traffic goes through a recording proxy (Harness Contract §16, `run_sdk`)."""

    def __init__(self, cfg, drv, url):
        super().__init__(cfg)
        self.drv = drv
        self.url = url

    def call(self, method, path, actor, body=None, content_type="application/json", headers=None):
        req = {"method": method, "path": path, "actor": actor, "via": f"sdk:{self.drv.LANGUAGE}",
               "body": body, "headers": dict(headers or {}) or None}
        try:
            status, raw, op = self.drv.call(self.url, self.cfg.tokens.get(actor), method, path,
                                            body=body, headers=headers, timeout=self.cfg.timeout_s)
        except self.drv.Unmapped as e:
            raise Stop(None) from e   # handled by the caller as an adapter gap
        except self.drv.TransportError as e:
            return Exchange(request=req, response={"error": str(e)}, outcome="transport_failed")
        req["sdk_operation"] = op
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, ValueError):
            parsed = raw.decode("utf-8", "replace")
        outcome = "accepted" if 200 <= status < 300 else "rejected" if 400 <= status < 500 else "sut_error"
        return Exchange(request=req, response={"status": status, "body": parsed}, outcome=outcome)


class Recording:
    """Wraps an adapter and keeps every exchange it makes, in order."""

    def __init__(self, inner):
        self.inner, self.log = inner, []
        self.cfg = inner.cfg

    def __getattr__(self, k):
        return getattr(self.inner, k)

    def call(self, *a, **kw):
        ex = self.inner.call(*a, **kw)
        self.log.append(ex)
        return ex

    # Route the convenience methods through call() so that every exchange is kept.
    def load_config(self, doc, actor=None):
        return RestAdapter.load_config(self, doc, actor)

    def get_project(self, name, actor="P-RELEASE"):
        return self.call("GET", f"/projects/{name}", actor)

    def delete_project(self, name, actor="P-ADMIN"):
        return RestAdapter.delete_project(self, name, actor)

    def execute(self, project, suite="cts-suite", environment="cts-env", actor="P-RELEASE"):
        return RestAdapter.execute(self, project, suite, environment, actor)

    def put_project(self, name, doc, actor="P-APPROVER"):
        return RestAdapter.put_project(self, name, doc, actor)

    def post(self, path, body, actor):
        return self.call("POST", path, actor, body)

    def get(self, path, actor="P-RELEASE"):
        return self.call("GET", path, actor)

    def to_engine_form(self, doc):
        return self.inner.to_engine_form(doc)


class SubContext(CaseContext):
    """A context for one surface's run of another test, in Projects of its own (CTS 1.6);
    its evidence is stored under CT-SDK-002."""

    def __init__(self, parent, adapter, tag):
        super().__init__(parent.case_id, parent.run, adapter, parent.store, parent.scripted)
        self.tag = tag

    def project_name(self, suffix=""):
        return super().project_name(self.tag + (f"-{suffix}" if suffix else ""))

    def record(self, ex, note=None):
        return super().record(ex, f"[{self.tag}] {note or ''}".strip())


TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


def ids_in(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and (k == "id" or k.endswith("_id") or k in ("execution", "resolves")):
                acc.add(v)
            ids_in(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            ids_in(v, acc)
    return acc


def is_duration(k, v):
    return k.endswith("_ms") and isinstance(v, (int, float)) and not isinstance(v, bool)


def normal(obj, ids, names, path="", timed=None):
    """A record with identifiers, references to its own Execution, and times replaced
    (CT-SDK-002, Expected). "Times" covers timestamps and measured durations: a latency
    the engine measured differs between any two runs, whichever surface started them.
    Every path replaced as a duration is listed in `timed`."""
    if isinstance(obj, dict):
        # An Artifact {name: "<x>_ms", data: <number>} is a measured duration.
        if isinstance(obj.get("name"), str) and is_duration(obj["name"], obj.get("data")):
            if timed is not None:
                timed.add(f"{path}.data ({obj['name']})")
            obj = {**obj, "data": "<duration>"}
        out = {}
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k.endswith("_at"):
                out[k] = "<time>"
            elif is_duration(k, v):
                if timed is not None:
                    timed.add(p)
                out[k] = "<duration>"
            else:
                out[k] = normal(v, ids, names, p, timed)
        return out
    if isinstance(obj, list):
        return [normal(v, ids, names, f"{path}[{i}]", timed) for i, v in enumerate(obj)]
    if isinstance(obj, str):
        if obj in ids:
            return "<id>"
        if TIME.match(obj):
            return "<time>"
        for n in names:
            obj = obj.replace(n, "<project>")
        for i in ids:
            if len(i) >= 8:
                obj = obj.replace(i, "<id>")
    return obj


def records(log, rest, ctx):
    """The Results and GateResults recorded in one surface's run: every GateResult its
    exchanges returned, and the Results of every Execution it created, read back through
    the REST API."""
    gate_results, executions = [], []
    for ex in log:
        bd = ex.body if isinstance(ex.body, dict) else {}
        if ex.outcome != "accepted":
            continue
        if isinstance(bd.get("gates"), dict):
            gate_results.append({"from": f"{ex['request']['method']} {ex['request']['path']}",
                                 "gates": bd["gates"]})
        if isinstance(bd.get("gate_evaluation"), dict) and isinstance(bd["gate_evaluation"].get("gates"), dict):
            gate_results.append({"from": "execution gate_evaluation", "gates": bd["gate_evaluation"]["gates"]})
        for e in bd.get("executions") or []:
            if isinstance(e, dict) and e.get("id"):
                project = ex["request"]["path"].split("/")[2]
                executions.append((project, e["id"], e.get("scenario")))
    results = []
    for project, eid, sc in executions:
        g = ctx.record(rest.get(f"/projects/{project}/executions/{eid}/results"),
                       f"read back the Results of {sc}")
        b = g.body
        items = b.get("items", b.get("results", [])) if isinstance(b, dict) else (b or [])
        results.append({"scenario": sc, "results": items})
    return {"gate_results": gate_results, "results": results}


def surface(ctx, adapter, tag, fn, base):
    sub = SubContext(ctx, Recording(adapter), tag)
    try:
        res = fn(sub, base)
    except Stop as s:
        if s.result is None:
            raise
        res = s.result
    return sub, res


def sdk002(ctx, b):
    cfg = ctx.a.cfg
    from .runner import implemented
    impl_tests, impl_cases = implemented()
    langs = sorted(c.split(":", 1)[1] for c in cfg.capabilities_claimed if c.startswith("sdk:"))
    missing = [l for l in langs if l not in cfg.sdk_drivers or not cfg.sdk_drivers[l].is_file()]
    if missing:
        ctx.stop("NOT_RUN", "ADAPTER_GAP", f"no SDK driver configured for {', '.join(missing)} (sdk.<language>)")
    problems, cleanup = [], []
    for lang in langs:
        try:
            drv = driver(cfg.sdk_drivers[lang], f"sdk_{lang}")
        except Exception as e:
            ctx.stop("NOT_RUN", "ADAPTER_GAP", f"the {lang} SDK driver did not load: {type(e).__name__}: {e}")
        for tid in TESTS:
            fn = impl_cases.get(tid) or impl_tests.get(tid)
            short = tid.lower().replace("ct-", "")
            rest_sub, rest_res = surface(ctx, RestAdapter(cfg), f"rest-{short}", fn, b)
            proxy = RecordingProxy(cfg.base_url).start()
            try:
                sdk_sub, sdk_res = surface(ctx, SdkAdapter(cfg, drv, proxy.url), f"{lang}-{short}", fn, b)
            except Stop as s:
                cleanup += [rest_sub]
                ctx.stop("NOT_RUN", "ADAPTER_GAP", f"{tid}: the {lang} SDK has no named operation "
                                                   f"for a request the test makes: {s.__cause__}")
            finally:
                proxy.stop()
            ctx.refs.append(ctx.store.add(ctx.case_id, "harness_call", {
                "note": f"{tid} through the {lang} SDK: versions, the SDK operations called, and the "
                        "recording proxy's log of its REST traffic (headers and tokens not recorded)",
                "sdk": {"language": lang, "sdk_version": getattr(drv, "VERSION", None),
                        "language_version": getattr(drv, "LANGUAGE_VERSION", None)},
                "operations": [ex["request"].get("sdk_operation") for ex in sdk_sub.a.log],
                "proxy_log": proxy.entries()}))
            cleanup += [rest_sub, sdk_sub]
            if (rest_res.outcome, rest_res.reason_code) != (sdk_res.outcome, sdk_res.reason_code):
                problems.append(f"{tid}: REST {rest_res.outcome}/{rest_res.reason_code}, "
                                f"{lang} SDK {sdk_res.outcome}/{sdk_res.reason_code} ({sdk_res.reason[:150]})")
                continue
            rl, sl = rest_sub.a.log, sdk_sub.a.log
            if len(rl) != len(sl):
                problems.append(f"{tid}: {len(rl)} requests through REST, {len(sl)} through the {lang} SDK")
                continue
            for i, (x, y) in enumerate(zip(rl, sl)):
                if x.outcome != y.outcome or x.status != y.status:
                    problems.append(f"{tid} request {i + 1} ({x['request']['method']} {x['request']['path']}): "
                                    f"REST {x.status}, {lang} SDK {y.status}")
            rest = RestAdapter(cfg)
            ra, sa = records(rl, rest, rest_sub), records(sl, rest, sdk_sub)
            ids = ids_in(ra, set()) | ids_in(sa, set()) | ids_in([e.body for e in rl + sl], set())
            names = sorted(set(rest_sub.created + sdk_sub.created), key=len, reverse=True)
            timed = set()
            na, ns = normal(ra, ids, names, "", timed), normal(sa, ids, names, "", timed)
            ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
                "note": f"{tid}: outcomes and recorded Results and GateResults, REST vs {lang} SDK, "
                        "with identifiers, Execution references and times replaced",
                "replaced_as_durations": sorted(timed),
                "rest": {"outcome": rest_res.outcome, "reason_code": rest_res.reason_code, "records": na},
                "sdk": {"outcome": sdk_res.outcome, "reason_code": sdk_res.reason_code, "records": ns}}))
            if na != ns:
                from .tests_rui import diff
                d = diff(na, ns)
                problems.append(f"{tid}: a recorded Result or GateResult differs between REST and the "
                                f"{lang} SDK: {'; '.join(d[:3]) or 'see evidence'}")
    for sub in cleanup:
        sub.cleanup()
    if not langs:
        ctx.stop("NOT_RUN", "ADAPTER_GAP", "no sdk:<language> is claimed")
    if problems:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "; ".join(problems)[:1500])
    return ctx.result("PASS", "EXPECTED_MET",
                      f"{len(TESTS)} tests through REST and through the SDK of {', '.join(langs)}: "
                      "same outcomes, same statuses, same recorded Results and GateResults")


def registry():
    return {"CT-SDK-001": sdk001, "CT-SDK-002": sdk002}, {}
