# Run r261111153723

aqef-reference-engine slice-16 (9f58330); AQEF 1.0-CR1.2; CTS 1.0-CR1.2; harness 0.10.0

Cases: FAIL 0, NOT_RUN 1, PASS 2, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-REL-024 | PASS | run 1: the evaluation failed, the override was recorded while the pipeline waited, then the pipeline passed shown as pass_with_override (job success); run 2: functional-gate failed without an override and the pipeline failed (job failure) |
| CT-REL-025 | PASS | the review was not answered; semantic-gate fail; the pipeline failed after 47.552 s (timeout 45 s, budget 75 s); job failure |
| CT-REL-037 | NOT_RUN | the integration's configuration and the platform's records were collected; evidence collected for review (CTS 1.8) |

Report verification: OK
