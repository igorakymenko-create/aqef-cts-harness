# Run r261024144559

aqef-reference-engine slice-11; AQEF 0.41.5; CTS WD9; harness 0.3.0

Cases: FAIL 0, NOT_RUN 1, PASS 178, NOT_APPLICABLE 33

| Case | Outcome | Reason |
|---|---|---|
| CT-ABD-001 | NOT_APPLICABLE | capability action_boundary is not claimed |
| CT-ABD-002 | NOT_APPLICABLE | capability action_boundary is not claimed |
| CT-ABD-003 | NOT_APPLICABLE | capability action_boundary is not claimed |
| CT-ABD-004 | NOT_APPLICABLE | capability action_boundary is not claimed |
| CT-ABD-005 | NOT_APPLICABLE | capability action_boundary is not claimed |
| CT-ABD-006 | NOT_APPLICABLE | capability action_boundary is not claimed |
| CT-ABD-007 | NOT_APPLICABLE | capability action_boundary is not claimed |
| CT-ADM-001 | PASS |  |
| CT-ADM-002 | PASS | variants share one Project; CTS asks one each, which changes nothing observed here |
| CT-ADM-003 | PASS |  |
| CT-ADM-004 | PASS |  |
| CT-ADM-005 | PASS |  |
| CT-ADM-006 | PASS | member identities read from the panel Result's member_results |
| CT-ADM-007 | PASS |  |
| CT-API-001 | PASS | p = 1 (the engine's documented minimum); offset/limit on all three; s-1's two clauses already give more than p Results, so no extra Constraints were added |
| CT-API-002 | PASS | history read through the same paths after deletion |
| CT-ASM-001 | PASS |  |
| CT-ASM-002 | PASS |  |
| CT-ASM-003 | PASS |  |
| CT-ASM-004 | PASS |  |
| CT-ASM-005 | PASS |  |
| CT-ASM-006 | PASS |  |
| CT-ASM-007 | PASS |  |
| CT-ASM-008 | PASS |  |
| CT-ASM-009 | PASS | no re-check offered: two Executions with identical Responses |
| CT-ASM-010 | PASS | review review-openai-ct-asm-010 by reviewer://openai/gpt-6: Declaration verified against offered five built-ins. Runtime determinism across every deployed dependency is not measured by this review; the declaration is supported by documentation and inspected im |
| CT-ASM-011 | PASS |  |
| CT-ASM-012 | PASS |  |
| CT-ASM-013 | PASS |  |
| CT-ASM-014 | NOT_RUN | the engine offers no way to define cts-crash (its Custom Validators are declarative) and documents no fault hook (CTS CT-ASM-014) |
| CT-ASM-015 | PASS |  |
| CT-ASM-016 | PASS |  |
| CT-ASM-017 | PASS | review review-openai-ct-asm-017 by reviewer://openai/gpt-6: Prevention mode: both model-call registration attempts were rejected (HTTP 422); allowlisted declarative operations only. Not a claim that arbitrary executable plugin code was exercised. |
| CT-ASM-018 | NOT_APPLICABLE | the engine offers no re-check of a Validator on stored Evidence (permitted, CTS 1.2) |
| CT-ASM-019 | PASS | (a) assertions 3 |
| CT-ASM-020 | PASS | variant: expected {minimum: "one"}; the engine documents null or {} for a parameterless Custom Validator |
| CT-CFG-001 | PASS |  |
| CT-CFG-002 | PASS |  |
| CT-CFG-003 | PASS |  |
| CT-CFG-004 | PASS |  |
| CT-CFG-005 | PASS |  |
| CT-CFG-006 | PASS |  |
| CT-CFG-007 | PASS |  |
| CT-CFG-008 | PASS |  |
| CT-CFG-009 | PASS |  |
| CT-CFG-010 | PASS |  |
| CT-CFG-011 | PASS |  |
| CT-CFG-012 | PASS |  |
| CT-CFG-013 | PASS |  |
| CT-CFG-014 | PASS |  |
| CT-CFG-015 | PASS |  |
| CT-CFG-016 | PASS |  |
| CT-CFG-017 | PASS |  |
| CT-CFG-018 | PASS |  |
| CT-CFG-019 | PASS |  |
| CT-CFG-020 | PASS |  |
| CT-CFG-021 | PASS |  |
| CT-CFG-022 | PASS |  |
| CT-CFG-023 | PASS |  |
| CT-CFG-024 | PASS |  |
| CT-CFG-025.01 | PASS |  |
| CT-CFG-025.02 | PASS |  |
| CT-CFG-025.03 | PASS |  |
| CT-CFG-025.04 | PASS |  |
| CT-CFG-025.05 | PASS |  |
| CT-CFG-025.06 | PASS |  |
| CT-CFG-025.07 | PASS |  |
| CT-CFG-025.08 | PASS |  |
| CT-CFG-025.09 | PASS |  |
| CT-CFG-025.10 | PASS |  |
| CT-CFG-025.11 | PASS |  |
| CT-CFG-025.12 | PASS |  |
| CT-CFG-025.13 | PASS |  |
| CT-CFG-025.14 | PASS |  |
| CT-CFG-025.15 | PASS |  |
| CT-CFG-025.16 | PASS |  |
| CT-CFG-025.17 | PASS |  |
| CT-CFG-025.18 | PASS |  |
| CT-CFG-025.19 | PASS |  |
| CT-CFG-025.20 | PASS |  |
| CT-CFG-025.21 | PASS |  |
| CT-CFG-025.22 | PASS |  |
| CT-CFG-025.23 | PASS |  |
| CT-CFG-025.24 | NOT_APPLICABLE | capability dataset_mechanism:edge_cases is not claimed |
| CT-CFG-025.25 | PASS |  |
| CT-CFG-026 | PASS |  |
| CT-CFG-027 | PASS |  |
| CT-CFG-028 | PASS | unclaimed: data_mutation, fuzzing, edge_cases, adversarial |
| CT-DEC-001 | PASS |  |
| CT-DEC-002 | PASS |  |
| CT-DEC-003 | PASS |  |
| CT-DEC-004 | PASS |  |
| CT-DEC-005 | PASS |  |
| CT-DEC-006 | PASS |  |
| CT-DEC-007 | PASS |  |
| CT-DEC-008 | PASS |  |
| CT-DEC-009 | PASS | review review-openai-ct-dec-009 by reviewer://openai/gpt-6: Inspected documented Gate/Contract/Aggregation configuration and decision.py; non-actionable results add a failure reason and are not included among usable entries. This is static inspection, not an e |
| CT-DEC-010 | PASS |  |
| CT-DEC-011 | PASS |  |
| CT-DEC-012 | PASS |  |
| CT-DEC-013 | PASS |  |
| CT-DEC-014 | PASS |  |
| CT-DEC-015 | PASS |  |
| CT-DEC-016 | PASS |  |
| CT-DEC-017 | PASS |  |
| CT-DEC-018 | PASS |  |
| CT-DEC-019 | PASS |  |
| CT-DEC-020 | PASS |  |
| CT-DEC-021 | PASS | review review-openai-ct-dec-021 by reviewer://openai/gpt-6: No statistical interval is exposed in checked GateResults/Reports; the negative prohibition is satisfied vacuously. Report descriptions refer to application of Oracle Confidence to assessment, not to  |
| CT-DEC-022 | PASS |  |
| CT-DEC-023 | PASS |  |
| CT-DEC-024 | PASS |  |
| CT-DSR-001 | NOT_APPLICABLE | capability dataset:generated is not claimed |
| CT-DSR-002 | NOT_APPLICABLE | capability dataset:production_replay is not claimed |
| CT-DSR-003 | NOT_APPLICABLE | capability dataset:generated is not claimed |
| CT-DSR-004 | NOT_APPLICABLE | capability dataset:production_replay is not claimed |
| CT-EXE-001 | PASS |  |
| CT-EXE-002 | PASS |  |
| CT-EXE-003 | PASS |  |
| CT-EXE-004 | PASS |  |
| CT-EXE-005 | PASS |  |
| CT-EXE-006 | PASS |  |
| CT-EXE-007 | PASS |  |
| CT-EXE-008 | PASS |  |
| CT-EXE-009 | PASS | review review-openai-ct-exe-009 by reviewer://openai/gpt-6: All three Executions were on-demand suite/environment triggered by P-RELEASE. Recorded sequential order is 0 for s-1, 1 for s-2, 2 for s-3, within batch 331560f5-2259-4c76-b134-94509f5fd148. |
| CT-EXE-010 | PASS |  |
| CT-EXE-011 | PASS |  |
| CT-EXE-012 | PASS | 1: 307 ms recorded, 200 ms at the harness, fail; 2: 145 ms recorded, 0 ms at the harness, pass |
| CT-HRV-001 | PASS |  |
| CT-HRV-002 | PASS |  |
| CT-HRV-003 | PASS | budget 15 s; review_timeout 1s |
| CT-HRV-004 | PASS |  |
| CT-HRV-005 | PASS | review_timeout 2s, so that the early attempt lands before it |
| CT-HRV-006 | PASS |  |
| CT-MJG-001 | PASS |  |
| CT-MJG-002 | PASS |  |
| CT-MJG-003 | PASS |  |
| CT-MJG-004 | PASS |  |
| CT-MJG-005 | PASS |  |
| CT-MJG-006 | PASS |  |
| CT-MJG-007 | PASS | members keep 0.9 each; agreement reported separately as 0.6666666666666666; the Inspection half is for a reviewer |
| CT-MJG-008 | PASS |  |
| CT-MJG-009 | PASS |  |
| CT-PLG-001 | NOT_APPLICABLE | capability plugins:validator is not claimed |
| CT-PLG-002 | NOT_APPLICABLE | capability plugins:validator is not claimed |
| CT-PLG-003 | NOT_APPLICABLE | capability plugins:validator is not claimed |
| CT-PLG-004 | NOT_APPLICABLE | capability plugins:validator is not claimed |
| CT-PLG-005 | NOT_APPLICABLE | capability plugins:validator is not claimed |
| CT-PLG-006 | NOT_APPLICABLE | capability plugins:dataset is not claimed |
| CT-PLG-007 | NOT_APPLICABLE | capability plugins:report is not claimed |
| CT-REL-001 | PASS |  |
| CT-REL-002 | PASS |  |
| CT-REL-003 | PASS |  |
| CT-REL-004 | PASS | the engine takes no GateResults from the request; every decision carries every applicable Gate, so an incomplete one cannot be submitted |
| CT-REL-005 | PASS |  |
| CT-REL-006 | PASS |  |
| CT-REL-007 | PASS |  |
| CT-REL-008 | PASS |  |
| CT-REL-009 | PASS |  |
| CT-REL-010 | PASS | first rejection: {"detail": "Scoped configuration changed since Snapshot"} |
| CT-REL-011 | PASS | rejection: {"detail": "Scoped configuration changed since Snapshot"} |
| CT-REL-012 | PASS |  |
| CT-REL-013 | PASS | inline Contract keyed 'scenario:cts-suite/s-greeting' |
| CT-REL-014 | PASS | evaluation 1's GateResult, as returned, keeps threshold 1.0 |
| CT-REL-015 | PASS |  |
| CT-REL-016 | PASS |  |
| CT-REL-017 | PASS |  |
| CT-REL-018 | PASS |  |
| CT-REL-019 | PASS | SA-CI's owner (P-RELEASE) is not retrievable through the API (no GET for Principals); left to Inspection |
| CT-REL-020 | PASS | approver and review reference sent as the engine's documented headers |
| CT-REL-021 | PASS | cts-approver is the Role holding baseline_approve |
| CT-REL-022 | PASS | the deletion was rejected (409) |
| CT-REL-023 | PASS | review review-openai-ct-rel-023 by reviewer://openai/gpt-6: Release id dc79bdf1 links to Report 6678d86f and Snapshot 3652d0ea; GateResult f63526f7 carries override approval de1d6b6e (P-APPROVER); Report metrics refer to two Result IDs found in 012; both link  |
| CT-REL-024 | NOT_APPLICABLE | capability ci_cd:<platform> is not claimed |
| CT-REL-025 | NOT_APPLICABLE | capability ci_cd:<platform> + human_review is not claimed |
| CT-REL-026 | PASS |  |
| CT-REL-027 | PASS | review review-openai-ct-rel-027 by reviewer://openai/gpt-6: Published declaration is 0.41.5 and claims human_review, multi_judge, seeded_controls; Team binding none. Review brief confirms run capabilities_claimed from this statement. Evidence for harness invoc |
| CT-REL-028 | PASS |  |
| CT-REL-029 | PASS | (a) the Report generated after the override |
| CT-REL-030 | PASS |  |
| CT-REL-031 | PASS | the engine offers no modifying operation; PUT and PATCH tried |
| CT-REL-032 | PASS | approved_by and approval_role are set by the engine, not sent |
| CT-REL-033 | PASS | A.12 gives the decision no Principal-kind field; SA-CI is identified as a Service Account in the audit log and the decision carries release_policy. Personal name or e-mail: Inspection |
| CT-REL-034 | PASS | no deletion operation succeeded; Contract version 1 recovered from the Baseline's frozen copy |
| CT-REL-035 | PASS | low_confidence summed over its per-Scenario entries |
| CT-REL-036 | NOT_APPLICABLE | review review-openai-ct-rel-036 by reviewer://openai/gpt-6: Engine explicitly offers Reports with Metrics but no KPI/dashboard frontend. Metric-to-Result IDs are observable, but there is no KPI artifact from which to start. Under the explicit Expected exceptio |
| CT-REL-037 | NOT_APPLICABLE | capability ci_cd:<platform> is not claimed |
| CT-REL-038 | PASS | 6 entries; actions execute, release_decide |
| CT-REL-039 | NOT_APPLICABLE | the Conformance Statement says the engine binds no Project or Suite to Teams (CTS 1.2) |
| CT-RUI-001 | NOT_APPLICABLE | capability reference_ui is not claimed |
| CT-RUI-002 | NOT_APPLICABLE | capability reference_ui is not claimed |
| CT-RUI-003 | NOT_APPLICABLE | capability reference_ui + multi_judge is not claimed |
| CT-RUI-004 | NOT_APPLICABLE | capability reference_ui is not claimed |
| CT-SCT-001 | PASS |  |
| CT-SCT-002 | PASS |  |
| CT-SCT-003 | PASS | both Scenarios send 'Hello'; the harness answers the first call (the control, which runs first) with SR-BYE |
| CT-SCT-004 | PASS |  |
| CT-SCT-005 | PASS |  |
| CT-SCT-006 | PASS |  |
| CT-SCT-007 | PASS |  |
| CT-SCT-008 | PASS | fresh controls run in a separate Suite of the same Project, bound to @2 |
| CT-SCT-009 | PASS |  |
| CT-SCT-010 | PASS |  |
| CT-SCT-011 | PASS |  |
| CT-SCT-012 | PASS | the control runs first; the harness answers the first subject call as the control |
| CT-SCT-013 | PASS |  |
| CT-SCT-014 | PASS | fresh controls run in a separate Suite of the same Project, bound to @2 |
| CT-SCT-015 | PASS |  |
| CT-SDK-001 | NOT_APPLICABLE | capability cli is not claimed |
| CT-SDK-002 | NOT_APPLICABLE | capability sdk:<language> is not claimed |
| CT-TTP-001 | NOT_APPLICABLE | capability test_type:regression is not claimed |
| CT-TTP-002 | NOT_APPLICABLE | capability test_type:agent + action_boundary is not claimed |

Report verification: OK
