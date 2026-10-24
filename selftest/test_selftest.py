"""Harness self-test against the mock engine: every case must come out as the mock's
known answers say, and every report must verify with validate.py.

    AQEF_REPO=/path/to/AQEF python -m pytest selftest -q
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mock"))
from aqef_harness import config as C  # noqa: E402
from aqef_harness import runner  # noqa: E402
import mock_engine  # noqa: E402

REPO = pathlib.Path(os.environ.get("AQEF_REPO", ROOT.parent / "AQEF")).resolve()
CTS = REPO / "conformance-tests"

NEGATIVE = ["CT-CFG-002", "CT-CFG-003", "CT-CFG-004", "CT-CFG-005", "CT-CFG-006",
            "CT-CFG-009", "CT-CFG-010", "CT-CFG-011", "CT-CFG-015", "CT-CFG-017",
            "CT-CFG-019", "CT-CFG-020", "CT-CFG-021", "CT-CFG-022", "CT-CFG-024"]
C025 = [f"CT-CFG-025.{i:02d}" for i in range(1, 26) if i != 24]   # .24: dataset_mechanism, unclaimed

EXPECTED = {
    "golden": {**{c: "PASS" for c in ["CT-CFG-001", "CT-CFG-007", "CT-CFG-008", "CT-CFG-014",
                                      "CT-CFG-018", "CT-CFG-023"] + NEGATIVE + C025},
               "CT-CFG-012": "NOT_RUN", "CT-CFG-013": "NOT_RUN", "CT-CFG-016": "NOT_RUN"},
    "accept-all": {**{c: "FAIL" for c in NEGATIVE + C025 + ["CT-CFG-014", "CT-CFG-018", "CT-CFG-023"]},
                   "CT-CFG-001": "PASS", "CT-CFG-007": "NOT_RUN", "CT-CFG-008": "NOT_RUN",
                   "CT-CFG-012": "NOT_RUN", "CT-CFG-013": "NOT_RUN", "CT-CFG-016": "NOT_RUN"},
    "reject-all": {**{c: "NOT_RUN" for c in NEGATIVE + C025 + ["CT-CFG-007", "CT-CFG-008",
                                                               "CT-CFG-016", "CT-CFG-018", "CT-CFG-023"]},
                   "CT-CFG-001": "FAIL", "CT-CFG-012": "FAIL", "CT-CFG-013": "FAIL",
                   "CT-CFG-014": "FAIL"},
    "refuse-auth": {c: "NOT_RUN" for c in ["CT-CFG-%03d" % i for i in range(1, 25)] + C025},
}


# The mock knows the rules of Section 10 up to CT-CFG-025 (CTS WD8); CT-CFG-026 to 028
# (WD9) are checked against the reference engine only.
SECTION_10 = ["CT-CFG-%03d" % i for i in range(1, 26)]


def cfg_for(port):
    return C.Config(aqef_repo=REPO, base_url=f"http://127.0.0.1:{port}",
                    tokens={"P-APPROVER": "t"}, sut_name="mock", sut_version="0",
                    capabilities_claimed=["seeded_controls"], scripted_port=0,
                    engine_slices_done=1)   # the mock implements configuration only


@pytest.mark.parametrize("mode", list(EXPECTED))
def test_mode(mode, tmp_path):
    srv = mock_engine.serve(mode, CTS)
    try:
        out, report, errs = runner.run(cfg_for(srv.server_port), SECTION_10, tmp_path, quiet=True)
    finally:
        srv.shutdown()
    assert errs == [], errs
    got = {c["case_id"]: (c["outcome"], c.get("reason", "")) for c in report["cases"]}
    wrong = {k: (got[k], v) for k, v in EXPECTED[mode].items() if got[k][0] != v}
    assert not wrong, wrong
    assert set(got) - {"CT-CFG-025.24"} == set(EXPECTED[mode])
    assert got["CT-CFG-025.24"][0] == "NOT_APPLICABLE"


def test_unclaimed_capability_is_not_applicable(tmp_path):
    srv = mock_engine.serve("golden", CTS)
    try:
        cfg = cfg_for(srv.server_port)
        cfg.capabilities_claimed = []
        _, report, errs = runner.run(cfg, ["CT-CFG-025"], tmp_path, quiet=True)
    finally:
        srv.shutdown()
    assert errs == []
    c = {c["case_id"]: c for c in report["cases"]}["CT-CFG-025.25"]
    assert (c["outcome"], c["reason_code"]) == ("NOT_APPLICABLE", "CAPABILITY_NOT_CLAIMED")
