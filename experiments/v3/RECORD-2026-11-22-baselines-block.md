# Record: the baselines on the block of validation 3 (BASELINES, 2026-11-22)

Plan `BASELINE-PLAN.md`, frozen at `9438dffa` (approved 2026-11-21), section 9. The block is validation 3's (seeds
440400–440599, 9600 runs), whose oracle, IM (v2) and WM (F3) rows were known before this run. It is a fixed
comparison on a used block, not a new validation.

## Provenance

- **Run:** `diag/baselines_run.py block`, then `score`, on Arch from a clean clone at `9438dffa`
  (`~/Research/sdts-v3-bl-9438dffa`), 14 workers, `nice 19`, the venv of `0ce80072` (CPython 3.12.13, numpy 2.5.5,
  scipy 1.18.1). Started 2026-11-21 22:23:59, finished 2026-11-22 05:32:01 (+0300); the block step and the score step
  both exited 0. The 48-run identity check ran first: v2 equal to the block's record on all 48.
- **The same machine** also ran a sensor logger (sysfs reads once a second, for a separate thermal study) from
  05:29:09, alongside the block's last rows.
- **Outputs:** `results/v3/baselines/block-9438dffa/`: `meta.json`, `identity.json`, `scores.json` (sha256
  `5b6f75c9…8867`), `rows.jsonl.gz` (gzip of `rows.jsonl`, sha256 of the plain file `77d05365…ca6e`), `run.sh`,
  `block.log`, `score.log`. The Mac copy was checked against Arch by sha256. `meta.json` records the reference rows'
  sha256 (`d9b90cef…`, freeze 3's), the chosen configurations' (`d8c4704d…`) and the manifest's (`0a40cbdf…`).

## Results (the repository's scorer)

7,255 certified events, 7,228 of them detected by v2; v2's paired lag is 262,482 s.

| method | configuration | memory (reals) | paired lag (s) | D_paired | misses | at t\* | ms per sample |
|---|---|---|---|---|---|---|---|
| WM (F3) | W = 256, K = 64, smoothing fold | 107 | 1,264 | 0.9952 | 0 | 7,243 | (validation 3) |
| B5 | F3, the fold's horizon at the base (filtering) | 107 | 3,782 | 0.9856 | 4 | 7,227 | 20.4 |
| TS (cyl16p) | freeze 1 | 42 | 146,415 | 0.4422 | 11 | 5,967 | 0.061 |
| IM (v2) | | 2 | 262,482 | 0 | 27 | 5,257 | |
| B1@M2 | n_c = 4, o = 8, fifo, box+err | 203 | 475,338 | −0.811 | 52 | 5,030 | 2.88 |
| B1@M1 | n_c = 1, o = 2, fifo, box+err | 32 | 2,002,324 | −6.63 | 300 | 3,521 | 2.90 |
| B4 | L = (M₁₂, M₂₂, −0.01) | 6 | 7,500,988 | −27.6 | 1,799 | 790 | 0.011 |
| B3 | o = 2, box, q = 0.01 | 21 | 9,978,043 | −37.0 | 2,463 | 204 | 0.075 |
| B2 | o = 2, box | 21 | 12,544,024 | −46.8 | 3,293 | 22 | 0.076 |

- Misses and detections at t\* are over the 7,255 events; IM's are from the block's reference rows. B5 is F3's code
  with the fold using the measurements up to the new base only (plan section 3), so it keeps the same state as F3 (at
  most 65 measurements were kept). The time is each worker's wall time per processed sample (`time.monotonic`), with
  14 workers on 8 cores (16 threads): it compares the methods with each other, not with a dedicated core.
- **Soundness:** no method alarmed on an admissible row or before t\*. B5's 7,254 alarms are all certified; it
  solved 54.0 million LPs with 618 re-solves and no fallback. B1@M2 had one failed LP (440430, healthy, E1, ramp,
  edge noise); the fallback is the unconstrained hull, which is outer.

**Hypotheses** (seed bootstrap over the 200 seeds, 2,000 draws, RNG seed 20261121, the 95 % interval of ours minus
the baseline's paired lag):

| hypothesis | difference (s) | 95 % interval | verdict |
|---|---|---|---|
| H-B1, TS vs B1@M1 | −1,855,909 | [−1,994,089, −1,712,180] | supported |
| H-B1, TS vs B2 | −12,397,609 | [−12,546,101, −12,246,833] | supported |
| H-B1, TS vs B3 | −9,831,628 | [−10,185,855, −9,449,888] | supported |
| H-B1, TS vs B4 | −7,354,573 | [−7,700,748, −6,983,045] | supported |
| H-B2, WM vs B5 | −2,518 | [−5,378, −414] | supported |
| H-B3, WM vs B1@M2 | −474,074 | [−517,380, −431,128] | supported |

## OBSERVED

- All three hypotheses are supported. H-B2's interval is the closest to 0: the smoothing fold removes 2,518 of the
  forward window's 3,782 s of paired lag, and the forward window alone already reaches D_paired 0.986.
- The order of the methods is the one DEV gave. The nearest set method, B1 at 203 reals, has 1.8 times IM's paired
  lag (2.1 on DEV); with 32 reals, 7.6 times.
- TS's D_paired on this block is 0.442; on validation 1's block it was 0.387.

## A correction to the plan's text

`BASELINE-PLAN.md` section 4 gives B1's memory as 3 + 3·(3o) + n_c·(3o + 1), which counts 3o generators. The code
(`diag/baselines_cz.py`, `ng_max = 3 * order + n_c`) keeps 3o + n_c generators, so the count is
3 + 3·n_g + n_c·(n_g + 1) with n_g = 3o + n_c: 32 and 203 for the chosen (1, 2) and (4, 8), as section 9 and the rows
give; the plan's formula gives 28 and 175. Found by the author of the independent scorer below while scoring DEV.
The paper uses 32 and 203.

## The independent scorer

Written from the plan alone, outside this repository, with the Python standard library and no project imports. On
DEV it reproduced `report.json` in 189 checks and `tune.json` in 1,496 with no difference. Its own RNG seed and
percentile rule differ from the repository's (the plan fixes neither). **Its verdicts on the block: pending.**

## What this does not show

- A new validation: WM's and IM's results on this block were known before the run.
- Other published variants of the baselines (another strip weight, a time-varying gain, another reduction); they
  were not in the plan's grid.
- WM's timing in this run: WM was not run again; its times are validation 3's.
- Equal RAM: memory counts the reals stored between samples, not bytes, and no method's LP workspace.
