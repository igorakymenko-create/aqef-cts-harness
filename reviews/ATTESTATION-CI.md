# Attestation of the CTS 1.8 review record for CT-REL-037

I, Igor Akymenko, owner of the AQEF project and of this repository, attest the following.

## The record

| Record | Method | Decision |
|---|---|---|
| `CT-REL-037.gemini-1.review.json` | inspection | PASS (`VERIFIED`) |

`reviews/ci-reviews.json` holds the same record, for the harness.

It is against CTS 1.0-CR1.2. The reviewed evidence is report `r261111153723`, from
GitHub Actions run 43049912906 of `.github/workflows/cts-ci-github.yml`:
aqef-reference-engine slice-16 (`9f58330`), harness 0.10.0. The report is in `runs/`.

## The reviewer

1. **Who.** Google Gemini (`reviewer://google/gemini-3.8-flash`, as it reported its model),
   in the Gemini web app, in a new conversation. It did not write the engine, the CTS, or
   this harness. The engine was written by OpenAI Codex. Gemini can neither sign nor hold
   an account, so I sign for it.
2. **What it was given.** A pack (`rel037-review`):
   - CT-REL-037, the test it reuses (CT-REL-024), and CTS 1.8;
   - Volume XIII;
   - the harness evidence of the reviewed report;
   - extracts of the integration's `action.yml` and of the pipeline workflow;
   - the SHA-256 of every file.

   It was told to decide only from the pack, and to record an ambiguity rather than
   resolve it.

## What I changed in the record

3. **`signed_at`.** I set it to the time I received the record.
4. **Nothing else.**
   - `signature_ref` reads `pending://owner-attestation`. The commit that adds this file
     and the record is its signature (Harness Contract §13).

## Two points in the record, stated here and not changed in it

The owner's assistant (Claude, Anthropic) checked the record's references against the
pack. Its substance holds:
- the Gates are defined in the engine's configuration and evaluated by the engine;
- the integration's step only runs `python -m aqef_client.ci.github`, and neither file
  holds a threshold or Gate logic;
- the platform recorded `success` for rel024-a (overridden, `pass_with_override`) and
  `failure` for rel024-b.

Two details are inexact, and neither bears on the decision:
5. **Item 1** calls the step at `integration-action.yml` lines 49–62 "AQEF Quality Gates".
   That step is named "Translate AQEF Gates". "AQEF Quality Gates" is the Action's own name
   (line 1) and the name of the step in `pipeline-workflow.yml` (line 56).
6. **Item 2** places "subject SR-EMPTY" in `CT-REL-037-010.json`. That file shows
   `functional-gate` with status `fail`. The subject is named in `CT-REL-037-008.json` and
   `CT-REL-037-013.json`.

## Where the record is applied

7. The record is applied in the next run of `.github/workflows/cts-ci-github.yml` started
   after this commit, with `harness.ci-github.yaml` (`manual_reviews:
   reviews/ci-reviews.json`). That run uses the same engine, slice-16. It uses the CTS at
   the `aqef-ref` it is started with. CT-REL-024 and CT-REL-037 are word for word the same
   in 1.0-CR1.2 and 1.0-CR1.4. Its report is added to `runs/` with its run number.

Signed through that commit, 2026-11-17.
