# BASELINE2: two strengthened baselines on validation 3's block (plan v2, 2026-11-23)

Status: APPROVED v2 by Can Koç on 2026-11-23 for the DEV grid, unit checks and tuning ("onaylıyorum."). v1 was approved for its DEV grid at fe738d5e, but nothing ran under it: review r3
found two flaws in its code before the grid started (B4s had no effect; B1 is chaotic at the 1e-15 level), and the
queued run was stopped. v2 replaces v1. The block runs only after the status line reads "Status: FROZEN" and quotes the
sha256 of the chosen configurations, of validation 3's rows and of the first comparison's block rows.

## 0. Why

Reviews r2 and r3 (2026-11-23) read the code of the first comparison (BASELINE-PLAN.md, block 9438dffa):
- B4, the interval observer, never intersects its range with the measurement; IM does. In the cooperative form the
  winning gain also zeroes the as-column, so an intersection alone would be lost at the next step.
- B1, constrained zonotopes, is numerically chaotic: on DEV run 430010 drift_0.002 a shift of the data by 1e-15 °C
  moves its first detection between 635, 1101, 2247 and 2258 (checked on the Mac, 2026-11-23), and the first
  comparison's own records disagree across machines for that run (635 on Arch, 1101 on the Mac). Its discrete choices
  (exact elimination, Girard near-ties, prior strips) switch on the last bits.
The first comparison stays as it is (plan, code, rows, verdicts); the paper reports both and states B1's instability.

## 1. Methods (`diag/baselines_strong.py`; `baselines.py` and `baselines_cz.py` unchanged)

- **B1s**: B1 with stable discrete choices and its own fixes: rows scaled before the lifted reduction; exact
  elimination up to 1e-12; scores rounded to 1e-10 before sorting (near-ties by index); a prior strip only beyond
  1e-9; every nonzero coefficient in the interval rescaling. Every choice is still an outer approximation.
  On five DEV runs (2026-11-23) its detections did not change under shifts of 0, ±1e-15 and 2e-15.
- **B4s**: B4 with three outer tightenings: the as-range intersected with the measurement slab; the box+err prior by
  interval propagation; IM's rate rule. By construction it is never later than IM; on DEV runs it equals IM. It is a
  check that the interval-observer family reaches IM, not a rival expected to pass it. (r3 computed that the
  observer in transformed cooperative coordinates keeps an as-range of at least about 0.7 °C; that is r3's result and
  is not part of this plan.)
- Not done here, and stated in the paper: Scott's LP rescaling and constrained-range prior checks at block scale
  (they cost several times more), other strip weights for B2, B3, and a fresh-block head-to-head of every method.

## 2. Data

- DEV: the 1,400 rows of the first comparison. Block: validation 3's 9,600 runs (seeds 440400–440599), a used block:
  a fixed comparison, not a new validation.

## 3. Grid, unit checks and tuning (`diag/baselines2_run.py`, on Arch)

- B1s: (n_c, o) in (1, 2), (3, 1) [M1, at most 42 reals] and (4, 8), (16, 8), (64, 8) [M2]; policies fifo and greedy;
  prior box+err. 10 configurations.
- B4s: three gains: L = 0, the first comparison's chosen gain, and (M12, M22, −0.01).
- Unit checks before tuning (reported, any finding stops the freeze until Can decides): B4s never later than IM on
  any DEV row; no configuration flags an admissible row or before t*; stability: the first comparison's B1@M2 and
  every B1s configuration on 100 DEV rows (smallest sha256 keys) with the data shifted by 0, ±1e-15 and 2e-15, the
  number of rows whose detection changes.
- Tuning rule as in the first comparison: per family and budget, the smallest paired lag on DEV among configurations
  with no alarm on an admissible row and none before t*. M1: at most 42 reals; M2: no upper limit.

## 4. Hypotheses (fixed now; `baselines_run.boot_diff`, 2,000 draws over the 200 seeds)

Paired lag over validation 3's paired events, ours minus the baseline's; supported if the 95 % interval lies below 0.
- **H-S1**: WM's paired lag is below B1s@M2's.
- **H-S2a**: TS's paired lag is below B1s@M1's.
- **H-S2b**: TS's paired lag is below B4s@M1's.

## 5. Reported either way

For every chosen configuration and for the first comparison's B1 and B4 on the same rows: D_paired against IM,
misses, detections at t*, alarms on admissible runs and before t*, memory (reals between samples), time per sample,
LP count and LP failures. Before the block: an identity check (the first comparison's B1@M2 and B4 on one run per
design cell must give the first block's detections; with B1's instability a difference is possible and stops the
block until Can decides). If a hypothesis is not supported, the paper says so and drops the claim that every baseline
lagged; the abstract and highlights follow the result.

## 6. Order and cost

1. Can approves v2. 2. DEV grid, unit checks, tuning on Arch (14 workers; about 2 h). 3. Freeze: status FROZEN with the
three sha256, committed. 4. Identity check and block on Arch (about 2 h). 5. Score; a dated record.
