"""CTS Section 24: Dataset Sources (CT-DSR-001 to 006).

The scripted generator and capture source are in scripted.py. How an engine reaches
them (model identifier `cts-scripted-generator@1`, capture source `cts-capture`) is
set up by the engine's start script, as for the scripted subject and Judges (CTS 1.4).
Generating a Dataset again goes through Appendix C, `POST .../datasets/{dataset}/versions`
(Harness Contract §16, `generate_dataset`)."""
import copy

GEN_MODEL = "cts-scripted-generator@1"
GEN = {"model": GEN_MODEL, "instruction": "Generate one greeting query per row, as `query`."}
CAP = {"source": "cts-capture", "date_range": ["2026-10-01", "2026-10-31"], "sampling": "random",
       "sample_size": 1, "anonymization": True}


def ds_gen(version="1.0.0", generator=None):
    return {"name": "ds-gen", "version": version, "source": "generated",
            "generator": copy.deepcopy(GEN if generator is None else generator)}


def ds_replay(capture=None):
    return {"name": "ds-replay", "version": "1.0.0", "source": "production_replay",
            "capture": copy.deepcopy(CAP if capture is None else capture)}


def with_ds(b, ds, bind=False, replay=False):
    p = copy.deepcopy(b)
    p["datasets"] = [ds]
    if bind:
        s = p["suites"][0]["scenarios"][0]
        s.pop("variables", None)
        s["dataset"] = f"{ds['name']}@{ds['version']}"
        if replay:
            s.pop("prompt", None)
    return p


def ok(ctx, why=""):
    return ctx.result("PASS", "EXPECTED_MET", why)


def fail(ctx, why):
    return ctx.result("FAIL", "EXPECTED_VIOLATED", why)


def rejection_variants(ctx, start, what, variants):
    ctx.control(start, what)
    loaded = []
    for label, d in variants:
        ex, _ = ctx.load(d, f"variant ({label})", suffix=label)
        if ex.outcome == "accepted":
            loaded.append(label)
    if loaded:
        return fail(ctx, f"variant(s) {', '.join(loaded)} loaded")
    return ok(ctx, f"all {len(variants)} variants rejected; the complete one loads")


# ------------------------------------------------------------------ CT-DSR-001
def dsr001(ctx, b):
    ctx.behave("SR-OK", generator="H-GEN-DSR-003")
    variants = []
    for label, drop in (("a", None), ("b", "model"), ("c", "instruction")):
        ds = ds_gen()
        if drop is None:
            ds.pop("generator")
        else:
            ds["generator"].pop(drop)
        variants.append((label, with_ds(b, ds)))
    return rejection_variants(ctx, with_ds(b, ds_gen()), "F-BASE with a complete ds-gen", variants)


# ------------------------------------------------------------------ CT-DSR-002
def dsr002(ctx, b):
    ctx.behave("SR-OK", capture="C-HELLO")
    variants = []
    ds = ds_replay()
    ds.pop("capture")
    variants.append(("a", with_ds(b, ds)))
    for label, field in zip("bcdef", ("source", "date_range", "sampling", "sample_size", "anonymization")):
        ds = ds_replay()
        ds["capture"].pop(field)
        variants.append((label, with_ds(b, ds)))
    return rejection_variants(ctx, with_ds(b, ds_replay()), "F-BASE with a complete ds-replay", variants)


# ------------------------------------------------------------------ helpers for 003-005
def prompts_since(ctx, n0):
    return [c["request"].get("prompt") for c in ctx.scripted.subject_calls()[n0:]]


def rows_of(ctx, project, dataset, version, note):
    g = ctx.record(ctx.a.get(f"/projects/{project}/datasets/{dataset}/rows?version={version}"), note)
    if g.outcome != "accepted":
        return g, None
    b = g.body
    items = b if isinstance(b, list) else (b.get("items") or b.get("rows") or []) if isinstance(b, dict) else []
    return g, [{"id": r.get("id"), "variables": r.get("variables")} for r in items if isinstance(r, dict)]


def versions_of(ctx, project, dataset, note):
    g = ctx.record(ctx.a.get(f"/projects/{project}/datasets"), note)
    b = g.body
    items = b if isinstance(b, list) else (b.get("items") or []) if isinstance(b, dict) else []
    vs = []
    for d in items:
        if isinstance(d, dict) and d.get("name") == dataset:
            if d.get("version"):
                vs.append(d["version"])
            vs += [v.get("version") if isinstance(v, dict) else v for v in d.get("versions") or []]
    return g, sorted({v for v in vs if v})


def setup_gen(ctx, b, generator):
    ctx.behave("SR-ECHO", generator=generator)
    ex, name = ctx.load(with_ds(b, ds_gen(), bind=True), "setup: load F-BASE with ds-gen@1.0.0 "
                        "bound to s-greeting (generates ds-gen@1.0.0)")
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"ds-gen@1.0.0 could not be generated ({ex.status})")
    ctx.setup_status = "ready"
    return name


def generate_again(ctx, name, version, note):
    """Harness Contract §16, generate_dataset: the operation, its request and response."""
    body = {"name": "ds-gen", "version": version, "source": "generated", "generator": copy.deepcopy(GEN)}
    return ctx.record(ctx.a.post(f"/projects/{name}/datasets/ds-gen/versions", body, ctx.a.cfg.loader),
                      f"generate_dataset: {note} (POST .../datasets/ds-gen/versions)")


# ------------------------------------------------------------------ CT-DSR-003
def dsr003(ctx, b):
    name = setup_gen(ctx, b, "H-GEN-DSR-003")
    _, before = rows_of(ctx, name, "ds-gen", "1.0.0", "rows of ds-gen@1.0.0, before")
    _, vs_before = versions_of(ctx, name, "ds-gen", "ds-gen versions, before")
    n0 = len(ctx.scripted.subject_calls())
    ctx.execute(name, "execution 1")
    p1 = prompts_since(ctx, n0)

    g = generate_again(ctx, name, "1.0.1", "generate ds-gen again")
    if g.outcome == "transport_failed":
        ctx.stop("NOT_RUN", "TRANSPORT_FAILED", "generate again: the engine did not answer")
    _, after = rows_of(ctx, name, "ds-gen", "1.0.0", "rows of ds-gen@1.0.0, after")
    _, vs_after = versions_of(ctx, name, "ds-gen", "ds-gen versions, after")
    new = []
    if g.outcome == "accepted":
        _, new = rows_of(ctx, name, "ds-gen", "1.0.1", "rows of the version the request produced")
    n1 = len(ctx.scripted.subject_calls())
    ctx.execute(name, "execution 2")
    p2 = prompts_since(ctx, n1)

    problems = []
    if p1 != ["Gen-1"]:
        problems.append(f"execution 1 sent {p1}")
    if p2 != ["Gen-1"]:
        problems.append(f"execution 2 sent {p2}")
    if before is None or after != before:
        problems.append(f"ds-gen@1.0.0 rows before {before}, after {after}")
    if g.outcome == "accepted" and "1.0.1" not in vs_after:
        problems.append(f"the second generation was accepted, but versions are {vs_after}")
    if problems:
        return fail(ctx, "; ".join(problems))
    second = (f"accepted, new version 1.0.1 with rows {new}" if g.outcome == "accepted"
              else f"refused ({g.status})")
    return ok(ctx, f"both Executions sent Gen-1; ds-gen@1.0.0 unchanged; second generation {second}; "
                   f"versions {vs_before} -> {vs_after}")


# ------------------------------------------------------------------ CT-DSR-004
def dsr004(ctx, b):
    ctx.behave("SR-ECHO", capture="C-HELLO")
    doc = with_ds(b, ds_replay(), bind=True, replay=True)
    ex, name = ctx.load(doc, "load F-BASE with ds-replay@1.0.0 bound to s-greeting, no prompt or variables")
    if ex.outcome != "accepted":
        return fail(ctx, f"the configuration was rejected ({ex.status}): {ex.text()[:300]}")
    ctx.setup_status = "ready"
    n0 = len(ctx.scripted.subject_calls())
    ctx.execute(name)
    sent = prompts_since(ctx, n0)
    if sent != ["Hello"]:
        return fail(ctx, f"the scripted subject received {sent}")
    return ok(ctx, "loaded without prompt; the subject received the captured Prompt, Hello")


# ------------------------------------------------------------------ CT-DSR-006
def dsr006(ctx, b):
    """CTS 1.0-CR1.4. CT-DSR-004's configuration is the starting configuration; the
    variant is the same with `prompt: { template: "Hello" }` on s-greeting. The template
    uses no Variables, so a Row that lacks them cannot be the ground for rejecting it."""
    ctx.behave("SR-ECHO", capture="C-HELLO")
    start = with_ds(b, ds_replay(), bind=True, replay=True)
    variant = with_ds(b, ds_replay(), bind=True, replay=True)
    variant["suites"][0]["scenarios"][0]["prompt"] = {"template": "Hello"}
    ctx.control(start, "CT-DSR-004's configuration (ds-replay bound to s-greeting, no prompt)")
    ex, _ = ctx.load(variant, 'variant: s-greeting also carries prompt { template: "Hello" }',
                     suffix="prompt")
    if ex.outcome == "accepted":
        return fail(ctx, "the variant was loaded")
    return ok(ctx, f"the variant was rejected ({ex.status}: {ex.text()[:200]}); "
                   "CT-DSR-004's configuration loads")


# ------------------------------------------------------------------ CT-DSR-005
def dsr005(ctx, b):
    name = setup_gen(ctx, b, "H-GEN-DSR-003")
    ctx.behave("SR-ECHO", generator="generator.malformed")
    g = generate_again(ctx, name, "2.0.0", "generate ds-gen@2.0.0 from a malformed generation")
    if g.outcome == "transport_failed":
        ctx.stop("NOT_RUN", "TRANSPORT_FAILED", "generate: the engine did not answer")
    r = ctx.record(ctx.a.get(f"/projects/{name}/datasets/ds-gen?version=2.0.0"), "retrieve ds-gen@2.0.0")
    rr, rows = rows_of(ctx, name, "ds-gen", "2.0.0", "rows of ds-gen@2.0.0")
    _, vs = versions_of(ctx, name, "ds-gen", "list of ds-gen's versions")
    exists = ("2.0.0" in vs or (r.outcome == "accepted" and isinstance(r.body, dict)
                                and r.body.get("version") == "2.0.0")
              or (rr.outcome == "accepted" and rows))
    if g.outcome == "accepted":
        return fail(ctx, f"the generation was accepted ({g.status}); versions {vs}")
    if exists:
        return fail(ctx, f"a version 2.0.0 exists: versions {vs}, rows {rows}")
    return ok(ctx, f"the generation was reported as failed ({g.status}: {g.text()[:160]}); "
                   f"no ds-gen@2.0.0 (versions {vs})")


def registry():
    return {"CT-DSR-001": dsr001, "CT-DSR-002": dsr002, "CT-DSR-003": dsr003,
            "CT-DSR-004": dsr004, "CT-DSR-005": dsr005,
            "CT-DSR-006": dsr006}, {}
