# Run r261116204857

aqef-reference-engine slice-17 (c3b9263); AQEF 1.0-CR1.4; CTS 1.0-CR1.4; harness 0.12.0

Cases: FAIL 0, NOT_RUN 3, PASS 5, NOT_APPLICABLE 0

| Case | Outcome | Reason |
|---|---|---|
| CT-PLG-001 | PASS | cts-flaky was called 2 times on the same input and rejected (422: {"detail": "Validator Plugin output varied on the fixed repeatability probe"}); cts-len registered |
| CT-PLG-002 | NOT_RUN | Inspection: the registration response, record, and documentation were collected; evidence collected for review (CTS 1.8) |
| CT-PLG-003 | PASS | (a) cts-probe received exactly the five logical inputs and returned pass, naming cts-probe@ct-plg-003-078d77; transport headers seen, not compared: none beyond the usual. (b) oracle_unavailable with verdict null; the Judge was not called |
| CT-PLG-004 | PASS | Results and Baselines unchanged; the cts-len Result still names cts-len@ct-plg-004-c48dd8 |
| CT-PLG-005 | NOT_RUN | Declaration: automated part met (registration refused); reported, not judged: cts-reach reached ['clock', 'network', 'random'] (Volume V SHOULD); the statement awaits review; evidence collected for review (CTS 1.8) |
| CT-PLG-006 | PASS | ds-plugin has version 1.0.0 and a Scenario references it as ds-plugin@1.0.0; row Plugin-1 present |
| CT-PLG-007 | NOT_RUN | Inspection: the Metric and the Results it links were collected; evidence collected for review (CTS 1.8) |
| CT-PLG-008 | PASS | (a) pass, Confidence 0.90, naming the plugin and version; (b) oracle_unavailable, verdict null |

Report verification: OK
