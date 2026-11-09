"""UI driver for aqef-reference-ui (CT-RUI-001). Specific to that UI, as
bootstrap_reference_engine.py is specific to aqef-reference-engine.

It authors one Scenario in the Visual Test Designer, through the UI's own forms and
its own Review & Apply path, and returns what it observed: screenshots with the URL
and capture time in a strip outside the page, the page's visible text, the YAML diff
the UI showed, and the outcome the UI reported. It decides nothing about the test.

How this UI works, from its README: the browser edits YAML files in a local
workspace (served at /workspace), and Apply sends them to the engine through a proxy
(/api). The workspace must therefore hold the Project the Scenario is added to. The
driver writes the fixture there first, as a person would open the Project's file."""
import datetime
import io
import json

import yaml
from playwright.sync_api import sync_playwright

FILE = "project.yaml"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _caption(png, url, when):
    """The screenshot with a strip above it naming the URL and the capture time."""
    from PIL import Image, ImageDraw
    im = Image.open(io.BytesIO(png)).convert("RGB")
    out = Image.new("RGB", (im.width, im.height + 44), (30, 30, 30))
    d = ImageDraw.Draw(out)
    d.text((10, 6), f"URL: {url}", fill=(255, 255, 255))
    d.text((10, 24), f"Captured (UTC): {when}   caption added by the harness, outside the page",
           fill=(200, 200, 200))
    out.paste(im, (0, 44))
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def _write_workspace(page, project_doc):
    current = page.request.get(f"/workspace/files?path={FILE}")
    etag = current.json().get("etag") if current.ok else None
    content = yaml.safe_dump({"project": project_doc}, sort_keys=False, allow_unicode=True)
    r = page.request.put(f"/workspace/files?path={FILE}",
                         data=json.dumps({"content": content, "expected_etag": etag}),
                         headers={"Content-Type": "application/json"})
    if not r.ok:
        raise RuntimeError(f"workspace write refused: {r.status} {r.text()[:200]}")


def author_visually(ui_url, project_doc, suite, scenario):
    files, log = [], {"steps": [], "engine_requests": []}

    def shot(page, label, full=False):
        when = _now()
        png = page.screenshot(full_page=full)
        files.append({"kind": "screenshot", "ext": "png", "data": _caption(png, page.url, when)})
        files.append({"kind": "other", "ext": "txt",
                      "data": f"URL: {page.url}\nCaptured (UTC): {when}\n\n{page.inner_text('body')}".encode()})
        log["steps"].append({"t": when, "step": label, "url": page.url})

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(base_url=ui_url, viewport={"width": 1440, "height": 1000})
        page.on("request", lambda r: log["engine_requests"].append(
            {"t": _now(), "method": r.method, "url": r.url, "body": r.post_data})
            if "/api/" in r.url and r.method != "GET" else None)
        try:
            page.goto("/")
            _write_workspace(page, project_doc)
            log["steps"].append({"t": _now(), "step": f"workspace file {FILE} holds the fixture Project"})

            page.goto("/#designer")
            page.get_by_role("button", name=FILE, exact=True).wait_for()
            page.get_by_label("Suite", exact=True).select_option(suite)
            page.get_by_label("Scenario name", exact=True).fill(scenario["name"])
            page.get_by_label("Prompt template", exact=True).fill(scenario["prompt"]["template"])
            page.get_by_label("Variables / Dataset binding", exact=True).select_option("variables")
            page.get_by_label("Variables (YAML mapping)", exact=True).fill(
                yaml.safe_dump(scenario.get("variables", {}), sort_keys=False, allow_unicode=True))
            page.get_by_label("Contract source", exact=True).select_option("inline")
            n = 0
            for c in scenario["contract"].get("constraints", []):
                n += 1
                page.get_by_role("button", name="Add Constraint", exact=True).click()
                page.get_by_label(f"Clause {n} Validator", exact=True).select_option(c["validator"])
                page.get_by_label(f"Clause {n} target", exact=True).fill(c["target"])
                page.get_by_label(f"Clause {n} expected", exact=True).fill(
                    yaml.safe_dump(c["expected"], sort_keys=False, allow_unicode=True))
            for e in scenario["contract"].get("expectations", []):
                n += 1
                page.get_by_role("button", name="Add Expectation", exact=True).click()
                page.get_by_label(f"Clause {n} criteria", exact=True).fill(e["criteria"])
                page.get_by_label(f"Clause {n} Judge model", exact=True).fill(e["judge"]["model"])
                page.get_by_label(f"Clause {n} Confidence source", exact=True).select_option(
                    e["judge"]["confidence_source"])
                page.get_by_label(f"Clause {n} Confidence threshold", exact=True).fill(
                    str(e["confidence_threshold"]))
            diff = page.get_by_label("YAML diff", exact=True)
            diff.wait_for()
            log["yaml_diff"] = diff.inner_text()
            shot(page, "Visual Test Designer, form filled, YAML diff shown", full=True)

            page.get_by_role("button", name="Review & Apply", exact=True).click()
            page.get_by_role("region", name="Apply preview").wait_for()
            log["apply_preview"] = page.get_by_role("region", name="Apply preview").inner_text()
            shot(page, "Apply preview", full=True)
            page.get_by_role("button", name="Confirm Apply", exact=True).click()
            done = page.get_by_role("heading", name="Apply complete", exact=True)
            try:
                done.wait_for(timeout=30000)
                saved = True
            except Exception:
                saved = False
            log["outcome"] = page.inner_text("body")[:4000]
            shot(page, "after Confirm Apply", full=True)
        finally:
            browser.close()
    return {"saved": saved, "outcome": log.get("outcome", ""), "files": files, "log": log}
