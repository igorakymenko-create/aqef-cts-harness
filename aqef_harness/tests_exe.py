"""CTS Section 11, Execution and Evidence."""
import copy

from . import fixtures as F

OK = "Hello! How can I help?"


def f_multi(b):
    """CTS 2.4, F-MULTI."""
    p = copy.deepcopy(b)
    s0 = p["suites"][0]["scenarios"][0]
    p["suites"][0]["scenarios"] = []
    for name, q in (("s-1", "One"), ("s-2", "Two"), ("s-3", "Three")):
        s = copy.deepcopy(s0)
        s["name"], s["variables"] = name, {"query": q}
        p["suites"][0]["scenarios"].append(s)
    return p


def setup(ctx, doc, what="the fixture"):
    ex, name = ctx.load(doc, what)
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"{what} was rejected: {ex.text()[:200]}")
    ctx.setup_status = "ready"
    return name


def turns(g):
    b = g.body if isinstance(g.body, dict) else {}
    return b.get("turns", b.get("conversation", []))


def find(obj, key):
    """Every value under `key`, anywhere in obj."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                out.append(v)
            out += find(v, key)
    elif isinstance(obj, list):
        for v in obj:
            out += find(v, key)
    return out


def env_name(rec):
    e = rec.get("environment")
    return e.get("name") if isinstance(e, dict) else e


# ---------------------------------------------------------------- tests
def exe001(ctx, b):
    name = setup(ctx, b, "F-BASE")
    ctx.behave("SR-OK")
    execs, _ = ctx.execute(name)
    if not execs:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "no Execution was recorded")
    bad = [env_name(e) for e in execs if env_name(e) != "cts-env"]
    if bad:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"Execution records name {bad}, not cts-env")
    return ctx.result("PASS", "EXPECTED_MET")


def exe002(ctx, b):
    name = setup(ctx, b, "F-BASE")
    ctx.behave("SR-ECHO")
    convs = []
    for i in (1, 2):
        execs, _ = ctx.execute(name, f"execution {i}")
        convs.append(turns(ctx.conversation(name, execs[0]["id"])))
    prompts = [c["request"].get("prompt") for c in ctx.subject_log()]
    if prompts != ["Hello", "Hello"]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the subject received {prompts}")
    if [c[0].get("prompt") if c else None for c in convs] != ["Hello", "Hello"]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Conversations do not both record Hello")
    return ctx.result("PASS", "EXPECTED_MET")


def exe003(ctx, b):
    d = copy.deepcopy(b)
    d["execution"] = {"retry": {"max_attempts": 2, "on": "infrastructure_failure"}}
    name = setup(ctx, d, "F-BASE with retry")
    ctx.behave("SR-503-THEN-OK")
    execs, _ = ctx.execute(name)
    calls = ctx.subject_log()
    if len(calls) != 2:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the subject received {len(calls)} calls, not 2")
    mine = [e for e in execs if e.get("scenario") == "s-greeting"]
    if len(mine) != 1:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{len(mine)} Executions of s-greeting recorded")
    t = turns(ctx.conversation(name, mine[0]["id"]))
    if len(t) != 1 or t[0].get("response") != OK:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Conversation is {t}")
    ctx.needs_slice(3, "checking the Execution's Results")
    rs = ctx.results(name, mine[0]["id"])
    if not rs:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Execution has no Results")
    return ctx.result("PASS", "EXPECTED_MET")


def exe004(ctx, b):
    d = copy.deepcopy(b)
    d["execution"] = {"retry": {"max_attempts": 2, "on": "infrastructure_failure"}}
    name = setup(ctx, d, "F-BASE with retry")
    ctx.behave("SR-EMPTY")
    execs, _ = ctx.execute(name)
    calls = ctx.subject_log()
    if len(calls) != 1:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the subject received {len(calls)} calls, not 1")
    ctx.needs_slice(3, "checking the schema Constraint's failing Result")
    v = [r for r in ctx.results(name, execs[0]["id"]) if r.get("oracle_type") == "validator"]
    if len(v) != 1 or v[0].get("verdict") != "fail":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the schema Results are {v}")
    return ctx.result("PASS", "EXPECTED_MET")


def exe005(ctx, b):
    ctx.needs_slice(3, "this test, which compares Results")
    name = setup(ctx, b, "F-BASE")
    ctx.behave("SR-EMPTY")
    e1 = ctx.execute(name, "execution 1, SR-EMPTY")[0][0]
    before = ctx.results(name, e1["id"], "Results of execution 1")
    ctx.behave("SR-OK")
    e2 = ctx.execute(name, "execution 2, SR-OK")[0][0]
    second = ctx.results(name, e2["id"], "Results of execution 2")
    after = ctx.results(name, e1["id"], "Results of execution 1, again")
    v1 = [r for r in before if r.get("oracle_type") == "validator"]
    v2 = [r for r in second if r.get("oracle_type") == "validator"]
    if e1["id"] == e2["id"]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "only one Execution was recorded")
    if len(v1) != 1 or v1[0].get("verdict") != "fail" or len(v2) != 1 or v2[0].get("verdict") != "pass":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"schema Results: first {v1}, second {v2}")
    if after != before:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the first Execution's Results changed")
    return ctx.result("PASS", "EXPECTED_MET")


def exe006(ctx, b):
    d = f_multi(b)
    d["execution"] = {"parallelization": 3}
    name = setup(ctx, d, "F-MULTI with parallelization 3")
    ctx.behave("SR-ECHO")
    execs, _ = ctx.execute(name)
    ctx.subject_log()
    want = {"s-1": "One", "s-2": "Two", "s-3": "Three"}
    for e in execs:
        t = turns(ctx.conversation(name, e["id"]))
        q = want.get(e.get("scenario"))
        if [(x.get("prompt"), x.get("response")) for x in t] != [(q, q)]:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"{e.get('scenario')}: Conversation {t}")
    if sorted(e.get("scenario") for e in execs) != sorted(want):
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "not one Execution per Scenario")
    return ctx.result("PASS", "EXPECTED_MET")


KEYS7 = ["model_version", "prompt_version", "tool_configuration", "infra_target", "template"]


def exe007(ctx, b):
    name = setup(ctx, b, "F-BASE")
    ctx.behave("SR-OK")
    recs = []
    for i in (1, 2):
        execs, _ = ctx.execute(name, f"execution {i}")
        g = ctx.record(ctx.a.get(f"/projects/{name}/executions/{execs[0]['id']}"), f"Execution record {i}")
        recs.append(g.body if g.outcome == "accepted" else execs[0])
    for k in KEYS7:
        v = [find(r, k) for r in recs]
        if not v[0] or not v[1]:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"`{k}` is not recorded")
        if v[0][0] != v[1][0]:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"`{k}` differs: {v[0][0]!r} / {v[1][0]!r}")
    c = [find(r, "constraints") for r in recs]
    if not c[0] or c[0][-1] != c[1][-1]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Contract is not recorded, or differs")
    return ctx.result("PASS", "EXPECTED_MET")


def exe008(ctx, b):
    name = setup(ctx, b, "F-BASE")
    ctx.behave("SR-OK")
    execs, _ = ctx.execute(name)
    ctx.subject_log()
    g = ctx.conversation(name, execs[0]["id"])
    if g.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Conversation cannot be retrieved")
    t = turns(g)
    if [(x.get("prompt"), x.get("response")) for x in t] != [("Hello", OK)]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the Conversation is {t}")
    a = ctx.record(ctx.a.get(f"/projects/{name}/executions/{execs[0]['id']}/artifacts"), "Artifacts")
    if a.outcome != "accepted":
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the Artifacts cannot be retrieved")
    return ctx.result("PASS", "EXPECTED_MET")


def exe009(ctx, b):
    return ctx.result("NOT_RUN", "MANUAL_REVIEW_PENDING",
                      "Inspection (CTS 1.8): a reviewer establishes trigger and order from the records")


def exe010(ctx, b):
    name = setup(ctx, F.f_ds(b), "F-BASE drawing on ds-1@1.0.0")
    ctx.behave("SR-ECHO")
    recs = [ctx.execute(name, "execution 1")[0]]
    ds = F.ds1("Bye")
    ds["version"] = "1.1.0"
    r = ctx.record(ctx.a.post(f"/projects/{name}/datasets", ds, ctx.a.cfg.loader), "register ds-1@1.1.0")
    ctx.guard(r, "registering ds-1@1.1.0")
    if r.outcome != "accepted":
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"ds-1@1.1.0 could not be registered: {r.text()[:200]}")
    recs.append(ctx.execute(name, "execution 2")[0])
    prompts = [c["request"].get("prompt") for c in ctx.subject_log()]
    if prompts != ["Hi", "Hi"]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", f"the subject received {prompts}")
    for i, execs in enumerate(recs, 1):
        e = execs[0]
        text = str(e.get("dataset")) + " " + str(e.get("row_id", e.get("row")))
        if not ("ds-1" in text and "1.0.0" in text and "r1" in text):
            return ctx.result("FAIL", "EXPECTED_VIOLATED",
                              f"Execution {i} does not identify ds-1@1.0.0 and row r1: {text}")
    return ctx.result("PASS", "EXPECTED_MET")


def exe011(ctx, b):
    name = setup(ctx, b, "F-BASE")
    ctx.behave("SR-ECHO")
    runs = []
    for i in (1, 2):
        ctx.scripted.reset("SR-ECHO")
        execs, _ = ctx.execute(name, f"run {i}")
        runs.append(([c["request"] for c in ctx.subject_log(f"run {i}")],
                     len(turns(ctx.conversation(name, execs[0]["id"])))))
    if runs[0] != runs[1]:
        return ctx.result("FAIL", "EXPECTED_VIOLATED", "the two runs sent different requests or turns")
    return ctx.result("PASS", "EXPECTED_MET")


LATENCY = {"validator": "latency", "target": "duration_ms", "expected": 150}   # engine's documented path


def exe012(ctx, b):
    """CTS WD9: recorded latency at least what the harness observed; each latency Result
    agrees with its own Execution's recorded latency against max 150 ms."""
    ctx.needs_slice(3, "this test, which reads the latency Constraint's Result")
    d = copy.deepcopy(b)
    d["suites"][0]["scenarios"][0]["contract"]["constraints"].append(dict(LATENCY))
    name = setup(ctx, d, "F-BASE with the latency Constraint")
    notes = []
    for i, beh in ((1, "SR-SLOW-200"), (2, "SR-OK")):
        ctx.behave(beh)
        e = ctx.execute(name, f"execution {i}, {beh}")[0][0]
        calls = ctx.subject_log(f"{beh} calls")
        arts = ctx.record(ctx.a.get(f"/projects/{name}/executions/{e['id']}/artifacts"), f"Artifacts {i}")
        items = arts.body if isinstance(arts.body, list) else (arts.body or {}).get("items", [])
        lat = [a.get("data") for a in items if a.get("name") == "latency_ms"]
        observed = calls[0]["harness_ms"] if calls else None
        if not lat or not isinstance(lat[0], (int, float)) or (observed is not None and lat[0] < observed):
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"execution {i}: recorded {lat}, harness observed {observed} ms")
        if i == 1 and lat[0] < 200:
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"execution 1 recorded {lat[0]} ms")
        lr = [r for r in ctx.results(name, e["id"]) if "latency" in str(r.get("oracle"))]
        want = "pass" if lat[0] <= LATENCY["expected"] else "fail"
        if len(lr) != 1 or lr[0].get("verdict") != want or (i == 1 and want != "fail"):
            return ctx.result("FAIL", "EXPECTED_VIOLATED", f"execution {i}: recorded {lat[0]} ms, Result {lr}")
        notes.append(f"{i}: {lat[0]:.0f} ms recorded, {observed:.0f} ms at the harness, {want}")
    return ctx.result("PASS", "EXPECTED_MET", "; ".join(notes))

def registry():
    return {f"CT-EXE-{i:03d}": f for i, f in enumerate(
        [exe001, exe002, exe003, exe004, exe005, exe006, exe007, exe008, exe009, exe010,
         exe011, exe012], 1)}, {}
