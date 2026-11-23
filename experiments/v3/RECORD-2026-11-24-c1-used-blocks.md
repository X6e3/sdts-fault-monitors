# Record: c1 beside the frozen C state on the used validation blocks (2026-11-24)

Plan `C1-USED-BLOCKS-PLAN.md`, committed at 8d16cca3 before the run, approved by Can Koç on 2026-11-24. Used blocks
only: no new seeds, no oracle runs.

## Run

- Arch, clean clone `~/Research/sdts-v3-c8c4971c` fast-forwarded to 8d16cca3; `mcu/esp32/c1_val_compare.py`, 14
  workers, nice 19, 2026-11-24 01:37:24 to 01:41:11 (+0300), exit 0, 226.5 s.
- Binaries as the plan names them (the script checks their sha256): frozen `esp32-cyl16p-double/host_trace`
  `aa581fb2…`, c1 `esp32-c1-b68f865d/host_trace` `5d4fddee…`.
- Results in `results/v3/c-state/c1-used-blocks-8d16cca3/`: `score.json`, `rows.jsonl.gz` (19,200 lines), `run.log`.

## Results

| | validation 1 (440000–440199) | validation 3 (440400–440599) |
|---|---|---|
| U1 complete (runs × 3,600 samples) | 9,600 | 9,600 |
| U2 c1 earlier than the frozen C state | 0 | 0 |
| U3 first flag differs from the frozen C state | 0 | 0 |
| U4 frozen build against the recorded `c.cyl16p_double` | 0 differ | (not applicable) |
| U5 c1 alarms on admissible runs | 0 | 0 |
| c1 against the Python template (reported) | 0 differ | 0 differ |
| certified events / paired | 7,201 / 7,177 | 7,255 / 7,228 |
| IM's paired lag (s) | 233,441 | 262,482 |
| c1's paired lag (s), D_paired, misses | 143,205, 0.3865, 16 | 146,415, 0.4422, 11 |

**Verdict: SAME ALARMS.** On every one of the 19,200 runs, c1's PC build flags at the frozen C state's sample, which is
the Python template's, so it reproduces the template's recorded scores (validation 1, where the template was
validated: D_paired 0.387, 16 misses; validation 3, a used block for TS, scored in the first comparison: 0.442, 11
misses). The boards were not part of this check. U4 shows that the regenerated data and this build
reproduce validation 1's own C detections.

## What this is not

Both blocks were seen before c1 existed, so this is not a validation of c1; it shows that its wider slab (δ + η) and
raised start supports changed no alarm on these runs. A fresh-seed validation (440600–440999 are the last two fresh
blocks) is a separate decision.
