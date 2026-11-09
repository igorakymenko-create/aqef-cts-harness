"""Self-test for CT-RUI-001: the reference-UI driver, but it authors one value
differently (the Expectation's confidence_threshold, 0.85 for 0.8). Pointed to by
ui.driver, it must make CT-RUI-001 FAIL; a harness that still reports PASS compares
nothing."""
import copy, importlib.util
spec = importlib.util.spec_from_file_location("real", str(__import__("pathlib").Path(__file__).resolve().parents[1] / "setup" / "ui_reference_ui.py"))
real = importlib.util.module_from_spec(spec); spec.loader.exec_module(real)
def author_visually(ui_url, project_doc, suite, scenario):
    s = copy.deepcopy(scenario)
    s["contract"]["expectations"][0]["confidence_threshold"] = 0.85
    return real.author_visually(ui_url, project_doc, suite, s)
