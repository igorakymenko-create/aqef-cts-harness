# Attestation of the CTS 1.8 review records for CT-PLG-002, CT-PLG-005 and CT-PLG-007

I, Igor Akymenko, owner of the AQEF project and of this repository, attest the following.

## The records

| Record | Method | Decision |
|---|---|---|
| `CT-PLG-002.gemini-1.review.json` | inspection | PASS (`VERIFIED`) |
| `CT-PLG-005.gemini-1.review.json` | declaration | PASS (`VERIFIED`) |
| `CT-PLG-007.gemini-1.review.json` | inspection | PASS (`VERIFIED`) |

`reviews/plg-reviews.json` holds the same three records together, for the harness.

All three are against CTS 1.0-CR1.4. The reviewed evidence is run `r261116204857`:
aqef-reference-engine slice-17 (`c3b9263`), harness 0.12.0.

## The reviewer

1. **Who.** Google Gemini (`reviewer://google/gemini-3.8-flash`, as it reported its model),
   in the Gemini web app, in a new conversation. It did not write the engine, the CTS, or
   this harness. The engine was written by OpenAI Codex. Gemini can neither sign nor hold
   an account, so I sign for it.
2. **What it was given.** A pack (`plg-review`):
   - the three tests, Section 25's introduction, F-SIGNALS and CT-REL-035, CTS 2.5 and
     CTS 1.8;
   - Volume XVI in full, and extracts of Volume V (Custom Validators, Validator SDK) and
     Volume XI (KPIs);
   - the harness evidence of the reviewed run;
   - the engine's Conformance Statement and docs/PLUGINS.md at slice-17;
   - the SHA-256 of every file.

   It was told to decide only from the pack, and to record an ambiguity rather than
   resolve it.
3. **One follow-up.** The first records had no `answer` in their checklist items. In the
   same conversation, I asked for the field, from the reviewer's own review, with nothing
   else changed. The second records differ from the first only by `answer` (`met` in
   every item). This was checked field by field.

## What I changed in the records

4. **`signed_at`.** I set it on all three records to the time I received the second
   records.
5. **`declaration_ref`.**
   - **CT-PLG-005, a Declaration:** set to `evidence://CT-PLG-005-001.json`, the
     implementation's statement as the harness recorded it.
   - **CT-PLG-002 and CT-PLG-007, Inspections:** removed. The template put the
     placeholder in every record. A `declaration_ref` belongs only to a Declaration
     (Harness Contract §13), and the earlier Inspection records here carry none.
6. **Nothing else.**
   - `signature_ref` reads `pending://owner-attestation`. The commit that adds this file
     and the records is their signature (Harness Contract §13).

## Two points in the CT-PLG-005 record, stated here and not changed in it

7. **Checklist item 4 says `cts-reach` "did not reach the network". That is not so.**
   - Its report reached the harness over the network, and the harness log holding it is
     `CT-PLG-005-003.json`.
   - The cause was a defect of harness 0.12.0, not the reviewer's: the test plugin wrote
     down what it had reached before its network attempt, so `network` was missing from
     its record. The reviewer read the missing field as "not reached".
   - Harness 0.12.1 makes the network attempt a separate connection before the report,
     and records its outcome. In the run below, `cts-reach` reached the clock,
     randomness, and the network.
   - Item 4 is "reported, not judged", and the engine declares the deviation from Volume
     V's SHOULD for all three in its Conformance Statement. The decision does not depend
     on it.
8. **Line numbers.** Items 1 and 4 cite `engine-CONFORMANCE-STATEMENT.md` lines 115–117
   for the "V Validator SDK, XVI remote hosting" deviation. That row is line 120. The
   quotation in the record is exact.

The owner's assistant (Claude, Anthropic) checked every other reference in the three
records against the pack. In CT-PLG-007, all six `result_ids` resolve to the six Results
of the batch, two of them with Confidence 0.6, which gives the value 1/3.

## Where the records are applied

9. The three records are applied in run `r261117094006`, with the same engine and CTS and
   with harness 0.12.1. Its result is CT-PLG-001 to 008 PASS. The run regenerates the
   evidence, so its identifiers differ from the reviewed run `r261116204857`, which is
   kept alongside it.

Signed through that commit, 2026-11-17.
