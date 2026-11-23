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
  `identity.json` (`d926ef9d…`), `rows.jsonl.gz` (sha256 of the uncompressed file, as on Arch, `251e8864…`), `run.log`.
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
| B1s n_c 64, o 8 (M2) | 5,963 | −2.3923 | 890,426 | 120 | 4,201 | 11.494 | 28,112,288 | 34 |
| B1s n_c 1, o 2 (M1) | 32 | −9.6378 | 2,792,233 | 484 | 2,848 | 3.177 | 31,927,828 | 0 |
| B4 (first comparison) | 6 | −27.5772 | 7,500,988 | 1,799 | 790 | 0.011 | 0 | 0 |

7,255 certified events. Time is wall time per processed sample of one worker, 14 workers on Arch. The first
comparison's rows for B1, B4 and TS equal its record (D −0.81, −27.6 and 0.442).

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
- B4s was never later than IM on any of the 9,600 runs (misses counted at sample 3,600), as by construction; it was
  earlier on 506 of the 7,255 events and equal on 6,749.
- B1s@M2 had 34 failed LPs in 28,112,288; B1s@M1 none; the first comparison's B1@M2 one.

## Additional counts (not in the plan; computed on the Mac from the rows above, 2026-11-24)

B1s against the first comparison's B1, event by event (7,255 events, a miss counted at 3,600):
- same configuration, n_c 1, order 2 (32 reals): B1s later on 1,765, earlier on 147, equal on 5,343;
- B1s@M2 (n_c 64, 5,963 reals) against B1@M2 (n_c 4, 203 reals): B1s later on 1,879, earlier on 283, equal on 5,093.
B1s, the stable and outer version, is later than B1 at both budgets on this block. Which of its changes (plan
sections 1, 7, 8) costs the detections was not isolated; B1's rescaling treats coefficients below 1e-12 as zero, which
is not outer, and its detections move with shifts of 1e-15 (plan section 0).

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
