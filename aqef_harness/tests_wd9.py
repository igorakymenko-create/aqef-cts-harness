"""CTS WD9 additions: CT-CFG-026 to 028, CT-DEC-024, CT-REL-038, CT-REL-039."""
import copy
import json

from . import fixtures as F
from .tests_dec import gate_is, gates, run, with_sem
from .tests_exe import setup
from .tests_rel import release
from .tests_rel2 import audit, items, scenario_path


def ok(ctx, note=""):
    return ctx.result("PASS", "EXPECTED_MET", note)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


def cfg026(ctx, b):
    c = with_sem(b)
    ctx.control(c, "(c) F-BASE with semantic-gate")
    a = copy.deepcopy(c)
    a["suites"][0]["scenarios"][0]["contract"].pop("expectations")
    bb = copy.deepcopy(c)
    bb["quality_gates"].append({"name": "operational-gate", "aggregate": "operational", "threshold": 0.5,
                                "on_failure": "warn"})
    for label, d in (("a", a), ("b", bb)):
        ex, _ = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome == "accepted":
            return fail(ctx, f"variant {label} loaded")
    ex, name = ctx.load(c, "(c)", suffix="c")
    if ex.outcome != "accepted":
        return fail(ctx, f"(c) rejected: {ex.text()[:200]}")
    cur = ctx.record(ctx.a.get(scenario_path(name)), "s-greeting").body or {}
    ch = copy.deepcopy(cur)
    ch["contract"].pop("expectations", None)
    x = ctx.record(ctx.a.call("PUT", scenario_path(name), "P-APPROVER", ch), "remove the Expectation")
    now = ctx.record(ctx.a.get(scenario_path(name)), "s-greeting after").body or {}
    if x.outcome == "accepted" or not (now.get("contract") or {}).get("expectations"):
        return fail(ctx, "the change took effect")
    return ok(ctx)


def cfg027(ctx, b):
    def doc(p, s):
        d = copy.deepcopy(b)
        d["contracts"] = [{"constraints": [{"validator": "schema", "target": "response",
                                            "expected": {"type": "string"}}],
                           "policies": {"validator_composition": p}}]
        d["suites"][0]["scenarios"][0]["contract"]["policies"] = {"validator_composition": s}
        return d
    ctx.control(b, "F-BASE")
    res = {}
    for label, p, s in (("a", "AND", "OR"), ("b", "hard-veto", "AND"), ("c", "OR", "AND")):
        ex, _ = ctx.load(doc(p, s), f"({label}) {p} over {s}", suffix=label)
        res[label] = ex.outcome
    if res["a"] == "accepted" or res["b"] == "accepted" or res["c"] != "accepted":
        return fail(ctx, f"outcomes {res}")
    return ok(ctx)


MECH = ("data_mutation", "fuzzing", "edge_cases", "adversarial")


def cfg028(ctx, b):
    """CTS 1.0-CR1: synthetic Datasets and every mechanism are reserved, and rejected."""
    ctx.control(F.f_ds(b), "F-DS")
    variants = []
    for t in MECH:
        d = F.f_ds(b)
        d["datasets"][0]["mechanisms"] = [{"type": t}]
        variants.append((t.replace("_", "-"), d))
    d = F.f_ds(b)
    d["datasets"][0]["source"] = "synthetic"
    d["datasets"][0].pop("rows", None)
    variants.append(("synthetic", d))
    for label, d in variants:
        ex, _ = ctx.load(d, f"variant {label}", suffix=label)
        if ex.outcome == "accepted":
            return fail(ctx, f"{label} loaded")
    return ok(ctx, "four mechanisms and source: synthetic, each rejected")


def dec024(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    _, batch = run(ctx, name, judge="J-PASS-60")
    g, _ = gates(ctx, name, batch)
    r = gate_is(ctx, g, "semantic-gate", "fail", ["insufficient_basis", "non_actionable_results"])
    if r.get("value") != "not_computed":
        return fail(ctx, f"value {r.get('value')!r}")
    return ok(ctx)


def rel038(ctx, b):
    name = setup(ctx, with_sem(b), "F-BASE with semantic-gate")
    ctx.behave("SR-OK")
    x = ctx.record(ctx.a.execute(name, actor="P-NOPERM"), "execute as P-NOPERM")
    ctx.guard(x, "the Execution")
    batch = x.body["execution_batch_id"]
    _, body = gates(ctx, name, batch)
    d = release(ctx, name, batch, body["snapshot_id"])
    if d.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"the Release Decision was rejected: {d.text()[:200]}")
    r1 = audit(ctx, name, "audit, read 1")
    r2 = audit(ctx, name, "audit, read 2")
    if json.dumps(r1, sort_keys=True) != json.dumps(r2, sort_keys=True):
        return fail(ctx, f"the two reads differ ({len(r1)} vs {len(r2)} entries)")

    def has(pid, act):
        return [e for e in r1 if e.get("principal_id") == pid and act in str(e.get("action"))
                and e.get("principal_kind") == "person" and e.get("timestamp")
                and (e.get("details") or {}).get("target")]
    ex, rd = has("P-NOPERM", "execut"), has("P-RELEASE", "release")
    if not ex or not rd:
        return fail(ctx, f"Execution entry {bool(ex)}, Release Decision entry {bool(rd)}")
    return ok(ctx, f"{len(r1)} entries; actions {ex[0]['action']}, {rd[0]['action']}")


def rel039(ctx, b):
    if ctx.a.cfg.team_binding == "none":
        return ctx.result("NOT_APPLICABLE", "OPTIONAL_FEATURE_ABSENT",
                          "the Conformance Statement says the engine binds no Project or Suite to Teams (CTS 1.2)")
    return ctx.result("NOT_RUN", "ADAPTER_GAP", "this harness has no adapter for a Team binding")


def registry():
    return {"CT-CFG-026": cfg026, "CT-CFG-027": cfg027, "CT-CFG-028": cfg028, "CT-DEC-024": dec024,
            "CT-REL-038": rel038, "CT-REL-039": rel039}, {}
