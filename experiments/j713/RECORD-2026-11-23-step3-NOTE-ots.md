# Note to RECORD-2026-11-23-step3.md: what the Bitcoin proofs date (2026-11-23)

The stamps were upgraded with their Bitcoin proofs (the pending files are kept as `*.ots.pending`); every merkle root
was checked against the block header (blockstream.info).

| stamped file | calendars received it (+0300) | first Bitcoin block | block time (+0300) |
|---|---|---|---|
| PLAN-step3-manifest.txt (plan, criterion, code, development data) | 11:59 | 977177 | 12:13:39 |
| PLAN-step3-ADDENDUM-1.md (Can's conditions, data release) | 12:00 | 977177 | 12:13:39 |
| PLAN-step3-ADDENDUM-2.md (transistor record) | 12:05 | 977177 | 12:13:39 |
| PLAN-step3-ADDENDUM-3.md (channel identification) | about 12:10 | 977177 | 12:13:39 |
| RESULT-step3-manifest.txt (record, evaluation, data) | about 13:10 | 977184 | 13:24:44 |

What the proofs show, and what they do not:
- The Bitcoin proof dates the plan to no later than 12:13:39. The step3 recording started at 12:01:50 (idle phase);
  the 6-thread load began at 12:11:50, the run ended at 13:06:58 and the evaluation ran at 13:07:18. So the proof puts
  the plan, the criterion and the evaluation code before 53 of the run's 65 minutes and before the evaluation, but
  not before the recording's first 12 minutes; the earlier times (11:59 to 12:10) are the calendars' receipt times,
  which the Bitcoin proof does not attest.
- Bitcoin block times are themselves only accurate to about two hours.
- The record's sentence "stamped ... at 11:59 +0300 before any step3 data existed" states the submission time; read it
  with this note.
