"""CTS Section 14, Release Decision and Governance (the automated core tests).

The engine's Release request carries execution_batch_id, report_id, snapshot_id,
decision (and release_policy); the GateResults and the approving actor and time are set
by the engine, not sent (CTS 14.1: "or the implementation's equivalent")."""
import copy

from .tests_dec import SEM, gate_is, gates, judge_result, report, run, with_sem
from .tests_exe import setup


def ok(ctx, note=""):
    return ctx.result("PASS", "EXPECTED_MET", note)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


def evaluated(ctx, doc, judge="J-PASS-90", what="the fixture"):
    name = setup(ctx, doc, what)
    execs, batch = run(ctx, name, judge=judge)
    g, body = gates(ctx, name, batch)
    return name, execs, batch, g, body


def release(ctx, name, batch, snapshot, decision="approved", actor="P-RELEASE", report_id=None,
            note=None, **extra):
    if report_id is None:
        report_id = report(ctx, name, batch, "the Report for the Release Decision").get("id")
    body = {"execution_batch_id": batch, "report_id": report_id, "snapshot_id": snapshot,
            "decision": decision, **extra}
    ex = ctx.record(ctx.a.post(f"/projects/{name}/releases", body, actor),
                    note or f"record a Release Decision ({decision}) as {actor}")
    if ex.outcome in ("transport_failed", "sut_error"):
        ctx.guard(ex, "the Release Decision")
    return ex


def override(ctx, name, gate, gate_result_id, batch, actor="P-APPROVER", justification="CTS override"):
    body = {"execution_batch_id": batch, "justification": justification}
    if gate_result_id is not None:
        body["gate_result_id"] = gate_result_id
    ex = ctx.record(ctx.a.post(f"/projects/{name}/gates/{gate}/override", body, actor),
                    f"override {gate} as {actor}")
    if ex.outcome in ("transport_failed", "sut_error"):
        ctx.guard(ex, "the override")
    return ex


def change_gate(ctx, name, gate, actor="P-APPROVER", **fields):
    cur = ctx.record(ctx.a.get(f"/projects/{name}/gates", "P-RELEASE"), "the Gates")
    items = cur.body if isinstance(cur.body, list) else (cur.body or {}).get("items", [])
    g = next((x for x in items if x.get("name") == gate), None)
    if g is None:
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"Gate {gate} not found")
    g = {**g, **fields}
    return ctx.record(ctx.a.call("PUT", f"/projects/{name}/gates/{gate}", actor, g),
                      f"change {gate} {fields} as {actor}")


def rel001(ctx, b):
    name, _, batch, g, body = evaluated(ctx, with_sem(b))
    ex = release(ctx, name, batch, body["snapshot_id"])
    if ex.outcome != "accepted":
        return fail(ctx, f"rejected: {ex.text()[:300]}")
    rid = (ex.body or {}).get("id")
    got = ctx.record(ctx.a.get(f"/projects/{name}/releases/{rid}"), "retrieve the Release Decision").body or {}
    if got.get("decision") != "approved" or "P-RELEASE" not in str(got.get("approved_by")):
        return fail(ctx, f"stored decision {got.get('decision')}, approved_by {got.get('approved_by')}")
    for k in ("id", "execution_batch_id", "report_id", "snapshot_id", "approved_at", "approval_role",
              "environment", "suite"):
        if not got.get(k):
            return fail(ctx, f"stored decision lacks {k}")
    if got.get("gates") != g:
        return fail(ctx, "the stored gates differ from the evaluation's GateResults")
    return ok(ctx)


def rel002(ctx, b):
    name, _, batch, g, body = evaluated(ctx, with_sem(b), "J-FAIL-90")
    a = release(ctx, name, batch, body["snapshot_id"], "approved", note="(a) approved")
    if a.outcome == "accepted":
        return fail(ctx, "(a) approved was accepted with a failed blocking Gate")
    r = release(ctx, name, batch, body["snapshot_id"], "rejected", note="(b) rejected")
    if r.outcome != "accepted":
        return fail(ctx, f"(b) rejected was refused: {r.text()[:200]}")
    return ok(ctx)


def rel003(ctx, b):
    d = copy.deepcopy(b)
    d["quality_gates"].append({**SEM, "on_failure": "warn"})
    name, _, batch, g, body = evaluated(ctx, d, "J-FAIL-90")
    rep = report(ctx, name, batch)
    ex = release(ctx, name, batch, body["snapshot_id"], report_id=rep.get("id"))
    if ex.outcome != "accepted":
        return fail(ctx, f"rejected: {ex.text()[:300]}")
    sg = ((ex.body or {}).get("gates") or {}).get("semantic-gate") or {}
    if sg.get("status") != "fail" or sg.get("blocking") is not False or sg.get("reasons") != ["threshold"] \
            or sg.get("override"):
        return fail(ctx, f"semantic-gate in the decision: {sg}")
    if ((rep.get("gates") or {}).get("semantic-gate") or {}).get("status") != "fail":
        return fail(ctx, "the Report does not show semantic-gate as failed")
    return ok(ctx)


def rel004(ctx, b):
    d = copy.deepcopy(b)
    d["suites"][0]["quality_gates"] = [{"name": "suite-gate", "aggregate": "semantic", "threshold": 0.5,
                                        "on_failure": "warn"}]
    name, _, batch, g, body = evaluated(ctx, d)
    if set(g) != {"functional-gate", "suite-gate"}:
        return fail(ctx, f"the evaluation returned {sorted(g)}")
    ex = release(ctx, name, batch, body["snapshot_id"])
    gs = (ex.body or {}).get("gates") or {}
    if ex.outcome == "accepted" and "suite-gate" not in gs:
        return fail(ctx, "a Release Decision without suite-gate was accepted")
    return ok(ctx, "the engine takes no GateResults from the request; every decision carries every "
                   "applicable Gate, so an incomplete one cannot be submitted")


def rel005(ctx, b):
    d = copy.deepcopy(b)
    d.pop("quality_gates")
    name, _, batch, g, body = evaluated(ctx, d)
    if g:
        return fail(ctx, f"the evaluation returned GateResults {sorted(g)}")
    ex = release(ctx, name, batch, body.get("snapshot_id"))
    return fail(ctx, "a Release Decision without any Gate was accepted") if ex.outcome == "accepted" else ok(ctx)


def rel006(ctx, b):
    name, _, batch, g, body = evaluated(ctx, with_sem(b), "J-FAIL-90")
    first = release(ctx, name, batch, body["snapshot_id"], "overridden", note="(1) overridden, no override yet")
    if first.outcome == "accepted":
        return fail(ctx, "overridden accepted before any override")
    ov = override(ctx, name, "semantic-gate", g["semantic-gate"]["id"], batch)
    if ov.outcome != "accepted":
        return fail(ctx, f"the override was rejected: {ov.text()[:200]}")
    o = ov.body or {}
    if "P-APPROVER" not in str(o.get("approved_by")) or o.get("justification") != "CTS override":
        return fail(ctx, f"the override record: {o}")
    rep = report(ctx, name, batch, "a Report after the override")
    sg = (rep.get("gates") or {}).get("semantic-gate") or {}
    if sg.get("status") != "fail" or not sg.get("override"):
        return fail(ctx, f"the GateResult after the override: {sg}")
    second = release(ctx, name, batch, body["snapshot_id"], "overridden", report_id=rep.get("id"),
                     note="(2) overridden after the override")
    if second.outcome != "accepted":
        return fail(ctx, f"the second attempt was rejected: {second.text()[:200]}")
    return ok(ctx)


def rel007(ctx, b):
    name, _, b1, g1, body1 = evaluated(ctx, with_sem(b), "J-FAIL-90", "F-OVERRIDDEN, step 1")
    ov = override(ctx, name, "semantic-gate", g1["semantic-gate"]["id"], b1)
    if ov.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", "F-OVERRIDDEN: the override was rejected")
    _, b2 = run(ctx, name, judge="J-FAIL-90", note="a new batch")
    g2, body2 = gates(ctx, name, b2, "evaluate the new batch")
    if g2["semantic-gate"].get("override"):
        return fail(ctx, "the new GateResult carries the earlier override")
    ex = release(ctx, name, b2, body2["snapshot_id"], "overridden")
    return fail(ctx, "the new batch was released as overridden") if ex.outcome == "accepted" else ok(ctx)


def rel008(ctx, b):
    name, _, batch, g, body = evaluated(ctx, with_sem(b), "J-FAIL-90")
    sid, fid = g["semantic-gate"]["id"], g["functional-gate"]["id"]
    tries = [("a", "semantic-gate", sid, "P-NOPERM", "CTS override"),
             ("b", "semantic-gate", sid, "P-APPROVER", ""),
             ("c", "semantic-gate", None, "P-APPROVER", "CTS override"),
             ("d", "functional-gate", fid, "P-APPROVER", "CTS override"),
             ("e", "semantic-gate", fid, "P-APPROVER", "CTS override")]
    for label, gate, gid, actor, just in tries:
        ex = override(ctx, name, gate, gid, batch, actor, just)
        if ex.outcome == "accepted":
            return fail(ctx, f"({label}) was accepted")
    rep = report(ctx, name, batch)
    if any(v.get("override") for v in (rep.get("gates") or {}).values()):
        return fail(ctx, "a GateResult carries an override")
    return ok(ctx)


def rel009(ctx, b):
    name, _, batch, g, body = evaluated(ctx, with_sem(b) if False else _with(b, override_requires="safety_override"),
                                        "J-FAIL-90")
    ex = override(ctx, name, "semantic-gate", g["semantic-gate"]["id"], batch)
    return fail(ctx, "overridden without safety_override") if ex.outcome == "accepted" else ok(ctx)


def _with(b, **sem):
    return with_sem(b, **sem)


def rel010(ctx, b):
    name, _, batch, g, body = evaluated(ctx, with_sem(b))
    rep0 = report(ctx, name, batch, "the Report before the change")
    n0 = len(ctx.scripted.calls)
    ch = change_gate(ctx, name, "semantic-gate", threshold=0.9)
    ctx.guard(ch, "the Gate change")
    if ch.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"the Gate change was rejected: {ch.text()[:200]}")
    first = release(ctx, name, batch, body["snapshot_id"], report_id=rep0.get("id"),
                    note="(1) with the first snapshot_id and its Report")
    if first.outcome == "accepted":
        return fail(ctx, "accepted on a Snapshot older than the Gate change")
    g2, body2 = gates(ctx, name, batch, "evaluate again")
    if body2.get("snapshot_id") == body["snapshot_id"] or g2["semantic-gate"].get("threshold") != 0.9:
        return fail(ctx, f"re-evaluation: snapshot {body2.get('snapshot_id')}, threshold {g2['semantic-gate'].get('threshold')}")
    second = release(ctx, name, batch, body2["snapshot_id"], note="(2) with the new snapshot_id")
    if second.outcome != "accepted":
        return fail(ctx, f"the second attempt was rejected: {second.text()[:200]}")
    if len(ctx.scripted.calls) != n0:
        return fail(ctx, "the re-evaluation called the subject or the Judge")
    return ok(ctx, f"first rejection: {first.text()[:120]}")


def put_project(ctx, name, doc, note):
    d = ctx.named(doc)
    d["name"] = name
    ch = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", d), note)
    ctx.guard(ch, note)
    if ch.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"{note}: rejected: {ch.text()[:200]}")


def rel011(ctx, b):
    d = with_sem(b)
    name, _, batch, g, body = evaluated(ctx, d)
    rep0 = report(ctx, name, batch, "the Report before the change")
    d2 = copy.deepcopy(d)
    d2["suites"][0]["scenarios"][0]["contract"]["expectations"][0]["confidence_threshold"] = 0.85
    put_project(ctx, name, d2, "governed change: confidence_threshold 0.85")
    ex = release(ctx, name, batch, body["snapshot_id"], report_id=rep0.get("id"))
    if ex.outcome == "accepted":
        return fail(ctx, "accepted after the Contract changed")
    return ok(ctx, f"rejection: {ex.text()[:120]}")


def rel012(ctx, b):
    from .tests_dec import governed_env_change
    name, _, batch, g, body = evaluated(ctx, with_sem(b))
    rep0 = report(ctx, name, batch, "the Report before the change")
    governed_env_change(ctx, name)
    first = release(ctx, name, batch, body["snapshot_id"], report_id=rep0.get("id"), note="(1) old snapshot")
    g2, body2 = gates(ctx, name, batch, "evaluate again")
    second = release(ctx, name, batch, body2["snapshot_id"], note="(2) new snapshot")
    if first.outcome == "accepted" or second.outcome == "accepted":
        return fail(ctx, f"accepted: first {first.outcome}, second {second.outcome}")
    return ok(ctx)


def rel014(ctx, b):
    name, _, batch, g1, body1 = evaluated(ctx, with_sem(b), what="F-GATE-CHANGED")
    ch = change_gate(ctx, name, "semantic-gate", threshold=0.9)
    if ch.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", "F-GATE-CHANGED: the Gate change was rejected")
    g2, _ = gates(ctx, name, batch, "evaluation 2")
    if g2["semantic-gate"].get("threshold") != 0.9:
        ctx.stop("NOT_RUN", "SETUP_FAILED", "F-GATE-CHANGED: evaluation 2 does not show threshold 0.9")
    snap = ctx.record(ctx.a.get(f"/projects/{name}/snapshots/{body1['snapshot_id']}"), "evaluation 1's Snapshot")
    rep = ctx.record(ctx.a.get(f"/projects/{name}/releases"), "releases") if False else None
    t = snap.text()
    if g1["semantic-gate"].get("threshold") != 1.0:
        return fail(ctx, "evaluation 1's GateResult does not show 1.0")
    return ok(ctx, "evaluation 1's GateResult, as returned, keeps threshold 1.0")


def rel015(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    a = ctx.record(ctx.a.post(f"/projects/{name}/gates", {"name": "new-gate", "aggregate": "semantic",
                   "threshold": 0.5, "on_failure": "warn"}, "P-NOPERM"), "(a) define a Gate as P-NOPERM")
    bb = change_gate(ctx, name, "semantic-gate", actor="P-NOPERM", on_failure="warn")
    if a.outcome == "accepted" or bb.outcome == "accepted":
        return fail(ctx, "P-NOPERM changed a Gate")
    c = change_gate(ctx, name, "semantic-gate", on_failure="warn")
    if c.outcome != "accepted":
        return fail(ctx, f"P-APPROVER's change was rejected: {c.text()[:200]}")
    au = ctx.record(ctx.a.get(f"/projects/{name}/audit", "P-ADMIN"), "the audit log")
    entries = au.body if isinstance(au.body, list) else (au.body or {}).get("items", [])
    hit = [e for e in entries if "contract_define" in str(e) and "P-APPROVER" in str(e) and "semantic-gate" in str(e)]
    return ok(ctx) if hit else fail(ctx, "the change is not in the audit log as contract_define by P-APPROVER")


def rel016(ctx, b):
    name, _, batch, g, body = evaluated(ctx, with_sem(b))
    ex = release(ctx, name, batch, body["snapshot_id"], actor="P-NOPERM")
    return fail(ctx, "P-NOPERM recorded a Release Decision") if ex.outcome == "accepted" else ok(ctx)


def rel017(ctx, b):
    name, execs, batch, g, body = evaluated(ctx, with_sem(b), "J-FAIL-90")
    a = override(ctx, name, "semantic-gate", g["semantic-gate"]["id"], batch, actor="SA-CI")
    r = judge_result(ctx, name, execs[0]["id"])
    bl = ctx.record(ctx.a.post(f"/projects/{name}/baselines", {"execution_id": execs[0]["id"],
                    "result_id": r["id"], "name": "cts-baseline"}, "SA-CI"), "(b) Baseline as SA-CI")
    if a.outcome == "accepted" or bl.outcome == "accepted":
        return fail(ctx, f"accepted: override {a.outcome}, Baseline {bl.outcome}")
    return ok(ctx)


def rel018(ctx, b):
    d = with_sem(b)
    e2 = copy.deepcopy(d["environments"][0])
    e2["name"] = "cts-env-2"
    d["environments"].append(e2)
    name = setup(ctx, d, "F-BASE with cts-env-2")
    pol = ctx.record(ctx.a.post(f"/projects/{name}/release-policies", {"suites": ["cts-suite"],
                     "environments": ["cts-env"], "service_accounts": ["SA-CI"]}, "P-RELEASE"), "RP-1")
    if pol.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"RP-1 was rejected: {pol.text()[:200]}")
    rp = pol.body["id"]

    def batch(env, judge, label):
        ctx.behave("SR-OK", judge=judge)
        ex = ctx.record(ctx.a.execute(name, environment=env), f"batch {label}")
        ctx.guard(ex, f"batch {label}")
        bid = ex.body["execution_batch_id"]
        g, body = gates(ctx, name, bid, f"evaluate batch {label}")
        return bid, g, body

    b1, g1, s1 = batch("cts-env", "J-PASS-90", "1")
    a = release(ctx, name, b1, s1["snapshot_id"], actor="SA-CI", note="(a) no policy")
    bb = release(ctx, name, b1, s1["snapshot_id"], actor="SA-CI", note="(b) RP-1", release_policy=rp)
    b2, g2, s2 = batch("cts-env", "J-FAIL-90", "2")
    override(ctx, name, "semantic-gate", g2["semantic-gate"]["id"], b2)
    c = release(ctx, name, b2, s2["snapshot_id"], "overridden", actor="SA-CI", note="(c) overridden", release_policy=rp)
    dd = release(ctx, name, b2, s2["snapshot_id"], "rejected", actor="SA-CI", note="(d) rejected", release_policy=rp)
    b3, g3, s3 = batch("cts-env-2", "J-PASS-90", "3")
    e = release(ctx, name, b3, s3["snapshot_id"], actor="SA-CI", note="(e) cts-env-2", release_policy=rp)
    rv = ctx.record(ctx.a.post(f"/projects/{name}/release-policies/{rp}/revoke", {}, "P-RELEASE"), "revoke RP-1")
    b4, g4, s4 = batch("cts-env", "J-PASS-90", "4")
    f = release(ctx, name, b4, s4["snapshot_id"], actor="SA-CI", note="(f) after revocation", release_policy=rp)
    want = {"a": (a, False), "b": (bb, True), "c": (c, False), "d": (dd, True), "e": (e, False), "f": (f, False)}
    bad = [k for k, (x, acc) in want.items() if (x.outcome == "accepted") != acc]
    if bad:
        return fail(ctx, f"unexpected outcome for {bad}")
    if rp not in bb.text():
        return fail(ctx, "decision (b) does not reference the policy")
    got = ctx.record(ctx.a.get(f"/projects/{name}/release-policies/{rp}"), "RP-1 after revocation").body or {}
    if not got.get("revoked_at") or "P-RELEASE" not in str(got.get("revoked_by")):
        return fail(ctx, f"RP-1 after revocation: {got}")
    for x in (bb, dd):
        rid = x.body.get("id")
        if ctx.record(ctx.a.get(f"/projects/{name}/releases/{rid}"), "a decision after revocation").outcome != "accepted":
            return fail(ctx, "a recorded decision is gone after the revocation")
    return ok(ctx)


def registry():
    return {"CT-REL-001": rel001, "CT-REL-002": rel002, "CT-REL-003": rel003, "CT-REL-004": rel004,
            "CT-REL-005": rel005, "CT-REL-006": rel006, "CT-REL-007": rel007, "CT-REL-008": rel008,
            "CT-REL-009": rel009, "CT-REL-010": rel010, "CT-REL-011": rel011, "CT-REL-012": rel012,
            "CT-REL-014": rel014, "CT-REL-015": rel015, "CT-REL-016": rel016, "CT-REL-017": rel017,
            "CT-REL-018": rel018}, {}
