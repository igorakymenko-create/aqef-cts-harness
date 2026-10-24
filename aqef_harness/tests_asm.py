"""CTS Section 12, Assessment."""
import copy

from .tests_exe import setup

REQ = ["id", "execution", "clause", "oracle_type", "oracle", "verdict", "confidence",
       "disposition", "supporting_evidence", "recorded_at"]
NO_VERDICT = ("awaiting_review", "oracle_unavailable", "not_assessed")
CTS_LEN = {"name": "cts-len", "version": "1",
           "rule": {"operation": "schema", "expected": {"type": "string", "minLength": 1}}}


def run_once(ctx, b, subject="SR-OK", judge="J-PASS-90", doc=None, name=None, note="execute"):
    if name is None:
        name = setup(ctx, doc or b, "the fixture")
    ctx.behave(subject, judge=judge)
    execs, _ = ctx.execute(name, note)
    return name, execs[0], ctx.results(name, execs[0]["id"])


def of(results, kind):
    return [r for r in results if r.get("oracle_type") == kind]


def one(ctx, results, kind):
    r = of(results, kind)
    if len(r) != 1:
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{len(r)} {kind} Results, expected 1")
    return r[0]


def register_cts_len(ctx, name):
    ex = ctx.record(ctx.a.post(f"/projects/{name}/validators", CTS_LEN, "P-APPROVER"),
                    "register the Custom Validator cts-len (CTS 2.5)")
    ctx.guard(ex, "registering cts-len")
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        ctx.stop("NOT_RUN", "FIXTURE_UNAVAILABLE", f"cts-len could not be registered: {ex.text()[:200]}")


def asm001(ctx, b):
    name, e, rs = run_once(ctx, b, subject="SR-EMPTY")
    v = one(ctx, rs, "validator")
    calls = ctx.judge_log()
    if v.get("verdict") != "fail":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the schema Result is {v.get('verdict')}")
    if calls:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Judge received {len(calls)} call(s)")
    return ctx.result("PASS", "EXPECTED_MET")


def asm002(ctx, b):
    name, e, rs = run_once(ctx, b)
    calls = ctx.judge_log()
    v, j = one(ctx, rs, "validator"), one(ctx, rs, "judge")
    if len(calls) != 1:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Judge received {len(calls)} calls")
    if not (v.get("recorded_at") and j.get("recorded_at") and v["recorded_at"] < j["recorded_at"]):
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          f"recorded_at: Validator {v.get('recorded_at')}, Judge {j.get('recorded_at')}")
    return ctx.result("PASS", "EXPECTED_MET")


def asm003(ctx, b):
    name, e, rs = run_once(ctx, b)
    v = one(ctx, rs, "validator")
    want = {"confidence": "not_applicable", "verdict": "pass", "disposition": "actionable"}
    bad = {k: v.get(k) for k, x in want.items() if v.get(k) != x}
    if bad or not v.get("oracle") or "schema" not in str(v.get("oracle")):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the schema Result has {bad or v.get('oracle')}")
    return ctx.result("PASS", "EXPECTED_MET")


def judge_case(judge, want):
    def run(ctx, b):
        name, e, rs = run_once(ctx, b, judge=judge)
        j = one(ctx, rs, "judge")
        bad = {k: j.get(k) for k, x in want.items() if j.get(k) != x}
        if bad:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Judge Result has {bad}, expected {want}")
        return ctx.result("PASS", "EXPECTED_MET")
    return run


def asm006(ctx, b):
    name = setup(ctx, b, "F-BASE")
    for judge in ("J-PASS-90", "J-PASS-60", "J-FAIL-90", "J-DOWN"):
        _, e, rs = run_once(ctx, b, judge=judge, name=name, note=f"execute with {judge}")
        for r in rs:
            miss = [k for k in REQ if k not in r]
            if miss:
                return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{judge}: a Result lacks {miss}")
            if r["confidence"] is None:
                return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{judge}: confidence is bare null")
            if (r["disposition"] in NO_VERDICT) != (r["verdict"] is None):
                return ctx.result("FAIL", "EXPECTED_VIOLATED",
                                  f"{judge}: verdict {r['verdict']} with disposition {r['disposition']}")
            if r["verdict"] not in (None, "pass", "fail"):
                return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{judge}: verdict {r['verdict']}")
    return ctx.result("PASS", "EXPECTED_MET")


def asm007(ctx, b):
    name, e, rs = run_once(ctx, b, judge="J-DOWN")
    calls = ctx.judge_log()
    j = one(ctx, rs, "judge")
    want = {"disposition": "oracle_unavailable", "verdict": None, "confidence": "not_applicable"}
    bad = {k: j.get(k) for k, x in want.items() if j.get(k) != x}
    if bad:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Result has {bad}")
    se = j.get("supporting_evidence") or {}
    attempts = se.get("attempts") if isinstance(se, dict) else None
    n = len(attempts) if isinstance(attempts, list) else None
    if n != len(calls):
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          f"supporting_evidence records {n} attempt(s); the Judge received {len(calls)} call(s)")
    return ctx.result("PASS", "EXPECTED_MET")


def asm008(ctx, b):
    name, e, rs = run_once(ctx, b, judge="J-DOWN-THEN-PASS-90")
    calls = ctx.judge_log()
    js = of(rs, "judge")
    if len(js) > 1 and not any(r.get("resolves") for r in js):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{len(js)} Results for the Expectation, none resolving")
    if len(calls) == 1 and len(js) == 1 and js[0].get("disposition") == "oracle_unavailable":
        return ctx.result("PASS", "EXPECTED_MET")
    if len(calls) == 2 and len(js) == 1 and js[0].get("verdict") == "pass":
        att = (js[0].get("supporting_evidence") or {}).get("attempts", [])
        if len(att) == 2:
            return ctx.result("PASS", "EXPECTED_MET")
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "re-attempted, but the failed attempt is not recorded")
    return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{len(calls)} call(s), Results {js}")


SAME = ["verdict", "confidence", "disposition", "clause", "oracle", "oracle_type"]


def strip_exec(se, execution_id):
    return json_replace(se, execution_id)


def json_replace(obj, s):
    import json
    return json.loads(json.dumps(obj).replace(str(s), "<execution>"))


def two_runs_same(ctx, b, doc, pick, label):
    name = setup(ctx, doc, "the fixture")
    pair, convs = [], []
    for i in (1, 2):
        _, e, rs = run_once(ctx, b, name=name, note=f"execution {i}")
        r = pick(rs)
        if r is None:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"execution {i} has no {label} Result")
        pair.append((r, e["id"]))
        convs.append(ctx.conversation(name, e["id"]).body)
    if convs[0] != convs[1]:
        return ctx.result("NOT_RUN", "SETUP_FAILED", "the two Responses differ, so the inputs are not the same")
    (r1, e1), (r2, e2) = pair
    diff = [k for k in SAME if r1.get(k) != r2.get(k)]
    if strip_exec(r1.get("supporting_evidence"), e1) != strip_exec(r2.get("supporting_evidence"), e2):
        diff.append("supporting_evidence")
    if diff:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{label} Results differ in {diff}")
    return None


def asm009(ctx, b):
    out = two_runs_same(ctx, b, b, lambda rs: next((r for r in rs if r.get("oracle_type") == "validator"), None),
                        "schema")
    if out is not None:
        return out
    return ctx.result("PASS", "EXPECTED_MET", "no re-check offered: two Executions with identical Responses")


def asm011(ctx, b):
    name, e, rs = run_once(ctx, b)
    calls = ctx.judge_log()
    if not calls:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Judge received no call")
    import json
    t = json.dumps(calls[0]["request"])
    if "The response greets the user." not in t or "Hello! How can I help?" not in t:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the criteria or the Response is absent from the request")
    return ctx.result("PASS", "EXPECTED_MET")


def asm012(ctx, b):
    name, e, rs = run_once(ctx, b)
    if len(rs) != 2:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{len(rs)} Results, expected 2")
    for r in rs:
        o = r.get("oracle")
        if not o or not isinstance(o, str) or not r.get("oracle_type"):
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"a Result names no single Oracle: {o!r}")
        if r["oracle_type"] == "validator" and "schema" not in o:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Validator Result's oracle is {o}")
        if r["oracle_type"] == "judge" and "cts-scripted-judge@1" not in o:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Judge Result's oracle is {o}")
    return ctx.result("PASS", "EXPECTED_MET")


def asm013(ctx, b):
    ctx.needs_slice(5, "Multi Judge")
    return ctx.result("NOT_RUN", "ADAPTER_GAP", "this harness version does not yet drive panels")


def asm014(ctx, b):
    return ctx.result("NOT_RUN", "FIXTURE_UNAVAILABLE",
                      "the engine offers no way to define cts-crash (its Custom Validators are "
                      "declarative) and documents no fault hook (CTS CT-ASM-014)")


def asm015(ctx, b):
    name, e, rs = run_once(ctx, b, judge="J-FAIL-THEN-PASS-90")
    calls = ctx.judge_log()
    j = one(ctx, rs, "judge")
    if len(calls) != 1:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Judge received {len(calls)} calls")
    want = {"verdict": "fail", "confidence": 0.9, "disposition": "actionable"}
    bad = {k: j.get(k) for k, x in want.items() if j.get(k) != x}
    return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Result has {bad}") if bad \
        else ctx.result("PASS", "EXPECTED_MET")


def with_cts_len(b):
    d = copy.deepcopy(b)
    d["suites"][0]["scenarios"][0]["contract"]["constraints"].append(
        {"validator": "cts-len", "target": "response", "expected": {}, "dimension": "functional"})
    return d


def asm016(ctx, b):
    base_name = setup(ctx, b, "F-BASE, to register cts-len in")
    register_cts_len(ctx, base_name)
    d = with_cts_len(b)
    d["name"] = base_name
    ex = ctx.record(ctx.a.call("PUT", f"/projects/{base_name}", "P-APPROVER", d),
                    "add the cts-len Constraint")
    ctx.guard(ex, "adding the cts-len Constraint")
    if ex.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the cts-len Constraint was rejected: {ex.text()[:300]}")
    pick = lambda rs: next((r for r in rs if "cts-len" in str(r.get("oracle"))), None)  # noqa: E731
    pair = []
    for i in (1, 2):
        _, e, rs = run_once(ctx, b, name=base_name, note=f"execution {i}")
        r = pick(rs)
        if r is None:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"execution {i} has no cts-len Result")
        pair.append((r, e["id"]))
    for r, _ in pair:
        want = {"oracle_type": "validator", "verdict": "pass", "confidence": "not_applicable",
                "disposition": "actionable"}
        bad = {k: r.get(k) for k, x in want.items() if r.get(k) != x}
        if bad or not r.get("supporting_evidence"):
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the cts-len Result has {bad or 'no supporting_evidence'}")
    (r1, e1), (r2, e2) = pair
    diff = [k for k in SAME if r1.get(k) != r2.get(k)]
    if strip_exec(r1["supporting_evidence"], e1) != strip_exec(r2["supporting_evidence"], e2):
        diff.append("supporting_evidence")
    if diff:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the two cts-len Results differ in {diff}")
    return ctx.result("PASS", "EXPECTED_MET")


def asm018(ctx, b):
    return ctx.result("NOT_APPLICABLE", "OPTIONAL_FEATURE_ABSENT",
                      "the engine offers no re-check of a Validator on stored Evidence (permitted, CTS 1.2)")


def asm019(ctx, b):
    out = {}
    for label, judge, crit in (("a", "J-PASS-90-A3", "The response greets the user, offers help, and names no product."),
                               ("b", "J-PASS-90", None)):
        d = copy.deepcopy(b)
        if crit:
            d["suites"][0]["scenarios"][0]["contract"]["expectations"][0]["criteria"] = crit
        ex, name = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome != "accepted":
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"variant {label} rejected")
        ctx.behave("SR-OK", judge=judge)
        execs, _ = ctx.execute(name, f"variant {label}")
        rs = [r for r in ctx.results(name, execs[0]["id"]) if r.get("oracle_type") == "judge"]
        out[label] = rs[0] if rs else {}
    a = out["a"].get("assertions")
    if not (isinstance(a, int) and not isinstance(a, bool) and a > 1):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"(a) assertions {a!r}")
    if "assertions" in out["b"]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"(b) has assertions {out['b']['assertions']!r}")
    return ctx.result("PASS", "EXPECTED_MET", f"(a) assertions {a}")


def manual(what):
    def run(ctx, b):
        return ctx.result("NOT_RUN", "MANUAL_REVIEW_PENDING", f"{what} (CTS 1.8)")
    return run


def registry():
    T = {"CT-ASM-001": asm001, "CT-ASM-002": asm002, "CT-ASM-003": asm003,
         "CT-ASM-004": judge_case("J-PASS-90", {"oracle_type": "judge", "verdict": "pass",
                                                "confidence": 0.9, "disposition": "actionable"}),
         "CT-ASM-005": judge_case("J-PASS-60", {"verdict": "pass", "confidence": 0.6,
                                                "disposition": "inconclusive"}),
         "CT-ASM-006": asm006, "CT-ASM-007": asm007, "CT-ASM-008": asm008, "CT-ASM-009": asm009,
         "CT-ASM-010": manual("Declaration: the implementation states each built-in Validator's inputs"),
         "CT-ASM-011": asm011, "CT-ASM-012": asm012, "CT-ASM-014": asm014,
         "CT-ASM-015": asm015, "CT-ASM-016": asm016,
         "CT-ASM-017": manual("Inspection: how a Custom Validator is defined, and whether it can call a model"),
         "CT-ASM-018": asm018, "CT-ASM-019": asm019, "CT-ASM-020": asm020}
    return T, {}



def asm020(ctx, b):
    """CTS WD9: cts-len with an `expected` form the engine does not accept (Appendix A §A.5)."""
    name = setup(ctx, b, "F-BASE, to register cts-len in")
    register_cts_len(ctx, name)
    d = with_cts_len(b)
    d["name"] = name
    ok = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", d), "CT-ASM-016's configuration")
    if ok.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"CT-ASM-016's configuration was rejected: {ok.text()[:200]}")
    v = copy.deepcopy(d)
    for c in v["suites"][0]["scenarios"][0]["contract"]["constraints"]:
        if c.get("validator") == "cts-len":
            c["expected"] = {"minimum": "one"}
    ex = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", v), "expected {minimum: one}")
    if ex.outcome == "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the variant loaded")
    return ctx.result("PASS", "EXPECTED_MET", "variant: expected {minimum: \"one\"}; the engine documents "
                      "null or {} for a parameterless Custom Validator")
