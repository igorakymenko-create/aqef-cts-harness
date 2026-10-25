# AQEF CTS harness

Runs the [AQEF](https://github.com/igorakymenko-create/AQEF) Conformance Test
Specification (CTS) against an AQEF engine through its REST API. It writes a run
report and evidence in the form the CTS Harness Contract defines, and verifies the
report with the AQEF repository's own `validate.py` before the run ends.

Version 0.5.0, for AQEF 1.0-CR1, CTS 1.0-CR1, Harness Contract 0.8. It drives
every test of the CTS:
- the automated ones, through the engine's API and the scripted subject and Judges;
- the Inspection and Declaration ones, by collecting the evidence a reviewer needs and
  applying the reviewer's records (CTS 1.8).

It was used to check [aqef-reference-engine](https://github.com/igorakymenko-create/aqef-reference-engine)
slice by slice. The current run, CTS 1.0-CR1 against `slice-11`, is in
[`runs/r261024202325/`](runs/r261024202325/): 189 passed, none failed, 36 not
applicable, none left unrun. Its evidence is `evidence.zip` there, to be unpacked beside
`report.json` before verifying it. The earlier runs, of WD9 (`r261024144559`) and WD10
(`r261024172943`), are kept.

The harness knows an engine only through Appendix C and the settings in
`harness.yaml`. Only `setup/` is specific to aqef-reference-engine.

## Setup

```
pip install -r requirements.txt
cp harness.example.yaml harness.yaml     # then check every value
```

`aqef_repo` points to a checkout of the AQEF repository at the version under test. The
harness reads the CTS from it:
- F-BASE comes from the CTS text;
- the test inventory, the schemas, and the validator come from `conformance-tests/`.

For aqef-reference-engine, `setup/start_reference_engine.sh`, run from the engine's
checkout, does three things:
- starts the engine;
- maps the CTS model identifiers to this harness;
- creates the CTS Principals (`setup/bootstrap_reference_engine.py`).

Another engine needs its own equivalent.

## The scripted subject and Judges

The harness plays the subject (CTS 2.2) and every Judge (CTS 2.3, 13.1, 22) through the
engine's provider interface. It listens on `scripted_port` (default 9100), at
`/subject` and `/judge`. The engine must map every CTS model identifier there:
- `cts-scripted-subject@1`;
- `cts-scripted-judge@1` and `@2`;
- `cts-scripted-judge-a@1` to `-c@1`;
- `cts-reference-judge@1`.

## Check the harness first

Before trusting a run against an engine, run the self-test against the mock engine:

```
AQEF_REPO=../AQEF python -m pytest selftest -q
```

The mock gives known answers to Section 10 up to CT-CFG-025 (CTS WD8) in four modes:
- accepting everything;
- rejecting everything;
- refusing every request for authorization;
- accepting exactly what the CTS says loads.

Every case must come out as expected in every mode. This catches a harness that would
pass an engine that accepts or rejects everything.

## Run

```
python -m aqef_harness.runner --config harness.yaml               # every test
python -m aqef_harness.runner --config harness.yaml --tests CT-DEC  # a section
```

Each run writes a folder `runs/<run id>/`:
- `report.json` and `manifest.json`;
- `evidence/`, with every exchange with the engine and every call the scripted
  services received. Tokens are never recorded;
- `summary.md`, one line per case, for triage.

The exit status is 0 when the report verifies, and 2 when it does not.

## How outcomes are decided

The CTS decides. The harness adds only rules that turn a would-be PASS into NOT_RUN,
never into FAIL:
- **Control.** Before a test that expects a configuration to be rejected, the
  unchanged starting configuration is loaded in a Project of its own (CTS 1.6). If that
  is rejected, the case is NOT_RUN (`SETUP_FAILED`).
- **Authorization.** A 401 or 403 never counts as rejecting a configuration (CTS 1.5).
- **Reviews.** Inspection and Declaration tests stay NOT_RUN
  (`MANUAL_REVIEW_PENDING`) until `manual_reviews` names a record for them. The record
  is then stored as the case's evidence.

## Reviews

The CTS 1.8 review records for the Inspection and Declaration tests are in `reviews/`.
Each names its reviewer. A reviewer that cannot sign has its records signed by the
project owner (Harness Contract 0.7, §13): an attestation in `reviews/`, added by an
authenticated commit, which is the records' `signature_ref`.

| Records | Tests | Attestation | Signed by commit |
|---|---|---|---|
| `wd9-slice11-reviews.json` (unchanged), `wd9-slice11-reviews.signed.json` (with `signature_ref`) | eight, CTS WD9 | `ATTESTATION.md` | `b99f9cb` |
| `wd10-api003-review.json` | CT-API-003, CTS WD10 | `ATTESTATION-WD10.md` | the commit that adds them |

`wd10-all-reviews.json` is the nine records together, as runs `r261024172943` and
`r261024202325` applied them. The nine tests they decide are unchanged in CTS 1.0-CR1.

## Layout

| Path | Content |
|---|---|
| `aqef_harness/runner.py` | Plan, run, report, verification |
| `aqef_harness/core.py` | Case context and the outcome rules above |
| `aqef_harness/adapter_rest.py` | Appendix C mapping; every exchange recorded |
| `aqef_harness/evidence.py` | Evidence store and manifest (RFC 8785) |
| `aqef_harness/scripted.py` | Scripted subject and Judges |
| `aqef_harness/fixtures.py` | CTS fixtures as data |
| `aqef_harness/tests_*.py` | The tests, by CTS section |
| `aqef_harness/tests_inspect.py` | Evidence collection and review records for CTS 1.8 |
| `mock/`, `selftest/` | Known-answer mock engine and the self-test |
| `setup/` | Starting aqef-reference-engine and creating the CTS Principals |
| `runs/`, `reviews/` | The published final run and its review records |

## License

Apache 2.0. The AQEF specification and its Conformance Test Specification are CC BY
4.0, in their own repository.
