# BASELINE2: two strengthened baselines on validation 3's block (plan v3.1, 2026-11-23)

Status: FROZEN on 2026-11-23 at 20:11, after the DEV grid, the unit checks and the tuning of section 3 (Arch, commit
3b363394, 16:59 to 20:04; outputs in `results/v3/baselines2/dev-3b363394/`), which gave no finding; Can's approval
below lets the freeze and the block follow. The block runs with
`results/v3/baselines2/dev-3b363394/chosen.json`, sha256
f7e48016ba8b5168cecddc5aa8c1efcc3a86aa390706a31fb66f2863ef68f836; validation 3's rows
`results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl`, sha256
d9b90cef1c9b932468888fa375ff11c8373520ce0d972337b5631cbee3f6988f; the first comparison's block rows
`results/v3/baselines/block-9438dffa/rows.jsonl.gz`, sha256
be3ffc160ee34e2d86079a98fb866c1ec360e7f10cab15f9d70b66675106bcb5.
- Chosen: B1s@M1 n_c 1, order 2, fifo (32 reals); B1s@M2 n_c 64, order 8, fifo (5,963 reals); B4s@M1 and B4s@M2
  L = 0 (6 reals).
- DEV, paired lag over 1,073 paired events (IM 32,925 s): B1s@M1 447,173 s, B1s@M2 146,563 s, B4s with L = 0
  31,315 s. B4s with L = 0 is earlier than IM on 64 of the 1,400 rows (all drifts) and later on none; section 1's
  "on DEV runs it equals IM" held for the five pre-check runs only (its box+err prior is information IM does not
  use). B4s with the first comparison's gain has IM's paired lag and is never later than IM.
- Unit checks: 16,800 records, complete; duplicates that differ 0; B4s later than IM 0; alarms on admissible rows or
  before a certified t* 0, for every configuration.
- Stability on 100 DEV rows (reported, not a finding): the first comparison's B1@M2 changes its detection on 24;
  B1s on none, except n_c 16 fifo, n_c 64 fifo and n_c 64 greedy, on 1 each.
- LP failures on DEV: 7, all in B1s n_c 64 fifo (B1's code then uses the unconstrained hull, which is outer).

Approval: v3.1 by Can Koç on 2026-11-23. v3 was approved for the DEV grid, unit checks and tuning ("kontrol
sende run için onaylıyorum run yapabilirsin"); its grid started on Arch at 582f798f at 16:36:22 and was stopped at
16:38:52, before any row was written, to apply review r4's findings (section 8). Can then approved the steps that
follow ("kontrol sende ben çıkıyorum adamım. onay veriyorum diğer işlemlerin için."): if the unit checks have no
finding, the freeze and the block follow without a further approval; any finding stops there until Can decides.
v2 was approved by Can
Koç on 2026-11-23 ("onaylıyorum.") and its DEV grid ran on Arch at e068e81f from 15:27:10; it was stopped at 16:08:52 at
Can's request ("durdur adamım düzeltelim") after 393 of the 1,400 DEV rows, because B1s alarmed on admissible rows
(section 7). Its partial rows are kept on Arch (`~/Research/sdts-runs/baselines2-dev-e068e81f/`) and are not used. v1 was
approved for its DEV grid at fe738d5e, but nothing ran under it: review r3 found two flaws in its code before the grid
started (B4s had no effect; B1 is chaotic at the 1e-15 level), and the queued run was stopped. v3 replaces v2. The block
runs only after the status line reads "Status: FROZEN" and quotes the sha256 of the chosen configurations, of
validation 3's rows and of the first comparison's block rows.

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
  1e-9; an interval rescaling whose propagation is outer in binary64 (v3: every coefficient in the row sums, an
  outward rounding pad, tightening only through coefficients above 1e-9, quotients rounded outward); v3.1 (section 8):
  a near-zero row empties the set only if |b_i| exceeds the sum of its |a_ij|, underflow and overflow handled, only an
  exactly fixed xi loses its column. Every choice is an outer approximation; the exact operations (prediction,
  intersection, elimination) run in plain binary64, as in B1.
  Pre-checks on 14 DEV rows (sections 7, 8): no alarm while admissible or before t*.
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
- B4s: two gains: L = 0 and the first comparison's chosen gain, which is (M12, M22, −0.01) = (0.0667, 0.7667, −0.01).
  (v2 listed (M12, M22, −0.01) as a third gain; it is the second one, and v2's grid ran it twice per row.)
- Unit checks before tuning (reported, any finding stops the freeze until Can decides): the DEV records are complete
  (every configuration on every row, one record each; v3.1); B4s never later than IM on any DEV row; no configuration
  flags an admissible row or before a certified t*; stability: the first comparison's B1@M2 and
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

1. Can approves v3.1. 2. DEV grid, unit checks, tuning on Arch (14 workers). 3. Freeze: status FROZEN with the three
sha256, committed. 4. Identity check and block on Arch. 5. Score; a dated record.
Times from v2's 393 DEV rows (seconds per run on Arch: B1s 5 to 15, n_c 64 the slowest; B4s 0.5): the DEV grid about
2.4 h, the stability check about 0.7 h; the block 2.6 to 4.2 h, depending on the configuration chosen for B1s@M2. v2
said "about 2 h" for each; that was an underestimate.

## 7. v2 → v3 (2026-11-23)

- **B1s's rescaling was not outer.** v2 used every nonzero coefficient in B1's interval propagation, with no rounding
  pad. In v2's DEV run (Arch, 393 rows) B1s n_c 16, order 8, greedy alarmed on 7 admissible rows and before t* on 2;
  no other configuration did, and no configuration of the first comparison's DEV grid had. On the Mac, at every
  rescaling of DEV run 430021 healthy E0 rw, the propagation's bounds of xi were compared with the exact ones by LP:
  at t = 175 the propagation cut a xi's range by 1 (half its box), through a coefficient 2.5e-18 times the row's
  largest (a rounding error of the row divided by a near-zero coefficient), and the set emptied at t = 190 (368 on
  Arch). With B1's tolerance (1e-12) the largest cut on that run was 3.9e-13 and there was no alarm, but leaving small
  coefficients out of the sums is not outer either. v3's propagation is outer by construction (section 1); with it,
  at every third rescaling of the 9 rows above, the largest cut against the LP was 6.2e-13, within the LP's own
  tolerances (HiGHS, primal feasibility 1e-7), and none of the 9 rows alarmed while admissible or before t*.
- **B4s's grid** has two gains, not three (section 3); the unit checks and the tuning keep one record per row and
  configuration, and two records that disagree are a finding.
- **Pre-check** (DEV, 2026-11-23, before this plan is approved; v3 code as in section 1, sha256 of
  `baselines_strong.py` beginning e00755c2): every B1s configuration on the 9 rows above and on the 5 DEV rows of
  section 0's shift test (430010 drift_0.002 E0 rw; 430010, 430014, 430019 drift_0.0005 E0 ramp; 430014 gain_0.01 E1
  rw), data shifted by 0, ±1e-15 and 2e-15, on the Mac (14 rows × 10 configurations × 4 shifts) and on Arch (the
  same). No alarm on an admissible row or before t*, on either machine. On the Mac no detection moved under the
  shifts; on Arch one did (430021 jump_0.2 E0 rw, n_c 16, order 8, fifo: 552 at three shifts, 558 at 2e-15), so 1 of
  560 values differs between the machines. B1s is far steadier than B1 (section 0), but not bit-stable; the
  stability count of section 3 reports this on 100 rows.

## 8. v3 → v3.1 (2026-11-23, review r4 of the v3 code)

Review r4 read the v3 draft (read-only copy on Arch) and ran DEV-only checks. Its findings and what was done:
- **A near-zero row emptied the set** (`_eliminate_one`, inherited from B1): a row whose coefficients are all at
  most 1e-9 set the set empty when |b_i| > 1e-9, although a point with |xi| ≤ 1 can satisfy it (r4's example:
  A = [6e-10, 6e-10, 6e-10], b = 1.5e-9, xi = 5/6 each). v3.1: empty only if |b_i| > Σ|a_ij| + 1e-9; otherwise the row
  is dropped (outer).
- **The unit check counted an uncertified t\*** (one DEV row, 430003 drift_0.001 E1 rw, status undetermined, t* 1956):
  v3.1 counts alarms before t* on certified events only, as the scoring does; and the unit checks and the tuning
  refuse incomplete records or configurations off the grid.
- **Overflow and underflow in `_bounds`** (r4's constructed examples; not reachable in this plant, whose rows are
  scaled to unit norm): an overflowing row gave NaN bounds and wiped the generators; 25 copies of a row with
  coefficients 2^-1074 cut a feasible point. v3.1: the pad has an absolute term for underflow, a row with a non-finite
  sum tightens nothing, and crossed or non-finite bounds leave the set to the LP (B1: crossed by more than 1e-9).
- **A xi up to 1e-12 wide lost its column** (B1's rule; r4 measured 16 such drops on 3 DEV runs, the widest
  2.55e-15): v3.1 drops only an exactly fixed xi, so no step of the reduction leaves the outer approximation.
- **Portability** (r4: the DEV grid would fail on macOS's spawn start method): not confirmed; the DEV command ran one
  row with all 12 configurations on the Mac (spawn), because the child process imports the main script.
r4 found `_bounds` outer in binary64 in the finite range (its pad covers the rounding about twice over) and the other
B1s changes outer. B4s's propagation is unchanged (plain binary64; r4 found no false alarm on the 80 healthy DEV runs
with edge noise, both gains). All of r4's examples were rerun: v3 fails each, v3.1 passes each; on the 9 rows of
section 7 the outer probe gives the same detections and cuts as under v3.
- **Pre-check of v3.1** (same rows, shifts and machines as section 7; sha256 of `baselines_strong.py` beginning
  34c7ff6a): all 560 detections on each machine equal v3's; no alarm on an admissible row or before t*; the same
  single difference (Arch, 430021 jump_0.2 E0 rw, n_c 16, order 8, fifo, 558 at 2e-15).
