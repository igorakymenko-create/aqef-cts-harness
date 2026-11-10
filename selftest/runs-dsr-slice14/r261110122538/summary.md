# Run r261110122538

aqef-reference-engine slice-14 (9749393), self-test: before slice 14.1; AQEF 1.0-CR1.2; CTS 1.0-CR1.2; harness 0.8.0

Cases: FAIL 1, NOT_RUN 4, PASS 0, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-DSR-001 | NOT_RUN | the F-BASE with a complete ds-gen was rejected, so a rejection of the modified one shows nothing |
| CT-DSR-002 | NOT_RUN | the F-BASE with a complete ds-replay was rejected, so a rejection of the modified one shows nothing |
| CT-DSR-003 | NOT_RUN | ds-gen@1.0.0 could not be generated (422) |
| CT-DSR-004 | FAIL | the configuration was rejected (422): {"detail": [{"type": "value_error", "loc": ["body", "datasets", 0], "msg": "Value error, Register non-static Dataset versions through the Dataset API", "input": {"name": "ds-replay", "version": "1.0.0", "source": "production_replay", "capture": {"source": "cts-capture", "date_range": ["2026-10-01",  |
| CT-DSR-005 | NOT_RUN | ds-gen@1.0.0 could not be generated (422) |

Report verification: OK
