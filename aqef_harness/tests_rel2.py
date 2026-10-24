"""CTS Section 14, the remaining automated tests: CT-REL-019 to 022, 026, 028 to 034."""
import copy
import json

from . import fixtures as F
from .tests_dec import gate_is, gates, judge_result, multi, report, run, with_sem
from .tests_exe import setup
from .tests_rel import change_gate, override, release

S0 = ("suites", 0, "scenarios", 0)


def ok(ctx, note=""):
    return ctx.result("PASS", "EXPECTED_MET", note)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


def items(ex):
    b = ex.body
    return b if isinstance(b, list) else (b or {}).get("items", [])


def audit(ctx, name, note="the audit log", **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return items(ctx.record(ctx.a.get(f"/projects/{name}/audit" + (f"?{qs}" if qs else ""), "P-ADMIN"), note))


def policy(ctx, name, actor="P-RELEASE", note="RP-1"):
    return ctx.record(ctx.a.post(f"/projects/{name}/release-policies", {"suites": ["cts-suite"],
                      "environments": ["cts-env"], "service_accounts": ["SA-CI"]}, actor), note)


def sa_decisions(ctx, b):
    """CTS 2.7, F-SA-DECISIONS."""
    name = setup(ctx, with_sem(b), "F-SA-DECISIONS: F-BASE with semantic-gate")
    pol = policy(ctx, name)
    if pol.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"RP-1 rejected: {pol.text()[:200]}")
    rp = pol.body["id"]
    out = {}
    for label, judge, decision in (("b", "J-PASS-90", "approved"), ("d", "J-FAIL-90", "rejected")):
        _, batch = run(ctx, name, judge=judge, note=f"batch for ({label})")
        _, body = gates(ctx, name, batch, f"evaluate for ({label})")
        x = release(ctx, name, batch, body["snapshot_id"], decision, actor="SA-CI", note=f"decision ({label})",
                    release_policy=rp)
        if x.outcome != "accepted":
            ctx.stop("NOT_RUN", "SETUP_FAILED", f"F-SA-DECISIONS: ({label}) rejected: {x.text()[:200]}")
        out[label] = x.body
    rv = ctx.record(ctx.a.post(f"/projects/{name}/release-policies/{rp}/revoke", {}, "P-RELEASE"), "revoke RP-1")
    if rv.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", "F-SA-DECISIONS: revocation rejected")
    return name, rp, out


def new_principal(ctx, body, note):
    return ctx.record(ctx.a.post("/principals", body, "P-ADMIN"), note)


def rel019(ctx, b):
    name, _, dec = sa_decisions(ctx, b)
    es = audit(ctx, name, "audit, release_decide", action="release_decide")
    sa = [e for e in es if e.get("principal_id") == "SA-CI"]
    if len(sa) < 2 or any(e.get("principal_kind") != "service_account" for e in sa):
        return fail(ctx, f"release_decide entries for SA-CI: {sa}")
    allp = audit(ctx, name, "the whole audit log")
    persons = [e for e in allp if str(e.get("principal_id", "")).startswith("P-")]
    if not persons or any(e.get("principal_kind") != "person" for e in persons):
        return fail(ctx, "an entry for a Person's action does not state kind person")
    x = new_principal(ctx, {"id": "SA-NOOWNER", "kind": "service_account", "name": "cts no owner",
                            "roles": [], "token": "cts-sa-noowner"}, "create a Service Account with no owner")
    if x.outcome == "accepted":
        return fail(ctx, "a Service Account with no owning Person was created")
    return ok(ctx, "SA-CI's owner (P-RELEASE) is not retrievable through the API (no GET for Principals); "
                   "left to Inspection")


def rel020(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    a = change_gate(ctx, name, "semantic-gate", actor="SA-CI", threshold=0.9)
    cur = items(ctx.record(ctx.a.get(f"/projects/{name}/gates", "P-RELEASE"), "the Gates after (a)"))
    th = next((g.get("threshold") for g in cur if g.get("name") == "semantic-gate"), None)
    if a.outcome == "accepted" or th != 1.0:
        return fail(ctx, f"(a) took effect: {a.outcome}, threshold {th}")
    g = next(x for x in cur if x.get("name") == "semantic-gate")
    bb = ctx.record(ctx.a.call("PUT", f"/projects/{name}/gates/semantic-gate", "SA-CI", {**g, "threshold": 0.9},
                               headers={"X-Approved-By": "P-APPROVER", "X-External-Review-Ref": "review-cts-1"}),
                    "(b) with approver and review reference")
    if bb.outcome != "accepted":
        return fail(ctx, f"(b) rejected: {bb.text()[:200]}")
    ap = items(ctx.record(ctx.a.get(f"/projects/{name}/approvals", "P-ADMIN"), "the Approval Workflow records"))
    hit = [r for r in ap if r.get("requested_by") == "SA-CI" and r.get("approved_by") == "P-APPROVER"
           and r.get("external_review_reference") == "review-cts-1"]
    return ok(ctx, "approver and review reference sent as the engine's documented headers") if hit \
        else fail(ctx, f"no record names P-APPROVER and review-cts-1: {ap}")


def rel021(ctx, b):
    name = setup(ctx, b, "F-BASE")
    e1, _ = run(ctx, name, note="execution 1")
    run(ctx, name, note="execution 2")
    first = items(ctx.record(ctx.a.get(f"/projects/{name}/baselines"), "Baselines before"))
    eid = e1[0]["id"]
    r = judge_result(ctx, name, eid)
    body = {"execution_id": eid, "result_id": r["id"], "name": "cts-baseline"}
    a = ctx.record(ctx.a.post(f"/projects/{name}/baselines", body, "P-NOPERM"), "(a) as P-NOPERM")
    bb = ctx.record(ctx.a.post(f"/projects/{name}/baselines", body, "P-APPROVER"), "(b) as P-APPROVER")
    if first:
        return fail(ctx, f"a Baseline existed before (b): {first}")
    if a.outcome == "accepted" or bb.outcome != "accepted":
        return fail(ctx, f"(a) {a.outcome}, (b) {bb.outcome}: {bb.text()[:200]}")
    x = bb.body
    want = {"scenario": "s-greeting", "environment": "cts-env", "execution_id": eid, "approved_by": "P-APPROVER",
            "approval_role": "cts-approver"}
    bad = {k: x.get(k) for k, v in want.items() if x.get(k) != v}
    if bad or not x.get("approved_at"):
        return fail(ctx, f"fields: {bad}, approved_at {x.get('approved_at')}")
    return ok(ctx, "cts-approver is the Role holding baseline_approve")


def baselined(ctx, b):
    """CTS 2.7, F-BASELINED."""
    name = setup(ctx, b, "F-BASELINED: F-BASE")
    e1, b1 = run(ctx, name, note="execution 1")
    run(ctx, name, note="execution 2")
    r = judge_result(ctx, name, e1[0]["id"])
    bl = ctx.record(ctx.a.post(f"/projects/{name}/baselines", {"execution_id": e1[0]["id"], "result_id": r["id"],
                    "name": "cts-baseline"}, "P-APPROVER"), "designate the Baseline")
    _, body = gates(ctx, name, b1, "evaluate the first batch")
    if bl.outcome != "accepted" or not body.get("snapshot_id"):
        ctx.stop("NOT_RUN", "SETUP_FAILED", "F-BASELINED could not be built")
    return name, bl.body["id"], body["snapshot_id"]


def rel022(ctx, b):
    name, bid, sid = baselined(ctx, b)
    d = ctx.record(ctx.a.call("DELETE", f"/projects/{name}/environments/cts-env", "P-APPROVER"), "DELETE cts-env")
    if d.outcome == "sut_error":
        ctx.guard(d, "the deletion")
    bl = ctx.record(ctx.a.get(f"/projects/{name}/baselines/{bid}"), "the Baseline")
    sn = ctx.record(ctx.a.get(f"/projects/{name}/snapshots/{sid}"), "the Snapshot")
    if d.outcome != "accepted":
        return ok(ctx, f"the deletion was rejected ({d.status})")
    if bl.outcome != "accepted" or sn.outcome != "accepted":
        return fail(ctx, "the deletion succeeded and a record was lost")
    if "cts-scripted-subject@1" not in bl.text() or "cts-scripted-subject@1" not in sn.text():
        return fail(ctx, "cts-env is not preserved as a frozen record")
    return ok(ctx, "deleted; cts-env preserved in both records")


def rel026(ctx, b):
    name = setup(ctx, b, "Definition: load F-BASE")
    execs, batch = run(ctx, name, note="Execution")
    eid = execs[0]["id"]
    conv = ctx.conversation(name, eid)
    if not conv:
        return fail(ctx, "Evidence: no Conversation")
    rs = ctx.results(name, eid, "Assessment: the Results")
    kinds = {r.get("oracle_type") for r in rs}
    if not {"validator", "judge"} <= kinds:
        return fail(ctx, f"Assessment: Result kinds {kinds}")
    g, body = gates(ctx, name, batch, "Decision: evaluate the Gates")
    gate_is(ctx, g, "functional-gate", "pass")
    x = release(ctx, name, batch, body["snapshot_id"], note="Decision: Release Decision as P-RELEASE")
    return ok(ctx) if x.outcome == "accepted" else fail(ctx, f"Release Decision rejected: {x.text()[:200]}")


def rel028(ctx, b):
    name = setup(ctx, b, "F-BASE")
    before = len(items(ctx.record(ctx.a.get(f"/projects/{name}/executions"), "Executions before")))
    g = ctx.record(ctx.a.call("GET", f"/projects/{name}", None), "GET with no credentials")
    p = ctx.record(ctx.a.call("POST", f"/projects/{name}/executions", None,
                              {"suite": "cts-suite", "environment": "cts-env"}), "POST executions with no credentials")
    after = len(items(ctx.record(ctx.a.get(f"/projects/{name}/executions"), "Executions after")))
    if g.status not in (401, 403) or p.status not in (401, 403) or after != before:
        return fail(ctx, f"unauthenticated: GET {g.status}, POST {p.status}, Executions {before}->{after}")
    ctx.behave("SR-OK")
    x = ctx.record(ctx.a.execute(name, actor="P-NOPERM"), "POST executions as P-NOPERM")
    if x.outcome != "accepted":
        return fail(ctx, f"P-NOPERM's Execution rejected: {x.text()[:200]}")
    es = [e for e in audit(ctx, name, principal_id="P-NOPERM")]
    if not es or any(e.get("principal_kind") != "person" for e in es):
        return fail(ctx, f"no audit entry attributes the Execution to P-NOPERM as a Person: {es}")
    return ok(ctx)


C10 = ("id", "generated_at", "scope", "gates", "metrics", "signals")
SIGNALS = ("retries", "low_confidence", "multi_judge", "unenforced_boundaries", "boundary_attempts",
           "unadmitted_judges")


def c10_missing(rep):
    miss = [k for k in C10 if k not in rep]
    miss += [f"signals.{k}" for k in SIGNALS if not isinstance((rep.get("signals") or {}).get(k), list)]
    return miss


def rel029(ctx, b):
    name, execs, batch = None, None, None
    name = setup(ctx, with_sem(b), "(a) F-OVERRIDDEN")
    _, batch = run(ctx, name, judge="J-FAIL-90")
    g, body = gates(ctx, name, batch)
    ov = override(ctx, name, "semantic-gate", g["semantic-gate"]["id"], batch)
    if ov.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"F-OVERRIDDEN: override rejected: {ov.text()[:200]}")
    rel = release(ctx, name, batch, body["snapshot_id"], "overridden")
    if rel.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"F-OVERRIDDEN: decision rejected: {rel.text()[:200]}")
    ra = report(ctx, name, batch, "(a) the Report after the override")
    m = c10_missing(ra)
    sg = (ra.get("gates") or {}).get("semantic-gate") or {}
    if m or sg.get("status") != "fail" or "threshold" not in sg or "basis" not in sg or not sg.get("override"):
        return fail(ctx, f"(a) missing {m}; semantic-gate {sg}")
    ex, n2 = ctx.load(multi(b, min_basis={"scenarios": 4}), "(b) CT-DEC-004's configuration", suffix="b")
    if ex.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", "(b) rejected")
    _, b2 = run(ctx, n2, "SR-ECHO", note="(b) execute")
    gates(ctx, n2, b2, "(b) evaluate")
    rb = report(ctx, n2, b2, "(b) the Report")
    sg = (rb.get("gates") or {}).get("semantic-gate") or {}
    if c10_missing(rb) or "insufficient_basis" not in (sg.get("reasons") or []) or "threshold" in (sg.get("reasons") or []) \
            or "basis" not in sg:
        return fail(ctx, f"(b) missing {c10_missing(rb)}; semantic-gate {sg}")
    return ok(ctx, "(a) the Report generated after the override")


def scenario_path(name):
    return f"/projects/{name}/suites/cts-suite/scenarios/s-greeting"


def rel030(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    cur = ctx.record(ctx.a.get(scenario_path(name)), "s-greeting").body or {}
    sa = copy.deepcopy(cur)
    sa["variables"] = {"query": "Hi"}
    a = ctx.record(ctx.a.call("PUT", scenario_path(name), "P-EDITOR", sa), "(a) variables.query Hi")
    sb = copy.deepcopy(sa)
    sb["contract"]["expectations"][0]["confidence_threshold"] = 0.5
    bb = ctx.record(ctx.a.call("PUT", scenario_path(name), "P-EDITOR", sb), "(b) confidence_threshold 0.5")
    d = ctx.named(with_sem(b))
    d["name"] = name
    d["suites"][0]["scenarios"][0]["variables"] = {"query": "Hi"}
    d["quality_gates"] = [dict(q, threshold=0.5) if q["name"] == "semantic-gate" else q for q in d["quality_gates"]]
    c = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-EDITOR", ctx.a.to_engine_form(d)), "(c) PUT the Project")
    now = ctx.record(ctx.a.get(scenario_path(name)), "s-greeting after").body or {}
    gs = items(ctx.record(ctx.a.get(f"/projects/{name}/gates"), "the Gates after"))
    th = next((g.get("threshold") for g in gs if g.get("name") == "semantic-gate"), None)
    ct = (((now.get("contract") or {}).get("expectations") or [{}])[0]).get("confidence_threshold")
    if a.outcome != "accepted":
        return fail(ctx, f"(a) rejected: {a.text()[:200]}")
    if bb.outcome == "accepted" or c.outcome == "accepted" or ct != 0.8 or th != 1.0:
        return fail(ctx, f"(b) {bb.outcome}, (c) {c.outcome}; now confidence_threshold {ct}, threshold {th}")
    y = ctx.record(ctx.a.call("PUT", scenario_path(name), "P-APPROVER", sb), "(b) as P-APPROVER")
    if y.outcome != "accepted":
        return fail(ctx, f"(b) by P-APPROVER rejected: {y.text()[:200]}")
    es = audit(ctx, name, "audit, contract_define", action="contract_define")
    if not [e for e in es if e.get("principal_id") == "P-APPROVER"]:
        return fail(ctx, "P-APPROVER's change is not logged as contract_define")
    return ok(ctx)


def rel031(ctx, b):
    name = setup(ctx, b, "F-BASE")
    pol = policy(ctx, name)
    if pol.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", "RP-1 rejected")
    rp = pol.body["id"]
    got = ctx.record(ctx.a.get(f"/projects/{name}/release-policies/{rp}"), "RP-1").body or {}
    miss = [k for k in ("id", "project", "suites", "environments", "service_accounts", "approved_by",
                        "approval_role", "approved_at") if k not in got]
    if miss or got.get("approved_by") != "P-RELEASE" or got.get("approval_role") != "cts-release":
        return fail(ctx, f"RP-1: missing {miss}; approved_by {got.get('approved_by')}, role {got.get('approval_role')}")
    a = policy(ctx, name, "SA-CI", "RP-2 as SA-CI")
    r = ctx.record(ctx.a.post(f"/projects/{name}/release-policies/{rp}/revoke", {}, "SA-CI"), "revoke RP-1 as SA-CI")
    if a.outcome == "accepted" or r.outcome == "accepted":
        return fail(ctx, f"SA-CI: approve {a.outcome}, revoke {r.outcome}")
    ch = dict(got, environments=["cts-env-2"])
    tries = [ctx.record(ctx.a.call(m, f"/projects/{name}/release-policies/{rp}", "P-RELEASE", ch), f"{m} RP-1")
             for m in ("PUT", "PATCH")]
    again = ctx.record(ctx.a.get(f"/projects/{name}/release-policies/{rp}"), "RP-1 again").body or {}
    if any(t.outcome == "accepted" for t in tries) or again != got:
        return fail(ctx, "RP-1 changed")
    return ok(ctx, "the engine offers no modifying operation; PUT and PATCH tried")


def rel032(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    _, batch = run(ctx, name)
    _, body = gates(ctx, name, batch)
    a = release(ctx, name, batch, body["snapshot_id"], actor="P-ROLE-A", note="(a) P-ROLE-A, Role release_manager")
    bb = release(ctx, name, batch, body["snapshot_id"], actor="P-ROLE-B", note="(b) P-ROLE-B, Role observer")
    if a.outcome == "accepted":
        return fail(ctx, "(a) accepted")
    if a.status == 422 or "release_decide" not in a.text():
        return fail(ctx, f"(a) not rejected for the missing Permission: {a.status} {a.text()[:200]}")
    if bb.outcome != "accepted" or (bb.body or {}).get("approval_role") != "observer":
        return fail(ctx, f"(b): {bb.outcome} {bb.text()[:200]}")
    return ok(ctx, "approved_by and approval_role are set by the engine, not sent")


def rel033(ctx, b):
    name, _, dec = sa_decisions(ctx, b)
    did = dec["b"]["id"]
    x = ctx.record(ctx.a.get(f"/projects/{name}/releases/{did}"), "decision (b)").body or {}
    es = [e for e in audit(ctx, name, principal_id="SA-CI")]
    if not es or any(e.get("principal_kind") != "service_account" for e in es):
        return fail(ctx, f"an audit entry for SA-CI is not marked service_account: {es}")
    if x.get("approved_by") != "SA-CI" or not x.get("release_policy"):
        return fail(ctx, f"decision (b): approved_by {x.get('approved_by')}, release_policy {x.get('release_policy')}")
    y = new_principal(ctx, {"id": "SA-ASPERSON", "kind": "person", "owner_person_id": "P-RELEASE",
                            "token": "cts-sa-asperson"}, "a Principal with an owner, marked person")
    if y.outcome == "accepted":
        return fail(ctx, "a Person with an owning Person was created")
    return ok(ctx, "A.12 gives the decision no Principal-kind field; SA-CI is identified as a Service Account in "
                   "the audit log and the decision carries release_policy. Personal name or e-mail: Inspection")


def rel034(ctx, b):
    d = F.f_ds(b)
    contract = copy.deepcopy(d["suites"][0]["scenarios"][0]["contract"])
    name = setup(ctx, d, "F-DS")
    c1 = ctx.record(ctx.a.post(f"/projects/{name}/contracts", {"name": "cts-contract", **contract}, "P-APPROVER"),
                    "cts-contract version 1")
    cur = ctx.record(ctx.a.get(scenario_path(name)), "s-greeting").body or {}
    cur["contract"] = "cts-contract"
    s = ctx.record(ctx.a.call("PUT", scenario_path(name), "P-APPROVER", cur), "reference cts-contract by name")
    if c1.outcome != "accepted" or s.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"{c1.text()[:150]} / {s.text()[:150]}")
    execs, _ = run(ctx, name)
    eid = execs[0]["id"]
    r = judge_result(ctx, name, eid)
    bl = ctx.record(ctx.a.post(f"/projects/{name}/baselines", {"execution_id": eid, "result_id": r["id"],
                    "name": "cts-baseline"}, "P-APPROVER"), "designate the Baseline")
    if bl.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"Baseline rejected: {bl.text()[:200]}")
    c2 = copy.deepcopy(contract)
    c2["expectations"][0]["confidence_threshold"] = 0.85
    v2 = ctx.record(ctx.a.call("PUT", f"/projects/{name}/contracts/cts-contract", "P-APPROVER",
                               {"name": "cts-contract", **c2}), "cts-contract version 2")
    ds = F.ds1("Bye")
    ds["version"] = "1.1.0"
    d2 = ctx.record(ctx.a.post(f"/projects/{name}/datasets", ds, "P-APPROVER"), "register ds-1@1.1.0")
    if v2.outcome != "accepted" or d2.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", "version 2 or ds-1@1.1.0 rejected")
    dels = [ctx.record(ctx.a.call("DELETE", p, "P-ADMIN"), f"DELETE {p}") for p in
            (f"/projects/{name}/datasets/ds-1", f"/projects/{name}/contracts/cts-contract")]
    got = ctx.record(ctx.a.get(f"/projects/{name}/baselines/{bl.body['id']}"), "the Baseline")
    t = got.text()
    rows = ctx.record(ctx.a.get(f"/projects/{name}/datasets/ds-1/rows?version=1.0.0"), "rows of ds-1@1.0.0")
    if any(x.outcome == "accepted" for x in dels):
        note = "a deletion was accepted"
    else:
        note = "no deletion operation succeeded"
    if got.outcome != "accepted" or "1.0.0" not in t or '"Hi"' not in t or "0.85" in t or "0.8" not in t:
        return fail(ctx, f"the Baseline does not keep ds-1@1.0.0 and version 1: {t[:300]}")
    if rows.outcome != "accepted" or '"Hi"' not in rows.text():
        return fail(ctx, "ds-1@1.0.0 is not retrievable with its rows")
    return ok(ctx, f"{note}; Contract version 1 recovered from the Baseline's frozen copy")


def registry():
    return {"CT-REL-019": rel019, "CT-REL-020": rel020, "CT-REL-021": rel021, "CT-REL-022": rel022,
            "CT-REL-026": rel026, "CT-REL-028": rel028, "CT-REL-029": rel029, "CT-REL-030": rel030,
            "CT-REL-031": rel031, "CT-REL-032": rel032, "CT-REL-033": rel033, "CT-REL-034": rel034,
            **registry2()[0]}, {}


# ---------------------------------------------------------------- CT-REL-013, CT-API-001, CT-API-002
def rel013(ctx, b):
    name = setup(ctx, with_sem(b), "F-CONTRACT-CHANGED: F-BASE with semantic-gate")
    _, batch = run(ctx, name)
    _, body = gates(ctx, name, batch)
    sid = body["snapshot_id"]
    s1 = ctx.record(ctx.a.get(f"/projects/{name}/snapshots/{sid}"), "the Snapshot, before the change").body or {}
    cur = ctx.record(ctx.a.get(scenario_path(name)), "s-greeting").body or {}
    cur["contract"]["expectations"][0]["confidence_threshold"] = 0.85
    ch = ctx.record(ctx.a.call("PUT", scenario_path(name), "P-APPROVER", cur), "governed change: 0.85")
    if ch.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"F-CONTRACT-CHANGED: change rejected: {ch.text()[:200]}")
    s2 = ctx.record(ctx.a.get(f"/projects/{name}/snapshots/{sid}"), "the Snapshot, after the change").body or {}
    if s1 != s2:
        return fail(ctx, "the Snapshot changed after the governed change")
    miss = [k for k in ("id", "captured_at", "project", "suites", "environments", "contracts", "inline_contracts",
                        "quality_gates") if k not in s2]
    envs = json.dumps(s2.get("environments"))
    inl = s2.get("inline_contracts") or {}
    key = next((k for k in inl if "cts-suite" in k and "s-greeting" in k), None)
    gnames = sorted(g.get("name") for g in (s2.get("quality_gates") or []))
    problems = []
    if miss:
        problems.append(f"missing {miss}")
    if s2.get("project") != name or s2.get("suites") != ["cts-suite"]:
        problems.append(f"project/suites {s2.get('project')}, {s2.get('suites')}")
    if "cts-env" not in envs or "cts-scripted-subject@1" not in envs:
        problems.append("environments")
    if s2.get("contracts") != {}:
        problems.append(f"contracts {s2.get('contracts')}")
    if key is None or "0.8" not in json.dumps(inl[key]) or "0.85" in json.dumps(inl[key]):
        problems.append(f"inline_contracts {list(inl)}")
    if gnames != ["functional-gate", "semantic-gate"]:
        problems.append(f"quality_gates {gnames}")
    return fail(ctx, "; ".join(problems)) if problems else ok(ctx, f"inline Contract keyed {key!r}")


def pages(ctx, path, actor, p, label):
    got, off, n = [], 0, 0
    sep = "&" if "?" in path else "?"
    while n < 200:
        x = ctx.record(ctx.a.get(f"{path}{sep}offset={off}&limit={p}", actor), f"{label}, offset {off}")
        it = items(x)
        if len(it) > p:
            return None, f"{label}: {len(it)} items on a page of {p}"
        if not it:
            break
        got += it
        off += p
        n += 1
    ref = items(ctx.record(ctx.a.get(f"{path}{sep}offset=0&limit=1000", actor), f"{label}, reference set"))
    ids = [json.dumps(i, sort_keys=True) for i in got]
    if ids != [json.dumps(i, sort_keys=True) for i in ref] or len(set(ids)) != len(ids):
        return None, f"{label}: pages differ from the reference set ({len(got)} vs {len(ref)})"
    if n < 2:
        return None, f"{label}: fewer than two pages"
    return got, None


def api001(ctx, b):
    name = setup(ctx, multi(b), "F-MULTI with semantic-gate")
    for i in (1, 2):
        _, batch = run(ctx, name, note=f"execution {i}")
    for t in (0.9, 1.0):
        change_gate(ctx, name, "semantic-gate", threshold=t)
    p = 1
    ex = items(ctx.record(ctx.a.get(f"/projects/{name}/executions?offset=0&limit=1000"), "Executions"))
    e1 = next(e for e in ex if e.get("scenario") == "s-1")
    for path, actor, label in ((f"/projects/{name}/executions", "P-RELEASE", "executions"),
                               (f"/projects/{name}/executions/{e1['id']}/results", "P-RELEASE", "results"),
                               (f"/projects/{name}/audit", "P-ADMIN", "audit")):
        _, err = pages(ctx, path, actor, p, label)
        if err:
            return fail(ctx, err)
    return ok(ctx, "p = 1 (the engine's documented minimum); offset/limit on all three; s-1's two clauses "
                   "already give more than p Results, so no extra Constraints were added")


def api002(ctx, b):
    name, bid, _ = baselined(ctx, b)
    au0 = audit(ctx, name, "audit before")
    a = ctx.record(ctx.a.call("DELETE", f"/projects/{name}", "P-ADMIN"), "(a) DELETE, no statement")
    bb = ctx.record(ctx.a.call("DELETE", f"/projects/{name}?retain_history=false", "P-ADMIN"),
                    "(b) DELETE, history not retained, no separate authorization")
    still = ctx.record(ctx.a.get(f"/projects/{name}/baselines/{bid}"), "the Baseline after (a), (b)")
    if a.outcome == "accepted" or bb.outcome == "accepted" or still.outcome != "accepted":
        return fail(ctx, f"(a) {a.status}, (b) {bb.status}; Baseline {still.status}")
    c = ctx.record(ctx.a.call("DELETE", f"/projects/{name}?retain_history=true", "P-ADMIN"), "(c) DELETE, retain history")
    if c.outcome != "accepted":
        return ok(ctx, f"(c) rejected ({c.status})")
    bl = ctx.record(ctx.a.get(f"/projects/{name}/baselines/{bid}"), "the Baseline after (c)")
    au = ctx.record(ctx.a.get(f"/projects/{name}/audit", "P-ADMIN"), "the audit log after (c)")
    if bl.outcome != "accepted" or au.outcome != "accepted":
        return fail(ctx, f"after (c): Baseline {bl.status}, audit {au.status}; the engine documents no other "
                         "way to read retained history")
    ids0 = {e.get("id") for e in au0}
    ids1 = {e.get("id") for e in items(au)}
    dele = [e for e in items(au) if "delete" in str(e.get("action"))]
    if not ids0 <= ids1 or not dele or "retain" not in json.dumps(dele):
        return fail(ctx, f"audit after (c): lost {len(ids0 - ids1)}; deletion record {dele}")
    return ok(ctx, "history read through the same paths after deletion")


def registry2():
    from .tests_dec import manual
    return {"CT-REL-013": rel013, "CT-API-001": api001, "CT-API-002": api002,
            "CT-REL-023": manual("Inspection: a reviewer traces a Release Decision to its evidence"),
            "CT-REL-027": manual("Inspection: the published Conformance Statement against §10"),
            "CT-REL-036": manual("Inspection: a KPI decomposes into Metrics and Results")}, {}
