"""Run CTS tests against an engine and write a verified run report.

    python -m aqef_harness.runner --config harness.yaml [--tests CT-CFG] [--out runs/]

`--tests` takes test IDs or prefixes (CT-CFG, CT-CFG-001); by default every test this
harness version implements. Output, in a new folder under --out:
    report.json      the run report (Harness Contract §15)
    manifest.json    the evidence manifest (§12)
    evidence/        every exchange with the engine, as stored
    summary.md       one line per case, for triage
The report is verified with the AQEF repository's validate.py before the run ends; a
report that does not verify is reported as such, and the exit status is 2.
"""
import argparse
import datetime
import json
import pathlib
import re
import sys
import traceback

from . import CONTRACT_VERSION, VERSION
from . import config as C
from . import fixtures as F
from . import tests_adm, tests_asm, tests_cfg, tests_dec, tests_exe, tests_rel, tests_rel2, tests_scoped, tests_wd9, tests_inspect, tests_wd10, tests_cr1
from .scripted import Scripted
from .adapter_rest import ADAPTER_VERSION, RestAdapter
from .core import CaseContext, CaseResult, Stop
from .evidence import EvidenceStore, now


def implemented():
    tests, cases = tests_cfg.registry()
    for mod in (tests_exe, tests_asm, tests_adm, tests_dec, tests_rel, tests_rel2, tests_scoped, tests_wd9, tests_inspect, tests_wd10, tests_cr1):
        t, c = mod.registry()
        tests, cases = {**tests, **t}, {**cases, **c}
    return tests, cases


def aqef_version(repo):
    t = (repo / "front-matter" / "00-document-status.md").read_text(encoding="utf-8")
    return re.search(r"\| Version \| ([^|]+) \|", t).group(1).strip()


def select(inv, impl_tests, impl_cases, wanted, unclaimed=lambda t: False):
    have = sorted(t for t in inv["tests"]
                  if t in impl_tests or all(c in impl_cases for c in inv["tests"][t]["cases"]) or unclaimed(t))
    if not wanted:
        return have
    return [t for t in have if any(t == w or t.startswith(w) for w in wanted)]


def run(cfg, wanted=None, out=None, quiet=False):
    V = cfg.validator()
    inv = V.load_inventory(cfg.cts)
    impl_tests, impl_cases = implemented()
    claims = cfg.capabilities_claimed
    plan_ids = select(inv, impl_tests, impl_cases, wanted, lambda t: all(
        not V.is_claimed(inv["tests"][t]["case_caps"][c], claims) for c in inv["tests"][t]["cases"]))
    if not plan_ids:
        raise SystemExit("no implemented test matches the selection")
    run_id = "r" + datetime.datetime.now().strftime("%y%m%d%H%M%S")
    out_dir = pathlib.Path(out or "runs") / run_id
    store = EvidenceStore(out_dir / "evidence", run_id, V)
    adapter = RestAdapter(cfg)
    base = F.f_base(cfg.cts)
    claims = cfg.capabilities_claimed

    if cfg.conformance_statement and cfg.conformance_statement.is_file():
        stmt = {"conformance_statement": cfg.conformance_statement.read_text(encoding="utf-8")}
    else:
        stmt = {"conformance_statement": None,
                "note": "not supplied to the harness; capabilities_claimed come from its configuration",
                "capabilities_claimed": claims}
    stmt_ref = store.add(None, "statement", stmt)

    scripted = Scripted(cfg.scripted_port).start()
    started = now()
    results = {}
    for tid in plan_ids:
        for cid in inv["tests"][tid]["cases"]:
            caps = inv["tests"][tid]["case_caps"][cid]
            if not V.is_claimed(caps, claims):
                results[cid] = CaseResult(cid, "NOT_APPLICABLE", "CAPABILITY_NOT_CLAIMED",
                                          f"capability {' + '.join(caps)} is not claimed")
                continue
            fn = impl_cases.get(cid) or impl_tests[tid]
            ctx = CaseContext(cid, run_id, adapter, store, scripted)
            try:
                res = fn(ctx, base)
            except Stop as s:
                res = s.result
            except Exception as e:  # a harness fault never becomes a FAIL
                res = ctx.result("NOT_RUN", "HARNESS_FAILURE", f"{type(e).__name__}: {e}")
                store.add(cid, "other", {"traceback": traceback.format_exc()})
            try:
                res.cleanup_status = ctx.cleanup()
            except Exception:
                res.cleanup_status = "failed"
            results[cid] = res
            if not quiet:
                print(f"{cid:16} {res.outcome:15} {res.reason}")
    ended = now()
    scripted.stop()

    cases = []
    for tid in plan_ids:
        for cid in inv["tests"][tid]["cases"]:
            r = results[cid]
            c = {"case_id": cid, "test_id": tid,
                 "capability": " + ".join(inv["tests"][tid]["case_caps"][cid]),
                 "outcome": r.outcome, "reason_code": r.reason_code,
                 "evidence_refs": r.evidence_refs,
                 "evidence_grades": ["observed"] if r.evidence_refs else [],
                 "setup_status": r.setup_status, "cleanup_status": r.cleanup_status}
            if r.reason:
                c["reason"] = r.reason
            cases.append(c)
    co = {c["case_id"]: c["outcome"] for c in cases}
    tests = [{"test_id": t, "outcome": V.summarize([co[c] for c in inv["tests"][t]["cases"]]),
              "case_ids": inv["tests"][t]["cases"]} for t in plan_ids]
    reqs = []
    for rid, q in inv["requirements"].items():
        if q["derived_from"]:
            tr = inv["requirements"][q["derived_from"]]["traced"]
            reqs.append({"requirement_id": rid, "state": V.requirement_state(tr, co),
                         "traced_to": tr, "derived_from": q["derived_from"]})
        else:
            reqs.append({"requirement_id": rid, "state": V.requirement_state(q["traced"], co),
                         "traced_to": q["traced"]})

    def count(items, key, keys):
        return {k: sum(1 for i in items if i[key] == k) for k in keys}

    full = set(plan_ids) == set(inv["tests"])
    plan = {"scope": "full" if full else "partial", "test_ids": plan_ids}
    if not full:
        plan["reason"] = (f"harness {VERSION} implements {len(plan_ids)} of {len(inv['tests'])} "
                          "tests" + (f"; selection: {', '.join(wanted)}" if wanted else ""))
    manifest = store.manifest()
    report = {
        "schema_version": CONTRACT_VERSION, "run_id": run_id,
        "provenance": {"aqef_version": aqef_version(cfg.aqef_repo), "cts_revision": inv["revision"],
                       "harness_contract_version": CONTRACT_VERSION, "harness_version": VERSION,
                       "adapter_id": cfg.adapter_id, "adapter_version": ADAPTER_VERSION,
                       "sut_name": cfg.sut_name, "sut_version": cfg.sut_version,
                       "conformance_statement_ref": stmt_ref,
                       "capabilities_claimed": claims},
        "plan": plan, "started_at": started, "ended_at": ended,
        "summary": {"cases": count(cases, "outcome", V.ORDER),
                    "tests": count(tests, "outcome", V.ORDER),
                    "requirements": count(reqs, "state", V.STATES)},
        "cases": cases, "tests": tests, "requirements": reqs,
        "manual_reviews": [],
        "evidence_manifest_ref": "evidence://manifest.json",
        "evidence_manifest_sha256": manifest["manifest_sha256"],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    (out_dir / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    lines = [f"# Run {run_id}", "",
             f"{cfg.sut_name} {cfg.sut_version}; AQEF {report['provenance']['aqef_version']}; "
             f"CTS {inv['revision']}; harness {VERSION}", "",
             "Cases: " + ", ".join(f"{k} {v}" for k, v in report["summary"]["cases"].items()), "",
             "| Case | Outcome | Reason |", "|---|---|---|"]
    lines += [f"| {c['case_id']} | {c['outcome']} | {c.get('reason', '').replace('|', '/')} |"
              for c in cases]
    errs = V.check_report(report, inv, manifest, out_dir / "evidence")
    lines += ["", "Report verification: " + ("OK" if not errs else f"{len(errs)} problem(s)")]
    lines += [f"- {e}" for e in errs]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    return out_dir, report, errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run AQEF CTS tests against an engine.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--tests", nargs="*")
    ap.add_argument("--out", default="runs")
    a = ap.parse_args(argv)
    out_dir, report, errs = run(C.load(a.config), a.tests, a.out)
    print(f"\n{out_dir}: " + ", ".join(f"{k} {v}" for k, v in report["summary"]["cases"].items()))
    if errs:
        print("report verification FAILED:\n" + "\n".join(errs))
        return 2
    print("report verified with validate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
