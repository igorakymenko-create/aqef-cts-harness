"""CTS 1.0-CR1: CT-TTP-001, now core."""
from .tests_dec import gates, judge_result, run, with_sem
from .tests_exe import setup


def ttp001(ctx, b):
    d = with_sem(b)
    d["quality_gates"].append({"name": "regression-gate", "aggregate": "regression",
                               "compare_against": "latest_approved", "threshold": 0,
                               "on_failure": "block_release"})
    name = setup(ctx, d, "F-BASE with semantic-gate and regression-gate")
    e1, b1 = run(ctx, name, subject="SR-OK", judge="J-CATCH", note="execution 1, SR-OK")
    r = judge_result(ctx, name, e1[0]["id"])
    bl = ctx.record(ctx.a.post(f"/projects/{name}/baselines", {"execution_id": e1[0]["id"], "result_id": r["id"],
                    "name": "cts-baseline"}, "P-APPROVER"), "designate the Baseline")
    if bl.outcome != "accepted":
        return ctx.result("NOT_RUN", "SETUP_FAILED", f"the Baseline was rejected: {bl.text()[:200]}")
    e2, b2 = run(ctx, name, subject="SR-BYE", judge="J-CATCH", note="execution 2, SR-BYE")
    g, _ = gates(ctx, name, b2)
    rg = g.get("regression-gate") or {}
    c1 = ctx.record(ctx.a.get(f"/projects/{name}/executions/{e1[0]['id']}"), "execution 1 record").body or {}
    c2 = ctx.record(ctx.a.get(f"/projects/{name}/executions/{e2[0]['id']}"), "execution 2 record").body or {}
    same = c1.get("configuration") == c2.get("configuration")
    if rg.get("status") != "fail":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"regression-gate: {rg.get('status')} {rg.get('reasons')}")
    if not same:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Executions' recorded configurations differ")
    return ctx.result("PASS", "EXPECTED_MET", "regression-gate failed; both Executions record the same configuration")


def registry():
    return {"CT-TTP-001": ttp001}, {}
