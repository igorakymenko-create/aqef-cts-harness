# Attestation of the CTS 1.8 review records for CT-SDK-001

I, Igor Akymenko, owner of the AQEF project and of this repository, attest the following.

## The records

| Record | CTS | Reviewed evidence | Decision |
|---|---|---|---|
| `CT-SDK-001.gemini-1.review.json` | 1.0-CR1 | run `r261109094028` | NOT_RUN (`UNRESOLVED_INTERPRETATION`) |
| `CT-SDK-001.gemini-2.review.json` | 1.0-CR1.2 | run `r261109120325` | PASS (`VERIFIED`) |

The records are kept as the reviewer returned them. I set only `signed_at`, which the
reviewer left for me: the time I received each record. Their `signature_ref` reads
`pending://owner-attestation`. The commit that adds this file and the records is their
signature (Harness Contract §13). GitHub authenticates that commit as made by my account.

## The reviewer

1. **Who.** Google Gemini (`reviewer://google/gemini-3.8-flash`, model name as it reported
   it), in the Gemini web app. It did not write the engine, its CLI, the CTS, or this
   harness. The CLI was written by OpenAI Codex. Gemini can neither sign nor hold an
   account, so I sign for it.
2. **What it was given.** A pack with:
   - the test's text and CTS 1.8;
   - Volume XIV and Appendix C in full;
   - the harness evidence of the reviewed run, with extracts and their SHA-256.

   It was told to decide only from the pack, and to record an ambiguity rather than
   resolve it.
3. **Independence of the second review.** The second review was made in a new
   conversation. Its pack did not contain the first record.

## What happened

4. **First review (CTS 1.0-CR1).** The three CLI commands made the matching Appendix C
   calls. The reviewer then found two readings of the test:
   - **Expected:** "maps to a REST operation";
   - **Action:** "the REST operations of Appendix C".

   Seven commands of the CLI wrap operations that the engine documents beyond Appendix C.
   The reviewer could not decide between the readings, and the test was NOT_RUN. Every
   reference in the record was checked against the pack by the owner's assistant (Claude,
   Anthropic). All were correct.
5. **Clarification.** As the CTS author, I chose the first reading. The requirement under
   test is that a CLI command is a REST call, not logic of its own. CTS 1.0-CR1.2
   (AQEF commit `9902b17`) states it in CT-SDK-001. The specification's text did not
   change.
6. **Second review (CTS 1.0-CR1.2).** Harness 0.7.1 also collected the engine's own API
   documentation, which the clarified Action asks for. The reviewer decided PASS:
   - 64 commands map to Appendix C operations;
   - 7 map to operations the engine documents beyond it;
   - the CLI's help and its documentation list the same 71 commands.

   The owner's assistant checked the counts and the cited lines against the pack. All
   were correct.
7. **Applied.** The second record, unchanged, is applied in run `r261109125722`: the
   same engine (slice-13, `7e03ce3`), CTS 1.0-CR1.2, and harness 0.7.1. That run
   regenerates the evidence, so its identifiers and Project names differ from the
   reviewed run `r261109120325`, which is kept alongside it.

Signed through that commit, 2026-11-09.
