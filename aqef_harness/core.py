"""What every test uses: a context per case, the case result, and the rules for
reading an engine's answer. A test never decides an outcome from an answer the
engine did not give: a refusal for authorization is not a refusal of the
configuration, and a starting configuration that does not load makes the case
NOT_RUN, never PASS."""
import copy
import re
from dataclasses import dataclass, field


@dataclass
class CaseResult:
    case_id: str
    outcome: str                      # PASS | FAIL | NOT_RUN | NOT_APPLICABLE
    reason_code: str
    reason: str = ""
    evidence_refs: list = field(default_factory=list)
    setup_status: str = "not_needed"
    cleanup_status: str = "skipped"


class Stop(Exception):
    """Ends a case early with a result."""

    def __init__(self, result):
        self.result = result


AUTH = (401, 403)


class CaseContext:
    def __init__(self, case_id, run, adapter, store, scripted=None):
        self.case_id = case_id
        self.run = run
        self.a = adapter
        self.store = store
        self.scripted = scripted
        self.refs = []
        self.created = []
        self.setup_status = "not_needed"

    # -------------------------------------------------------------- naming
    def project_name(self, suffix=""):
        base = f"cts-{self.run}-{self.case_id.lower().replace('.', '-')}"
        return base + (f"-{suffix}" if suffix else "")

    def named(self, doc, suffix=""):
        """A copy of `doc` in a Project of this case's own (CTS 1.6)."""
        d = copy.deepcopy(doc)
        if "name" in d:
            d["name"] = self.project_name(suffix)
        return d

    # -------------------------------------------------------------- evidence
    def record(self, ex, note=None):
        obj = dict(ex)
        if note:
            obj["note"] = note
        self.refs.append(self.store.add(self.case_id, "sut_response", obj))
        return ex

    # -------------------------------------------------------------- results
    def result(self, outcome, code, reason=""):
        return CaseResult(self.case_id, outcome, code, reason, list(self.refs),
                          self.setup_status)

    def stop(self, outcome, code, reason=""):
        raise Stop(self.result(outcome, code, reason))

    def guard(self, ex, what):
        """Stop the case if the exchange says nothing about the behavior under test."""
        if ex.outcome == "transport_failed":
            self.stop("NOT_RUN", "TRANSPORT_FAILED", f"{what}: {ex['response'].get('error')}")
        if ex.outcome == "sut_error":
            self.stop("FAIL", "SUT_ERROR", f"{what}: the engine answered {ex.status}")
        if ex.outcome == "rejected" and ex.status in AUTH:
            self.stop("NOT_RUN", "SETUP_FAILED",
                      f"{what}: refused with {ex.status}, an authorization refusal, which says "
                      "nothing about the configuration; check the Principal's Permissions")

    # -------------------------------------------------------------- operations
    def load(self, doc, note, suffix=""):
        d = self.named(doc, suffix)
        ex = self.record(self.a.load_config(d), note)
        self.guard(ex, note)
        if ex.outcome == "accepted" and "name" in d:
            self.created.append(d["name"])
        return ex, d.get("name")

    def control(self, doc, what="starting configuration"):
        """Setup check: the unmodified starting configuration loads. Without it a
        rejection of the modified one shows nothing (an engine that rejects everything
        would pass every negative test)."""
        ex, _ = self.load(doc, f"setup check: the {what} loads", suffix="ctl")
        if ex.outcome != "accepted":
            self.setup_status = "failed"
            self.stop("NOT_RUN", "SETUP_FAILED",
                      f"the {what} was rejected, so a rejection of the modified one shows nothing")
        self.setup_status = "ready"

    # -------------------------------------------------------------- execution
    def needs_slice(self, n, what):
        """Stop as NOT_RUN if the engine has not yet reached slice `n`."""
        if self.a.cfg.engine_slices_done < n:
            self.stop("NOT_RUN", "ADAPTER_GAP",
                      f"{what} needs slice {n} of the engine; it reports slice "
                      f"{self.a.cfg.engine_slices_done} done")

    def behave(self, subject="SR-OK", **kw):
        if self.scripted is None:
            self.stop("NOT_RUN", "HARNESS_FAILURE", "the scripted subject is not running")
        self.scripted.reset(subject, **kw)

    def execute(self, project, note="execute cts-suite against cts-env"):
        """Execute; return the Execution records, or stop if the request was refused."""
        ex = self.record(self.a.execute(project), note)
        self.guard(ex, note)
        if ex.outcome != "accepted":
            self.stop("FAIL", "EXPECTED_VIOLATED", f"{note}: rejected ({ex.status}): {ex.text()[:300]}")
        body = ex.body if isinstance(ex.body, dict) else {}
        return body.get("executions", body.get("items", [])), body

    def conversation(self, project, execution_id):
        g = self.record(self.a.get(f"/projects/{project}/executions/{execution_id}/conversation"),
                        "retrieve the Conversation")
        return g

    def judge_log(self, note="calls the scripted Judge received"):
        calls = self.scripted.judge_calls()
        self.refs.append(self.store.add(self.case_id, "harness_call", {"note": note, "calls": calls}))
        return calls

    def results(self, project, execution_id, note="retrieve the Results"):
        g = self.record(self.a.get(f"/projects/{project}/executions/{execution_id}/results"), note)
        if g.outcome != "accepted":
            self.stop("FAIL", "EXPECTED_VIOLATED", f"{note}: {g.status}")
        b = g.body
        return b.get("items", b.get("results", [])) if isinstance(b, dict) else (b or [])

    def subject_log(self, note="calls the scripted subject received"):
        calls = self.scripted.subject_calls()
        self.refs.append(self.store.add(self.case_id, "harness_call", {"note": note, "calls": calls}))
        return calls

    def cleanup(self):
        if not self.created:
            return "skipped"
        ok = True
        for name in self.created:
            ex = self.a.delete_project(name)
            ok = ok and ex.outcome == "accepted"
        return "complete" if ok else "failed"


def mentions(ex, *needles):
    t = ex.text().lower()
    return all(str(n).lower() in t for n in needles)


def expect_rejected(ctx, ex, *must_name, what="the configuration"):
    """PASS if rejected (naming each of `must_name` in the error), FAIL otherwise."""
    if ex.outcome == "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{what} was loaded")
    if must_name and not mentions(ex, *must_name):
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          f"{what} was rejected, but the error does not name {', '.join(map(str, must_name))}")
    return ctx.result("PASS", "EXPECTED_MET")


def subset_diff(want, got, path="project"):
    """Paths where `got` lacks or alters something `want` has. Lists of objects with a
    `name` are matched by name; other lists by position."""
    out = []
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return [f"{path}: expected an object"]
        for k, v in want.items():
            if k not in got:
                out.append(f"{path}.{k}: missing")
            else:
                out += subset_diff(v, got[k], f"{path}.{k}")
    elif isinstance(want, list):
        if not isinstance(got, list):
            return [f"{path}: expected a list"]
        if all(isinstance(x, dict) and "name" in x for x in want):
            byname = {x.get("name"): x for x in got if isinstance(x, dict)}
            for x in want:
                if x["name"] not in byname:
                    out.append(f"{path}[{x['name']}]: missing")
                else:
                    out += subset_diff(x, byname[x["name"]], f"{path}[{x['name']}]")
        elif len(want) != len(got):
            out.append(f"{path}: {len(want)} items expected, {len(got)} found")
        else:
            for i, (w, g) in enumerate(zip(want, got)):
                out += subset_diff(w, g, f"{path}[{i}]")
    elif want != got and not (isinstance(want, (int, float)) and isinstance(got, (int, float))
                              and float(want) == float(got)):
        out.append(f"{path}: {want!r} expected, {got!r} found")
    return out


def project_of(body):
    if isinstance(body, dict) and isinstance(body.get("project"), dict):
        return body["project"]
    return body
