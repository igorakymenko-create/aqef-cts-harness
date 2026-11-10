# Run r261110122627

aqef-reference-engine slice-14.1 (eeccb83); AQEF 1.0-CR1.2; CTS 1.0-CR1.2; harness 0.8.0

Cases: FAIL 0, NOT_RUN 0, PASS 6, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-DSR-001 | PASS | all 3 variants rejected; the complete one loads |
| CT-DSR-002 | PASS | all 6 variants rejected; the complete one loads |
| CT-DSR-003 | PASS | both Executions sent Gen-1; ds-gen@1.0.0 unchanged; second generation accepted, new version 1.0.1 with rows [{'id': 'gen-2', 'variables': {'query': 'Gen-2'}}]; versions ['1.0.0'] -> ['1.0.0', '1.0.1'] |
| CT-DSR-004 | PASS | loaded without prompt; the subject received the captured Prompt, Hello |
| CT-DSR-005 | PASS | the generation was reported as failed (502: {"detail": "Dataset generation returned invalid or duplicate Rows"}); no ds-gen@2.0.0 (versions ['1.0.0']) |
| CT-SDK-002 | PASS | 3 tests through REST and through the SDK of python: same outcomes, same statuses, same recorded Results and GateResults |

Report verification: OK
