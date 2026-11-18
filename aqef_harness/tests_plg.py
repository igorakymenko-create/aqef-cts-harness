"""CTS Section 25: Plugins (CT-PLG-001 to 008), and CT-ASM-014 with the test plugin
cts-crash (CTS 2.5).

The test plugins run as external HTTP services next to the engine (setup/cts_plugins.py;
Harness Contract 8.5), registered through POST /plugins (Appendix C) as setup. Each case
registers its own versions, so that registrations never collide within a run. Every
plugin reads `configuration.oracle` for its registration ID (the engine's docs/PLUGINS.md).
"""
import copy
import json
import uuid

from .tests_asm import of, one
from .tests_dec import designate_execution
from .tests_exe import setup
from .tests_inspect import pending

PLUGIN_PORT = 9200
LOGICAL = {"evidence", "expected", "configuration", "execution", "clause"}
TRANSPORT = {"host", "content-length", "content-type", "accept", "accept-encoding",
             "connection", "user-agent"}


def url(name):
    return f"http://127.0.0.1:{PLUGIN_PORT}/{name}"


def ok(ctx, why=""):
    return ctx.result("PASS", "EXPECTED_MET", why)


def bad(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


def register(ctx, kind, name, version=None, setup_step=True, **cfg):
    """Register a test plugin. Returns (exchange, registration ID)."""
    version = version or f"{ctx.case_id.lower()}-{uuid.uuid4().hex[:6]}"
    rid = f"{name}@{version}"
    body = {"type": kind, "name": name, "version": version, "endpoint": url(name),
            "configuration": {"oracle": rid, "nonce": uuid.uuid4().hex, **cfg}}
    ex = ctx.record(ctx.a.post("/plugins", body, "P-APPROVER"), f"register {kind} plugin {rid}")
    ctx.guard(ex, f"registering {rid}")
    if setup_step and ex.outcome != "accepted":
        ctx.setup_status = "failed"
        ctx.stop("NOT_RUN", "FIXTURE_UNAVAILABLE", f"{rid} could not be registered: {ex.text()[:200]}")
    return ex, rid


def with_validator(b, rid, expected):
    d = copy.deepcopy(b)
    d["suites"][0]["scenarios"][0]["contract"]["constraints"] = [
        {"validator": f"plugin:{rid}", "target": "response", "dimension": "functional",
         "expected": expected}]
    return d


def with_judge_plugin(b, rid):
    d = copy.deepcopy(b)
    e = d["suites"][0]["scenarios"][0]["contract"]["expectations"][0]
    e["judge"] = {**e["judge"], "plugin": rid}
    return d


def plugin_log(ctx, name, note):
    calls = [c for c in ctx.scripted.calls_of("plugin") if c.get("behavior") == name]
    ctx.refs.append(ctx.store.add(ctx.case_id, "harness_call", {"note": note, "calls": calls}))
    return calls


def run(ctx, doc, note, subject="SR-OK", judge="J-PASS-90", suffix=""):
    ex, name = ctx.load(doc, note, suffix=suffix)
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"{note} was rejected: {ex.text()[:200]}")
    ctx.setup_status = "ready"
    ctx.behave(subject, judge=judge)
    execs, _ = ctx.execute(name, f"{note}: execute cts-suite")
    return name, execs[0], ctx.results(name, execs[0]["id"], f"{note}: retrieve the Results")


def by_oracle(results, rid):
    return [r for r in results if r.get("oracle") == rid]


# ------------------------------------------------------------------ CT-PLG-001
def plg001(ctx, b):
    ctx.behave("SR-OK")
    flaky, rid_f = register(ctx, "validator", "cts-flaky", setup_step=False)
    calls = plugin_log(ctx, "cts-flaky", "what cts-flaky received during its registration")
    inputs = [json.dumps(c["request"].get("request"), sort_keys=True) for c in calls]
    lenx, rid_l = register(ctx, "validator", "cts-len", setup_step=False)
    if flaky.outcome == "accepted":
        return bad(ctx, f"cts-flaky was registered after {len(calls)} call(s)")
    if len(calls) < 2 or len(set(inputs)) != 1:
        return bad(ctx, f"cts-flaky was called {len(calls)} time(s), on {len(set(inputs))} distinct input(s)")
    if lenx.outcome != "accepted":
        return bad(ctx, f"cts-len was rejected: {lenx.text()[:200]}")
    return ok(ctx, f"cts-flaky was called {len(calls)} times on the same input and rejected "
                   f"({flaky.status}: {flaky.text()[:140]}); cts-len registered")


# ------------------------------------------------------------------ CT-PLG-002
def plg002(ctx, b):
    ex, rid = register(ctx, "validator", "cts-len")
    ctx.record(ctx.a.get(f"/plugins/{rid}", "P-APPROVER"), "the registration record")
    doc = ctx.a.cfg.conformance_statement.parent / "PLUGINS.md" if ctx.a.cfg.conformance_statement else None
    text = doc.read_text(encoding="utf-8") if doc and doc.is_file() else None
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "for the reviewer: the engine's plugin documentation", "file": "docs/PLUGINS.md", "text": text}))
    return pending(ctx, "Inspection: the registration response, record, and documentation were collected")


# ------------------------------------------------------------------ CT-PLG-003
def plg003(ctx, b):
    out = {}
    for label, marker, cfg in (("a", 1, {}), ("b", 2, {"malformed": True})):
        _, rid = register(ctx, "validator", "cts-probe", **cfg)
        name, e, rs = run(ctx, with_validator(b, rid, {"marker": marker}), f"({label}) F-BASE with cts-probe",
                          suffix=label)
        # ctx.behave (inside run) clears the session log, so this holds only this Execution's calls.
        calls = plugin_log(ctx, "cts-probe", f"({label}) what cts-probe received")
        judges = ctx.judge_log(f"({label}) calls the scripted Judge received")
        out[label] = (rid, e, rs, calls, judges)
    # (a)
    rid, e, rs, calls, judges = out["a"]
    real = [c for c in calls if (c["request"].get("request") or {}).get("execution") == e["id"]]
    if len(real) != 1:
        return bad(ctx, f"(a) cts-probe received {len(real)} assessment call(s) for the Execution")
    req = real[0]["request"]["request"]
    extra = set(req) - LOGICAL
    if extra:
        return bad(ctx, f"(a) cts-probe received further inputs: {sorted(extra)}")
    hdr = {k.lower() for k in real[0]["request"].get("headers") or {}}
    if "authorization" in hdr or any(ctx.a.cfg.tokens.get(p, "\0") in json.dumps(req) for p in ctx.a.cfg.tokens):
        return bad(ctx, "(a) a credential reached the plugin")
    checks = {"evidence is the Response": isinstance(req.get("evidence"), str) and bool(req.get("evidence")),
              "expected": req.get("expected") == {"marker": 1},
              "configuration": (req.get("configuration") or {}).get("oracle") == rid,
              "execution": req.get("execution") == e["id"],
              "clause": bool(req.get("clause"))}
    if not all(checks.values()):
        return bad(ctx, f"(a) inputs not as expected: {[k for k, v in checks.items() if not v]}")
    r = by_oracle(rs, rid)
    if len(r) != 1 or r[0].get("verdict") != "pass":
        return bad(ctx, f"(a) the cts-probe Result is {[x.get('verdict') for x in r]}")
    # (b)
    rid_b, e_b, rs_b, calls_b, judges_b = out["b"]
    r = by_oracle(rs_b, rid_b)
    if len(r) != 1:
        return bad(ctx, f"(b) {len(r)} cts-probe Results")
    if r[0].get("disposition") != "oracle_unavailable" or r[0].get("verdict") is not None:
        return bad(ctx, f"(b) the Result is {r[0].get('disposition')} / verdict {r[0].get('verdict')}")
    if judges_b:
        return bad(ctx, f"(b) the Judge received {len(judges_b)} call(s)")
    extra_h = sorted(hdr - TRANSPORT)
    return ok(ctx, "(a) cts-probe received exactly the five logical inputs and returned pass, naming "
                   f"{rid}; transport headers seen, not compared: {extra_h or 'none beyond the usual'}. "
                   "(b) oracle_unavailable with verdict null; the Judge was not called")


# ------------------------------------------------------------------ CT-PLG-004
def plg004(ctx, b):
    _, rid = register(ctx, "validator", "cts-len")
    name, e, rs = run(ctx, with_validator(b, rid, {}), "F-BASE with cts-len")
    designate_execution(ctx, name, e["id"])
    bl_before = ctx.record(ctx.a.get(f"/projects/{name}/baselines", "P-APPROVER"), "the Baselines, before")
    dep = ctx.record(ctx.a.post(f"/plugins/{rid}/deprecate", {}, "P-APPROVER"), f"deprecate {rid}")
    ctx.guard(dep, "deprecating cts-len")
    if dep.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"the deprecation was refused: {dep.text()[:200]}")
    rs2 = ctx.results(name, e["id"], "retrieve the Results after the deprecation")
    bl_after = ctx.record(ctx.a.get(f"/projects/{name}/baselines", "P-APPROVER"), "the Baselines, after")
    if rs2 != rs:
        return bad(ctx, "the Results changed after the deprecation")
    if bl_after.body != bl_before.body or not bl_after.body:
        return bad(ctx, "the Baselines changed, or none was found")
    r = by_oracle(rs2, rid)
    if len(r) != 1:
        return bad(ctx, f"{len(r)} Results name {rid}")
    return ok(ctx, f"Results and Baselines unchanged; the cts-len Result still names {rid}")


# ------------------------------------------------------------------ CT-PLG-005
def plg005(ctx, b):
    stmt = ctx.a.cfg.conformance_statement
    texts = {}
    for f in ("CONFORMANCE-STATEMENT.md", "PLUGINS.md"):
        p = stmt.parent / f if stmt else None
        texts[f] = p.read_text(encoding="utf-8") if p and p.is_file() else None
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "for the reviewer: the implementation's statement of how its Validator SDK enforces "
                "determinism and the absence of Confidence", "files": texts}))
    ctx.behave("SR-OK")
    ex, rid = register(ctx, "validator", "cts-reach", setup_step=False)
    reach = plugin_log(ctx, "cts-reach", "what cts-reach reached (its reports to the harness)")
    # cts-reach's network probe is logged as its own call; its report carries all three outcomes.
    reached = [c["request"].get("reached") for c in reach if c["request"].get("reached") is not None]
    auto = {"registered": ex.outcome == "accepted", "registration_reply": ex.text()[:300],
            "reached_during_registration": reached,
            "note": "ten equal verdicts would be a sampled consistency check, not a proof of determinism"}
    if ex.outcome == "accepted":
        name = setup(ctx, with_validator(b, rid, {}), "F-BASE with cts-reach")
        vs = []
        for i in range(10):
            ctx.behave("SR-OK")
            execs, _ = ctx.execute(name, f"execution {i + 1} of 10")
            r = by_oracle(ctx.results(name, execs[0]["id"], f"Results {i + 1}"), rid)
            vs.append((r[0].get("verdict"), r[0].get("confidence"), r[0].get("disposition")) if r else None)
        auto["results"] = vs
        if any(v and isinstance(v[1], (int, float)) for v in vs):
            ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"automated": auto}))
            return bad(ctx, "a cts-reach Result carries a numeric Confidence")
        if len({v[0] for v in vs if v}) > 1:
            ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"automated": auto}))
            return bad(ctx, "the ten cts-reach Results differ in verdict")
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"automated": auto}))
    deviation = [k for c in reached for k, v in (c or {}).items() if v]
    return pending(ctx, "Declaration: automated part met "
                        f"({'registration refused' if not auto['registered'] else 'ten Results without Confidence, equal verdicts'}); "
                        f"reported, not judged: cts-reach reached {sorted(set(deviation)) or 'nothing'} "
                        "(Volume V SHOULD); the statement awaits review")


# ------------------------------------------------------------------ CT-PLG-006
def plg006(ctx, b):
    _, rid = register(ctx, "dataset", "cts-dataset")
    d = copy.deepcopy(b)
    ds = {"name": "ds-plugin", "version": "1.0.0", "source": "plugin", "plugin": rid}
    d["datasets"] = [ds]
    s = d["suites"][0]["scenarios"][0]
    s.pop("variables", None)
    s["dataset"] = "ds-plugin@1.0.0"
    ex, name = ctx.load(d, "F-BASE with a Dataset produced by cts-dataset, bound as ds-plugin@1.0.0")
    if ex.outcome != "accepted":
        return bad(ctx, f"the configuration was rejected: {ex.text()[:240]}")
    g = ctx.record(ctx.a.get(f"/projects/{name}/datasets", "P-APPROVER"), "retrieve the Datasets")
    items = g.body.get("items", g.body) if isinstance(g.body, dict) else (g.body or [])
    hit = [x for x in items if isinstance(x, dict) and x.get("name") == "ds-plugin"]
    if not hit or not hit[0].get("version"):
        return bad(ctx, f"the Dataset has no version: {str(hit)[:200]}")
    rows = json.dumps(hit[0])
    note = "row Plugin-1 present" if "Plugin-1" in rows else "rows not in the listing"
    return ok(ctx, f"ds-plugin has version {hit[0]['version']} and a Scenario references it as "
                   f"ds-plugin@1.0.0; {note}")


# ------------------------------------------------------------------ CT-PLG-007
def plg007(ctx, b):
    from .tests_dec import gates, with_sem
    from .tests_exe import f_multi
    _, rid = register(ctx, "report", "cts-report")
    d = with_sem(f_multi(b))
    d["execution"] = {"scheduling": "sequential", "retry": {"max_attempts": 2, "on": "infrastructure_failure"}}
    name = setup(ctx, d, "F-SIGNALS: CT-REL-035's configuration")
    ctx.behave("SR-ECHO", subject_by_prompt={"One": "SR-503-THEN-ECHO"},
               judge_map={"One": "J-PASS-60", "Two": "J-PASS-60", "Three": "J-PASS-90"})
    execs, body = ctx.execute(name, "F-SIGNALS: execute")
    batch = body.get("execution_batch_id")
    gates(ctx, name, batch, "F-SIGNALS: evaluate the Gates")
    m = ctx.record(ctx.a.post(f"/projects/{name}/reports/metrics",
                              {"execution_batch_id": batch, "plugin": rid}, "P-APPROVER"),
                   "generate the Report Plugin's Metric for the batch")
    ctx.guard(m, "the Report Plugin Metric")
    mid = (m.body or {}).get("id") if isinstance(m.body, dict) else None
    if mid:
        g = ctx.record(ctx.a.get(f"/projects/{name}/reports/metrics/{mid}", "P-APPROVER"),
                       "the Metric, retrieved")
        ids = (g.body or {}).get("result_ids", []) if isinstance(g.body, dict) else []
        for e in execs:
            ctx.record(ctx.a.get(f"/projects/{name}/executions/{e['id']}/results", "P-APPROVER"),
                       f"trace: Results of {e.get('scenario')} (the Metric links {len(ids)} Result IDs)")
    return pending(ctx, "Inspection: the Metric and the Results it links were collected")


# ------------------------------------------------------------------ CT-PLG-008
def plg008(ctx, b):
    out = {}
    for label, cfg in (("a", {}), ("b", {"no_confidence": True})):
        _, rid = register(ctx, "judge", "cts-judge-probe", **cfg)
        name, e, rs = run(ctx, with_judge_plugin(b, rid), f"({label}) F-BASE with cts-judge-probe",
                          suffix=label)
        out[label] = (rid, by_oracle(rs, rid), rs)
    rid, r, rs = out["a"]
    if len(r) != 1:
        return bad(ctx, f"(a) {len(r)} Results name {rid}; oracles: {[x.get('oracle') for x in rs]}")
    want = {"verdict": "pass", "confidence": 0.9}
    diff = {k: r[0].get(k) for k, v in want.items() if r[0].get(k) != v}
    if diff:
        return bad(ctx, f"(a) the Result has {diff}")
    rid, r, rs = out["b"]
    if len(r) != 1:
        return bad(ctx, f"(b) {len(r)} Results name {rid}; oracles: {[x.get('oracle') for x in rs]}")
    if r[0].get("disposition") != "oracle_unavailable" or r[0].get("verdict") is not None:
        return bad(ctx, f"(b) the Result is {r[0].get('disposition')} / verdict {r[0].get('verdict')}")
    if isinstance(r[0].get("confidence"), (int, float)):
        return bad(ctx, f"(b) the Result carries a Confidence the plugin did not return: {r[0]['confidence']}")
    return ok(ctx, "(a) pass, Confidence 0.90, naming the plugin and version; (b) oracle_unavailable, "
                   "verdict null")


# ------------------------------------------------------------------ CT-ASM-014
def asm014(ctx, b):
    """CT-ASM-014. The engine's one way to define a Validator that raises is a Validator
    Plugin, cts-crash (CTS 2.5). A plugin that raises on every call fails Volume XVI's
    registration check, so it cannot be registered. Then the test's own fallback applies
    ("Where the implementation offers no way to define one"): the built-in Validator with
    an absent target, as in harness 0.11 and earlier (tests_wd10). The report names the
    route taken."""
    from . import tests_wd10
    ex, rid = register(ctx, "validator", "cts-crash", setup_step=False)
    if ex.outcome == "accepted":
        return ctx.result("NOT_RUN", "ADAPTER_GAP", f"{rid} registered; this harness drives only the fallback route")
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "route: cts-crash could not be registered (it fails the Volume XVI registration check), "
                "so the test's fallback route is used", "reply": ex.text()[:300]}))
    return tests_wd10.asm014(ctx, b)


def registry():
    return {"CT-PLG-001": plg001, "CT-PLG-002": plg002, "CT-PLG-003": plg003,
            "CT-PLG-004": plg004, "CT-PLG-005": plg005, "CT-PLG-006": plg006,
            "CT-PLG-007": plg007, "CT-PLG-008": plg008, "CT-ASM-014": asm014}, {}
