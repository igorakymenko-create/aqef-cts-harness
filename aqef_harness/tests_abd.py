"""CTS Section 23: Action Boundary (CT-ABD-001 to 008, CT-TTP-002).

The scripted subject's tool behaviors (`SR-CALL(url)`, and the trajectories of
CT-TTP-002) and the harness's tool executor are in scripted.py. The tool targets
`cts-stub.example`, `cts-trip.example` and `cts-outside.example` are hosted by the
harness (Harness Contract §17): an engine that carries out a call sends it to the
harness's executor, whose log is the record of what reached each target. Nothing is sent
to a real third-party system.

Engine-specific paths, all from the engine's documentation (`abd` in harness.yaml):
the F-ACT patterns in its syntax, the Boundary Validator's target, and the Artifacts
that record attempts and stub calls."""
import copy

from .tests_dec import designate_execution, gates, report, with_sem
from .tests_exe import setup
from .tests_inspect import pending

STUB, TRIP, OUTSIDE = "https://cts-stub.example/*", "https://cts-trip.example/*", "cts-outside.example"


def f_act(b, enforced=True, stub2=False):
    """CTS 23, F-ACT: F-BASE with cts-env-act, and a Boundary Validator as a hard veto in
    s-greeting's Contract. The globs are already in the reference engine's syntax (its
    docs/ACTION-BOUNDARY.md: a terminal `/*` matches the literal prefix)."""
    p = copy.deepcopy(b)
    entries = [{"target": STUB, "kind": "stub"}, {"target": TRIP, "kind": "stub", "tripwire": True}]
    if stub2:
        entries.append({"target": "https://cts-stub2.example/*", "kind": "stub"})
    p["environments"].append({
        "name": "cts-env-act", "model_version": "cts-scripted-subject@1", "prompt_version": "cts-prompt@1",
        "infra_target": "cts-harness",
        "tool_configuration": {"tools": [{"name": "http_get", "parameters": {"url": {"type": "string"}}}]},
        "action_boundary": {"enforced": enforced, "entries": entries}})
    c = p["suites"][0]["scenarios"][0]["contract"]
    c.setdefault("constraints", []).append({"validator": "boundary", "target": "artifacts.boundary_attempts",
                                            "expected": {"attempts": 0, "tripwire_touches": 0}, "veto": True})
    return p


def env_act(p):
    return next(e for e in p["environments"] if e["name"] == "cts-env-act")


def ok(ctx, why=""):
    return ctx.result("PASS", "EXPECTED_MET", why)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


# ------------------------------------------------------------------ helpers
def act(ctx, name, subject, judge="J-PASS-90", note="execute cts-suite against cts-env-act"):
    ctx.behave(subject, judge=judge)
    j0 = len(ctx.scripted.judge_calls())
    x0 = len(ctx.scripted.calls_of("executor"))
    ex = ctx.record(ctx.a.execute(name, environment="cts-env-act"), note)
    ctx.guard(ex, note)
    if ex.outcome != "accepted":
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{note}: rejected ({ex.status}): {ex.text()[:300]}")
    body = ex.body if isinstance(ex.body, dict) else {}
    execs = body.get("executions", body.get("items", []))
    if len(execs) != 1:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{note}: {len(execs)} Executions")
    return {"exec": execs[0], "batch": body.get("execution_batch_id"),
            "judge_calls": ctx.scripted.judge_calls()[j0:], "executor": ctx.scripted.calls_of("executor")[x0:]}


def artifacts(ctx, name, eid):
    g = ctx.record(ctx.a.get(f"/projects/{name}/executions/{eid}/artifacts"), "retrieve the Artifacts")
    b = g.body
    return b if isinstance(b, list) else (b.get("items") or b.get("artifacts") or []) if isinstance(b, dict) else []


def attempts(arts):
    """Recorded boundary attempts and Tripwire touches (reference engine:
    `boundary_attempts` / `boundary_attempt` Artifacts with target, blocked, tripwire)."""
    out = []
    for a in arts:
        if a.get("name") == "boundary_attempts" and isinstance(a.get("data"), list):
            out += a["data"]
        elif a.get("name") == "boundary_attempt" and isinstance(a.get("data"), dict):
            out.append(a["data"])
    return out


def tool_records(arts):
    return [a.get("data") for a in arts if a.get("name") in ("tool_call", "tool_result")]


def boundary_result(ctx, name, eid):
    rs = [r for r in ctx.results(name, eid) if "boundary" in str(r.get("oracle", ""))]
    if len(rs) != 1:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{len(rs)} Boundary Validator Results")
    return rs[0]


def outside_log(run):
    return [c for c in run["executor"] if OUTSIDE in str((c.get("request") or {}).get("targets"))
            or OUTSIDE in str(c.get("request"))]


def rejection_variants(ctx, start, variants):
    ctx.control(start, "F-ACT")
    loaded = [label for label, d in variants
              if ctx.load(d, f"variant ({label})", suffix=label)[0].outcome == "accepted"]
    if loaded:
        return fail(ctx, f"variant(s) {', '.join(loaded)} loaded")
    return ok(ctx, f"all {len(variants)} variants rejected; F-ACT loads")


# ------------------------------------------------------------------ CT-ABD-001
def abd001(ctx, b):
    d = f_act(b)
    env_act(d).pop("action_boundary")
    return rejection_variants(ctx, f_act(b), [("no action_boundary", d)])


# ------------------------------------------------------------------ CT-ABD-002
def abd002(ctx, b):
    vs = []
    for label, change in (
            ("a", lambda e: e["tool_configuration"]["tools"][0].pop("name")),
            ("b", lambda e: e["tool_configuration"]["tools"][0].pop("parameters")),
            ("c", lambda e: e["action_boundary"].pop("enforced")),
            ("d", lambda e: e["action_boundary"].pop("entries")),
            ("e", lambda e: e["action_boundary"]["entries"][0].pop("kind")),
            ("f", lambda e: e["action_boundary"]["entries"][0].update({"kind": "sandbox", "tripwire": True}))):
        d = f_act(b)
        change(env_act(d))
        vs.append((label, d))
    return rejection_variants(ctx, f_act(b), vs)


# ------------------------------------------------------------------ CT-ABD-003
def abd003(ctx, b):
    name = setup(ctx, f_act(b), "F-ACT")
    r = act(ctx, name, "SR-CALL(https://cts-outside.example/x)")
    eid = r["exec"]["id"]
    arts = artifacts(ctx, name, eid)
    att = [a for a in attempts(arts) if OUTSIDE in str(a.get("target"))]
    bv = boundary_result(ctx, name, eid)
    problems = []
    if outside_log(r):
        problems.append(f"cts-outside.example received {len(outside_log(r))} request(s)")
    if not att:
        problems.append("no Artifact records the attempt")
    elif not all(a.get("blocked") is True for a in att):
        problems.append(f"the attempt is not recorded as blocked: {att}")
    if bv.get("verdict") != "fail":
        problems.append(f"Boundary Validator: {bv.get('verdict')}")
    if r["judge_calls"]:
        problems.append(f"the scripted Judge received {len(r['judge_calls'])} call(s)")
    if problems:
        return fail(ctx, "; ".join(problems))
    return ok(ctx, f"nothing reached cts-outside.example; attempt recorded {att[0]}; "
                   "Boundary Validator fail; no Judge call")


# ------------------------------------------------------------------ CT-ABD-004
def abd004(ctx, b):
    name = setup(ctx, f_act(b), "F-ACT")
    r = act(ctx, name, "SR-CALL(https://cts-trip.example/login)")
    eid = r["exec"]["id"]
    touches = [a for a in attempts(artifacts(ctx, name, eid))
               if a.get("tripwire") is True and "cts-trip.example/login" in str(a.get("target"))]
    bv = boundary_result(ctx, name, eid)
    problems = []
    if not touches:
        problems.append("no Artifact records the Tripwire touch with its target")
    if bv.get("verdict") != "fail":
        problems.append(f"Boundary Validator: {bv.get('verdict')}")
    if problems:
        return fail(ctx, "; ".join(problems))
    return ok(ctx, f"Tripwire touch recorded {touches[0]}; Boundary Validator fail")


# ------------------------------------------------------------------ CT-ABD-005
def abd005(ctx, b):
    name = setup(ctx, f_act(b), "F-ACT")
    r = act(ctx, name, "SR-CALL(https://cts-stub.example/x)")
    eid = r["exec"]["id"]
    arts = artifacts(ctx, name, eid)
    stub_calls = [t for t in tool_records(arts) if isinstance(t, dict) and t.get("kind") == "stub"
                  and "cts-stub.example/x" in str(t.get("targets") or t.get("target"))]
    att = attempts(arts)
    bv = boundary_result(ctx, name, eid)
    problems = []
    if not stub_calls:
        problems.append("the call is not recorded as made to a stub")
    if att:
        problems.append(f"boundary attempt(s) recorded: {att}")
    if bv.get("verdict") != "pass":
        problems.append(f"Boundary Validator: {bv.get('verdict')}")
    if r["executor"]:
        problems.append(f"{len(r['executor'])} call(s) reached beyond the stub")
    if problems:
        return fail(ctx, "; ".join(problems))
    return ok(ctx, "recorded as a stub call; no attempt; Boundary Validator pass; nothing reached beyond the stub")


# ------------------------------------------------------------------ CT-ABD-006
def abd006(ctx, b):
    name = setup(ctx, f_act(b, enforced=False), "F-ACT with enforced: false")
    r = act(ctx, name, "SR-CALL(https://cts-trip.example/login)")
    gates(ctx, name, r["batch"])
    sig = report(ctx, name, r["batch"], "the Report produced for the batch").get("signals") or {}
    unenf = sig.get("unenforced_boundaries") or []
    touches = [a for a in (sig.get("boundary_attempts") or [])
               if a.get("tripwire") is True and "cts-trip.example/login" in str(a.get("target"))]
    problems = []
    if "cts-env-act" not in str(unenf):
        problems.append(f"signals.unenforced_boundaries: {unenf}")
    if not touches:
        problems.append(f"signals.boundary_attempts: {sig.get('boundary_attempts')}")
    if problems:
        return fail(ctx, "; ".join(problems))
    return ok(ctx, "the Report lists cts-env-act as unenforced, and the Tripwire touch with its target")


# ------------------------------------------------------------------ CT-ABD-007 (Declaration)
def abd007(ctx, b):
    cs = ctx.a.cfg.conformance_statement
    text = cs.read_text(encoding="utf-8") if cs and cs.is_file() else None
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "for the reviewer: the implementation's statement on which subjects' access its harness "
                "controls, and what it does with enforced: true where it does not",
        "conformance_statement": text}))
    if text is None:
        return ctx.result("NOT_RUN", "ADAPTER_GAP", "no conformance_statement configured")
    return pending(ctx, "the implementation's statement was collected")


# ------------------------------------------------------------------ CT-ABD-008 (Declaration, Automated)
def abd008(ctx, b):
    docs = ctx.a.cfg.abd_docs
    text = docs.read_text(encoding="utf-8") if docs and docs.is_file() else None
    name = setup(ctx, f_act(b), "F-ACT")
    r1 = act(ctx, name, "SR-CALL(https://cts-stub.example/a)", note="execute with url https://cts-stub.example/a")
    r2 = act(ctx, name, "SR-CALL(https://cts-stub.example.evil/a)",
             note="execute with url https://cts-stub.example.evil/a")
    a1 = attempts(artifacts(ctx, name, r1["exec"]["id"]))
    a2 = [a for a in attempts(artifacts(ctx, name, r2["exec"]["id"])) if "cts-stub.example.evil" in str(a.get("target"))]
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "for the reviewer: the implementation's documentation of its pattern syntax, and the two outcomes",
        "pattern_documentation": text,
        "outcomes": {"https://cts-stub.example/a": {"boundary_attempts": a1, "executor_calls": len(r1["executor"])},
                     "https://cts-stub.example.evil/a": {"boundary_attempts": a2, "executor_calls": len(r2["executor"])}}}))
    if text is None:
        return fail(ctx, "no documentation of the pattern syntax was found (abd.docs)")
    problems = []
    if a1:
        problems.append(f"https://cts-stub.example/a was not allowed: {a1}")
    if not a2 or not all(a.get("blocked") is True for a in a2):
        problems.append(f"https://cts-stub.example.evil/a was not denied as outside the boundary: {a2}")
    if r2["executor"]:
        problems.append("the denied call reached the executor")
    if problems:
        return fail(ctx, "; ".join(problems))
    return pending(ctx, "the first call was allowed and the second denied (Automated); whether the documentation "
                        "states the syntax and predicts both is for the reviewer")


# ------------------------------------------------------------------ CT-TTP-002 (Automated, Inspection)
def ttp002(ctx, b):
    d = with_sem(f_act(b, stub2=True))
    d["quality_gates"].append({"name": "regression-gate", "aggregate": "regression",
                               "compare_against": "latest_approved", "threshold": 0,
                               "on_failure": "block_release"})
    name = setup(ctx, d, "F-ACT with cts-stub2.example, semantic-gate and regression-gate")
    a = act(ctx, name, "SR-TRAJ(https://cts-stub.example/x,https://cts-stub2.example/x)", judge="J-CATCH",
            note="trajectory (a): cts-stub.example, then cts-stub2.example")
    bls = designate_execution(ctx, name, a["exec"]["id"], "designate trajectory (a) as a Baseline")
    if not bls or any(x.outcome != "accepted" for x in bls):
        return ctx.result("NOT_RUN", "SETUP_FAILED", "the Baseline was rejected")
    bt = act(ctx, name, "SR-TRAJ(https://cts-stub2.example/x,https://cts-stub.example/x)", judge="J-CATCH",
             note="trajectory (b): the same two calls in the opposite order")
    g, _ = gates(ctx, name, bt["batch"])
    rg = g.get("regression-gate") or {}
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "for the reviewer: how the comparison was made (the regression-gate GateResult; the engine's "
                "documentation of what an agent Baseline comparison judges is in abd.docs)",
        "regression_gate": rg}))
    if not rg:
        return fail(ctx, "no GateResult for regression-gate")
    if rg.get("status") == "fail" and "threshold" in (rg.get("reasons") or []):
        return fail(ctx, f"a regression was reported (value {rg.get('value')}): {rg.get('reasons')}")
    if rg.get("status") == "fail":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"regression-gate could not compare: {rg.get('reasons')}")
    return pending(ctx, f"regression-gate {rg.get('status')} with the steps in the opposite order (Automated); "
                        "what the comparison judged is for the reviewer")


def registry():
    return {"CT-ABD-001": abd001, "CT-ABD-002": abd002, "CT-ABD-003": abd003, "CT-ABD-004": abd004,
            "CT-ABD-005": abd005, "CT-ABD-006": abd006, "CT-ABD-007": abd007, "CT-ABD-008": abd008,
            "CT-TTP-002": ttp002}, {}
