# Attestation of the CTS 1.8 review records for CT-ABD-007, CT-ABD-008 and CT-TTP-002

I, Igor Akymenko, owner of the AQEF project and of this repository, attest the following.

## The records

| Record | Method | Decision |
|---|---|---|
| `CT-ABD-007.gemini-1.review.json` | declaration | PASS (`VERIFIED`) |
| `CT-ABD-008.gemini-1.review.json` | inspection | PASS (`VERIFIED`) |
| `CT-TTP-002.gemini-1.review.json` | inspection | PASS (`VERIFIED`) |

All three are against CTS 1.0-CR1.2. The reviewed evidence is run `r261110132118`:
aqef-reference-engine slice-15 (`39201b3`), harness 0.9.0.

## The reviewer

1. **Who.** Google Gemini (`reviewer://google/gemini-3.8-flash`, as it reported its
   model), in the Gemini web app, in a new conversation. It did not write the engine, the
   CTS, or this harness. The engine was written by OpenAI Codex. Gemini can neither sign
   nor hold an account, so I sign for it.
2. **What it was given.** A pack with:
   - the three tests, F-ACT, and CTS 1.8;
   - Volume III, Appendix A §A.2 and §A.11, the AI Agent extract of Volume I, Chapter 7,
     and Volume X;
   - the harness evidence of the reviewed run, with extracts and their SHA-256.

   It was told to decide only from the pack, and to record an ambiguity rather than
   resolve it.

## What I changed in the records

3. **`signed_at`.** I set it on all three records to the time I received them.
4. **`declaration_ref`.** I added it to the CT-ABD-007 record:
   `evidence://CT-ABD-007-001.json`, the Conformance Statement as the harness recorded
   it.
   - The schema requires this field for a Declaration review.
   - The template given to the reviewer omitted it. That was a defect of the template,
     not of the review.
   - The reviewer's own text names the same statement.
5. **Nothing else.**
   - `signature_ref` reads `pending://owner-attestation`. The commit that adds this
     file and the records is their signature (Harness Contract §13).
   - Every reference in the three records was checked against the pack by the owner's
     assistant (Claude, Anthropic). All were correct.

## Where the records are applied

6. The three records, as described above, are applied in run `r261110222356`. It uses the same
   engine, the same CTS, and harness 0.9.0. Its result is that CT-ABD-001 to 008,
   CT-TTP-001 and CT-TTP-002 are PASS. The run regenerates the evidence, so its
   identifiers differ from the reviewed run `r261110132118`, which is kept alongside it.

Signed through that commit, 2026-11-10.
