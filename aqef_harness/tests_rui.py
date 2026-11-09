"""CTS Section 26, CT-RUI-001: a Scenario authored in a Reference UI's Visual Test
Designer is the same, once saved, as one written in YAML.

The test is generic. It knows the engine through Appendix C and the UI only through a
driver module named in harness.yaml (`ui.driver`). The driver authors one Scenario
through the UI and returns what it observed; everything specific to one UI lives in
it. A failure of the driver to operate the UI is a harness or adapter fault (NOT_RUN),
never a FAIL of the implementation."""
import copy
import importlib.util
import json

from .core import Stop

# Fields an implementation sets itself (CT-RUI-001, Expected): identifiers, timestamps,
# version or provenance fields. Matched by name; every excluded key is recorded.
IMPL_SET_EXACT = {"id", "uuid", "etag", "version", "revision", "provenance",
                  "created_by", "updated_by", "recorded_by"}
IMPL_SET_SUFFIX = ("_at", "_id")


def impl_set(key):
    return key in IMPL_SET_EXACT or key.endswith(IMPL_SET_SUFFIX)


def diff(a, b, path="", excluded=None):
    """Every path where a and b differ. An implementation-set key (identifier,
    timestamp, version, provenance) is not compared when both sides have it; a key
    present on one side only is always a difference, so a value the UI invented for
    one Scenario alone is never hidden."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in a:
                out.append(f"{p}: only in the second")
            elif k not in b:
                out.append(f"{p}: only in the first")
            elif impl_set(k):
                if excluded is not None:
                    excluded.add(p)
            else:
                out += diff(a[k], b[k], p, excluded)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: {len(a)} items vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]", excluded)
    elif a != b:
        out.append(f"{path}: {json.dumps(a, ensure_ascii=False)} vs {json.dumps(b, ensure_ascii=False)}")
    return out


def at(obj, dotted):
    for part in dotted.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


def load_driver(cfg):
    if not cfg.ui_url or not cfg.ui_driver or not cfg.ui_driver.is_file():
        return None
    spec = importlib.util.spec_from_file_location("ui_driver", cfg.ui_driver)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rui001(ctx, base):
    cfg = ctx.a.cfg
    drv = load_driver(cfg)
    if drv is None:
        ctx.stop("NOT_RUN", "ADAPTER_GAP", "no Reference UI configured (harness.yaml: ui.url, ui.driver)")

    # 1. s-greeting, written in YAML: F-BASE, loaded as the CTS loads every fixture.
    ex, project = ctx.load(base, "F-BASE, with s-greeting written in YAML")
    if ex.outcome != "accepted":
        ctx.setup_status = "failed"
        ctx.stop("NOT_RUN", "SETUP_FAILED", f"F-BASE was rejected: {ex.text()[:200]}")
    ctx.setup_status = "ready"
    suite = base["suites"][0]["name"]
    greeting = copy.deepcopy(base["suites"][0]["scenarios"][0])
    visual = {**copy.deepcopy(greeting), "name": "s-visual"}

    # 2. s-visual, with the same content, authored in the Visual Test Designer.
    project_doc = ctx.named(base)
    try:
        observed = drv.author_visually(cfg.ui_url, project_doc, suite, visual)
    except Exception as e:  # the driver could not operate the UI
        ctx.refs.append(ctx.store.add(ctx.case_id, "other", {"driver_error": f"{type(e).__name__}: {e}"}))
        ctx.stop("NOT_RUN", "ADAPTER_GAP", f"the UI driver could not author s-visual: {type(e).__name__}: {e}")
    for item in observed.get("files", []):
        ctx.refs.append(ctx.store.add_bytes(ctx.case_id, item["kind"], item["data"], item["ext"]))
    ctx.refs.append(ctx.store.add(ctx.case_id, "event_log", observed.get("log", {})))
    if not observed.get("saved"):
        ctx.stop("NOT_RUN", "ADAPTER_GAP",
                 f"the UI did not report the save as complete: {observed.get('outcome', '')[:200]}")

    # 3. Retrieve both through the REST API and compare every author-supplied field.
    got = {}
    for name in ("s-greeting", "s-visual"):
        g = ctx.record(ctx.a.get(f"/projects/{project}/suites/{suite}/scenarios/{name}", cfg.loader),
                       f"retrieve {name}")
        ctx.guard(g, f"retrieve {name}")
        if g.outcome != "accepted" or not isinstance(g.body, dict):
            ctx.stop("FAIL", "EXPECTED_VIOLATED", f"{name} could not be retrieved after saving: {g.status}")
        got[name] = g.body
    removed = set()
    fields = diff({k: v for k, v in got["s-greeting"].items() if k != "name"},
                  {k: v for k, v in got["s-visual"].items() if k != "name"}, "scenario", removed)

    # 4. The effective Contract each resolves to, as the engine froze it in an Execution.
    ctx.behave("SR-OK")
    execs, _ = ctx.execute(project)
    eff = {}
    for name in ("s-greeting", "s-visual"):
        rec = next((e for e in execs if e.get("scenario") == name), None)
        if rec is None:
            ctx.stop("FAIL", "EXPECTED_VIOLATED", f"no Execution was returned for {name}")
        g = ctx.record(ctx.a.get(f"/projects/{project}/executions/{rec['id']}", cfg.loader),
                       f"retrieve the Execution of {name}, with its frozen configuration")
        ctx.guard(g, f"retrieve the Execution of {name}")
        c = at(g.body if isinstance(g.body, dict) else {}, cfg.effective_contract_path)
        if c is None:
            ctx.stop("NOT_RUN", "ADAPTER_GAP",
                     f"the Execution record has no effective Contract at '{cfg.effective_contract_path}'")
        eff[name] = c
    contracts = diff(eff["s-greeting"], eff["s-visual"], "effective_contract", removed)

    ctx.refs.append(ctx.store.add(ctx.case_id, "other", {
        "note": "comparison (CT-RUI-001, Expected)",
        "excluded_as_implementation_set": sorted(removed),
        "authored_field_differences": fields,
        "effective_contract_differences": contracts}))
    if fields or contracts:
        return ctx.result("FAIL", "EXPECTED_VIOLATED",
                          "; ".join((fields + contracts)[:5]))
    return ctx.result("PASS", "EXPECTED_MET",
                      f"identical apart from name; excluded as implementation-set: {', '.join(sorted(removed)) or 'none'}")


def registry():
    return {"CT-RUI-001": rui001}, {}
