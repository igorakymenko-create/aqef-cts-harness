# Run r261116204806

aqef-reference-engine slice-17 (c3b9263); AQEF 1.0-CR1.4; CTS 1.0-CR1.4; harness 0.12.0

Cases: FAIL 0, NOT_RUN 1, PASS 0, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-ASM-014 | NOT_RUN | cts-crash raises on every call (CTS 2.5), so it fails the engine's registration probe (Volume XVI) and cannot be registered (422: {"detail": "Validator Plugin repeatability probe did not return a valid Result"}); the engine documents no fault hook |

Report verification: OK
