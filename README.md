# AQEF CTS harness

Runs the [AQEF](https://github.com/igorakymenko-create/AQEF) Conformance Test
Specification (CTS) against an AQEF engine through its REST API. It writes a run
report and evidence in the form the CTS Harness Contract defines, and verifies the
report with the AQEF repository's own `validate.py` before the run ends.

Version 0.6.0, for AQEF 1.0-CR1, CTS 1.0-CR1, Harness Contract 0.8. It drives
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

## Reference UI (CT-RUI-001)

CT-RUI-001 checks that a Scenario authored in a Reference UI's Visual Test Designer is,
once saved, the same as one written in YAML. The test (`aqef_harness/tests_rui.py`) is
generic:
1. It loads F-BASE through the REST API, so that `s-greeting` is the Scenario written in YAML.
2. It has a driver author `s-visual`, with the same content, through the UI's own forms
   and its own save path.
3. It retrieves both Scenarios through the REST API, and compares every field apart from
   the name.
4. It runs the Suite, and compares the effective Contract each Execution froze.

**What is not compared.** Only keys an implementation sets itself (identifiers,
timestamps, version, provenance) are left out of the comparison, and only where both
Scenarios have them. A key present on one side only is always a difference, so a value
the UI invents for the visual Scenario alone is never hidden. The comparison and every
excluded path are stored as evidence.

**The driver.** Everything specific to one UI is in a driver module named in
`harness.yaml` (`ui.driver`). It returns what it observed: screenshots with the URL and
capture time in a strip outside the page, each page's visible text, the YAML diff and
Apply preview the UI showed, and the UI's outcome. A driver that cannot operate the UI
makes the case NOT_RUN (`ADAPTER_GAP`), never FAIL.
- `setup/ui_reference_ui.py` drives
  [aqef-reference-ui](https://github.com/igorakymenko-create/aqef-reference-ui).
- `setup/start_reference_ui.sh`, run from that UI's checkout, starts it as the run needs
  it:
  - the engine it vendors, with the CTS model identifiers mapped to this harness;
  - the CTS Principals and the UI's own Person;
  - an empty workspace;
  - the UI on :3000.

**Self-test.** `selftest/rui001_mutating_driver.py` authors one value differently. Pointed
to by `ui.driver`, it must make CT-RUI-001 FAIL. Its run is in `selftest/runs-rui001/`:
FAIL on `confidence_threshold`, as intended.

**Run.** [`runs/r261108160634/`](runs/r261108160634/): CT-RUI-001 against
aqef-reference-ui `60c354e` (with its vendored engine, slice-12), on AQEF 1.0-CR1. PASS,
and the report verifies with `validate.py`. CT-RUI-002 to 004 are Inspection tests. Their
review records are kept with the UI.

## CLI and SDKs (CT-SDK-001, CT-SDK-002)

Both tests are generic. They know the CLI or SDK only through a driver module named in
`harness.yaml`: `cli.driver`, and `sdk.<language>` for each claimed `sdk:<language>`.
A driver that cannot run makes the case NOT_RUN (`ADAPTER_GAP`), never FAIL.

**CT-SDK-001.** The CLI's traffic goes through a recording proxy (`aqef_harness/proxy.py`).
It records the method, path, query, status and body of each request, and no headers, so no
token is logged.
1. The CLI loads F-BASE, executes `cts-suite`, and evaluates the Gates.
2. The harness checks that each command appears in the proxy log as the matching
   Appendix C operation. A command without it is a FAIL.
3. It then collects, for the reviewer: the CLI's help for every command group, its
   documentation (`cli.docs`), the operations of Appendix C, and the implementation's own
   documentation of its REST API (`cli.api_docs`), for operations beyond Appendix C
   (CTS 1.0-CR1.2).

The case stays NOT_RUN (`MANUAL_REVIEW_PENDING`) until a named reviewer decides whether
every documented command maps to a REST operation (CTS 1.8). The token reaches the CLI
only through `AQEF_TOKEN`.

**CT-SDK-002.** CT-CFG-002, CT-DEC-006 and CT-REL-002 run twice, each in Projects of
their own: once through the REST adapter, and once through an adapter that carries out
every request through the SDK's *named* operation for that route, never through its
low-level request method. Compared:
- each test's outcome;
- the status of every request, in order;
- the Results of every Execution, read back through REST, and every GateResult returned.

Identifiers, references to the Execution, and times are not compared. "Times" includes
measured durations, such as a latency Artifact: those differ between any two runs. Every
path treated as a duration is listed in the evidence.

**Drivers** for aqef-reference-engine's `aqef-client` (slice 13):
- `setup/cli_aqef_client.py`: the `aqef` command; `AQEF_CLI` overrides its path;
- `setup/sdk_aqef_client.py`: the `aqef_client` package; operations are matched by the
  route each method's docstring states.

**Self-tests.** Each must make its test FAIL:
- `selftest/sdk001_local_driver.py`: `execution run` answers locally, without a REST call.
  Run: `selftest/runs-sdk001/`.
- `selftest/sdk002_lying_driver.py`: an SDK that reports a rejected configuration as
  accepted. Run: `selftest/runs-sdk002/`.

**Runs** (`harness.reference-cli-sdk.yaml`), against aqef-reference-engine slice-13
(`7e03ce3`):
- `runs/r261109094028/`: CTS 1.0-CR1, harness 0.7.0. CT-SDK-002 PASS; CT-SDK-001 awaited
  review. The review found two readings of the test; CTS 1.0-CR1.2 clarified it.
- `runs/r261109120325/`: CTS 1.0-CR1.2, harness 0.7.1. The evidence the second review
  decided from.
- `runs/r261109125722/`: the same, with the review applied. **CT-SDK-001 PASS, CT-SDK-002
  PASS.** Review records and attestation: `reviews/CT-SDK-001.*`,
  `reviews/ATTESTATION-CLI-SDK.md`.

An engine the harness cannot reach makes CT-SDK-001 NOT_RUN (`TRANSPORT_FAILED`), never
FAIL: a command that made no call proves nothing while the engine is down.

## Dataset Sources (CT-DSR-001 to 005)

**Scripted services** (`aqef_harness/scripted.py`):
- **generator** (`/generator`):
  - `H-GEN-DSR-003`: the first call returns one row, `query: "Gen-1"`; every later call
    `"Gen-2"`;
  - `generator.malformed`: a valid row and a row without `id` (Harness Contract §9).
- **capture source** (`/capture`): one captured Conversation whose user turn is `Hello`.

The rows are the CTS's. The envelopes, `{"rows": [...]}` and `{"conversations": [...]}`,
are the reference engine's documented protocols (its `docs/DATASETS.md`). For another
engine they are part of its adapter.

`setup/start_reference_engine.sh` maps the model identifier `cts-scripted-generator@1`
and the capture source `cts-capture` to these services. `setup/bootstrap_reference_engine.py`
grants the engine's own Permission for Production Replay data, `production_replay_read`,
to the CTS Principals that load, execute and clean up.

**Generating again** (CT-DSR-003, CT-DSR-005) uses Appendix C,
`POST .../datasets/ds-gen/versions`. The request, the response, and the versions read
before and after are the evidence (Harness Contract §16, `generate_dataset`).

**Rejection tests** (CT-DSR-001, CT-DSR-002) first load the complete Dataset as a setup
check (CTS 1, "Rejection tests"). An engine that rejects every generated or replay
Dataset is NOT_RUN there, not PASS.

**Self-test.** `selftest/runs-dsr-slice14/` is the run against engine slice 14, before
slice 14.1 accepted non-static Datasets in a Project's configuration:
- CT-DSR-001, 002, 003 and 005 are NOT_RUN at their setup checks;
- CT-DSR-004 FAILs: the configuration was rejected.

**Run.** `runs/r261110122627/`, `harness.reference-engine-14.yaml`, engine slice 14.1
(`eeccb83`), CTS 1.0-CR1.2: CT-DSR-001 to 005 PASS, and CT-SDK-002 PASS again, now with
the SDK's traffic through a recording proxy and its versions recorded (Harness Contract
§16, `run_sdk`).

## Action Boundary (CT-ABD-001 to 008, CT-TTP-002)

**Scripted subject** (`aqef_harness/scripted.py`):
- `SR-CALL(url)`: requests `http_get` with `url`, then answers `"Done."` after the tool's
  response or refusal;
- `SR-TRAJ(url1,url2)`: the two trajectories of CT-TTP-002.

The `{"tool_calls": [...]}` envelope is the reference engine's documented protocol (its
`docs/ACTION-BOUNDARY.md`). For another engine it is part of the adapter.

**Tool targets.** `cts-stub.example`, `cts-trip.example` and `cts-outside.example` are
hosted by the harness (Harness Contract §17). An engine that carries out a `sandbox` or
`real` call sends it to the harness's tool executor (`/executor`). That log is the
record of what reached each target, including "the log of `cts-outside.example`".
Nothing is sent to a real system.

`setup/start_reference_engine.sh` configures the executor, and names
`cts-scripted-subject@1` as a subject whose access the harness controls
(`AQEF_CONTROLLED_SUBJECTS`). Without that, the engine rejects `enforced: true`.

**F-ACT's patterns** are already in the reference engine's syntax: a terminal `/*` matches
the literal prefix.

**Inspection and Declaration parts.** These stay NOT_RUN (`MANUAL_REVIEW_PENDING`) until a
reviewer decides them (CTS 1.8):
- CT-ABD-007: the Conformance Statement;
- CT-ABD-008: the pattern documentation, with the two outcomes;
- CT-TTP-002: how the comparison was made.

**Designating an Execution as a Baseline** (CT-TTP-001, CT-TTP-002). Appendix A §A.11
designates an Execution. The reference engine records a Baseline per Result and compares
clause by clause. The harness therefore designates every Result of the Execution
(`designate_execution` in `tests_dec.py`).

Harness 0.8.0 and earlier designated only the Judge's Result. The Regression Gate then
had nothing to compare the other clauses with, and failed as `insufficient_basis`
(`value: not_computed`). CT-TTP-001's Expected ("`regression-gate` fails") was met, but
not by a detected regression. From 0.9.0 the Gate fails on the comparison itself:
`value 0.5`, `reasons: [threshold]`.

**Self-test.** `selftest/runs-abd-slice14/` is the run against engine slice 14.1, before
slice 15. Every case is NOT_RUN, because the engine rejected F-ACT, and none is PASS.

**Runs** (`harness.reference-engine-15.yaml`), engine slice 15 (`39201b3`), CTS 1.0-CR1.2:
- `runs/r261110132118/`: CT-ABD-001 to 006 and CT-TTP-001 PASS. CT-ABD-007, CT-ABD-008
  and CT-TTP-002 awaited review. This is the evidence the reviewer decided from.
- `runs/r261110222356/`: the same, with the three review records applied. **All ten PASS.** Records
  and attestation: `reviews/CT-ABD-007.*`, `reviews/CT-ABD-008.*`,
  `reviews/CT-TTP-002.*`, `reviews/ATTESTATION-ABD.md`.

## CI/CD on GitHub Actions (CT-REL-024, CT-REL-025, CT-REL-037)

These tests need a pipeline on the platform itself (Harness Contract §16, `run_pipeline`).
The pipeline is a fixture the tester supplies: `.github/workflows/cts-ci-github.yml` in
this repository. It runs only when started by hand: Actions → "CTS ci_cd:github_actions"
→ Run workflow.

**Pipeline jobs.** Each `pipeline (<run>)` job is one pipeline run, on its own
GitHub-hosted runner:

| Run | Test | What the harness's controller does while the pipeline runs |
|---|---|---|
| `rel024-a` | CT-REL-024 | Fixture: CT-REL-006's configuration (`J-FAIL-90`). Waits for the pipeline's own Gate evaluation, then overrides `semantic-gate` on that GateResult, as `P-APPROVER` |
| `rel024-b` | CT-REL-024 | The same with `SR-EMPTY`, so `functional-gate` fails as well. Overrides `semantic-gate` only |
| `rel025` | CT-REL-025 | Fixture: CT-DEC-011's, with no `review_timeout`. Does not answer the review. Pipeline timeout 45 s, grace 30 s |

Each pipeline job:
1. starts the engine and the controller (`python -m aqef_harness.ci_github prepare`);
2. runs the integration under test, `igorakymenko-create/aqef-reference-engine@slice-16`,
   on that batch;
3. always records the Action step's result, its outputs, its job summary, and the time
   it took on the runner's monotonic clock (`collect`).

The job's own success or failure is the platform-native status. The token reaches the
Action only through its input, and is masked in the log.

**Report job.** It reads the platform's record of the run
(`gh api repos/.../actions/runs/{id}/jobs`), downloads the pipeline jobs' artifacts, and
runs the harness (`harness.ci-github.yaml`). There, `aqef_harness/tests_ci.py` decides
CT-REL-024 and 025. CT-REL-037 is an Inspection and awaits a reviewer: the harness
collects the workflow, the Action's `action.yml`, and the platform's records. The
verified run report is the `cts-report` artifact.

**Checked before the first run on GitHub.** The three pipeline runs were simulated on one
machine, with the same `prepare`, entry point, and `collect`:
- `rel024-a`: `pass_with_override` after the override;
- `rel024-b`: `fail`;
- `rel025`: `fail` after 45.2 s.

A simulated platform record is not evidence for the tests, so that run is not published.

## Layout

| Path | Content |
|---|---|
| `aqef_harness/runner.py` | Plan, run, report, verification |
| `aqef_harness/core.py` | Case context and the outcome rules above |
| `aqef_harness/adapter_rest.py` | Appendix C mapping; every exchange recorded |
| `aqef_harness/evidence.py` | Evidence store and manifest (RFC 8785) |
| `aqef_harness/tests_rui.py` | CT-RUI-001, through a UI driver |
| `aqef_harness/tests_sdk.py`, `aqef_harness/proxy.py` | CT-SDK-001 and CT-SDK-002; the recording proxy |
| `aqef_harness/tests_dsr.py` | CT-DSR-001 to 005 |
| `aqef_harness/tests_abd.py` | CT-ABD-001 to 008, CT-TTP-002 |
| `aqef_harness/ci_github.py`, `aqef_harness/tests_ci.py`, `.github/workflows/cts-ci-github.yml` | CT-REL-024, 025, 037 on GitHub Actions |
| `setup/cli_aqef_client.py`, `setup/sdk_aqef_client.py` | CLI and SDK drivers for aqef-reference-engine's `aqef-client` |
| `setup/ui_reference_ui.py`, `setup/start_reference_ui.sh` | Driver and start script for aqef-reference-ui |
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
