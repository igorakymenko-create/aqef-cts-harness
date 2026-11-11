"""CT-REL-024, CT-REL-025 and CT-REL-037 on GitHub Actions (Harness Contract §16,
`run_pipeline`).

A pipeline is a job of `.github/workflows/cts-ci-github.yml`, run on a GitHub-hosted
runner. Each pipeline job runs, on its own runner:
  1. the engine (setup/start_reference_engine.sh) and the harness's controller, in the
     background (`prepare`): the controller starts the scripted services, loads the
     fixture, triggers the Execution, and then plays the tester's part while the
     pipeline runs: it watches for the pipeline's Gate evaluation and overrides a Gate
     where the test says so, or does nothing;
  2. the integration under test, the Action of the implementation, on that batch;
  3. `collect`, always: it stops the controller and records what the pipeline's own
     step reported.
The report job then runs the ordinary runner, whose CT-REL-024/025/037 read the pipeline
jobs' artifacts and the platform's own record of the run (`gh api .../jobs`).

Durations are measured by the harness on the runner's monotonic clock (CTS 1, Waiting).
Tokens reach the Action only through its `token` input, masked in the log; none is
recorded."""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

from . import config as C
from . import fixtures as F
from .adapter_rest import RestAdapter
from .core import CaseContext, Stop
from .evidence import EvidenceStore
from .scripted import Scripted

# The pipeline runs of the three tests. `wait` is the pipeline timeout the tester sets
# (CT-REL-025), and the Action's wait budget in every run.
RUNS = {
    "rel024-a": {"test": "CT-REL-024", "subject": "SR-OK", "judge": "J-FAIL-90",
                 "override": ["semantic-gate"], "wait": 90,
                 "what": "CT-REL-006's configuration; override semantic-gate"},
    "rel024-b": {"test": "CT-REL-024", "subject": "SR-EMPTY", "judge": "J-FAIL-90",
                 "override": ["semantic-gate"], "wait": 60,
                 "what": "the same with functional-gate failing as well (SR-EMPTY); override semantic-gate only"},
    "rel025": {"test": "CT-REL-025", "subject": "SR-OK", "judge": "J-PASS-90", "human_review": True,
               "override": [], "wait": 45,
               "what": "CT-DEC-011's fixture with no review_timeout; the review is not answered"},
}
GRACE_S = 30   # the grace period of the waiting budget (CTS 1, Waiting), stated before the run


def fixture(run, base):
    from .tests_dec import with_sem
    from .tests_scoped import f_hr
    return f_hr(base) if run.get("human_review") else with_sem(base)


def j(path, obj):
    pathlib.Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ controller
def controller(cfg_path, key, out):
    out = pathlib.Path(out)
    (out / "evidence").mkdir(parents=True, exist_ok=True)
    run = RUNS[key]
    cfg = C.load(cfg_path)
    store = EvidenceStore(out / "evidence", "pipeline", cfg.validator())
    scripted = Scripted(cfg.scripted_port).start()
    tag = "gh" + os.environ.get("GITHUB_RUN_ID", str(int(time.time())))[-9:]
    ctx = CaseContext(run["test"], tag + "-" + key.split("-")[-1], RestAdapter(cfg), store, scripted)
    tl = {"run": key, "what": run["what"], "wait_timeout_s": run["wait"], "grace_s": GRACE_S, "events": []}

    def event(what, **kw):
        tl["events"].append({"what": what, "t_monotonic": time.monotonic(), **kw})
        j(out / "timeline.json", tl)

    try:
        for _ in range(60):
            if ctx.a.get("/projects", "P-RELEASE").outcome != "transport_failed":
                break
            time.sleep(1)
        ctx.behave(run["subject"], judge=run["judge"])
        doc = ctx.named(fixture(run, F.f_base(cfg.cts)))
        ex = ctx.record(ctx.a.load_config(doc), f"load {run['what']}")
        if ex.outcome != "accepted":
            raise Stop(ctx.result("NOT_RUN", "SETUP_FAILED", f"the fixture was rejected ({ex.status})"))
        name = doc["name"]
        tr = ctx.record(ctx.a.execute(name), "trigger the Execution of cts-suite against cts-env")
        batch = (tr.body or {}).get("execution_batch_id") if isinstance(tr.body, dict) else None
        if not batch:
            raise Stop(ctx.result("NOT_RUN", "SETUP_FAILED", f"no batch ({tr.status})"))
        j(out / "ready.json", {"project": name, "batch": batch, "suite": "cts-suite",
                               "environment": "cts-env", "wait": run["wait"]})
        event("ready", project=name, batch=batch)

        seen, done, probed = None, set(run["override"]), set()
        while not (out / "stop").exists():
            if seen is None:
                # The engine's Snapshot list does not name the batch; its Gate evaluation does
                # (docs/CI-GITHUB.md: "aqef snapshot list", then "aqef gate-evaluation get").
                snaps = ctx.a.get(f"/projects/{name}/snapshots").body
                items = snaps if isinstance(snaps, list) else (snaps or {}).get("items", []) if isinstance(snaps, dict) else []
                for sid in [x.get("id") for x in items if isinstance(x, dict)]:
                    if sid in probed:
                        continue
                    probed.add(sid)
                    g = ctx.a.get(f"/projects/{name}/gates/evaluations/{sid}")
                    if g.outcome == "accepted" and isinstance(g.body, dict) and g.body.get("execution_batch_id") == batch:
                        ctx.record(g, "the pipeline's own Gate evaluation, as soon as it exists")
                        seen = g.body
                        event("pipeline_evaluation_seen", evaluation=sid,
                              gates={k: {"status": v.get("status"), "blocking": v.get("blocking"),
                                         "override": v.get("override")} for k, v in seen["gates"].items()})
                        break
            if seen is not None and done:
                gate = done.pop()
                gr = seen["gates"][gate]
                body = {"execution_batch_id": batch, "justification": "CTS override", "gate_result_id": gr["id"]}
                ov = ctx.record(ctx.a.post(f"/projects/{name}/gates/{gate}/override", body, "P-APPROVER"),
                                f"override {gate} on the pipeline's own GateResult, as P-APPROVER")
                event("override", gate=gate, gate_result_id=gr["id"], status=ov.status, outcome=ov.outcome)
            time.sleep(0.5)
        if seen is not None:
            ctx.record(ctx.a.get(f"/projects/{name}/gates/evaluations/{seen['id']}"),
                       "the pipeline's Gate evaluation after the pipeline finished")
        event("stopped")
        tl["status"] = "ok"
    except Stop as s:
        tl["status"], tl["result"] = "stopped", {"outcome": s.result.outcome, "reason_code": s.result.reason_code,
                                                  "reason": s.result.reason}
    except Exception as e:   # recorded, and the report job decides
        tl["status"], tl["error"] = "error", f"{type(e).__name__}: {e}"
    j(out / "timeline.json", tl)
    j(out / "manifest.json", store.manifest())
    scripted.stop()


# ------------------------------------------------------------------ prepare / collect
def prepare(cfg_path, key, out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "controller.log", "w")
    subprocess.Popen([sys.executable, "-m", "aqef_harness.ci_github", "controller", "--config", cfg_path,
                      "--run", key, "--out", str(out)], stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True)
    for _ in range(240):
        if (out / "ready.json").exists():
            r = json.loads((out / "ready.json").read_text())
            cfg = C.load(cfg_path)
            token = cfg.tokens["P-RELEASE"]
            print(f"::add-mask::{token}")
            lines = [f"project={r['project']}", f"batch={r['batch']}", f"suite={r['suite']}",
                     f"environment={r['environment']}", f"wait={r['wait']}", f"token={token}"]
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("\n".join(lines) + "\n")
            j(out / "action-start.json", {"t_monotonic": time.monotonic()})
            return 0
        tl = out / "timeline.json"
        if tl.exists() and json.loads(tl.read_text()).get("status") in ("stopped", "error"):
            print(tl.read_text())
            return 1
        time.sleep(0.5)
    print("the controller did not become ready")
    return 1


def collect(key, out, step_outcome, outcome, batch):
    out = pathlib.Path(out)
    t_end = time.monotonic()
    (out / "stop").write_text("stop")
    for _ in range(60):
        tl = out / "timeline.json"
        if tl.exists() and json.loads(tl.read_text()).get("status") in ("ok", "stopped", "error"):
            break
        time.sleep(0.5)
    start = json.loads((out / "action-start.json").read_text())["t_monotonic"] if (out / "action-start.json").exists() else None
    summaries = []
    cmd = pathlib.Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "_runner_file_commands"
    for p in sorted(cmd.glob("step_summary_*")) if cmd.is_dir() else []:
        t = p.read_text(encoding="utf-8", errors="replace")
        if "AQEF outcome" in t:
            summaries.append(t)
    j(out / "action.json", {"run": key, "step_outcome": step_outcome, "outcome_output": outcome,
                            "batch_output": batch, "t_action_start": start, "t_action_end": t_end,
                            "elapsed_s": None if start is None else round(t_end - start, 3),
                            "step_summary": summaries,
                            "github": {k: os.environ.get(k) for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
                                                                       "GITHUB_JOB", "GITHUB_REPOSITORY")}})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "controller", "collect"])
    ap.add_argument("--config")
    ap.add_argument("--run", required=True, choices=sorted(RUNS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--step-outcome", default="")
    ap.add_argument("--outcome", default="")
    ap.add_argument("--batch", default="")
    a = ap.parse_args(argv)
    if a.cmd == "controller":
        return controller(a.config, a.run, a.out) or 0
    if a.cmd == "prepare":
        return prepare(a.config, a.run, a.out)
    return collect(a.run, a.out, a.step_outcome, a.outcome, a.batch)


if __name__ == "__main__":
    sys.exit(main())
