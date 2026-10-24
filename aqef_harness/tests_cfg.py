"""CTS Section 10, Configuration and Definition. Each function runs one case and
returns its CaseResult; the CTS text it implements is cited in its docstring."""
import copy

from . import fixtures as F
from .core import expect_rejected, mentions, project_of, subset_diff

S = "suites[0].scenarios[0]"
EXP = f"{S}.contract.expectations[0]"
CON = f"{S}.contract.constraints[0]"
NEEDS_EXECUTION = ("needs an Execution and the scripted subject and Judge, which this "
                   "harness version does not yet drive")


def simple_reject(start, mutate, *must_name):
    """Control: `start` loads; then the mutated configuration must be rejected."""
    def run(ctx, base):
        s = start(base)
        ctx.control(s)
        ex, _ = ctx.load(mutate(s), "the modified configuration")
        return expect_rejected(ctx, ex, *must_name)
    return run


def variants_reject(start, mutations):
    """Every variant must be rejected; one test outcome."""
    def run(ctx, base):
        s = start(base)
        ctx.control(s)
        for label, m in mutations:
            ex, _ = ctx.load(m(s), f"variant {label}", suffix=label)
            r = expect_rejected(ctx, ex, what=f"variant {label}")
            if r.outcome != "PASS":
                return r
        return ctx.result("PASS", "EXPECTED_MET")
    return run


def base(b):
    return b


# ---------------------------------------------------------------- CT-CFG-001
def cfg001(ctx, b):
    """F-BASE loads, and every field of it is kept."""
    ex, name = ctx.load(b, "F-BASE")
    if ex.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "F-BASE was rejected")
    want = ctx.named(b)
    g = ctx.record(ctx.a.get_project(name), "retrieve the Project")
    if g.outcome != "accepted":
        return ctx.result("NOT_RUN", "OBSERVATION_INCOMPLETE",
                          "F-BASE loaded, but the Project could not be retrieved to check its fields")
    got = project_of(g.body)
    top = {k: v for k, v in want.items() if k != "suites"}
    diffs = subset_diff(top, got)
    for suite in want["suites"]:
        gs = ctx.record(ctx.a.get(f"/projects/{name}/suites/{suite['name']}"),
                        f"retrieve Suite {suite['name']}")
        if gs.outcome != "accepted":
            return ctx.result("NOT_RUN", "OBSERVATION_INCOMPLETE",
                              f"Suite {suite['name']} could not be retrieved")
        sb = gs.body.get("suite", gs.body) if isinstance(gs.body, dict) else gs.body
        diffs += subset_diff(suite, sb, f"project.suites[{suite['name']}]")
    if diffs:
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          "loaded with fields missing or altered: " + "; ".join(diffs[:10]))
    return ctx.result("PASS", "EXPECTED_MET")


# ---------------------------------------------------------------- CT-CFG-007
def cfg007(ctx, b):
    """A conflict between 0.9 and 0.8 on clause `greets` is reported."""
    ctx.control(b, "F-BASE")
    ex, _ = ctx.load(F.cfg007(b), "Project and Scenario contribute `greets` with 0.9 and 0.8")
    named = mentions(ex, "greets", "0.9", "0.8")
    if ex.outcome == "rejected":
        if named:
            return ctx.result("PASS", "EXPECTED_MET")
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          "rejected, but the error does not name the clause and both values")
    return ctx.result("NOT_RUN", "ADAPTER_GAP",
                      "loaded" + (" with the conflict reported" if named else "")
                      + "; whether s-greeting is assessed under the clause " + NEEDS_EXECUTION)


# ---------------------------------------------------------------- CT-CFG-008
def cfg008(ctx, b):
    ctx.control(b, "F-BASE")
    ex, _ = ctx.load(F.setv(b, f"{S}.prompt.template", "{{query}} {{name}}"),
                     "template references an unsupplied Variable")
    if ex.outcome == "rejected":
        return ctx.result("PASS", "EXPECTED_MET")
    ctx.needs_slice(2, "requesting an Execution of the loaded configuration")
    name = ctx.project_name()
    ctx.behave("SR-ECHO")
    ex2 = ctx.record(ctx.a.execute(name), "request an Execution")
    ctx.guard(ex2, "the Execution request")
    calls = ctx.subject_log()
    if calls:
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          f"the subject received {[c['request'].get('prompt') for c in calls]}")
    if ex2.outcome == "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Execution was accepted")
    if ex2.status in (404, 405):
        return ctx.result("FAIL", "REQUIRED_OPERATION_MISSING",
                          f"POST /projects/{{project}}/executions answered {ex2.status}")
    return ctx.result("PASS", "EXPECTED_MET")


# ---------------------------------------------------------------- CT-CFG-012, 013
def loads_then_executes(start, n_results, judge_calls):
    def run(ctx, b):
        ex, name = ctx.load(start(b), "the configuration")
        if ex.outcome != "accepted":
            return ctx.result("FAIL", "EXPECTED_VIOLATED", "the configuration was rejected")
        if mentions(ex, "conflict"):
            return ctx.result("FAIL", "EXPECTED_VIOLATED", "a conflict was reported")
        ctx.needs_slice(3, "the Expectation Results")
        ctx.behave("SR-OK", judge="J-PASS-90")
        execs, _ = ctx.execute(name)
        calls = ctx.judge_log()
        js = [r for r in ctx.results(name, execs[0]["id"]) if r.get("oracle_type") == "judge"]
        if len(js) != n_results or len(calls) != judge_calls:
            return ctx.result("FAIL", "EXPECTED_VIOLATED",
                              f"{len(js)} Expectation Results and {len(calls)} Judge calls; expected "
                              f"{n_results} and {judge_calls}")
        if any(r.get("disposition") != "actionable" for r in js):
            return ctx.result("FAIL", "EXPECTED_VIOLATED", "an Expectation Result is not actionable")
        return ctx.result("PASS", "EXPECTED_MET")
    return run


# ---------------------------------------------------------------- CT-CFG-014
def cfg014(ctx, b):
    d = F.f_ds(b)
    ex, _ = ctx.load(F.setv(d, f"{S}.dataset", "ds-1"), "dataset: ds-1, no version")
    r = expect_rejected(ctx, ex, what="the configuration without a version")
    if r.outcome != "PASS":
        return r
    ex2, _ = ctx.load(d, "dataset: ds-1@1.0.0", suffix="v")
    if ex2.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the configuration with a version was rejected")
    return ctx.result("PASS", "EXPECTED_MET")


# ---------------------------------------------------------------- CT-CFG-015
def cfg015(ctx, b):
    ctx.control(b, "F-BASE")
    d = F.setv(b, f"{CON}.id", "c1")
    d["suites"][0]["scenarios"][0]["contract"]["constraints"].append(
        {"id": "c1", "validator": "forbidden-content", "target": "response",
         "expected": {"patterns": [{"regex": "error"}]}})
    ex, _ = ctx.load(d, "two Constraints with id c1")
    return expect_rejected(ctx, ex, "c1")


# ---------------------------------------------------------------- CT-CFG-016
def cfg016(ctx, b):
    from .tests_asm import register_cts_len
    ctx.needs_slice(3, "registering the Custom Validator cts-len")
    ex, name = ctx.load(b, "F-BASE, to register cts-len in")
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        return ctx.result("NOT_RUN", "SETUP_FAILED", "F-BASE was rejected")
    register_cts_len(ctx, name)
    ctx.setup_status = "ready"
    d = ctx.named(b)
    d["suites"][0]["scenarios"][0]["contract"]["constraints"].append(
        {"validator": "cts-len", "target": "response", "expected": {}})
    ex1 = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", d), "cts-len without dimension")
    ctx.guard(ex1, "the first load")
    if ex1.outcome == "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "loaded without `dimension`")
    d["suites"][0]["scenarios"][0]["contract"]["constraints"][-1]["dimension"] = "functional"
    ex2 = ctx.record(ctx.a.call("PUT", f"/projects/{name}", "P-APPROVER", d), "cts-len with dimension")
    ctx.guard(ex2, "the second load")
    if ex2.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"rejected with `dimension`: {ex2.text()[:300]}")
    return ctx.result("PASS", "EXPECTED_MET")


# ---------------------------------------------------------------- CT-CFG-017
def cfg017(ctx, b):
    d = F.f_ds(b)
    ctx.control(d, "F-DS configuration")
    ex, _ = ctx.load(F.remove(d, "datasets[0].version"), "(a) ds-1 without version")
    r = expect_rejected(ctx, ex, what="(a)")
    if r.outcome != "PASS":
        return r
    name = ctx.project_name("ctl")
    ds = F.ds1()
    ds.pop("version")
    ex2 = ctx.record(ctx.a.post(f"/projects/{name}/datasets", ds, ctx.a.cfg.loader),
                     "(b) POST a Dataset without version")
    ctx.guard(ex2, "(b)")
    return expect_rejected(ctx, ex2, what="(b)")


# ---------------------------------------------------------------- CT-CFG-018
def cfg018(ctx, b):
    d = F.f_ds(b)
    ex, name = ctx.load(d, "ds-1@1.0.0 registered with query: Hi")
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        return ctx.result("NOT_RUN", "SETUP_FAILED", "the configuration with ds-1 was rejected")
    ctx.setup_status = "ready"
    ex2 = ctx.record(ctx.a.post(f"/projects/{name}/datasets", F.ds1("Bye"), ctx.a.cfg.loader),
                     "a second ds-1@1.0.0 with query: Bye")
    ctx.guard(ex2, "the second definition")
    if ex2.outcome == "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the second definition was accepted")
    rows = ctx.record(ctx.a.get(f"/projects/{name}/datasets/ds-1/rows"), "rows of ds-1")
    if rows.outcome != "accepted":
        return ctx.result("NOT_RUN", "OBSERVATION_INCOMPLETE", "the rows could not be retrieved")
    t = rows.text()
    if '"Hi"' in t and '"Bye"' not in t:
        return ctx.result("PASS", "EXPECTED_MET")
    return ctx.result("FAIL", "EXPECTED_VIOLATED", "the rows of ds-1@1.0.0 are not the original ones")


# ---------------------------------------------------------------- CT-CFG-023
def cfg023(ctx, b):
    ex, name = ctx.load(b, "F-BASE")
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        return ctx.result("NOT_RUN", "SETUP_FAILED", "F-BASE was rejected")
    ctx.setup_status = "ready"
    contract = copy.deepcopy(b["suites"][0]["scenarios"][0]["contract"])
    ex2 = ctx.record(ctx.a.post(f"/projects/{name}/contracts", contract, "P-APPROVER"),
                     "POST a Reusable Contract with no name, as P-APPROVER")
    ctx.guard(ex2, "the Contract")
    return expect_rejected(ctx, ex2, what="the Contract without a name")


# ---------------------------------------------------------------- CT-CFG-025
CASES_025 = [
    ("01", "base", "name"), ("02", "base", "environments[0].name"),
    ("03", "base", "environments[0].model_version"), ("04", "base", "environments[0].prompt_version"),
    ("05", "base", "environments[0].tool_configuration"), ("06", "base", "environments[0].infra_target"),
    ("07", "base", "suites[0].name"), ("08", "base", f"{S}.name"),
    ("09", "base", f"{CON}.target"), ("10", "base", f"{CON}.expected"),
    ("11", "base", f"{EXP}.criteria"), ("12", "base", f"{EXP}.judge.model"),
    ("13", "base", f"{EXP}.judge.confidence_source"), ("14", "base", "quality_gates[0].name"),
    ("15", "base", "quality_gates[0].aggregate"), ("16", "base", "quality_gates[0].threshold"),
    ("17", "base", "quality_gates[0].on_failure"), ("18", "retry", "execution.retry.max_attempts"),
    ("19", "ds", "datasets[0].name"), ("20", "ds", "datasets[0].source"),
    ("21", "ds", "datasets[0].rows"), ("22", "ds", "datasets[0].rows[0].id"),
    ("23", "ds", "datasets[0].rows[0].variables"), ("24", "dsm", "datasets[0].mechanisms[0].type"),
    ("25", "seed", "defect_classes[0].name"),
]
STARTS = {"base": lambda b: b, "retry": F.f_retry, "ds": F.f_ds,
          "dsm": lambda b: F.f_ds(b, mechanisms=True), "seed": F.f_seed}


def cfg025_case(start, path):
    def run(ctx, b):
        s = STARTS[start](b)
        ctx.control(s, f"starting configuration ({start})")
        d = F.remove(s, path)
        ex, _ = ctx.load(d, f"{path} removed", suffix="m")
        if ex.outcome == "accepted":
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"loaded without {path}")
        field_name = path.split(".")[-1].split("[")[0]
        if not mentions(ex, field_name):
            return ctx.result("FAIL", "EXPECTED_VIOLATED",
                              f"rejected, but the error does not name `{field_name}`")
        return ctx.result("PASS", "EXPECTED_MET")
    return run


# ---------------------------------------------------------------- registry
def registry():
    T = {
        "CT-CFG-001": cfg001,
        "CT-CFG-002": simple_reject(base, lambda s: F.remove(s, f"{S}.contract"), "s-greeting"),
        "CT-CFG-003": simple_reject(base, lambda s: F.setv(F.setv(s, f"{S}.contract.constraints", []),
                                                          f"{S}.contract.expectations", [])),
        "CT-CFG-004": variants_reject(base, [
            ("a", lambda s: F.remove(s, f"{EXP}.judge")),
            ("b", lambda s: F.setv(s, f"{EXP}.human_reviewer", {"role": "reviewer"}))]),
        "CT-CFG-005": simple_reject(base, lambda s: F.remove(s, f"{EXP}.confidence_threshold")),
        "CT-CFG-006": simple_reject(base, lambda s: F.setv(s, f"{EXP}.judge.model", "cts-scripted-subject@1"),
                                    "cts-scripted-subject@1"),
        "CT-CFG-007": cfg007,
        "CT-CFG-008": cfg008,
        "CT-CFG-009": simple_reject(base, lambda s: F.setv(s, "suites[0].quality_gates", [
            {"name": "functional-gate", "aggregate": "functional", "threshold": 0.5,
             "on_failure": "block_release"}])),
        "CT-CFG-010": simple_reject(base, lambda s: F.setv(s, "execution", {
            "retry": {"max_attempts": 2, "on": "result_failure"}})),
        "CT-CFG-011": simple_reject(base, lambda s: F.setv(F.setv(s, "datasets", [F.ds1()]),
                                                          f"{S}.dataset", "ds-1@1.0.0")),
        "CT-CFG-012": loads_then_executes(lambda b: F.cfg007(b, 0.8), 1, 1),
        "CT-CFG-013": loads_then_executes(lambda b: F.cfg007(b, 0.9, ids=False), 2, 2),
        "CT-CFG-014": cfg014,
        "CT-CFG-015": cfg015,
        "CT-CFG-016": cfg016,
        "CT-CFG-017": cfg017,
        "CT-CFG-018": cfg018,
        "CT-CFG-019": variants_reject(base, [
            ("a", lambda s: F.remove(s, f"{CON}.validator")),
            ("b", lambda s: F.setv(s, f"{CON}.validator", "cts-no-such-validator"))]),
        "CT-CFG-020": simple_reject(base, lambda s: F.setv(s, "environments", [])),
        "CT-CFG-021": simple_reject(base, lambda s: F.setv(s, "suites[0].scenarios", [])),
        "CT-CFG-022": variants_reject(base, [
            ("a", lambda s: F.remove(s, f"{S}.prompt")),
            ("b", lambda s: F.remove(s, f"{S}.prompt.template"))]),
        "CT-CFG-023": cfg023,
        "CT-CFG-024": simple_reject(base, lambda s: F.setv(s, "quality_gates[0].min_basis", {})),
    }
    cases = {f"CT-CFG-025.{n}": cfg025_case(st, p) for n, st, p in CASES_025}
    return T, cases
