# Record: the strengthened baselines on the block of validation 3 (BASELINE2, 2026-11-23)

Plan `BASELINE2-PLAN.md` v3.1, FROZEN at `606d91cb` (2026-11-23 20:11) with `chosen.json` sha256 `f7e48016…`,
validation 3's rows sha256 `d9b90cef…` and the first comparison's block rows sha256 `be3ffc16…`. The block is
validation 3's (seeds 440400–440599, 9,600 runs), already used by validation 3 and by the first comparison
(`RECORD-2026-11-22-baselines-block.md`): a fixed comparison on a used block, not a new validation.

## Run

- Arch, clean clone `~/Research/sdts-v3-c8c4971c` at `606d91cb`; script `~/Research/sdts-runs/baselines2-block-606d91cb.sh`
  (checks HEAD, then `baselines2_run.py block OUT --chosen results/v3/baselines2/dev-3b363394/chosen.json --workers 14`
  under `nice -n 19`, then `baselines2_run.py score OUT`).
- Block 2026-11-23 20:11:59 to 2026-11-24 00:29:58 (+0300), exit 0; score exit 0 at 00:29:59. No restart, no
  Traceback or error in the log.
- Identity check (plan section 5): the first comparison's B1@M2 and B4 on one run per design cell, 48 rows, gave the
  first block's detections on all 48 (`identity.json`: `{"rows": 48, "differ": []}`).
- Results in `results/v3/baselines2/block-606d91cb/`: `scores.json` (sha256 `15d74b8c…`), `meta.json` (`fb5aeff3…`),
  `identity.json` (`d926ef9d…`), `rows.jsonl.gz` (sha256 of the uncompressed file, as on Arch, `251e8864…`),
  `interim-peek.py` and `interim-peek.txt` (below), `run.sh` (the block script, copied from Arch on 2026-11-24) and
  `run.log` (the block's log; `*.log` is ignored by `.gitignore`, so it was added with `git add -f`, as the first
  comparison's logs were).
- Chosen configurations (DEV tuning; the plan's status block): B1s@M1 = n_c 1, order 2, fifo; B1s@M2 =
  n_c 64, order 8, fifo; B4s@M1 = B4s@M2 = L = 0 (prior box+err for B1s).

## Results (`scores.json`; paired lag over the 7,228 paired events (those IM detects), IM's paired lag 262,482 s)

| monitor | memory (reals) | D_paired | paired lag (s) | misses | at t* | ms/sample | LPs | failed LPs |
|---|---|---|---|---|---|---|---|---|
| WM (validation 3) | 107 | 0.9952 | 1,264 | 0 | 7,243 | | | |
| TS (first comparison's rows) | 42 | 0.4422 | 146,415 | 11 | 5,967 | | | |
| B4s, L = 0 (M1 and M2) | 6 | 0.0879 | 239,399 | 21 | 5,593 | 0.277 | 0 | 0 |
| IM (validation 3) | 2 | 0 | 262,482 | 27 | 5,257 | | | |
| B1 n_c 4, o 8 (first comparison, M2) | 203 | −0.8109 | 475,338 | 52 | 5,030 | 2.880 | 27,288,600 | 1 |
| B1 n_c 1, o 2 (first comparison, M1)* | 32 | −6.6284 | 2,002,324 | 300 | 3,521 | 2.897 | 30,348,378 | 0 |
| B1s n_c 64, o 8 (M2) | 5,963 | −2.3923 | 890,426 | 120 | 4,201 | 11.494 | 28,112,288 | 34 |
| B1s n_c 1, o 2 (M1) | 32 | −9.6378 | 2,792,233 | 484 | 2,848 | 3.177 | 31,927,828 | 0 |
| B4 (first comparison) | 6 | −27.5772 | 7,500,988 | 1,799 | 790 | 0.011 | 0 | 0 |

7,255 certified events. Time is wall time per processed sample of one worker, 14 workers on Arch. The first
comparison's rows for B1, B4 and TS equal its record (D −0.81, −27.6 and 0.442).

\* Not in `scores.json`: the scorer takes only the first comparison's B1@M2 (`FIRST_B1`), although plan section 5
names "the first comparison's B1 and B4" and the first comparison chose B1 at both budgets. Added on 2026-11-24 from
the same rows by the scorer's rules (found by review r7, which computed it independently; recomputed on the Mac with
the same result). It had no alarm on an admissible run or before t*.

## Hypotheses (plan section 4; `boot_diff`, 2,000 draws over the 200 seeds; ours minus the baseline's)

| hypothesis | point (s) | 95 % interval | verdict |
|---|---|---|---|
| H-S1: WM below B1s@M2 | −889,162 | [−981,119, −805,505] | supported |
| H-S2a: TS below B1s@M1 | −2,645,818 | [−2,813,359, −2,464,696] | supported |
| H-S2b: TS below B4s@M1 | −92,984 | [−116,210, −73,654] | supported |

## Soundness and the other counts of plan section 5

- No method raised an alarm on an admissible run or before t* (every `admissible_alarms` and `early` list is empty).
  B1s and B4s run in binary64 with the outer steps of plan section 1; for them this is an observation on these runs,
  not a guarantee.
- B4s was never later than IM on any of the 9,600 runs (misses counted at sample 3,600); it was earlier on 506 of the
  7,255 events (500 detected by both, 6 missed by IM) and equal on 6,749 (6,728 equal detections, 21 missed by
  both). This is an observation, not "by construction" as plan section 1 says: B4s uses the baselines' slab δ + η
  (`baselines.py` `SIG`), the frozen IM δ with one ulp outward (`thermal_machine.py` `observe`), so B4s's slab is the
  wider; against an IM with the same slab it could not be later in exact arithmetic. Review r7's example: z0 = 2.3 +
  5e-10 (shifted units) empties IM at sample 0 and not B4s.
- B1s@M2 had 34 failed LPs in 28,112,288; B1s@M1 none; the first comparison's B1@M2 one.

## Additional counts (not in the plan; computed on the Mac from the rows above, 2026-11-24)

B1s against the first comparison's B1, event by event (7,255 events, a miss counted at 3,600):
- same configuration, n_c 1, order 2 (32 reals): B1s later on 1,765 (1,571 detected by both, 194 missed by B1s only),
  earlier on 147 (137 and 10), equal on 5,343 (5,053 equal detections, 290 missed by both);
- B1s@M2 (n_c 64, 5,963 reals) against B1@M2 (n_c 4, 203 reals): B1s later on 1,879 (1,806 and 73), earlier on 283
  (278 and 5), equal on 5,093 (5,046 equal detections, 47 missed by both).
A miss counted at 3,600 orders one-sided misses correctly (the largest finite detection is 3,598); events missed by
both are listed apart, since which method would flag first after the horizon is unknown.
B1s, the stable and outer version, is later than B1 at both budgets on this block. Which of its changes (plan
sections 1, 7, 8) costs the detections is not established. Review r7's DEV diagnosis (2026-11-24, single process,
3 DEV rows; its own ablation class built from B1's code with B1s's changes as switches; not rerun by us) points
away from the coefficients below 1e-12: two changes, each alone, turn on eliminations of strip slack generators
(gn = 0) that B1 skips when rounding leaves their excess at +2.2e-16 or +4.4e-16. They are `EXACT_TOL` = 1e-12 in
`_eliminate_one` and the outward pad of `_bounds`. On 430012 drift_0.001 (n_c 4, o 8) the slack eliminations up
to t = 466 rise from 837 to 1,162 and 1,165 and the eliminations of state generators fall from 56 to 25 and 28;
removing both changes from B1s takes the three rows' detections from (3424, 2707, none) to (573, 623, 342). If this
holds on more rows, B1's earlier detections come from the same last-bit boundary effect that makes it unstable.
Proposed check (not run): a 2 x 2 table (`EXACT_TOL` 0 or 1e-12, `_bounds` pad off or on) on the 100 DEV rows of the
stability check, n_c 1, o 2 and n_c 4, o 8, with paired lag, the two elimination counts and the 1e-15 stability.

## Interim look

At about 23:15 on 2026-11-23, with 6,762 of the 9,600 rows finished, the scoring was run read-only on the finished
rows (`interim-peek.py`, output in `interim-peek.txt`). Nothing in the block, the plan or the chosen configurations
was changed, and the block was not stopped. The plan neither asks for nor forbids an interim look.

## Not done

The plan has no second scorer; the scoring is `baselines2_run.py score`, which reuses the first comparison's
bootstrap (`baselines_run.boot_diff`), whose numbers the first comparison's second scorer reproduced.

## For the paper

All three hypotheses are supported, so the claim that every baseline lagged stands (plan section 5). The baselines
section reports B1s and B4s beside the first comparison, B4s's 506 earlier events, and that B1s was later than B1.

## Review r7 (2026-11-24, read-only copy of 04016dc5 on Arch)

Review r7 recomputed every field of `scores.json` with its own standard-library code (0 differences), the three
bootstrap intervals with its own seed at 2,000 and 20,000 draws (all three supported, e.g. H-S2b
[−115,085, −74,317] and [−115,031, −73,639]), the three sha256 of the plan, the uncompressed rows' sha256 and
`git_head`, and the counts above. Its findings and what was done:
1. B1@M1 missing from `scores.json` and this record: row added above (plan section 5).
2. "B4s never later than IM by construction" holds against an IM with B4s's slab only: corrected above.
3. The paper's "Several sensors" paragraph named only δ − ε for the frozen TS; the Python template's open rate pads
   (2.1e-21 °C) and the AVR's ε = 9.9e-13 °C under two assumptions were left out: the paragraph now refers to the
   restrictions of the paragraph before it, and the Limitations item names both.
4. The paper's Limitations item on a shared ambient: "must then explain" reworded as the condition for the joint
   record to stay consistent, and the case of one shared ambient and of a bounded difference both named.
5. `run.log` was listed but ignored by `.gitignore`: added, with the block script.
6. Events missed by both methods were counted as equal: split out above.
7. Smaller points: "false-alarm rate" made "false-alarm probability per sensor over a record", and "the same model" made
   "the same model and assumptions" in the paper; `sizeof(v3_state)` is 189 bytes on the AVR (`-mdouble=64`, byte
   alignment), and 360 and 37,036 bytes on the ESP32 (checked with `xtensa-esp32-elf-gcc` static asserts); the hypothesis
   keys in `scores.json` read "H-S2 TS < B1s@M1" and "H-S2 TS < B4s@M1" for H-S2a and H-S2b; `identity.json` does not
   list its 48 rows: they are `baselines_run.identity_rows` of validation 3's rows, per design cell the run with the
   smallest sha256 of its key (40 fault cells, 8 healthy); the B1s cause sentence above was replaced by r7's diagnosis.


## Review r8 (2026-11-24, a second reader of the same package at 04016dc5)

Review r8 recomputed the table and the three intervals with its own code (its seed 20261124 gives the same intervals
as r7's; with 20261121 it reproduces `scores.json` exactly) and found the B4s counterexample independently
(y = 52.3000000005 °C at P0, the same as r7's z0). Its two "high" findings (BASELINE2 not yet in the paper, B4s "by
construction") were closed in 785213e8. Its other findings and what was done:
- ε is 4.852840351978194e-13 °C (`results/v3/c-state/c1-b68f865d/y123.json`, K6_data); the paper and README said
  4.85e-13, which is below it, so "sound for |v| ≤ δ − 4.85e-13" claimed 2.8e-16 °C too much. Both now say 4.86e-13,
  rounded up. The AVR's 9.9e-13 is above twice ε and stands.
- The 12 late events of validation 3: the margins show that the full history is inconsistent at t* under WM's own
  slab and matrix, not that η plays no part in what the window keeps. The paper now says the delays are losses of
  the compressed state and that η's effect on them was not isolated.
- The shared-ambient open problem: a fault common to all sensors that the plants' response to an admissible ambient
  change reproduces still has a twin; added.
- B1s: on two DEV runs (430027 jump_0.2 E0 ramp at (1, 2): B1 360, B1s 1,145; 430011 drift_0.002 E0 rw at (4, 8):
  B1 704, B1s 1,555), B1 with only its exact-elimination test relaxed to over ≤ 1e-12 gave B1s's first alarm; on the
  second run the rescaling alone also gave 1,555. Consistent with r7's diagnosis; the factorial of
  `diag/b1s_factorial.py` (committed f5f690eb before its run) measures it on 100 DEV rows.
- J713 step 3 (not this record): 0.205 °C is the largest absolute residual of the least-squares trajectory, so an
  upper bound on the smallest uniform error bound for that run, not that bound itself; to be worded so when the
  J713 run enters the paper.

## The B1s factorial (development rows, 2026-11-24)

`diag/b1s_factorial.py`, committed at f5f690eb before its run; Arch, clean clone at f5f690eb, 14 workers, nice 19,
01:01:19 to 01:26:40 (+0300), exit 0. Results in `results/v3/baselines2/b1s-factorial-f5f690eb/` (`summary.json`,
`rows.jsonl`, `run.log`). The 100 DEV rows of the stability check (85 paired events, IM's paired lag 6,401 s), each
with the shifts 0, ±1e-15 and 2e-15. The copy of B1s with (EXACT_TOL 1e-12, pad on) gave B1s's first alarm on all
100 rows at both configurations. Descriptive; development seeds only.

| (n_c, o) | variant | paired lag (s) | misses | rows unstable | slack / state eliminations |
|---|---|---|---|---|---|
| (1, 2) | B1 | 33,445 | 5 | 16 | |
| (1, 2) | B1s: EXACT_TOL 1e-12, pad on | 38,806 | 6 | 0 | 260,870 / 402,882 |
| (1, 2) | EXACT_TOL 1e-12, pad off | 38,806 | 6 | 0 | 260,872 / 402,880 |
| (1, 2) | EXACT_TOL 0, pad on | 33,051 | 5 | 4 | 227,440 / 428,256 |
| (1, 2) | EXACT_TOL 0, pad off | 33,413 | 5 | 15 | 214,813 / 433,542 |
| (4, 8) | B1 | 12,423 | 1 | 24 | |
| (4, 8) | B1s: EXACT_TOL 1e-12, pad on | 30,299 | 5 | 0 | 223,147 / 148,768 |
| (4, 8) | EXACT_TOL 1e-12, pad off | 30,299 | 5 | 0 | 223,211 / 148,714 |
| (4, 8) | EXACT_TOL 0, pad on | 25,128 | 3 | 27 | 204,141 / 172,801 |
| (4, 8) | EXACT_TOL 0, pad off | 17,503 | 3 | 29 | 160,308 / 145,696 |

No variant alarmed on an admissible row or before t*. What it shows, on these rows:
- With EXACT_TOL = 1e-12 the pad changes nothing, and no row is unstable.
- With EXACT_TOL = 0 the instability returns (4 and 15 rows at (1, 2), 27 and 29 at (4, 8); B1: 16 and 24) and so do
  most of B1's detections: at (1, 2) the paired lag falls to B1's (33,051 and 33,413 against 33,445); at (4, 8) the pad
  then matters (25,128 on, 17,503 off), and B1s's other changes keep 5,080 s of the 17,876 s gap to B1.
- EXACT_TOL = 1e-12 raises the slack eliminations and lowers the state eliminations, as reviews r7 and r8 traced.
So the tolerance that makes B1s stable costs most of its detections; B1's extra detections and its instability come
from the same last-bit decisions. The block's own gap (B1s later than B1 at both budgets) is not decomposed here.
