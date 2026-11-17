# Run r261117194515

aqef-reference-engine slice-16 (9f58330); AQEF 1.0-CR1.4; CTS 1.0-CR1.4; harness 0.12.1

Cases: FAIL 0, NOT_RUN 0, PASS 3, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-REL-024 | PASS | run 1: the evaluation failed, the override was recorded while the pipeline waited, then the pipeline passed shown as pass_with_override (job success); run 2: functional-gate failed without an override and the pipeline failed (job failure) |
| CT-REL-025 | PASS | the review was not answered; semantic-gate fail; the pipeline failed after 47.609 s (timeout 45 s, budget 75 s); job failure |
| CT-REL-037 | PASS | review rel-037-gemini-1 by reviewer://google/gemini-3.8-flash: No ambiguities were found in the specification or test fixture text. The implementation strictly adheres to Volume XIII by maintaining an architectural separation where Quality Gates are authored, sto |

Report verification: OK
