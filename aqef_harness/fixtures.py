"""CTS fixtures as data. F-BASE is read from the CTS text itself (02-fixtures.md §2.1),
so that the harness cannot drift from it; the others are built from F-BASE exactly as
the CTS sections that define them say, cited at each."""
import copy
import re

import yaml


def f_base(cts_dir):
    text = (cts_dir / "02-fixtures.md").read_text(encoding="utf-8")
    sec = text.split("## 2.1", 1)[1].split("## 2.2", 1)[0]
    block = re.search(r"```yaml\n(.*?)```", sec, re.S).group(1)
    return yaml.safe_load(block)["project"]


def judge(model="cts-scripted-judge@1"):
    return {"model": model, "confidence_source": "self_rating"}


def ds1(query="Hi"):
    """CT-CFG-011's Static Dataset."""
    return {"name": "ds-1", "version": "1.0.0", "source": "static",
            "rows": [{"id": "r1", "variables": {"query": query}}]}


def f_retry(base):
    """CT-CFG-025, F-RETRY."""
    p = copy.deepcopy(base)
    p["execution"] = {"retry": {"max_attempts": 2, "on": "infrastructure_failure"}}
    return p


def f_ds(base, mechanisms=False):
    """CT-CFG-025, F-DS: CT-CFG-011 with `variables` removed from the Scenario."""
    p = copy.deepcopy(base)
    d = ds1()
    if mechanisms:
        d["mechanisms"] = [{"type": "edge_cases"}]
    p["datasets"] = [d]
    s = p["suites"][0]["scenarios"][0]
    s.pop("variables")
    s["dataset"] = "ds-1@1.0.0"
    return p


def f_seed(base):
    """CTS 13.1, F-SEED."""
    p = copy.deepcopy(base)
    p["defect_classes"] = [{"name": "greeting-missing"}]
    p["suites"][0]["scenarios"].append({
        "name": "s-control",
        "seeded_control": {"defect_class": "greeting-missing",
                           "planted_defect": "The response does not greet the user.",
                           "confirmed_by": "construction"},
        "evidence": {"conversation": [{"role": "user", "content": "Hello"},
                                      {"role": "assistant", "content": "Goodbye."}]},
        "contract": {"expectations": [{
            "criteria": "The response greets the user.",
            "defect_classes": ["greeting-missing"],
            "judge": judge(), "confidence_threshold": 0.8}]},
    })
    return p


def cfg007(base, project_threshold=0.9, ids=True):
    """CT-CFG-007 (and 012, 013 with other values)."""
    p = copy.deepcopy(base)
    exp = {"criteria": "The response greets the user.", "judge": judge(),
           "confidence_threshold": project_threshold}
    if ids:
        exp = {"id": "greets", **exp}
        p["suites"][0]["scenarios"][0]["contract"]["expectations"][0] = {
            "id": "greets", **p["suites"][0]["scenarios"][0]["contract"]["expectations"][0]}
    p["contracts"] = [{"expectations": [exp]}]
    return p


_TOKEN = re.compile(r"([a-z_]+)(?:\[(\d+)\])?")


def _walk(doc, path):
    parts = path.split(".")
    node = doc
    for part in parts[:-1]:
        k, i = _TOKEN.fullmatch(part).groups()
        node = node[k]
        if i is not None:
            node = node[int(i)]
    return node, parts[-1]


def remove(doc, path):
    """Remove the field at `path` (e.g. `environments[0].name`) from a copy of `doc`."""
    d = copy.deepcopy(doc)
    node, last = _walk(d, path)
    k, i = _TOKEN.fullmatch(last).groups()
    if i is not None:
        del node[k][int(i)]
    else:
        del node[k]
    return d


def setv(doc, path, value):
    d = copy.deepcopy(doc)
    node, last = _walk(d, path)
    node[last] = value
    return d


def known_valid(base):
    """Configurations the CTS says load. Used only by the mock engine's golden mode."""
    p012 = cfg007(base, 0.8)
    p013 = cfg007(base, 0.9, ids=False)
    p014 = f_ds(base)
    return [base, f_retry(base), f_ds(base), f_ds(base, mechanisms=True), f_seed(base),
            p012, p013, p014]
