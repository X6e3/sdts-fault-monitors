# Record: the baselines' DEV tuning (BASELINES, 2026-11-21)

Plan `BASELINE-PLAN.md` (status DRAFT), section 7, step 2. DEV seeds only: 1400 rows (the 1320 comparison rows of
`dev-45cff1d` and the 80 edge-noise healthy rows 430070–430089). No run of the comparison block has been made.

## Provenance

- **Run:** `diag/baselines_run.py dev` on Arch, from a clean clone at `58db0897` (`~/Research/sdts-v3-bl-58db0897`),
  10 workers, `nice 19`, the venv of `0ce80072` (CPython 3.12.13, numpy 2.5.5, scipy 1.18.1). Grid 15:34–19:54, the
  B1 LP-rescaling subset 19:54–20:17 (+0300); both exited 0. 159,800 records: 114 configurations × 1400 rows, and
  B1lp on its 200-row subset.
- **The tuning step stopped** (20:17) with a `KeyError`: `score()` looked up every DEV row in B1lp's records, which
  cover 200 rows. Fixed in `ae609cd9` (each configuration is scored over the rows it was run on; `complete` says
  whether that is all 1400; the rule, which takes complete configurations only, is unchanged). The tuning step was
  run again at 20:26 from a clean clone at `ae609cd9` on the same output. No record of the DEV run was changed;
  both logs are kept (`tune.log`, `tune-ae609cd9.log`).
- **Report and diagnostic:** `diag/baselines_dev_report.py` and `diag/baselines_widths.py` (`b089e3f1`), written
  after the run had shown every baseline behind v2, committed before either was run. They read the run's files
  (and, for cyl16p, the ambient study's part (b)); neither changes the choice.
- **Outputs:** `results/v3/baselines/dev-58db0897/`: `meta.json`, `tune.json`, `chosen.json`, `rows.jsonl.gz`
  (gzip of `rows.jsonl`, sha256 of the plain file `5acc8ff7…2e29`), `report.json`, `widths.json`, the run script and
  the logs. The Mac copy was checked against Arch by sha256, file by file.

## The choice (the plan's rule, as run)

For each family and budget: the smallest DEV paired lag among complete configurations with no alarm on an
admissible row and none before t\*.

| | configuration | memory (reals) | paired lag (s) | D_paired | misses (of 1081) |
|---|---|---|---|---|---|
| v2 (reference) | | 2 | 32,925 | 0 | 8 |
| cyl16p (freeze 1) | | 42 | 20,222 | 0.386 | 4 |
| **B1@M1** | n_c = 1, o = 2, fifo, box+err | 32 | 306,089 | −8.30 | 54 |
| **B1@M2** | n_c = 4, o = 8, fifo, box+err | 203 | 68,710 | −1.09 | 12 |
| **B2** (M1 = M2) | o = 2, box | 21 | 1,877,905 | −56.0 | 504 |
| **B3** (M1 = M2) | o = 2, box, q = 0.01 | 21 | 1,523,216 | −45.3 | 378 |
| **B4** (M1 = M2) | L = (M₁₂, M₂₂, −0.01) | 6 | 1,177,530 | −34.8 | 289 |

- Paired lag over the 1073 events v2 detects (a miss counts as N − t\*); v2's own paired lag is 32,925 s. cyl16p is
  scored with the same function from the ambient study's part (b) at the frozen box (1320 rows; the 80 edge rows
  are not in that study and do not enter the paired lag): D_paired 0.3858, as recorded in DIAG-3 (0.386).
- For B2–B4 the best configuration is also the smallest, so the M2 choice equals the M1 choice.
- B4's c (the gain on TA) has no effect: c = 0, −0.01 and −0.05 give identical records. A negative c only widens the
  TA bound (A − LC ≥ 0 forbids a positive one), which stays at the box. The tie is broken by the configuration
  string, as the code does.
- **M2.** The plan defines M2 as F3's memory; the tuning code applies no memory limit at M2. Counted with its LP
  (445 rows × 679 variables at most on the block), F3's memory exceeds every grid point (the largest B1 has 5,963
  reals), so the two agree. Counted as stored reals only (65 measurements and 42 supports), B1@M2's 203 exceeds it.
  The choice was made by the code as committed before the run.

## OBSERVED

- **Every configuration of every family is behind v2** on DEV. The nearest is B1@M2, at 2.1 times v2's paired lag.
- **Soundness:** no alarm on an admissible row and none before t\* in any of the 115 configurations. LPs failed 5
  times in all (B1 (4, 8) with either prior: 2 each; B1lp: 1); a failed LP falls back to the unconstrained hull,
  which is outer.
- **The memory–lag frontier:** B1 32 → 203 reals: 306,089 → 68,710 s; more memory gave no further gain in the grid
  (n_c = 16 and 64 at o = 8: 111,971 and 122,092 s with box+err). Not monotone in memory; not explained here. B2, B3
  and B4: their smallest configuration is their best.
- **The prior's error-plane bounds** help B1 a great deal (best with box+err 68,710 s, with box only 369,969 s) and
  hurt B2 and B3 slightly (box 1,877,905 and 1,523,216 s; box+err 1,891,585 and 1,593,874 s), as the plan foresaw
  for outer strip intersections.
- **Scott's LP rescaling** (B1lp: n_c = 8, o = 4, fifo, box+err; 200 rows, 163 paired events): paired lag 23,033 s
  against v2's 7,897 s on the same rows (D_paired −1.92), 3 misses; the grid's (8, 4) greedy configuration on the
  same rows: 100,771 s, 21 misses. The interval-rescaled fifo (8, 4) is not in the grid, so the effect of the LP
  rescaling alone is not separated. B1lp costs 48.4 ms per sample against 1.9–6.2 ms for the grid's B1.
- **CPU per sample** (Arch, one core per worker, 10 workers): B1 1.9–6.2 ms (chosen: 2.36 and 2.34), B2 and B3
  0.04–0.11 ms, B4 0.008 ms.

## Why the set methods lag: the width of the as-range (explanatory, `widths.json`)

The alarm test compares the measurement with the predicted as-range. On DEV seed 430010 (E0, rw, uniform noise),
the healthy run's range width in °C:

| sample | 10 | 50 | 100 | 300 | 1000 | 3000 | median from 100 on |
|---|---|---|---|---|---|---|---|
| v2 (feasible interval) | 0.125 | 0.077 | 0.058 | 0.043 | 0.051 | 0.120 | 0.079 |
| B1@M1 | 0.115 | 0.301 | 0.106 | 0.069 | 0.120 | 0.280 | 0.158 |
| B1@M2 | 0.113 | 0.068 | 0.059 | 0.074 | 0.051 | 0.120 | 0.087 |
| B2 | 0.698 | 1.758 | 1.874 | 1.759 | 1.864 | 1.800 | 1.847 |
| B3 | 4.058 | 4.033 | 4.033 | 4.033 | 4.033 | 4.033 | 4.033 |
| B4 | 1.127 | 0.846 | 0.827 | 0.827 | 0.827 | 0.827 | 0.827 |

Detections on the same seed: jump_0.2 (t\* 502): v2 502, B1@M2 502, B1@M1, B2, B3, B4 none. drift_0.002 (t\* 565):
v2 635, B1@M2 1101, B1@M1 2258, B2 2750, B3 2267, B4 2258.

- B1, whose intersections are exact, keeps a range close to v2's; B1@M1 is about twice as wide.
- B2's strip intersection with the F-radius weight contracts the as-direction little, and its range stays near
  1.8 °C.
- B3's range stays at about the TA box's width (4 °C). With a small gain the observer's as-range follows the TA mode's
  uncertainty, which the constant gain never reduces. With a larger q the gain grows, and so does the noise it feeds
  back. On DEV q = 0.01 was the best of the four.
- B4's TA bound never leaves the box (above), and its as-range settles at 0.83 °C.
- v2 decides on two reals (its feasible interval) and keeps the information of every past measurement, through the
  rate bound on the measured coordinate. The set methods spend their budget on the ac and TA directions and lose that information in their
  outer approximations.

One seed, an explanation of the table above; not a result on its own.

## The plan's unit checks (step 1), on the chosen configurations

`baselines_run.py unit` at `147563bd`, on the Mac, after the choice (`results/v3/baselines/unit-147563bd/unit.json`):
- the true state lies inside each chosen set method's set (B1@M1, B1@M2, B2, B3, B4) at every sample of 12 healthy
  DEV runs (430000–430002, both arms, both ambient laws); none of them alarms;
- B5 equals F3 over the first 256 samples on 4 of those runs (no alarm, 512 LPs each). No fold happens before
  sample 256, so this checks the shared code up to the fold only.

## What this does not show

- Anything on the comparison block. The configurations above are the ones the block run would use.
- Whether other published variants (another strip weight for B2, a time-varying gain for B3, another reduction for
  B1) would do better. They were not in the plan's grid.
