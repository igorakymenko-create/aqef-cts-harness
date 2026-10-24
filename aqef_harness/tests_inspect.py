"""Evidence collection for the Inspection and Declaration tests (CTS 1.8). Each collector
carries out the test's Fixture and Action and records every exchange; the outcome stays
NOT_RUN / MANUAL_REVIEW_PENDING until a named reviewer decides it."""
from .tests_dec import gates, multi, report, run, with_sem
from .tests_exe import f_multi, setup
from .tests_rel import override, release


import json

CODES = {"PASS": "EXPECTED_MET", "FAIL": "EXPECTED_VIOLATED", "NOT_APPLICABLE": "OPTIONAL_FEATURE_ABSENT"}


def pending(ctx, what):
    path = ctx.a.cfg.manual_reviews
    recs = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else []
    rec = next((r for r in recs if r.get("case_id") == ctx.case_id), None)
    if rec is None or rec.get("decision") not in CODES:
        return ctx.result("NOT_RUN", "MANUAL_REVIEW_PENDING", f"{what}; evidence collected for review (CTS 1.8)")
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"manual_review": rec}))
    who = (rec.get("reviewer") or {}).get("id")
    return ctx.result(rec["decision"], CODES[rec["decision"]],
                      f"review {rec.get('review_id')} by {who}: {rec.get('note', '')[:200]}")


def get(ctx, path, note, actor="P-RELEASE"):
    return ctx.record(ctx.a.get(path, actor), note).body


def asm017(ctx, b):
    name = setup(ctx, b, "F-BASE, a Project to register in")
    for label, rule in (("judge", {"operation": "judge", "model": "cts-scripted-judge@1",
                                   "criteria": "The response greets the user."}),
                        ("http", {"operation": "http", "url": "http://127.0.0.1:9100/judge"})):
        ctx.record(ctx.a.post(f"/projects/{name}/validators",
                              {"name": f"cts-model-{label}", "version": "1", "rule": rule}, "P-APPROVER"),
                   f"register a Custom Validator whose check calls a model ({label})")
    return pending(ctx, "Inspection")


def dec021(ctx, b):
    for label, d, kw in (("a", multi(b), {}),
                         ("b", multi(b, min_basis={"results": 3}),
                          {"judge_map": {"One": "J-FAIL-90", "Two": "J-PASS-60", "Three": "J-PASS-90"}})):
        ex, name = ctx.load(d, f"({label}) CT-DEC-00{'2' if label == 'a' else '8'}'s configuration", suffix=label)
        _, batch = run(ctx, name, "SR-ECHO", note=f"({label}) execute", **kw)
        gates(ctx, name, batch, f"({label}) evaluate the Gates")
        report(ctx, name, batch, f"({label}) the Report")
    return pending(ctx, "Inspection")


def exe009(ctx, b):
    name = setup(ctx, f_multi(b), "F-MULTI")
    execs, batch = run(ctx, name, "SR-ECHO", note="execute cts-suite")
    get(ctx, f"/projects/{name}/executions", "the Executions, listed")
    for e in execs:
        get(ctx, f"/projects/{name}/executions/{e['id']}", f"Execution {e.get('scenario')}")
    get(ctx, f"/projects/{name}/audit", "the audit log", "P-ADMIN")
    return pending(ctx, "Inspection")


def rel023(ctx, b):
    name = setup(ctx, with_sem(b), "F-OVERRIDDEN: F-BASE with semantic-gate")
    execs, batch = run(ctx, name, judge="J-FAIL-90", note="F-OVERRIDDEN: execute")
    g, body = gates(ctx, name, batch, "F-OVERRIDDEN: evaluate the Gates")
    override(ctx, name, "semantic-gate", g["semantic-gate"]["id"], batch)
    rel = release(ctx, name, batch, body["snapshot_id"], "overridden", note="F-OVERRIDDEN: the Release Decision")
    did = (rel.body or {}).get("id")
    d = get(ctx, f"/projects/{name}/releases/{did}", "trace 1: the Release Decision") or {}
    get(ctx, f"/projects/{name}/reports/{d.get('report_id')}", "trace 2: its Report")
    get(ctx, f"/projects/{name}/snapshots/{d.get('snapshot_id')}", "trace 3: its Snapshot")
    get(ctx, f"/projects/{name}/approvals", "trace 4: Approval records (override, decision)", "P-ADMIN")
    get(ctx, f"/projects/{name}/audit", "trace 4: the audit log", "P-ADMIN")
    for e in execs:
        get(ctx, f"/projects/{name}/executions/{e['id']}/results", f"trace 5: Results of {e.get('scenario')}")
        get(ctx, f"/projects/{name}/executions/{e['id']}", f"trace 6: Execution {e.get('scenario')}")
        get(ctx, f"/projects/{name}/executions/{e['id']}/conversation", f"trace 7: Conversation of {e.get('scenario')}")
    return pending(ctx, "Inspection")


def rel036(ctx, b):
    d = with_sem(f_multi(b))
    d["execution"] = {"scheduling": "sequential", "retry": {"max_attempts": 2, "on": "infrastructure_failure"}}
    name = setup(ctx, d, "F-SIGNALS: CT-REL-035's configuration")
    ctx.behave("SR-ECHO", subject_by_prompt={"One": "SR-503-THEN-ECHO"},
               judge_map={"One": "J-PASS-60", "Two": "J-PASS-60", "Three": "J-PASS-90"})
    execs, body = ctx.execute(name, "F-SIGNALS: execute")
    batch = body.get("execution_batch_id")
    gates(ctx, name, batch, "F-SIGNALS: evaluate the Gates")
    rep = report(ctx, name, batch, "the Report, with its metrics")
    get(ctx, f"/projects/{name}/reports/{rep.get('id')}", "the Report, retrieved")
    for e in execs:
        get(ctx, f"/projects/{name}/executions/{e['id']}/results", f"Results of {e.get('scenario')}")
    return pending(ctx, "Inspection")


def nothing(what):
    return lambda ctx, b: pending(ctx, what)


def registry():
    return {"CT-ASM-010": nothing("Declaration: documentation only"), "CT-ASM-017": asm017,
            "CT-DEC-009": nothing("Inspection: documentation only"), "CT-DEC-021": dec021,
            "CT-EXE-009": exe009, "CT-REL-023": rel023,
            "CT-REL-027": nothing("Inspection: the published statement"), "CT-REL-036": rel036}, {}
