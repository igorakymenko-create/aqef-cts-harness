# Run r261110132118

aqef-reference-engine slice-15 (39201b3); AQEF 1.0-CR1.2; CTS 1.0-CR1.2; harness 0.9.0

Cases: FAIL 0, NOT_RUN 3, PASS 7, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-ABD-001 | PASS | all 1 variants rejected; F-ACT loads |
| CT-ABD-002 | PASS | all 6 variants rejected; F-ACT loads |
| CT-ABD-003 | PASS | nothing reached cts-outside.example; attempt recorded {'target': 'https://cts-outside.example/x', 'blocked': True, 'tripwire': False}; Boundary Validator fail; no Judge call |
| CT-ABD-004 | PASS | Tripwire touch recorded {'target': 'https://cts-trip.example/login', 'blocked': False, 'tripwire': True}; Boundary Validator fail |
| CT-ABD-005 | PASS | recorded as a stub call; no attempt; Boundary Validator pass; nothing reached beyond the stub |
| CT-ABD-006 | PASS | the Report lists cts-env-act as unenforced, and the Tripwire touch with its target |
| CT-ABD-007 | NOT_RUN | the implementation's statement was collected; evidence collected for review (CTS 1.8) |
| CT-ABD-008 | NOT_RUN | the first call was allowed and the second denied (Automated); whether the documentation states the syntax and predicts both is for the reviewer; evidence collected for review (CTS 1.8) |
| CT-TTP-001 | PASS | regression-gate failed (value 0.5, reasons ['threshold']); both Executions record the same configuration |
| CT-TTP-002 | NOT_RUN | regression-gate pass with the steps in the opposite order (Automated); what the comparison judged is for the reviewer; evidence collected for review (CTS 1.8) |

Report verification: OK
