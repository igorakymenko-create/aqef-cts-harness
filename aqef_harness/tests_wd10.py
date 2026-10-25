"""CTS WD10 additions: CT-CFG-029 (cases), CT-ASM-014 (absent-target route), CT-API-003."""
import copy

from . import fixtures as F
from .tests_dec import with_sem
from .tests_inspect import pending
from .tests_rel2 import scenario_path

SUITE = "/projects/{p}/suites/cts-suite/scenarios"


def ok(ctx, note=""):
    return ctx.result("PASS", "EXPECTED_MET", note)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


def start_pol(b):
    d = copy.deepcopy(b)
    d["contracts"] = [{"constraints": [{"validator": "schema", "target": "response", "expected": {"type": "string"}}],
                       "policies": {"validator_composition": "AND"}}]
    d["suites"][0]["scenarios"][0]["contract"]["policies"] = {"validator_composition": "AND"}
    return d


def start_seed(b):
    d = with_sem(F.f_seed(b))
    d["defect_classes"][0].update(difficulty_prior=0.9, prior_basis=50, prior_source="reference_oracles",
                                  reference_oracles=[{"model": "cts-reference-judge@1", "confidence_source": "self_rating"}])
    return d


def get(ctx, path, note):
    return ctx.record(ctx.a.get(path, "P-APPROVER"), note)


def call(ctx, method, path, body, note, actor="P-APPROVER"):
    return ctx.record(ctx.a.call(method, path, actor, body), note)


def extra(ctx, name, query="Extra"):
    cur = copy.deepcopy(get(ctx, scenario_path(name), "s-greeting, as a model for s-extra").body or {})
    cur["name"] = "s-extra"
    cur["variables"] = {"query": query}
    return cur


def case(start, valid, invalid, check):
    """valid/invalid(ctx, name) -> Exchange; check(ctx, name) -> None or a problem string."""
    def t(ctx, b):
        d = start(b)
        ex, name = ctx.load(d, "the start")
        if ex.outcome != "accepted":
            ctx.setup_status = "failed"
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"the start was rejected: {ex.text()[:200]}")
        v = valid(ctx, name)
        if v.status in (404, 405):
            return ctx.result("NOT_APPLICABLE", "OPTIONAL_FEATURE_ABSENT",
                              f"the engine offers no such operation ({v.status}) (CTS CT-CFG-029)")
        if v.outcome != "accepted":
            ctx.setup_status = "failed"
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"the valid change was rejected: {v.text()[:200]}")
        ctx.setup_status = "ready"
        x = invalid(ctx, name)
        ctx.guard(x, "the invalid change")
        if x.outcome == "accepted":
            return fail(ctx, "the invalid change was accepted")
        if x.status in (401, 403):
            return ctx.result("NOT_RUN", "SETUP_FAILED", f"refused for authorization ({x.status})")
        p = check(ctx, name)
        return fail(ctx, p) if p else ok(ctx, f"rejected: {x.text()[:120]}")
    return t


def put_scn(fn, scn="s-greeting"):
    def go(ctx, name):
        cur = copy.deepcopy(get(ctx, scenario_path(name).replace("s-greeting", scn), f"{scn}").body or {})
        fn(cur)
        return call(ctx, "PUT", scenario_path(name).replace("s-greeting", scn), cur, f"replace {scn}")
    return go


def scn_is(pred, what, scn="s-greeting"):
    def chk(ctx, name):
        cur = get(ctx, scenario_path(name).replace("s-greeting", scn), f"{scn} after").body or {}
        return None if pred(cur) else f"{scn} after the invalid change: {what}"
    return chk


def gate_put(fields):
    def go(ctx, name):
        gs = get(ctx, f"/projects/{name}/gates", "the Gates").body or []
        g = dict(next(x for x in gs if x["name"] == "functional-gate"), **fields)
        return call(ctx, "PUT", f"/projects/{name}/gates/functional-gate", g, f"functional-gate {fields}")
    return go


def gate_is(pred, what):
    def chk(ctx, name):
        gs = get(ctx, f"/projects/{name}/gates", "the Gates after").body or []
        return None if pred(gs) else what
    return chk


def env_put(fields):
    def go(ctx, name):
        e = dict(get(ctx, f"/projects/{name}/environments/cts-env", "cts-env").body or {}, **fields)
        return call(ctx, "PUT", f"/projects/{name}/environments/cts-env", e, f"cts-env {fields}")
    return go


def has_exp(s):
    return bool((s.get("contract") or {}).get("expectations"))


def registry():
    def add_extra(dataset=False):
        def go(ctx, name):
            s = extra(ctx, name)
            if dataset:
                s["name"] = "s-extra-2"
                s.pop("variables", None)
                s["dataset"] = "absent@1"
            return call(ctx, "POST", SUITE.format(p=name), s, "add s-extra" + (" with dataset absent@1" if dataset else ""))
        return go

    def scenarios(ctx, name):
        return [s.get("name") for s in (get(ctx, f"/projects/{name}/suites/cts-suite", "cts-suite").body or {}).get("scenarios", [])]

    def ds(name_, base=None):
        def go(ctx, name):
            d = {"name": name_, "version": "1", "source": "static", "rows": [{"id": "r1", "variables": {"query": "Hi"}}]}
            if base:
                d["base_dataset"] = base
            return call(ctx, "POST", f"/projects/{name}/datasets", d, f"create {name_}@1")
        return go

    def add_then_remove(ctx, name):
        a = add_extra()(ctx, name)
        if a.outcome != "accepted":
            return a
        return call(ctx, "DELETE", SUITE.format(p=name) + "/s-extra", None, "remove s-extra")

    def evidence_bye(s):
        conv = (s.get("evidence") or {}).get("conversation") or {}
        for t in conv.get("turns", []):
            t["response"] = "Bye now."

    def judge_ref(s):
        s["contract"]["expectations"][0]["judge"]["model"] = "cts-reference-judge@1"

    C = {
        "01": case(with_sem, add_extra(), add_extra(dataset=True),
                   lambda ctx, n: None if "s-extra-2" not in scenarios(ctx, n) else "s-extra-2 was added"),
        "02": case(with_sem, put_scn(lambda s: s.__setitem__("variables", {"query": "Hi"})),
                   put_scn(lambda s: s["contract"].pop("expectations", None)), scn_is(has_exp, "Expectation gone")),
        "03": case(start_pol, put_scn(lambda s: s.__setitem__("variables", {"query": "Hi"})),
                   put_scn(lambda s: s["contract"].__setitem__("policies", {"validator_composition": "OR"})),
                   scn_is(lambda s: (s["contract"].get("policies") or {}).get("validator_composition") != "OR", "OR stored")),
        "04": case(with_sem,
                   lambda ctx, n: call(ctx, "POST", f"/projects/{n}/gates", {"name": "semantic-gate-2", "aggregate": "semantic",
                                       "threshold": 0.5, "on_failure": "warn"}, "define semantic-gate-2"),
                   lambda ctx, n: call(ctx, "POST", f"/projects/{n}/gates", {"name": "operational-gate", "aggregate": "operational",
                                       "threshold": 0.5, "on_failure": "warn"}, "define operational-gate"),
                   gate_is(lambda gs: "operational-gate" not in [g["name"] for g in gs], "operational-gate exists")),
        "05": case(with_sem, gate_put({"threshold": 0.9}), gate_put({"aggregate": "operational"}),
                   gate_is(lambda gs: next(g for g in gs if g["name"] == "functional-gate")["aggregate"] == "functional",
                           "functional-gate's aggregate changed")),
        "06": case(with_sem, env_put({"prompt_version": "cts-prompt@2"}), env_put({"model_version": "cts-scripted-judge@1"}),
                   lambda ctx, n: None if (get(ctx, f"/projects/{n}/environments/cts-env", "cts-env after").body or {})
                   .get("model_version") == "cts-scripted-subject@1" else "model_version changed"),
        "07": case(with_sem, ds("ds-2"), ds("ds-3", "absent@1"),
                   lambda ctx, n: None if get(ctx, f"/projects/{n}/datasets/ds-3", "ds-3").status == 404 else "ds-3 exists"),
        "08": case(with_sem, add_then_remove,
                   lambda ctx, n: call(ctx, "DELETE", SUITE.format(p=n) + "/s-greeting", None, "remove s-greeting"),
                   lambda ctx, n: None if scenarios(ctx, n) == ["s-greeting"] else f"Scenarios {scenarios(ctx, n)}"),
        "09": case(start_seed, put_scn(evidence_bye, "s-control"), put_scn(judge_ref, "s-control"),
                   scn_is(lambda s: s["contract"]["expectations"][0]["judge"]["model"] == "cts-scripted-judge@1",
                          "the control's Judge changed", "s-control")),
    }
    return {"CT-ASM-014": asm014, "CT-API-003": api003}, {f"CT-CFG-029.{k}": v for k, v in C.items()}


def asm014(ctx, b):
    d = copy.deepcopy(b)
    d["suites"][0]["scenarios"][0]["contract"]["constraints"].append(
        {"validator": "schema", "target": "artifacts.cts-absent", "expected": {"type": "string"}})
    ex, name = ctx.load(d, "F-BASE with the absent-target Constraint")
    if ex.outcome != "accepted":
        return ctx.result("NOT_RUN", "FIXTURE_UNAVAILABLE", f"the absent-target Constraint was rejected: {ex.text()[:150]}")
    ctx.behave("SR-OK")
    execs, _ = ctx.execute(name)
    rs = ctx.results(name, execs[0]["id"])
    r = next((x for x in rs if "cts-absent" in str(x.get("oracle")) or "cts-absent" in str(x.get("supporting_evidence"))), None)
    calls = ctx.judge_log()
    if r is None:
        return fail(ctx, "no Result for the absent-target Constraint")
    want = {"oracle_type": "validator", "disposition": "oracle_unavailable", "verdict": None, "confidence": "not_applicable"}
    bad = {k: r.get(k) for k, v in want.items() if r.get(k) != v}
    if bad or calls:
        return fail(ctx, f"Result {bad}; Judge calls {len(calls)}")
    return ok(ctx, "route: built-in schema Validator, target artifacts.cts-absent")


def api003(ctx, b):
    return pending(ctx, "Inspection: whether a JSON Schema is published as Appendix B's")
