"""CTS Section 13, Decision; CT-ADM-004 to 007 (Section 16); CT-REL-035 (Section 14)."""
import copy

from .tests_adm import ADM_PASS, adm_pass, post as adm_post
from .tests_exe import f_multi, setup

SEM = {"name": "semantic-gate", "aggregate": "semantic", "threshold": 1.0, "on_failure": "block_release"}


def with_sem(doc, **extra):
    d = copy.deepcopy(doc)
    d["quality_gates"].append({**SEM, **extra})
    return d


def gates(ctx, name, batch, note="evaluate the Gates", actor="P-RELEASE"):
    ex = ctx.record(ctx.a.post(f"/projects/{name}/gates/check", {"execution_batch_id": batch}, actor), note)
    ctx.guard(ex, note)
    if ex.outcome != "accepted":
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{note}: rejected ({ex.status}): {ex.text()[:300]}")
    b = ex.body or {}
    return b.get("gates", {}), b


def run(ctx, name, subject="SR-OK", judge="J-PASS-90", note="execute", **kw):
    ctx.behave(subject, judge=judge, **kw)
    execs, body = ctx.execute(name, note)
    return execs, body.get("execution_batch_id")


def gate_is(ctx, g, name, status, reasons_has=(), reasons_lacks=()):
    r = g.get(name)
    if r is None:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"no GateResult for {name}")
    if r.get("status") != status:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{name} is {r.get('status')}, expected {status}: {r.get('reasons')}")
    rs = r.get("reasons") or []
    for x in reasons_has:
        if x not in rs:
            ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{name} reasons {rs} lack {x}")
    for x in reasons_lacks:
        if x in rs:
            ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{name} reasons {rs} include {x}")
    return r


def ok(ctx):
    return ctx.result("PASS", "EXPECTED_MET")


# ---------------------------------------------------------------- 13
def dec001(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    _, batch = run(ctx, name)
    g, body = gates(ctx, name, batch)
    if not body.get("snapshot_id"):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "no snapshot_id")
    ids = []
    for n in ("functional-gate", "semantic-gate"):
        r = gate_is(ctx, g, n, "pass")
        bad = [k for k in ("id", "basis") if not r.get(k)]
        if bad or r.get("blocking") is not True or "reasons" in r or r.get("override") \
                or not isinstance(r.get("value"), (int, float)) or r.get("threshold") != 1.0:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{n}: {r}")
        ids.append(r["id"])
    if ids[0] == ids[1]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the two GateResults share an id")
    return ok(ctx)


def multi(b, **sem):
    return with_sem(f_multi(b), **sem)


def basis_is(ctx, r, want):
    bs = r.get("basis") or {}
    bad = {k: bs.get(k) for k, v in want.items() if bs.get(k) != v}
    if bad:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"basis {bs}; expected {want}")


def dec002(ctx, b):
    name = setup(ctx, multi(b), "F-MULTI with semantic-gate")
    _, batch = run(ctx, name, "SR-ECHO")
    g, _ = gates(ctx, name, batch)
    basis_is(ctx, g.get("semantic-gate", {}), {"results": 3, "not_actionable": 0, "scenarios": 3,
                                                "executions": 3, "min_basis_met": "not_declared"})
    return ok(ctx)


def dec003(ctx, b):
    vals = []
    for label, sem in (("a", {}), ("b", {"min_basis": {"scenarios": 3}})):
        name = setup(ctx, multi(b, **sem), f"variant {label}") if label == "a" else None
        if label == "b":
            ex, name = ctx.load(multi(b, **sem), "variant b", suffix="b")
            if ex.outcome != "accepted":
                return ctx.result("NOT_RUN", "SETUP_FAILED", "variant b was rejected")
        _, batch = run(ctx, name, "SR-ECHO", note=f"execute variant {label}")
        g, _ = gates(ctx, name, batch, f"evaluate variant {label}")
        r = gate_is(ctx, g, "semantic-gate", "pass")
        vals.append((r.get("basis") or {}).get("min_basis_met"))
    if vals != ["not_declared", True]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"min_basis_met is {vals}")
    return ok(ctx)


def dec004(ctx, b):
    name = setup(ctx, multi(b, min_basis={"scenarios": 4}), "F-MULTI, min_basis scenarios 4")
    _, batch = run(ctx, name, "SR-ECHO")
    g, _ = gates(ctx, name, batch)
    r = gate_is(ctx, g, "semantic-gate", "fail", ["insufficient_basis"], ["threshold"])
    if (r.get("basis") or {}).get("min_basis_met") is not False:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"min_basis_met is {(r.get('basis') or {}).get('min_basis_met')}")
    return ok(ctx)


def dec005(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    _, batch = run(ctx, name, judge="J-FAIL-90")
    g, _ = gates(ctx, name, batch)
    r = gate_is(ctx, g, "semantic-gate", "fail", ["threshold"])
    if r.get("reasons") != ["threshold"]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"reasons {r.get('reasons')}")
    basis_is(ctx, r, {"results": 1, "not_actionable": 0})
    if not (isinstance(r.get("value"), (int, float)) and r["value"] < 1.0):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"value {r.get('value')}")
    gate_is(ctx, g, "functional-gate", "pass")
    return ok(ctx)


def dec008(ctx, b):
    name = setup(ctx, multi(b, min_basis={"results": 3}), "F-MULTI, min_basis results 3")
    _, batch = run(ctx, name, "SR-ECHO", judge_map={"One": "J-FAIL-90", "Two": "J-PASS-60", "Three": "J-PASS-90"})
    g, _ = gates(ctx, name, batch)
    r = gate_is(ctx, g, "semantic-gate", "fail", ["threshold", "non_actionable_results", "insufficient_basis"])
    basis_is(ctx, r, {"results": 2, "not_actionable": 1})
    return ok(ctx)


def non_actionable(judge):
    def t(ctx, b):
        name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
        _, batch = run(ctx, name, judge=judge)
        g, _ = gates(ctx, name, batch)
        r = gate_is(ctx, g, "semantic-gate", "fail", ["non_actionable_results"])
        basis_is(ctx, r, {"results": 0, "not_actionable": 1})
        if r.get("value") is None:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", "value is bare null")
        return ok(ctx)
    return t


def judge_result(ctx, name, eid):
    j = [r for r in ctx.results(name, eid) if r.get("oracle_type") == "judge"]
    if len(j) != 1:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{len(j)} Judge Results")
    return j[0]


def reassess(ctx, name, eid, r):
    ex = ctx.record(ctx.a.post(f"/projects/{name}/executions/{eid}/results/{r['id']}/reassess",
                               {"oracle": r["oracle"]}, "P-RELEASE"), "request a re-assessment")
    ctx.guard(ex, "the re-assessment")
    if ex.status in (404, 405):
        ctx.stop("FAIL", "REQUIRED_OPERATION_MISSING", f"reassess answered {ex.status}")
    return ex


def dec013(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    execs, batch = run(ctx, name, judge="J-PASS-60-THEN-90")
    r = judge_result(ctx, name, execs[0]["id"])
    ex = reassess(ctx, name, execs[0]["id"], r)
    if ex.outcome == "accepted":
        new = ex.body or {}
        if new.get("resolves") == r["id"]:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", "the same Judge resolved its inconclusive Result")
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "semantic-gate", "fail", ["non_actionable_results"])
    return ok(ctx)


def dec014(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    execs, batch = run(ctx, name, judge="J-DOWN")
    g, _ = gates(ctx, name, batch, "evaluation 1")
    gate_is(ctx, g, "semantic-gate", "fail", ["non_actionable_results"])
    r = judge_result(ctx, name, execs[0]["id"])
    ctx.scripted.judge = "J-PASS-90"
    ex = reassess(ctx, name, execs[0]["id"], r)
    if ex.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the re-assessment was rejected: {ex.text()[:200]}")
    new = ex.body or {}
    if new.get("resolves") != r["id"] or new.get("verdict") != "pass" or new.get("disposition") != "actionable":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the new Result is {new}")
    g2, _ = gates(ctx, name, batch, "evaluation 2")
    r2 = gate_is(ctx, g2, "semantic-gate", "pass")
    basis_is(ctx, r2, {"not_actionable": 0})
    if len(ctx.subject_log()) != 1:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the subject was called again")
    return ok(ctx)


def dec019(ctx, b):
    d = multi(b)
    d["contracts"] = [{"constraints": [{"validator": "forbidden-content", "target": "response",
                                        "expected": {"patterns": [{"regex": "Three"}]}, "veto": True}]}]
    d["quality_gates"].append({"name": "safety-gate", "aggregate": "safety", "threshold": 0.5,
                               "on_failure": "block_release"})
    name = setup(ctx, d, "F-MULTI with the safety veto")
    _, batch = run(ctx, name, "SR-ECHO")
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "safety-gate", "fail")
    return ok(ctx)


def dec020(ctx, b):
    d = multi(b)
    for i, w in enumerate((3.0, 1.0, 1.0)):
        d["suites"][0]["scenarios"][i]["contract"]["policies"] = {"weight": w}
    name = setup(ctx, d, "F-MULTI with weights")
    vals = []
    for label, m in (("A", ("J-FAIL-90", "J-PASS-90", "J-PASS-90")), ("B", ("J-PASS-90", "J-FAIL-90", "J-PASS-90"))):
        _, batch = run(ctx, name, "SR-ECHO", judge_map=dict(zip(("One", "Two", "Three"), m)), note=f"run {label}")
        g, _ = gates(ctx, name, batch, f"evaluate run {label}")
        vals.append(gate_is(ctx, g, "semantic-gate", "fail").get("value"))
    if not all(isinstance(v, (int, float)) for v in vals) or not vals[0] < vals[1]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"values A {vals[0]}, B {vals[1]}")
    return ok(ctx)


def governed_env_change(ctx, name):
    ex = ctx.record(ctx.a.call("GET", f"/projects/{name}/environments/cts-env", "P-APPROVER"), "the Environment")
    env = dict(ex.body or {})
    env["prompt_version"] = "cts-prompt@2"
    ch = ctx.record(ctx.a.call("PUT", f"/projects/{name}/environments/cts-env", "P-APPROVER", env),
                    "governed change: prompt_version to cts-prompt@2")
    ctx.guard(ch, "the Environment change")
    if ch.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"the Environment change was rejected: {ch.text()[:200]}")


def dec022(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    _, b1 = run(ctx, name, note="batch 1")
    g1, body1 = gates(ctx, name, b1, "evaluation 1")
    gate_is(ctx, g1, "semantic-gate", "pass")
    governed_env_change(ctx, name)
    g2, body2 = gates(ctx, name, b1, "evaluation 2, batch 1")
    if body2.get("snapshot_id") == body1.get("snapshot_id"):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "no new snapshot_id")
    for n in ("functional-gate", "semantic-gate"):
        r = gate_is(ctx, g2, n, "fail", ["stale_results"])
        basis_is(ctx, r, {"results": 0})
        if (r.get("basis") or {}).get("not_actionable", 0) < 1:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{n}: stale Results not counted as not actionable")
    _, b2 = run(ctx, name, note="batch 2")
    g3, _ = gates(ctx, name, b2, "evaluation, batch 2")
    gate_is(ctx, g3, "semantic-gate", "pass")
    gate_is(ctx, g3, "functional-gate", "pass")
    return ok(ctx)


def dec023(ctx, b):
    for label, ids in (("a", True), ("b", False)):
        d = with_sem(b)
        c = d["suites"][0]["scenarios"][0]["contract"]
        if ids:
            c["constraints"][0]["id"], c["expectations"][0]["id"] = "schema-1", "greets"
        ex, name = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome != "accepted":
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"variant {label} was rejected")
        _, batch = run(ctx, name, note=f"variant {label}")
        gates(ctx, name, batch, f"variant {label}: evaluation 1")
        d2 = ctx.named(d, label)
        d2["suites"][0]["scenarios"][0]["contract"]["expectations"][0]["confidence_threshold"] = 0.85
        ch = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", d2),
                        f"variant {label}: governed change, confidence_threshold 0.85")
        ctx.guard(ch, "the Contract change")
        if ch.outcome != "accepted":
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"the change was rejected: {ch.text()[:200]}")
        g, _ = gates(ctx, name, batch, f"variant {label}: evaluation 2")
        gate_is(ctx, g, "semantic-gate", "fail", ["stale_results"])
        if ids:
            gate_is(ctx, g, "functional-gate", "pass")
        else:
            gate_is(ctx, g, "functional-gate", "fail", ["stale_results"])
    return ok(ctx)


def scoped(n, what):
    def t(ctx, b):
        ctx.needs_slice(n, what)
        return ctx.result("NOT_RUN", "ADAPTER_GAP", "this harness version does not yet drive it")
    return t


def manual(what):
    def t(ctx, b):
        return ctx.result("NOT_RUN", "MANUAL_REVIEW_PENDING", f"{what} (CTS 1.8)")
    return t


# ---------------------------------------------------------------- 16: ADM-004 to 007
def report(ctx, name, batch, note="generate a Report"):
    ex = ctx.record(ctx.a.post(f"/projects/{name}/reports", {"execution_batch_id": batch}, "P-RELEASE"), note)
    ctx.guard(ex, note)
    if ex.outcome != "accepted":
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{note}: {ex.status} {ex.text()[:200]}")
    return ex.body or {}


def unadmitted(rep):
    return (rep.get("signals") or {}).get("unadmitted_judges")


def gate_admitted(b, **extra):
    return with_sem(b, require_admitted_judges=True, **extra)


def oracle_of(ctx, name, eid):
    return judge_result(ctx, name, eid)["oracle"]


def adm004(ctx, b):
    name = setup(ctx, gate_admitted(b), "F-BASE with gate-admitted")
    execs, batch = run(ctx, name)
    o = oracle_of(ctx, name, execs[0]["id"])
    steps = [("a", None, False), ("b", adm_pass(o), True), ("c", adm_pass(o, {"raw_agreement": 0.80,
             "chance_corrected_agreement": 0.52, "admitted": False}), False), ("d", adm_pass(o), True)]
    sent = []
    for label, body, admitted in steps:
        if body is not None:
            ex = adm_post(ctx, name, body, "P-REVIEWER", f"({label}) record")
            if ex.outcome != "accepted":
                return ctx.result("FAIL", "EXPECTED_VIOLATED", f"({label}) the Admission was rejected: {ex.text()[:200]}")
            sent.append(ex.body)
        g, _ = gates(ctx, name, batch, f"({label}) evaluate")
        rep = report(ctx, name, batch, f"({label}) Report")
        if admitted:
            gate_is(ctx, g, "semantic-gate", "pass")
        else:
            r = gate_is(ctx, g, "semantic-gate", "fail", ["judge_not_admitted"])
            if label == "a":
                basis_is(ctx, r, {"results": 0, "not_actionable": 1})
                gate_is(ctx, g, "functional-gate", "pass")
        u = unadmitted(rep)
        listed = u is not None and o in str(u)
        if listed == admitted:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"({label}) Report unadmitted_judges {u}")
    rs = ctx.record(ctx.a.get(f"/projects/{name}/admissions", "P-NOPERM"), "(e) the Admission records")
    got = rs.body.get("items", rs.body) if isinstance(rs.body, dict) else rs.body
    if got != sent:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Admission records differ from what was returned when recorded")
    return ok(ctx)


def adm005(ctx, b):
    name = setup(ctx, gate_admitted(b), "F-BASE with gate-admitted")
    execs, _ = run(ctx, name, note="setup execution")
    o1 = oracle_of(ctx, name, execs[0]["id"])
    ex = adm_post(ctx, name, adm_pass(o1), "P-REVIEWER", "record ADM-PASS for ORACLE-1")
    if ex.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"ADM-PASS was rejected: {ex.text()[:200]}")
    d = ctx.named(gate_admitted(b))
    d["suites"][0]["scenarios"][0]["contract"]["expectations"][0]["judge"]["model"] = "cts-scripted-judge@2"
    ch = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", d), "governed change: judge @2")
    ctx.guard(ch, "the change")
    if ch.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"the change was rejected: {ch.text()[:200]}")
    execs2, batch2 = run(ctx, name, note="execution with judge @2")
    o2 = oracle_of(ctx, name, execs2[0]["id"])
    if o2 == o1:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "ORACLE-2 equals ORACLE-1")
    g, _ = gates(ctx, name, batch2)
    gate_is(ctx, g, "semantic-gate", "fail", ["judge_not_admitted"])
    u = str(unadmitted(report(ctx, name, batch2)))
    if o2 not in u or o1 in u:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"unadmitted_judges {u}")
    return ok(ctx)


def adm007(ctx, b):
    name = setup(ctx, gate_admitted(b, min_basis={"results": 2}), "gate-admitted with min_basis")
    _, batch = run(ctx, name)
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "semantic-gate", "fail", ["judge_not_admitted", "insufficient_basis"])
    return ok(ctx)


# ---------------------------------------------------------------- 14: REL-035
def rel035(ctx, b):
    d = with_sem(f_multi(b))
    d["execution"] = {"scheduling": "sequential",
                      "retry": {"max_attempts": 2, "on": "infrastructure_failure"}}
    name = setup(ctx, d, "REL-035 configuration")
    ctx.behave("SR-ECHO", subject_by_prompt={"One": "SR-503-THEN-ECHO"},
               judge_map={"One": "J-PASS-60", "Two": "J-PASS-60", "Three": "J-PASS-90"})
    execs, body = ctx.execute(name)
    ctx.subject_log()
    rep = report(ctx, name, body.get("execution_batch_id"))
    sig = rep.get("signals") or {}
    need = ["retries", "low_confidence", "multi_judge", "unenforced_boundaries", "boundary_attempts",
            "unadmitted_judges"]
    miss = [k for k in need if not isinstance(sig.get(k), list)]
    if miss:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"signals lack lists {miss}")
    import json
    rt = json.dumps(sig["retries"])
    if "s-1" not in rt or "1" not in rt:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"retries {sig['retries']}")
    mine = [e for e in sig["low_confidence"] if "cts-scripted-judge@1" in json.dumps(e)]
    inc = sum(e.get("inconclusive", 0) for e in mine)
    tot = sum(e.get("results", 0) for e in mine)
    if (inc, tot) != (2, 3):
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          f"low_confidence for the Judge: {inc} inconclusive of {tot}; expected 2 of 3: {mine}")
    if any(sig[k] for k in ("multi_judge", "unenforced_boundaries", "boundary_attempts")):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "multi_judge, unenforced_boundaries or boundary_attempts not empty")
    if "cts-scripted-judge@1" not in json.dumps(sig["unadmitted_judges"]):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"unadmitted_judges {sig['unadmitted_judges']}")
    g = rep.get("gates") or {}
    r = gate_is(ctx, g, "semantic-gate", "fail", ["non_actionable_results"], ["judge_not_admitted"])
    if not all((g.get(n) or {}).get("basis") for n in ("functional-gate", "semantic-gate")):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "a Gate in the Report has no basis")
    return ctx.result("PASS", "EXPECTED_MET", "low_confidence summed over its per-Scenario entries")


def registry():
    T = {"CT-DEC-001": dec001, "CT-DEC-002": dec002, "CT-DEC-003": dec003, "CT-DEC-004": dec004,
         "CT-DEC-005": dec005, "CT-DEC-006": non_actionable("J-PASS-60"),
         "CT-DEC-007": non_actionable("J-DOWN"), "CT-DEC-008": dec008,
         "CT-DEC-009": manual("Inspection: no configuration lets a non-actionable Result pass"),
         "CT-DEC-013": dec013, "CT-DEC-014": dec014, "CT-DEC-019": dec019, "CT-DEC-020": dec020,
         "CT-DEC-021": manual("Inspection: a statistical interval is not labelled Confidence"),
         "CT-DEC-022": dec022, "CT-DEC-023": dec023,
         "CT-ADM-004": adm004, "CT-ADM-005": adm005, "CT-ADM-007": adm007,
         "CT-REL-035": rel035}
    return T, {}
