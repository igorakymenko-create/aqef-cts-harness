"""CTS Section 16, Admission of Judges (CT-ADM-001 to 003; 004 to 007 need Gates)."""
import copy

from .tests_asm import run_once

ADM_PASS = {"reference_set": "cts-greetings@1", "items": 20,
            "verdict_distribution": {"pass": 14, "fail": 6}, "raw_agreement": 0.90,
            "measure": "cohen_kappa", "chance_corrected_agreement": 0.76, "threshold": 0.70,
            "admitted": True, "labelled_by": ["P-REVIEWER"]}
# labelled_by: CTS WD8 16.1 names cts-labeller-1 and cts-labeller-2; the project owner
# decided (A-2) that WD9 names a registered Person instead, which holds under any reading.


def oracle_1(ctx, b):
    """CTS 16.1, ORACLE-1: the `oracle` on the Expectation's Result of a setup Execution."""
    ctx.needs_slice(3, "Admission")
    name, e, rs = run_once(ctx, b)
    j = [r for r in rs if r.get("oracle_type") == "judge"]
    if len(j) != 1 or not j[0].get("oracle"):
        ctx.setup_status = "failed"
        ctx.stop("NOT_RUN", "SETUP_FAILED", "setup check: the Expectation's Result carries no `oracle`")
    ctx.setup_status = "ready"
    return name, j[0]["oracle"]


def adm_pass(oracle, changes=None):
    d = {"oracle": oracle, **copy.deepcopy(ADM_PASS)}
    for k, v in (changes or {}).items():
        if v is DELETE:
            d.pop(k, None)
        else:
            d[k] = v
    return d


DELETE = object()


def post(ctx, name, body, actor, note):
    ex = ctx.record(ctx.a.post(f"/projects/{name}/admissions", body, actor), note)
    if ex.outcome in ("transport_failed", "sut_error"):
        ctx.guard(ex, note)
    return ex


def records(ctx, name, actor="P-NOPERM"):
    g = ctx.record(ctx.a.get(f"/projects/{name}/admissions", actor), "the Admission records")
    if g.outcome != "accepted":
        ctx.stop("FAIL", "EXPECTED_VIOLATED", f"the Admission records cannot be retrieved: {g.status}")
    b = g.body
    return b.get("items", b.get("admissions", [])) if isinstance(b, dict) else (b or [])


def adm001(ctx, b):
    name, o = oracle_1(ctx, b)
    a = post(ctx, name, adm_pass(o), "SA-REVIEW", "(a) as SA-REVIEW")
    if a.outcome == "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "a Service Account recorded an Admission")
    bb = post(ctx, name, adm_pass(o), "P-NOPERM", "(b) as P-NOPERM")
    if bb.outcome == "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "a Person without `review` recorded an Admission")
    c = post(ctx, name, adm_pass(o), "P-REVIEWER", "(c) as P-REVIEWER")
    if c.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"P-REVIEWER was refused: {c.text()[:300]}")
    rs = records(ctx, name)
    if len(rs) != 1:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{len(rs)} records, expected 1")
    r = rs[0]
    sent = adm_pass(o)
    diff = [k for k, v in sent.items() if r.get(k) != v]
    miss = [k for k in ("id", "recorded_at", "recorded_by") if not r.get(k)]
    if diff or miss:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"fields differ {diff}, missing {miss}")
    if "P-REVIEWER" not in str(r.get("recorded_by")):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"recorded_by is {r.get('recorded_by')}")
    return ctx.result("PASS", "EXPECTED_MET")


FIELDS = ["oracle", "reference_set", "items", "verdict_distribution", "raw_agreement", "measure",
          "chance_corrected_agreement", "threshold", "admitted", "labelled_by"]


def adm002(ctx, b):
    rejected = [(f"omit {f}", {f: DELETE}) for f in FIELDS] + [
        ("labelled_by []", {"labelled_by": []}),
        ("items 0", {"items": 0, "verdict_distribution": {}}),
        ("sum 21", {"verdict_distribution": {"pass": 15, "fail": 6}}),
        ("negative count", {"verdict_distribution": {"pass": 21, "fail": -1}}),
        ("raw 1.2", {"raw_agreement": 1.2}), ("raw -0.1", {"raw_agreement": -0.1}),
        ("cca null", {"chance_corrected_agreement": None}),
        ("id supplied", {"id": "adm-1"}), ("recorded_at supplied", {"recorded_at": "2030-01-01T00:00:00Z"}),
        ("recorded_by supplied", {"recorded_by": "P-REVIEWER"})]
    accepted = [("no arbitrations", {}), ("arbitrations []", {"arbitrations": []})]
    name, o = oracle_1(ctx, b)
    for label, ch in rejected:
        ex = post(ctx, name, adm_pass(o, ch), "P-REVIEWER", label)
        if ex.outcome == "accepted":
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"variant '{label}' was accepted")
    if records(ctx, name):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "a rejected variant left a record")
    for i, (label, ch) in enumerate(accepted, 1):
        ex = post(ctx, name, adm_pass(o, ch), "P-REVIEWER", label)
        if ex.outcome != "accepted":
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"variant '{label}' was rejected: {ex.text()[:200]}")
        rs = records(ctx, name)
        if len(rs) != i:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{len(rs)} records after '{label}'")
        last = rs[-1]
        if label == "no arbitrations" and "arbitrations" in last and last["arbitrations"] is not None:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"absent arbitrations reads back as {last['arbitrations']}")
        if label == "arbitrations []" and last.get("arbitrations") != []:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"empty arbitrations reads back as {last.get('arbitrations')}")
    return ctx.result("PASS", "EXPECTED_MET",
                      "variants share one Project; CTS asks one each, which changes nothing observed here")


def adm003(ctx, b):
    cases = [("a", {"chance_corrected_agreement": 0.70, "admitted": True}, True),
             ("b", {"chance_corrected_agreement": 0.70, "admitted": False}, False),
             ("c", {"chance_corrected_agreement": 0.69, "admitted": False}, True),
             ("d", {"chance_corrected_agreement": 0.69, "admitted": True}, False),
             ("e", {"raw_agreement": 0.95, "chance_corrected_agreement": 0.40, "admitted": True}, False),
             ("f", {"verdict_distribution": {"pass": 20}, "raw_agreement": 1.0,
                    "chance_corrected_agreement": "not_computed", "admitted": False}, True),
             ("g", {"verdict_distribution": {"pass": 20}, "raw_agreement": 1.0,
                    "chance_corrected_agreement": "not_computed", "admitted": True}, False)]
    name, o = oracle_1(ctx, b)
    for label, ch, ok in cases:
        ex = post(ctx, name, adm_pass(o, ch), "P-REVIEWER", f"({label})")
        if (ex.outcome == "accepted") != ok:
            return ctx.result("FAIL", "EXPECTED_VIOLATED",
                              f"({label}) was {'accepted' if ex.outcome == 'accepted' else 'rejected'}")
    if len(records(ctx, name)) != 3:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the records are not exactly (a), (c), (f)")
    return ctx.result("PASS", "EXPECTED_MET")


def registry():
    return {"CT-ADM-001": adm001, "CT-ADM-002": adm002, "CT-ADM-003": adm003}, {}
