"""CTS 14: CT-REL-024, CT-REL-025, CT-REL-037 on GitHub Actions, decided from the
pipeline jobs' artifacts and the platform's record of the run (see ci_github.py).

These tests do not drive the engine themselves: each pipeline job did, on its own
runner. They run in the workflow's report job, after the pipeline jobs, and read
`ci.artifacts/<run>/` and `ci.jobs` (the output of `gh api .../actions/runs/{id}/jobs`).
Without them a case is NOT_RUN (FIXTURE_UNAVAILABLE): the pipeline the tester supplies
was not run."""
import json

from .ci_github import GRACE_S, RUNS
from .tests_inspect import pending


def load(ctx, key):
    cfg = ctx.a.cfg
    d = cfg.ci_artifacts / key if cfg.ci_artifacts else None
    if d is None or not (d / "timeline.json").is_file() or not (d / "action.json").is_file():
        ctx.stop("NOT_RUN", "FIXTURE_UNAVAILABLE", f"no artifacts of pipeline run {key} (ci.artifacts)")
    tl = json.loads((d / "timeline.json").read_text())
    act = json.loads((d / "action.json").read_text())
    for p in sorted((d / "evidence").glob("*.json")):
        ctx.refs.append(ctx.store.add(ctx.case_id, "harness_call",
                                      {"note": f"pipeline run {key}: {p.name}, as its controller stored it",
                                       "recorded": json.loads(p.read_text())}))
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"note": f"pipeline run {key}: controller timeline "
                                                         "(monotonic clock of that runner)", "timeline": tl}))
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"note": f"pipeline run {key}: the Action step's result, "
                                                         "outputs and job summary", "action": act}))
    if tl.get("status") != "ok":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"pipeline run {key}: {tl.get('result') or tl.get('error')}")
    return tl, act


def platform(ctx, key):
    """The platform's own record of the pipeline job: its conclusion, and the Action step's."""
    p = ctx.a.cfg.ci_jobs
    if not p or not p.is_file():
        ctx.stop("NOT_RUN", "FIXTURE_UNAVAILABLE", "no platform record of the run (ci.jobs)")
    jobs = json.loads(p.read_text()).get("jobs", [])
    job = next((x for x in jobs if x.get("name") == f"pipeline ({key})"), None)
    if job is None:
        ctx.stop("NOT_RUN", "FIXTURE_UNAVAILABLE", f"the platform has no job pipeline ({key})")
    step = next((s for s in job.get("steps", []) if s.get("name") == "AQEF Quality Gates"), None)
    rec = {"job": job.get("name"), "job_conclusion": job.get("conclusion"), "html_url": job.get("html_url"),
           "step": step and {k: step.get(k) for k in ("name", "conclusion", "started_at", "completed_at")}}
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"note": f"the platform's record of pipeline ({key})",
                                                         "github_job": rec}))
    return rec


def ev(tl, what):
    return next((e for e in tl["events"] if e["what"] == what), None)


def ok(ctx, why):
    return ctx.result("PASS", "EXPECTED_MET", why)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


# ------------------------------------------------------------------ CT-REL-024
def rel024(ctx, b):
    problems = []
    tl, act = load(ctx, "rel024-a")
    pf = platform(ctx, "rel024-a")
    seen, ov = ev(tl, "pipeline_evaluation_seen"), ev(tl, "override")
    sg = (seen or {}).get("gates", {}).get("semantic-gate", {})
    if not seen or sg.get("status") != "fail" or sg.get("blocking") is not True or sg.get("override"):
        problems.append(f"run 1: before the override the pipeline's evaluation was {sg}")
    if not ov or ov.get("outcome") != "accepted":
        problems.append(f"run 1: the override was not accepted: {ov}")
    elif not (act.get("t_action_start") is not None and ov["t_monotonic"] < act["t_action_end"]):
        problems.append("run 1: the pipeline had finished before the override")
    if act.get("step_outcome") != "success" or pf["job_conclusion"] != "success":
        problems.append(f"run 1: after the override the pipeline was {act.get('step_outcome')} "
                        f"(platform: job {pf['job_conclusion']})")
    if act.get("outcome_output") != "pass_with_override" or not any("overridden" in s for s in act.get("step_summary", [])):
        problems.append(f"run 1: not shown as overridden (outcome {act.get('outcome_output')})")
    tl2, act2 = load(ctx, "rel024-b")
    pf2 = platform(ctx, "rel024-b")
    seen2, ov2 = ev(tl2, "pipeline_evaluation_seen"), ev(tl2, "override")
    g2 = (seen2 or {}).get("gates", {})
    if (g2.get("functional-gate") or {}).get("status") != "fail":
        problems.append(f"run 2: functional-gate did not fail: {g2.get('functional-gate')}")
    if not ov2 or ov2.get("outcome") != "accepted" or ov2.get("gate") != "semantic-gate":
        problems.append(f"run 2: the override of semantic-gate: {ov2}")
    if act2.get("step_outcome") != "failure" or pf2["job_conclusion"] != "failure":
        problems.append(f"run 2: the pipeline was {act2.get('step_outcome')} (platform: job {pf2['job_conclusion']})")
    if problems:
        return fail(ctx, "; ".join(problems))
    return ok(ctx, "run 1: the evaluation failed, the override was recorded while the pipeline waited, then the "
                   "pipeline passed shown as pass_with_override (job success); run 2: functional-gate failed "
                   "without an override and the pipeline failed (job failure)")


# ------------------------------------------------------------------ CT-REL-025
def rel025(ctx, b):
    tl, act = load(ctx, "rel025")
    pf = platform(ctx, "rel025")
    budget = RUNS["rel025"]["wait"] + GRACE_S
    seen = ev(tl, "pipeline_evaluation_seen")
    sg = (seen or {}).get("gates", {}).get("semantic-gate", {})
    problems = []
    if ev(tl, "override"):
        problems.append("an override was recorded")
    if act.get("elapsed_s") is None or act["elapsed_s"] > budget:
        problems.append(f"the pipeline ran {act.get('elapsed_s')} s, beyond its timeout plus grace ({budget} s)")
    if act.get("step_outcome") != "failure" or pf["job_conclusion"] != "failure":
        problems.append(f"the pipeline was {act.get('step_outcome')} (platform: job {pf['job_conclusion']})")
    if problems:
        return fail(ctx, "; ".join(problems))
    return ok(ctx, f"the review was not answered; semantic-gate {sg.get('status')}; the pipeline failed after "
                   f"{act['elapsed_s']} s (timeout {RUNS['rel025']['wait']} s, budget {budget} s); job failure")


# ------------------------------------------------------------------ CT-REL-037
def rel037(ctx, b):
    cfg = ctx.a.cfg
    load(ctx, "rel024-a")
    load(ctx, "rel024-b")
    pf = [platform(ctx, k) for k in ("rel024-a", "rel024-b")]
    files = {}
    for label, p in (("pipeline workflow", cfg.ci_workflow), ("integration (action.yml)", cfg.ci_action)):
        files[label] = p.read_text(encoding="utf-8") if p and p.is_file() else None
    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "for the reviewer: the integration's configuration (the pipeline workflow and the Action it uses) "
                "and the platform's records of the CT-REL-024 runs; the configurations the engine loaded are in "
                "the pipeline runs' evidence above", "files": files, "platform": pf}))
    if None in files.values():
        ctx.stop("NOT_RUN", "FIXTURE_UNAVAILABLE", "the workflow or the Action file was not found")
    return pending(ctx, "the integration's configuration and the platform's records were collected")


def registry():
    return {"CT-REL-024": rel024, "CT-REL-025": rel025, "CT-REL-037": rel037}, {}
