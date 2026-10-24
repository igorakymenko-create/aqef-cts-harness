"""CTS Sections 20 (Human Review), 21 (Multi Judge), 22 (Seeded Controls), and the
scoped tests of Section 13 (CT-DEC-010 to 012, 015 to 018), CT-ASM-013, CT-ADM-006."""
import copy
import json
import time

from . import fixtures as F
from .tests_adm import adm_pass, post as adm_post
from .tests_dec import SEM, basis_is, gate_is, gates, report, run, with_sem
from .tests_exe import setup

S0 = "suites[0].scenarios[0]"
EXP = f"{S0}.contract.expectations[0]"


def ok(ctx, note=""):
    return ctx.result("PASS", "EXPECTED_MET", note)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


# ---------------------------------------------------------------- fixtures
def f_hr(b, **hr):
    d = with_sem(b)
    e = d["suites"][0]["scenarios"][0]["contract"]["expectations"][0]
    e.pop("judge"), e.pop("confidence_threshold")
    e["human_reviewer"] = {"role": "reviewer", **hr}
    return d


PANEL = {"purpose": "independence",
         "judges": [{"model": f"cts-scripted-judge-{x}@1", "confidence_source": "self_rating"} for x in "abc"],
         "consensus": {"method": "voting", "threshold": "majority", "on_disagreement": "fail"}}


def f_panel(b, **sem):
    d = with_sem(b, **sem)
    e = d["suites"][0]["scenarios"][0]["contract"]["expectations"][0]
    e.pop("judge")
    e["multi_judge"] = copy.deepcopy(PANEL)
    return d


def control_expectation():
    return {"criteria": "The response greets the user.", "defect_classes": ["greeting-missing"],
            "judge": {"model": "cts-scripted-judge@1", "confidence_source": "self_rating"},
            "confidence_threshold": 0.8}


def f_seed(b):
    return with_sem(F.f_seed(b))


def f_seed_v(b):
    """CTS 22, F-SEED-V (as corrected in WD8)."""
    d = f_seed(b)
    c = d["suites"][0]["scenarios"][1]
    c.pop("evidence")
    c["seeded_control"] = {"defect_class": "greeting-missing", "planted_defect": "The response does not greet the user.",
                           "confirmed_by": "validator",
                           "confirmation": {"validator": "schema", "target": "response",
                                            "expected": {"type": "string", "pattern": "Goodbye"}}}
    c["variables"], c["prompt"] = {"query": "Hello"}, {"template": "{{query}}"}
    return d


def f_clean(b, text="Hi there! What do you need?", name="s-clean"):
    """CTS 22, F-CLEAN."""
    d = f_seed(b)
    d["suites"][0]["scenarios"][1] = {
        "name": name,
        "seeded_control": {"kind": "clean", "defect_class": "greeting-missing", "confirmed_by": "construction"},
        "evidence": {"conversation": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": text}]},
        "contract": {"expectations": [control_expectation()]}}
    return d


def f_clean_v(b):
    """CTS 22, F-CLEAN-V."""
    d = f_clean(b)
    c = d["suites"][0]["scenarios"][1]
    c.pop("evidence")
    c["seeded_control"] = {"kind": "clean", "defect_class": "greeting-missing", "confirmed_by": "validator",
                           "confirmation": {"validator": "forbidden-content", "target": "response",
                                            "expected": {"patterns": [{"regex": "Goodbye"}]}}}
    c["variables"], c["prompt"] = {"query": "Hello"}, {"template": "{{query}}"}
    return d


# ---------------------------------------------------------------- helpers
def by_scn(execs, scn):
    return next((e for e in execs if e.get("scenario") == scn), None)


def results(ctx, name, eid, note="retrieve the Results"):
    return ctx.results(name, eid, note)


def one_expectation(ctx, name, eid, kinds=("judge", "human_reviewer")):
    rs = [r for r in results(ctx, name, eid) if r.get("oracle_type") in kinds]
    eff = [r for r in rs if not any(x.get("resolves") == r["id"] for x in rs)]
    if len(eff) != 1:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{len(eff)} effective Expectation Results")
    return eff[0], rs


def scr(ctx, name, eid, scenario):
    g = ctx.record(ctx.a.get(f"/projects/{name}/executions/{eid}"), "the Execution record")
    for e in (g.body or {}).get("seeded_control_results") or []:
        if e.get("scenario") == scenario:
            return e
    ctx.stop("FAIL", "EXPECTED_VIOLATED", f"no seeded_control_results entry for {scenario}")


def review(ctx, name, eid, rid, actor, verdict="pass", confidence=None, note=None):
    body = {"verdict": verdict, "supporting_evidence": {"reason": "CTS review"}}
    if confidence is not None:
        body["confidence"] = confidence
    ex = ctx.record(ctx.a.post(f"/projects/{name}/executions/{eid}/results/{rid}/review", body, actor),
                    note or f"review as {actor}")
    if ex.outcome in ("transport_failed", "sut_error"):
        ctx.guard(ex, "the review")
    return ex


def loads_rejected(start, variants):
    def t(ctx, b):
        s = start(b)
        ctx.control(s)
        for label, mut in variants:
            ex, _ = ctx.load(mut(copy.deepcopy(s)), f"variant {label}", suffix=label)
            if ex.outcome == "accepted":
                return fail(ctx, f"variant {label} was loaded")
        return ok(ctx)
    return t


def exp_of(d, i=0):
    return d["suites"][0]["scenarios"][i]["contract"]["expectations"][0]


def mutate(fn):
    def m(d):
        fn(d)
        return d
    return m


# ---------------------------------------------------------------- 20 Human Review
def hrv002(ctx, b):
    name = setup(ctx, f_hr(b), "F-HR")
    execs, batch = run(ctx, name)
    eid = execs[0]["id"]
    r, _ = one_expectation(ctx, name, eid)
    if r.get("disposition") != "awaiting_review":
        return fail(ctx, f"the pending Result is {r.get('disposition')}")
    x = review(ctx, name, eid, r["id"], "P-REVIEWER-2")
    if x.outcome == "accepted":
        return fail(ctx, "P-REVIEWER-2 (no Role reviewer) completed the review")
    r1, all1 = one_expectation(ctx, name, eid)
    if r1 != r or len(all1) != 1:
        return fail(ctx, "the rejected review changed the Results")
    y = review(ctx, name, eid, r["id"], "P-REVIEWER")
    if y.outcome != "accepted":
        return fail(ctx, f"P-REVIEWER was refused: {y.text()[:200]}")
    r2, all2 = one_expectation(ctx, name, eid)
    if r2["id"] != r["id"] or r2.get("verdict") != "pass" or r2.get("disposition") != "actionable" \
            or len(all2) != 1 or "P-REVIEWER" not in json.dumps(r2.get("supporting_evidence")) \
            or "P-REVIEWER-2" in json.dumps(r2.get("supporting_evidence")):
        return fail(ctx, f"after the review: {r2}")
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "semantic-gate", "pass")
    return ok(ctx)


def wait_for(ctx, fn, budget=15.0, step=0.5):
    t0 = time.time()
    while time.time() - t0 < budget:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return None


def hrv003(ctx, b):
    name = setup(ctx, f_hr(b, ) if False else _hr_timeout(b), "F-HR, review_timeout 1s")
    execs, batch = run(ctx, name)
    eid = execs[0]["id"]

    def timed_out():
        r, _ = one_expectation(ctx, name, eid)
        return r if (r.get("review_route") or {}).get("state") == "timed_out" else None
    r = wait_for(ctx, timed_out)
    if r is None:
        return ctx.result("NOT_RUN", "BUDGET_EXCEEDED", "the timeout was not recorded within 15 s")
    if r.get("verdict") is not None or r.get("disposition") == "actionable":
        return fail(ctx, f"the timed-out Result: {r}")
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "semantic-gate", "fail", ["non_actionable_results"])
    return ok(ctx, "budget 15 s; review_timeout 1s")


def _hr_timeout(b, **kw):
    d = f_hr(b)
    exp_of(d)["review_timeout"] = "1s"
    exp_of(d).update(kw)
    return d


def hrv004(ctx, b):
    da = f_hr(b, captures_confidence=True)
    exp_of(da)["confidence_threshold"] = 0.8
    db = f_hr(b, captures_confidence=False)
    for label, d, conf, want in (("a", da, 0.6, (0.6, "inconclusive")), ("b", db, None, ("not_applicable", "actionable"))):
        ex, name = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome != "accepted":
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"variant {label} was rejected: {ex.text()[:200]}")
        execs, _ = run(ctx, name, note=f"variant {label}")
        r, _ = one_expectation(ctx, name, execs[0]["id"])
        y = review(ctx, name, execs[0]["id"], r["id"], "P-REVIEWER", confidence=conf, note=f"variant {label}: review")
        if y.outcome != "accepted":
            return fail(ctx, f"variant {label}: review refused: {y.text()[:200]}")
        r2, _ = one_expectation(ctx, name, execs[0]["id"])
        if (r2.get("confidence"), r2.get("disposition")) != want:
            return fail(ctx, f"variant {label}: {r2.get('confidence')}, {r2.get('disposition')}")
    return ok(ctx)


def hrv005(ctx, b):
    d = _hr_timeout(b, on_timeout="escalate", escalate_to="lead")
    exp_of(d)["review_timeout"] = "2s"
    name = setup(ctx, d, "F-HR, escalate to lead after 2s")
    execs, batch = run(ctx, name)
    eid = execs[0]["id"]
    r, _ = one_expectation(ctx, name, eid)
    early = review(ctx, name, eid, r["id"], "P-LEAD", note="P-LEAD before the timeout")
    if early.outcome == "accepted":
        return fail(ctx, "P-LEAD reviewed before escalation")

    def escalated():
        x, _ = one_expectation(ctx, name, eid)
        return x if (x.get("review_route") or {}).get("state") == "escalated" else None
    x = wait_for(ctx, escalated)
    if x is None:
        return ctx.result("NOT_RUN", "BUDGET_EXCEEDED", "the escalation was not recorded within 15 s")
    if x.get("disposition") != "awaiting_review" or x.get("verdict") is not None:
        return fail(ctx, f"after escalation: {x}")
    g, _ = gates(ctx, name, batch, "evaluate after escalation")
    gate_is(ctx, g, "semantic-gate", "fail", ["non_actionable_results"])
    late = review(ctx, name, eid, r["id"], "P-LEAD", note="P-LEAD after escalation")
    if late.outcome != "accepted":
        return fail(ctx, f"P-LEAD refused after escalation: {late.text()[:200]}")
    g2, _ = gates(ctx, name, batch, "evaluate after the review")
    gate_is(ctx, g2, "semantic-gate", "pass")
    return ok(ctx, "review_timeout 2s, so that the early attempt lands before it")


# ---------------------------------------------------------------- 21 Multi Judge
def panel_run(ctx, d, judges, note="execute", **kw):
    name = setup(ctx, d, "the panel fixture") if "name" not in kw else kw.pop("name")
    execs, batch = run(ctx, name, judge_by_model=judges, note=note)
    return name, execs, batch


def mjg005(ctx, b):
    d = f_panel(b)
    name = setup(ctx, d, "F-PANEL")
    out = []
    for label, thr in (("majority", "majority"), ("0.75", 0.75)):
        if label != "majority":
            d2 = ctx.named(d)
            d2["name"] = name
            exp_of(d2)["multi_judge"]["consensus"]["threshold"] = thr
            ch = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", d2), "threshold 0.75")
            if ch.outcome != "accepted":
                return ctx.result("NOT_RUN", "SETUP_FAILED", f"threshold 0.75 rejected: {ch.text()[:200]}")
        execs, _ = run(ctx, name, judge_by_model={"cts-scripted-judge-c@1": "J-FAIL-90"}, note=f"run {label}")
        calls = ctx.judge_log(f"Judge calls, {label}")
        models = sorted(c["request"].get("model") for c in calls)
        if models != [f"cts-scripted-judge-{x}@1" for x in "abc"]:
            return fail(ctx, f"{label}: Judge calls {models}")
        r, _ = one_expectation(ctx, name, execs[0]["id"])
        out.append((r.get("verdict"), r.get("panel")))
    if out[0] != ("pass", {"configured": 3, "counted": 3}) or out[1][0] != "fail":
        return fail(ctx, f"results {out}")
    return ok(ctx)


def mjg006(ctx, b):
    d = f_panel(b)
    mj = exp_of(d)["multi_judge"]
    mj["purpose"] = "stability"
    mj.pop("judges")
    mj["judge"] = {"model": "cts-scripted-judge-a@1", "confidence_source": "self_rating"}
    mj["samples"] = 3
    name = setup(ctx, d, "F-PANEL, stability")
    execs, batch = run(ctx, name)
    calls = [c for c in ctx.judge_log() if c["request"].get("model") == "cts-scripted-judge-a@1"]
    if len(calls) != 3:
        return fail(ctx, f"{len(calls)} calls to judge-a")
    r, _ = one_expectation(ctx, name, execs[0]["id"])
    if r.get("verdict") != "pass" or r.get("panel") != {"configured": 3, "counted": 3}:
        return fail(ctx, f"the Result: {r.get('verdict')}, {r.get('panel')}")
    g, _ = gates(ctx, name, batch)
    basis_is(ctx, gate_is(ctx, g, "semantic-gate", "pass"), {"results": 1})
    return ok(ctx)


def mjg007(ctx, b):
    name = setup(ctx, f_panel(b), "F-PANEL")
    execs, _ = run(ctx, name, judge_by_model={"cts-scripted-judge-c@1": "J-FAIL-90"})
    r, _ = one_expectation(ctx, name, execs[0]["id"])
    se = r.get("supporting_evidence") or {}
    members = se.get("member_results") or []
    confs = [m.get("confidence") for m in members]
    if confs != [0.9, 0.9, 0.9]:
        return fail(ctx, f"members' own Confidence: {confs}")
    if "agreement" in se and se["agreement"] == r.get("confidence"):
        return fail(ctx, "agreement is presented as the Result's Confidence")
    return ok(ctx, f"members keep 0.9 each; agreement reported separately as {se.get('agreement')}; "
                   "the Inspection half is for a reviewer")


def quorum(control_doc, control_name, judges):
    def t(ctx, b):
        out = []
        for label, mq in (("a", None), ("b", 2)):
            d = f_panel(b)
            if mq:
                exp_of(d)["multi_judge"]["consensus"]["min_qualified"] = mq
            ctl = control_doc(b)["suites"][0]["scenarios"][1]
            ctl["contract"]["expectations"][0].pop("judge")
            ctl["contract"]["expectations"][0]["multi_judge"] = copy.deepcopy(exp_of(d)["multi_judge"])
            d["suites"][0]["scenarios"].insert(0, ctl)
            if control_doc is f_clean:
                d["defect_classes"] = [{"name": "greeting-missing"}]
            else:
                d["defect_classes"] = [{"name": "greeting-missing"}]
            d["execution"] = {"scheduling": "sequential"}
            ex, name = ctx.load(d, f"variant {label}", suffix=label)
            if ex.outcome != "accepted":
                return ctx.result("NOT_RUN", "SETUP_FAILED", f"variant {label} rejected: {ex.text()[:200]}")
            execs, _ = run(ctx, name, judge_by_model=judges, note=f"variant {label}")
            e = by_scn(execs, "s-greeting")
            r, _ = one_expectation(ctx, name, e["id"])
            out.append(r)
        a, bb = out
        if a.get("disposition") != "not_assessed" or a.get("verdict") is not None:
            return fail(ctx, f"(a) {a.get('disposition')}, {a.get('verdict')}")
        if bb.get("verdict") != "pass" or bb.get("panel") != {"configured": 3, "counted": 2}:
            return fail(ctx, f"(b) {bb.get('verdict')}, {bb.get('panel')}")
        return ok(ctx)
    return t


def asm013(ctx, b):
    d = with_sem(b)
    e = exp_of(d)
    e.pop("judge")
    e["multi_judge"] = {"purpose": "independence",
                        "judges": [{"model": f"cts-scripted-judge-{x}@1", "confidence_source": "self_rating"} for x in "ab"],
                        "consensus": {"method": "voting", "threshold": "unanimous"}}
    name = setup(ctx, d, "two-Judge panel")
    execs, _ = run(ctx, name)
    models = sorted(c["request"].get("model") for c in ctx.judge_log())
    r, _ = one_expectation(ctx, name, execs[0]["id"])
    if models != ["cts-scripted-judge-a@1", "cts-scripted-judge-b@1"]:
        return fail(ctx, f"Judge calls {models}")
    if r.get("oracle_type") != "judge" or r.get("verdict") != "pass" or r.get("panel") != {"configured": 2, "counted": 2}:
        return fail(ctx, f"the Result {r.get('oracle_type')}, {r.get('verdict')}, {r.get('panel')}")
    return ok(ctx)


def adm006(ctx, b):
    name = setup(ctx, f_panel(b, require_admitted_judges=True), "F-PANEL with gate-admitted")
    execs, batch = run(ctx, name)
    r, _ = one_expectation(ctx, name, execs[0]["id"])
    members = (r.get("supporting_evidence") or {}).get("member_results") or []
    oracles = [m.get("oracle") for m in members]
    if len(set(oracles)) != 3 or None in oracles:
        ctx.setup_status = "failed"
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"member Oracle identities not observable: {oracles}")
    A, B, C = oracles
    steps = [("a", [(A, None), (B, None)], "fail"), ("b", [(C, None)], "pass"),
             ("c", [(B, {"raw_agreement": 0.80, "chance_corrected_agreement": 0.52, "admitted": False})], "fail")]
    for label, recs, want in steps:
        for o, ch in recs:
            ex = adm_post(ctx, name, adm_pass(o, ch), "P-REVIEWER", f"({label}) record")
            if ex.outcome != "accepted":
                return fail(ctx, f"({label}) Admission rejected: {ex.text()[:200]}")
        g, _ = gates(ctx, name, batch, f"({label}) evaluate")
        if want == "pass":
            gate_is(ctx, g, "semantic-gate", "pass")
        else:
            gate_is(ctx, g, "semantic-gate", "fail", ["judge_not_admitted"])
    return ok(ctx, "member identities read from the panel Result's member_results")


# ---------------------------------------------------------------- 22 and 13: Seeded Controls
def seeded(ctx, doc, judge="J-PASS-90", subject="SR-OK", what="the fixture", **kw):
    name = setup(ctx, doc, what)
    execs, batch = run(ctx, name, subject=subject, judge=judge, **kw)
    return name, execs, batch


def sct003(ctx, b):
    d = f_seed_v(b)
    name = setup(ctx, d, "F-SEED-V")
    execs, batch = run(ctx, name, subject="SR-OK", note="run 1, SR-OK")
    e = scr(ctx, name, by_scn(execs, "s-control")["id"], "s-control")
    g, _ = gates(ctx, name, batch, "run 1")
    if e.get("outcome") != "invalid" or e.get("invalidation_scope") != "none":
        return fail(ctx, f"run 1: {e.get('outcome')}, {e.get('invalidation_scope')}")
    gate_is(ctx, g, "semantic-gate", "pass")
    execs2, batch2 = run(ctx, name, subject="SR-OK", subject_by_prompt={}, note="run 2", judge="J-PASS-90")
    return _sct003_run2(ctx, name, b)


def _sct003_run2(ctx, name, b):
    # run 2: SR-BYE for s-control, SR-OK for s-greeting; both prompts are "Hello"
    ctx.behave("SR-OK", judge="J-PASS-90")
    ctx.scripted.subject_by_prompt = {}
    calls_before = len(ctx.scripted.calls)
    # the two Scenarios send the same Prompt; answer the control's call, which runs first
    order = {"n": 0}
    orig = ctx.scripted.handle

    def handle(path, req):
        if path.rstrip("/").endswith("/subject"):
            order["n"] += 1
            ctx.scripted.subject = "SR-BYE" if order["n"] == 1 else "SR-OK"
        return orig(path, req)
    ctx.scripted.handle = handle
    try:
        execs, body = ctx.execute(name, "run 2: SR-BYE for s-control")
    finally:
        ctx.scripted.handle = orig
    ctx.subject_log("run 2 subject calls")
    first = [c for c in ctx.scripted.calls[calls_before:] if c["role"] == "subject"][:1]
    e = scr(ctx, name, by_scn(execs, "s-control")["id"], "s-control")
    g, _ = gates(ctx, name, body.get("execution_batch_id"), "run 2")
    if e.get("outcome") != "missed":
        return fail(ctx, f"run 2: s-control is {e.get('outcome')}; first subject call answered {first}")
    gate_is(ctx, g, "semantic-gate", "fail", ["seeded_control_miss"])
    return ok(ctx, "both Scenarios send 'Hello'; the harness answers the first call (the control, which "
                   "runs first) with SR-BYE")


def dec015(ctx, b):
    name, execs, batch = seeded(ctx, f_seed(b), what="F-SEED")
    e = scr(ctx, name, by_scn(execs, "s-control")["id"], "s-control")
    want = {"defect_class": "greeting-missing", "outcome": "missed", "confirmed_by": "construction",
            "invalidation_scope": "defect_class", "reason": None}
    bad = {k: e.get(k) for k, v in want.items() if e.get(k) != v}
    if bad:
        return fail(ctx, f"the entry: {bad}")
    if len(ctx.subject_log()) != 1:
        return fail(ctx, "the subject was not called exactly once")
    r, _ = one_expectation(ctx, name, by_scn(execs, "s-greeting")["id"])
    if not ((r.get("verdict") == "pass" and r.get("disposition") == "actionable" and r.get("invalidated_by"))
            or (r.get("disposition") == "not_assessed" and r.get("verdict") is None)):
        return fail(ctx, f"s-greeting's Expectation Result: {r}")
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "semantic-gate", "fail", ["seeded_control_miss"])
    gate_is(ctx, g, "functional-gate", "pass")
    return ok(ctx)


def dec016(ctx, b):
    name, execs, batch = seeded(ctx, f_seed(b), judge="J-CATCH", what="F-SEED")
    e = scr(ctx, name, by_scn(execs, "s-control")["id"], "s-control")
    if (e.get("outcome"), e.get("invalidation_scope")) != ("caught", "none"):
        return fail(ctx, f"the entry: {e.get('outcome')}, {e.get('invalidation_scope')}")
    g, _ = gates(ctx, name, batch)
    basis_is(ctx, gate_is(ctx, g, "semantic-gate", "pass"), {"results": 1, "scenarios": 1})
    return ok(ctx)


def dec017(ctx, b, doc=None, judge="J-PASS-90", outcome="missed", reason="seeded_control_miss", ctl="s-control"):
    d = (doc or f_seed)(b)
    d["execution"] = {"on_seeded_control_miss": "halt_run"}
    name, execs, batch = seeded(ctx, d, judge=judge, what="halt_run fixture")
    e = scr(ctx, name, by_scn(execs, ctl)["id"], ctl)
    if e.get("outcome") != outcome or e.get("invalidation_scope") != "full_run" or not e.get("reason"):
        return fail(ctx, f"the entry: {e.get('outcome')}, {e.get('invalidation_scope')}, {e.get('reason')!r}")
    g, _ = gates(ctx, name, batch)
    for n in ("functional-gate", "semantic-gate"):
        r = gate_is(ctx, g, n, "fail", [reason])
        if r.get("value") is None:
            return fail(ctx, f"{n} value is bare null")
    return ok(ctx)


def sct015(ctx, b):
    return dec017(ctx, b, doc=f_clean, judge="J-ALARM", outcome="false_alarm",
                  reason="seeded_control_false_alarm", ctl="s-clean")


def dec018(ctx, b):
    name, execs, batch = seeded(ctx, f_seed(b), what="F-SEED-MISSED")
    eid = by_scn(execs, "s-greeting")["id"]
    r, _ = one_expectation(ctx, name, eid)
    ex = ctx.record(ctx.a.post(f"/projects/{name}/executions/{eid}/results/{r['id']}/reassess",
                               {"oracle": r["oracle"]}, "P-RELEASE"), "reassess with the same Judge")
    if ex.status in (404, 405):
        return ctx.result("FAIL", "REQUIRED_OPERATION_MISSING", "no reassess operation")
    if ex.outcome == "accepted" and (ex.body or {}).get("resolves") == r["id"]:
        return fail(ctx, "the unrequalified Judge resolved the invalidated Result")
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "semantic-gate", "fail", ["seeded_control_miss"])
    return ok(ctx)


def sct007(ctx, b):
    name, execs, batch = seeded(ctx, f_seed(b), what="F-SEED-MISSED")
    ceid = by_scn(execs, "s-control")["id"]
    path = f"/projects/{name}/executions/{ceid}/seeded-controls/s-control/invalidate"
    a = ctx.record(ctx.a.post(path, {"reason": ""}, "P-INVALIDATE"), "(a) empty reason")
    bb = ctx.record(ctx.a.post(path, {"reason": "x"}, "P-NOPERM"), "(b) no Permission")
    c = ctx.record(ctx.a.post(path, {"reason": "Judge prompt changed today"}, "P-INVALIDATE"), "(c)")
    if a.outcome == "accepted" or bb.outcome == "accepted":
        return fail(ctx, "(a) or (b) was accepted")
    if c.outcome != "accepted":
        return fail(ctx, f"(c) was rejected: {c.text()[:200]}")
    e = scr(ctx, name, ceid, "s-control")
    if e.get("invalidation_scope") != "full_run" or e.get("reason") != "Judge prompt changed today":
        return fail(ctx, f"after (c): {e.get('invalidation_scope')}, {e.get('reason')}")
    g, _ = gates(ctx, name, batch)
    gate_is(ctx, g, "semantic-gate", "fail", ["seeded_control_miss"])
    gate_is(ctx, g, "functional-gate", "fail", ["seeded_control_miss"])
    au = ctx.record(ctx.a.get(f"/projects/{name}/audit", "P-ADMIN"), "the audit log")
    if "P-INVALIDATE" not in au.text() or "invalidat" not in au.text():
        return fail(ctx, "(c) is not in the audit log")
    return ok(ctx)


def clean_case(judge, outcome, scope, sem, sem_reasons=(), lacks=()):
    def t(ctx, b):
        name, execs, batch = seeded(ctx, f_clean(b), judge=judge, what="F-CLEAN")
        e = scr(ctx, name, by_scn(execs, "s-clean")["id"], "s-clean")
        if (e.get("kind"), e.get("outcome"), e.get("invalidation_scope"), e.get("reason")) != ("clean", outcome, scope, None):
            return fail(ctx, f"the entry: {e.get('kind')}, {e.get('outcome')}, {e.get('invalidation_scope')}, {e.get('reason')}")
        g, _ = gates(ctx, name, batch)
        r = gate_is(ctx, g, "semantic-gate", sem, sem_reasons, lacks)
        gate_is(ctx, g, "functional-gate", "pass")
        if sem == "pass":
            basis_is(ctx, r, {"results": 1, "scenarios": 1})
            if len(ctx.subject_log()) != 1:
                return fail(ctx, "the subject was not called exactly once")
        return ok(ctx)
    return t


def sct012(ctx, b):
    name = setup(ctx, f_clean_v(b), "F-CLEAN-V")
    out = []
    for label, ctl_behavior in (("1", "SR-BYE"), ("2", "SR-HI")):
        ctx.behave("SR-OK", judge="J-ALARM")
        n = {"i": 0}
        orig = ctx.scripted.handle

        def handle(path, req, beh=ctl_behavior):
            if path.rstrip("/").endswith("/subject"):
                n["i"] += 1
                ctx.scripted.subject = beh if n["i"] == 1 else "SR-OK"
            return orig(path, req)
        ctx.scripted.handle = handle
        try:
            execs, body = ctx.execute(name, f"run {label}: {ctl_behavior} for s-clean")
        finally:
            ctx.scripted.handle = orig
        e = scr(ctx, name, by_scn(execs, "s-clean")["id"], "s-clean")
        g, _ = gates(ctx, name, body.get("execution_batch_id"), f"run {label}")
        out.append((e.get("outcome"), e.get("invalidation_scope"), g["semantic-gate"].get("status"),
                    g["semantic-gate"].get("reasons")))
    if out[0][:3] != ("invalid", "none", "pass"):
        return fail(ctx, f"run 1: {out[0]}")
    if out[1][0] != "false_alarm" or "seeded_control_false_alarm" not in (out[1][3] or []):
        return fail(ctx, f"run 2: {out[1]}")
    return ok(ctx, "the control runs first; the harness answers the first subject call as the control")


def confirm_case(doc, subject, judge, ctl, after_outcome, after_reason):
    def t(ctx, b):
        d = doc(b)
        c = d["suites"][0]["scenarios"][1]
        c["seeded_control"]["confirmed_by"] = "human_reviewer"
        c["seeded_control"].pop("confirmation", None)
        name = setup(ctx, d, "control confirmed by a Human Reviewer")
        ctx.behave("SR-OK", judge=judge)
        n = {"i": 0}
        orig = ctx.scripted.handle

        def handle(path, req):
            if path.rstrip("/").endswith("/subject"):
                n["i"] += 1
                ctx.scripted.subject = subject if n["i"] == 1 else "SR-OK"
            return orig(path, req)
        ctx.scripted.handle = handle
        try:
            execs, body = ctx.execute(name)
        finally:
            ctx.scripted.handle = orig
        batch = body.get("execution_batch_id")
        ceid = by_scn(execs, ctl)["id"]
        e0 = scr(ctx, name, ceid, ctl)
        g1, _ = gates(ctx, name, batch, "evaluation 1")
        if e0.get("outcome") != "invalid":
            return fail(ctx, f"before confirmation: {e0.get('outcome')}")
        gate_is(ctx, g1, "semantic-gate", "pass")
        path = f"/projects/{name}/executions/{ceid}/seeded-controls/{ctl}/confirm"
        body_c = {"confirmed": True, "supporting_evidence": {"reason": "CTS confirmation"}}
        sa = ctx.record(ctx.a.post(path, body_c, "SA-CI"), "confirm as SA-CI")
        pr = ctx.record(ctx.a.post(path, body_c, "P-REVIEWER"), "confirm as P-REVIEWER")
        if sa.outcome == "accepted" or pr.outcome != "accepted":
            return fail(ctx, f"SA-CI {sa.outcome}, P-REVIEWER {pr.outcome}: {pr.text()[:200]}")
        e1 = scr(ctx, name, ceid, ctl)
        g2, _ = gates(ctx, name, batch, "evaluation 2")
        if e1.get("outcome") != after_outcome:
            return fail(ctx, f"after confirmation: {e1.get('outcome')}")
        gate_is(ctx, g2, "semantic-gate", "fail", [after_reason])
        rep = report(ctx, name, batch)
        if g1["semantic-gate"]["id"] == g2["semantic-gate"]["id"]:
            return fail(ctx, "the first GateResult was replaced")
        return ok(ctx)
    return t


def sct008(ctx, b, clean=False):
    """Requalification after a miss (CT-SCT-008), or after a false alarm (CT-SCT-014)."""
    d = f_clean(b) if clean else f_seed(b)
    name = setup(ctx, d, "F-CLEAN with a false alarm" if clean else "F-SEED-MISSED")
    execs, batch = run(ctx, name, judge="J-ALARM" if clean else "J-PASS-90", note="setup run")
    ctl = "s-clean" if clean else "s-control"
    e = scr(ctx, name, by_scn(execs, ctl)["id"], ctl)
    if e.get("outcome") != ("false_alarm" if clean else "missed"):
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"setup check: {ctl} is {e.get('outcome')}")
    geid = by_scn(execs, "s-greeting")["id"]
    old, _ = one_expectation(ctx, name, geid)
    o2 = old["oracle"].replace("cts-scripted-judge@1", "cts-scripted-judge@2")

    def reassess(note):
        return ctx.record(ctx.a.post(f"/projects/{name}/executions/{geid}/results/{old['id']}/reassess",
                                     {"oracle": o2}, "P-RELEASE"), note)
    a = reassess("(a) reassess with @2 before any Requalification")
    if a.outcome == "accepted":
        return fail(ctx, "(a) accepted without a Requalification")
    # (b) run fresh controls against cts-scripted-judge@2
    d2 = ctx.named(d)
    d2["name"] = name
    scns = d2["suites"][0]["scenarios"]
    fresh_defect = copy.deepcopy(f_seed(b)["suites"][0]["scenarios"][1])
    fresh_defect["name"] = "s-control-2"
    fresh_defect["evidence"]["conversation"][1]["content"] = "Bye now."
    fresh_clean = copy.deepcopy(f_clean(b)["suites"][0]["scenarios"][1])
    fresh_clean["name"] = "s-clean-2"
    fresh_clean["evidence"]["conversation"][1]["content"] = "Hello, what can I do for you?"
    scns.append(fresh_defect)
    if clean:
        scns.append(fresh_clean)
    for s in scns[1:]:
        s["contract"]["expectations"][0]["judge"]["model"] = "cts-scripted-judge@2"
    d2["suites"].append({"name": "requal-suite", "scenarios": scns[1:]})
    d2["suites"][0]["scenarios"] = scns[:1] + scns[1:2]
    ch = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", ctx.a.to_engine_form(d2)),
                    "add the fresh controls, bound to cts-scripted-judge@2")
    if ch.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"the change was rejected: {ch.text()[:300]}")
    ctx.behave("SR-OK", judge="J-CATCH")
    ex = ctx.record(ctx.a.execute(name, suite="requal-suite"), "(b) run the fresh controls against @2")
    ctx.guard(ex, "(b)")
    if ex.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"(b) rejected: {ex.text()[:300]}")
    rexecs = ex.body["executions"]

    def ctl_result(s):
        r, _ = one_expectation(ctx, name, by_scn(rexecs, s)["id"])
        return r
    ids = {s: ctl_result(s)["id"] for s in [x["name"] for x in scns[1:]]}

    def requal(controls, note):
        return ctx.record(ctx.a.post(f"/projects/{name}/requalifications",
                                     {"oracle": o2, "defect_class": "greeting-missing", "controls": controls,
                                      "diagnosis": "CTS: corrected Judge configuration"}, "P-RELEASE"), note)
    if clean:
        b1 = requal([ids["s-control-2"]], "(b) defect control only")
        if b1.outcome != "accepted":
            return fail(ctx, f"(b) rejected: {b1.text()[:200]}")
        c = reassess("(c) reassess after a defect-only Requalification")
        if c.outcome == "accepted":
            return fail(ctx, "(c) accepted: a false alarm needs passed clean controls")
        dd = requal([ids["s-clean"]], "(d) the control that raised the false alarm")
        if dd.outcome == "accepted":
            return fail(ctx, "(d) accepted: s-clean raised the false alarm in the run")
        ee = requal([ids["s-clean-2"]], "(e) fresh clean control")
        if ee.outcome != "accepted":
            return fail(ctx, f"(e) rejected: {ee.text()[:200]}")
    else:
        cc = requal([ids["s-control"]], "(c) the missed control")
        if cc.outcome == "accepted":
            return fail(ctx, "(c) accepted: s-control was missed in the run")
        dd = requal([ids["s-control-2"]], "(d) fresh control")
        if dd.outcome != "accepted":
            return fail(ctx, f"(d) rejected: {dd.text()[:200]}")
    n0 = len(ctx.scripted.subject_calls())
    f = reassess("reassess after Requalification")
    if f.outcome != "accepted":
        return fail(ctx, f"the final reassess was rejected: {f.text()[:200]}")
    nb = f.body or {}
    if nb.get("resolves") != old["id"] or nb.get("verdict") != "pass":
        return fail(ctx, f"the new Result: {nb}")
    if len(ctx.scripted.subject_calls()) != n0:
        return fail(ctx, "the subject was called")
    g, _ = gates(ctx, name, batch, "evaluate the original batch again")
    gate_is(ctx, g, "semantic-gate", "pass")
    return ok(ctx, "fresh controls run in a separate Suite of the same Project, bound to @2")


def dec010(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    execs, batch = run(ctx, name, judge="J-PASS-60")
    eid = execs[0]["id"]
    g1, _ = gates(ctx, name, batch, "evaluation 1")
    gate_is(ctx, g1, "semantic-gate", "fail", ["non_actionable_results"])
    jr, _ = one_expectation(ctx, name, eid)
    y = review(ctx, name, eid, jr["id"], "P-REVIEWER")
    h = y.body or {}
    if y.outcome != "accepted" or h.get("oracle_type") != "human_reviewer" or h.get("resolves") != jr["id"] \
            or h.get("disposition") != "actionable":
        return fail(ctx, f"the Human Result: {y.text()[:300]}")
    g2, _ = gates(ctx, name, batch, "evaluation 2")
    basis_is(ctx, gate_is(ctx, g2, "semantic-gate", "pass"), {"results": 1, "not_actionable": 0})
    still = [r for r in results(ctx, name, eid) if r["id"] == jr["id"]]
    if still != [jr]:
        return fail(ctx, "the Judge's Result was changed or removed")
    return ok(ctx)


def dec011(ctx, b):
    name = setup(ctx, f_hr(b), "human_reviewer Expectation")
    execs, batch = run(ctx, name)
    eid = execs[0]["id"]
    r, _ = one_expectation(ctx, name, eid)
    if (r.get("disposition"), r.get("verdict"), r.get("confidence")) != ("awaiting_review", None, "not_applicable"):
        return fail(ctx, f"pending: {r}")
    g1, _ = gates(ctx, name, batch, "before the review")
    gate_is(ctx, g1, "semantic-gate", "fail", ["non_actionable_results"])
    y = review(ctx, name, eid, r["id"], "P-REVIEWER")
    if y.outcome != "accepted":
        return fail(ctx, f"the review was refused: {y.text()[:200]}")
    r2, allr = one_expectation(ctx, name, eid)
    if r2["id"] != r["id"] or r2.get("recorded_at") != r.get("recorded_at") or r2.get("verdict") != "pass" \
            or r2.get("disposition") != "actionable" or len(allr) != 1:
        return fail(ctx, f"after the review: {r2}")
    g2, _ = gates(ctx, name, batch, "after the review")
    gate_is(ctx, g2, "semantic-gate", "pass")
    return ok(ctx)


def dec012(ctx, b):
    variants = []
    # (a), (b): F-REVIEWED
    name = setup(ctx, with_sem(b), "F-REVIEWED")
    execs, batch = run(ctx, name, judge="J-PASS-60")
    eid = execs[0]["id"]
    jr, _ = one_expectation(ctx, name, eid)
    hr = review(ctx, name, eid, jr["id"], "P-REVIEWER", note="F-REVIEWED setup review")
    if hr.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", "F-REVIEWED: the review was refused")
    variants.append(("a", name, eid, batch, jr["id"], "P-REVIEWER", "fail"))
    variants.append(("b", name, eid, batch, hr.body["id"], "P-REVIEWER", "pass"))
    for label, judge in (("c", "J-PASS-90"), ("d", "J-PASS-60")):
        ex, n2 = ctx.load(with_sem(b), f"variant {label}", suffix=label)
        if ex.outcome != "accepted":
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"variant {label} rejected")
        e2, b2 = run(ctx, n2, judge=judge, note=f"variant {label}")
        r2, _ = one_expectation(ctx, n2, e2[0]["id"])
        variants.append((label, n2, e2[0]["id"], b2, r2["id"], "P-NOPERM" if label == "d" else "P-REVIEWER", "pass"))
    for label, n, e, bt, rid, actor, verdict in variants:
        before = results(ctx, n, e, f"({label}) Results before")
        gb, _ = gates(ctx, n, bt, f"({label}) evaluate before")
        y = review(ctx, n, e, rid, actor, verdict=verdict, note=f"({label}) the attempt")
        after = results(ctx, n, e, f"({label}) Results after")
        ga, _ = gates(ctx, n, bt, f"({label}) evaluate after")
        if y.outcome == "accepted":
            return fail(ctx, f"({label}) the attempt was accepted")
        if after != before:
            return fail(ctx, f"({label}) the Results changed")
        if {k: v.get("status") for k, v in gb.items()} != {k: v.get("status") for k, v in ga.items()}:
            return fail(ctx, f"({label}) the Gates changed")
    return ok(ctx)


def registry():
    T = {
        "CT-HRV-001": loads_rejected(f_hr, [("a", mutate(lambda d: exp_of(d)["human_reviewer"].pop("role")))]),
        "CT-HRV-002": hrv002, "CT-HRV-003": hrv003, "CT-HRV-004": hrv004, "CT-HRV-005": hrv005,
        "CT-HRV-006": loads_rejected(f_hr, [
            ("a", mutate(lambda d: exp_of(d).update(on_timeout="escalate"))),
            ("b", mutate(lambda d: exp_of(d).update(on_timeout="block", escalate_to="lead")))]),
        "CT-MJG-001": loads_rejected(f_panel, [("a", mutate(lambda d: exp_of(d)["multi_judge"].pop("purpose")))]),
        "CT-MJG-002": loads_rejected(f_panel, [
            ("a", mutate(lambda d: exp_of(d)["multi_judge"].pop("judges"))),
            ("b", mutate(lambda d: exp_of(d)["multi_judge"].update(samples=3))),
            ("c", mutate(lambda d: exp_of(d)["multi_judge"].update(purpose="stability"))),
            ("d", mutate(lambda d: exp_of(d)["multi_judge"].update(
                purpose="stability", samples=3, judge={"model": "cts-scripted-judge-a@1", "confidence_source": "self_rating"})))]),
        "CT-MJG-003": loads_rejected(f_panel, [
            ("a", mutate(lambda d: exp_of(d)["multi_judge"].pop("consensus"))),
            ("b", mutate(lambda d: exp_of(d)["multi_judge"]["consensus"].pop("method")))]),
        "CT-MJG-004": mjg004,
        "CT-MJG-005": mjg005, "CT-MJG-006": mjg006, "CT-MJG-007": mjg007,
        "CT-MJG-008": quorum(f_seed, "s-control", {"cts-scripted-judge-a@1": "J-PASS-90",
                                                   "cts-scripted-judge-b@1": "J-CATCH", "cts-scripted-judge-c@1": "J-CATCH"}),
        "CT-MJG-009": quorum(f_clean, "s-clean", {"cts-scripted-judge-a@1": "J-ALARM",
                                                  "cts-scripted-judge-b@1": "J-PASS-90", "cts-scripted-judge-c@1": "J-PASS-90"}),
        "CT-ASM-013": asm013, "CT-ADM-006": adm006,
        "CT-SCT-001": loads_rejected(f_seed, [
            (k, mutate(lambda d, k=k: d["suites"][0]["scenarios"][1]["seeded_control"].pop(k)))
            for k in ("defect_class", "planted_defect", "confirmed_by")]),
        "CT-SCT-002": sct002,
        "CT-SCT-003": sct003,
        "CT-SCT-004": confirm_case(f_seed_v, "SR-BYE", "J-PASS-90", "s-control", "missed", "seeded_control_miss"),
        "CT-SCT-005": sct005, "CT-SCT-006": sct006,
        "CT-SCT-007": sct007, "CT-SCT-008": lambda ctx, b: sct008(ctx, b, clean=False),
        "CT-SCT-009": sct009,
        "CT-SCT-010": clean_case("J-PASS-90", "passed", "none", "pass"),
        "CT-SCT-011": clean_case("J-ALARM", "false_alarm", "defect_class", "fail",
                                 ["seeded_control_false_alarm"], ["seeded_control_miss"]),
        "CT-SCT-012": sct012,
        "CT-SCT-013": confirm_case(f_clean_v, "SR-HI", "J-ALARM", "s-clean", "false_alarm", "seeded_control_false_alarm"),
        "CT-SCT-014": lambda ctx, b: sct008(ctx, b, clean=True),
        "CT-SCT-015": sct015,
        "CT-DEC-010": dec010, "CT-DEC-011": dec011, "CT-DEC-012": dec012,
        "CT-DEC-015": dec015, "CT-DEC-016": dec016, "CT-DEC-017": lambda ctx, b: dec017(ctx, b),
        "CT-DEC-018": dec018,
    }
    return T, {}


def mjg004(ctx, b):
    s = f_panel(b)
    ctx.control(s, "F-PANEL")
    vs = [("a", lambda c: c.update(threshold="0.75")), ("b", lambda c: c.update(threshold=0.5)),
          ("c", lambda c: c.update(method="confidence_weighted_mean", threshold=0.75)),
          ("d", lambda c: c.update(on_disagreement="flag"))]
    for label, m in vs:
        d = copy.deepcopy(s)
        m(exp_of(d)["multi_judge"]["consensus"])
        ex, _ = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome == "accepted":
            return fail(ctx, f"variant {label} was loaded")
    d = copy.deepcopy(s)
    exp_of(d)["multi_judge"]["consensus"]["threshold"] = 0.75
    ex, _ = ctx.load(d, "threshold 0.75", suffix="ok")
    return ok(ctx) if ex.outcome == "accepted" else fail(ctx, f"threshold 0.75 was rejected: {ex.text()[:200]}")


def sct002(ctx, b):
    ctx.control(f_seed(b), "F-SEED")
    conf = {"validator": "schema", "target": "response", "expected": {"type": "string", "pattern": "Goodbye"}}

    def v(fn, start):
        d = start(b)
        fn(d["suites"][0]["scenarios"][1], d)
        return d
    variants = [
        ("a", v(lambda c, d: c["seeded_control"].pop("confirmation"), f_seed_v)),
        ("b", v(lambda c, d: c["seeded_control"].update(confirmation=conf), f_seed)),
        ("c", v(lambda c, d: c.pop("evidence"), f_seed)),
        ("d", v(lambda c, d: c.update(variables={"query": "Hello"}, prompt={"template": "{{query}}"}), f_seed)),
        ("e", (lambda d: (d["suites"][0]["scenarios"][0].update(
            evidence=copy.deepcopy(F.f_seed(b)["suites"][0]["scenarios"][1]["evidence"])), d)[1])(with_sem(b)))]
    for label, d in variants:
        ex, _ = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome == "accepted":
            return fail(ctx, f"variant {label} was loaded")
    return ok(ctx)


def sct005(ctx, b):
    d = f_seed(b)
    ctx.control(d, "F-SEED")
    a = copy.deepcopy(d)
    a["defect_classes"][0]["difficulty_prior"] = 0.9
    ex, _ = ctx.load(a, "(a) prior without basis or source", suffix="a")
    if ex.outcome == "accepted":
        return fail(ctx, "(a) was loaded")
    name = ctx.project_name("ctl")
    ctx.behave("SR-OK", judge="J-PASS-90")
    execs, _ = ctx.execute(name, "(b) execute")
    e = scr(ctx, name, by_scn(execs, "s-control")["id"], "s-control")
    t = json.dumps(e)
    if '"difficulty_prior": 0' in t or '"difficulty_prior": 0.0' in t or e.get("difficulty_prior") != "not_established":
        return fail(ctx, f"(b) the prior reads {e.get('difficulty_prior')!r}")
    return ok(ctx)


def sct006(ctx, b):
    d = f_seed(b)
    ctx.control(d, "F-SEED")
    prior = {"difficulty_prior": 0.9, "prior_basis": 50, "prior_source": "reference_oracles"}
    a = copy.deepcopy(d)
    a["defect_classes"][0].update(prior, reference_oracles=[{"model": "cts-scripted-judge@1", "confidence_source": "self_rating"}])
    ex, _ = ctx.load(a, "(a) the tested Judge as reference", suffix="a")
    if ex.outcome == "accepted":
        return fail(ctx, "(a) was loaded")
    bb = copy.deepcopy(d)
    bb["defect_classes"][0].update(prior, reference_oracles=[{"model": "cts-reference-judge@1", "confidence_source": "self_rating"}])
    ex2, name = ctx.load(bb, "(b) an independent reference", suffix="b")
    if ex2.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"(b) was rejected: {ex2.text()[:300]}")
    ctx.behave("SR-OK", judge="J-PASS-90")
    execs, _ = ctx.execute(name, "(b) execute, missing the control")
    e = scr(ctx, name, by_scn(execs, "s-control")["id"], "s-control")
    g = ctx.record(ctx.a.get(f"/projects/{name}"), "the defect class after the miss").body or {}
    dc = (g.get("defect_classes") or [{}])[0]
    if dc.get("difficulty_prior") != 0.9 or dc.get("prior_basis") != 50:
        return fail(ctx, f"after the miss the class reads {dc}")
    return ok(ctx)


def sct009(ctx, b):
    s = f_clean(b)
    ctx.control(s, "F-CLEAN")
    vs = [("b", lambda c, d: c["seeded_control"].update(planted_defect="The response does not greet the user.")),
          ("c", lambda c, d: c["seeded_control"].update(difficulty_prior="not_established")),
          ("d", lambda c, d: c["seeded_control"].update(kind="unknown"))]
    for label, fn in vs:
        d = copy.deepcopy(s)
        fn(d["suites"][0]["scenarios"][1], d)
        ex, _ = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome == "accepted":
            return fail(ctx, f"variant {label} was loaded")
    e = f_seed(b)
    e["suites"][0]["scenarios"][1]["seeded_control"]["kind"] = "defect"
    e["suites"][0]["scenarios"][1]["seeded_control"].pop("planted_defect")
    ex, _ = ctx.load(e, "variant e", suffix="e")
    if ex.outcome == "accepted":
        return fail(ctx, "variant e was loaded")
    return ok(ctx)
