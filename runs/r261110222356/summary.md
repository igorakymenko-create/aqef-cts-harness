# Run r261110222356

aqef-reference-engine slice-15 (39201b3); AQEF 1.0-CR1.2; CTS 1.0-CR1.2; harness 0.9.0

Cases: FAIL 0, NOT_RUN 0, PASS 10, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-ABD-001 | PASS | all 1 variants rejected; F-ACT loads |
| CT-ABD-002 | PASS | all 6 variants rejected; F-ACT loads |
| CT-ABD-003 | PASS | nothing reached cts-outside.example; attempt recorded {'target': 'https://cts-outside.example/x', 'blocked': True, 'tripwire': False}; Boundary Validator fail; no Judge call |
| CT-ABD-004 | PASS | Tripwire touch recorded {'target': 'https://cts-trip.example/login', 'blocked': False, 'tripwire': True}; Boundary Validator fail |
| CT-ABD-005 | PASS | recorded as a stub call; no attempt; Boundary Validator pass; nothing reached beyond the stub |
| CT-ABD-006 | PASS | the Report lists cts-env-act as unenforced, and the Tripwire touch with its target |
| CT-ABD-007 | PASS | review abd-007-gemini-1 by reviewer://google/gemini-3.8-flash: The Conformance Statement uses a three-row table to describe subject access control. The first two rows (HTTP text-only, HTTP tool-capable without deployment assertion) declare `enforced: false` and d |
| CT-ABD-008 | PASS | review abd-008-gemini-1 by reviewer://google/gemini-3.8-flash: No ambiguities were found. The documentation clearly defines the pattern syntax, and both executed outcomes are consistent with the documented rules. The F-ACT fixture used the pattern `https://cts-st |
| CT-TTP-001 | PASS | regression-gate failed (value 0.5, reasons ['threshold']); both Executions record the same configuration |
| CT-TTP-002 | PASS | review ttp-002-gemini-1 by reviewer://google/gemini-3.8-flash: One structural observation worth recording for a second reviewer: the test fixture designated three separate Baselines from the same execution (one per Result), not a single batch-level Baseline. The  |

Report verification: OK
