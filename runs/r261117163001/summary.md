# Run r261117163001

aqef-reference-engine slice-17 (c3b9263); AQEF 1.0-CR1.5; CTS 1.0-CR1.5; harness 0.12.2

Cases: FAIL 0, NOT_RUN 0, PASS 8, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-PLG-001 | PASS | cts-flaky was called 2 times on the same input and rejected (422: {"detail": "Validator Plugin output varied on the fixed repeatability probe"}); cts-len registered |
| CT-PLG-002 | PASS | review plg-002-gemini-1 by reviewer://google/gemini-3.8-flash: No ambiguity. The implementation precisely reports 'repeatability_check' with runs count and output_matched Boolean, and docs/PLUGINS.md explicitly disclaims determinism proof, stating the registry re |
| CT-PLG-003 | PASS | (a) cts-probe received exactly the five logical inputs and returned pass, naming cts-probe@ct-plg-003-cf2554; transport headers seen, not compared: none beyond the usual. (b) oracle_unavailable with verdict null; the Judge was not called |
| CT-PLG-004 | PASS | Results and Baselines unchanged; the cts-len Result still names cts-len@ct-plg-004-915449 |
| CT-PLG-005 | PASS | review plg-005-gemini-1 by reviewer://google/gemini-3.8-flash: No ambiguity. Registration of cts-reach was refused with HTTP 422 because the plugin attempted to supply a confidence value (0.5), violating the validator protocol. During registration probe, cts-reac |
| CT-PLG-006 | PASS | ds-plugin has version 1.0.0 and a Scenario references it as ds-plugin@1.0.0; row Plugin-1 present |
| CT-PLG-007 | PASS | review plg-007-gemini-1 by reviewer://google/gemini-3.8-flash: Action difference analysis: The test's Action specifies 'Build F-SIGNALS (2.7); generate a Report for its batch with the plugin; follow the Metric to the Results behind it.' In this implementation, Re |
| CT-PLG-008 | PASS | (a) pass, Confidence 0.90, naming the plugin and version; (b) oracle_unavailable, verdict null |

Report verification: OK
