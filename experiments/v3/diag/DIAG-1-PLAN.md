# Diagnosis 1: where does the bounded state lose what the oracle knows? (plan, not run)

Status: PLAN. Nothing in it has been run. Written 2026-11-18, after freeze 1 passed (`RECORD-2026-11-18-validation.md`),
from the reviews (reviewers A, B and C) and the working notes.

**Scope:**
- DEV seeds only.
- Freeze 1 (its files, results and rules) is not touched.
- Seeds 440200 and up stay reserved.
- No new candidate is chosen here. This plan only finds where the loss happens.

## 0. The question, made exact

By Theorem 1, everything the history says lives in the 3-D set X_k of states (ac, as, TA), the common ambient path
included. "Correlation between far-apart measurements" is therefore not a separate kind of information; it is a
part of the shape of X_k. What is open is where cyl16p loses that shape, and when.

## 1. The three sets and the step at which they are compared

All three are taken **after measurement k has been applied** (cut to the slab of z_k):

| set | what it is | in the code |
|---|---|---|
| X_k | the exact information state | vertex enumeration (`exact_vrep.py`); a numerical diagnostic, see section 5 |
| H_k | hull_D(X_k): the tightest set with cyl16p's directions D that contains X_k, with h_i = max over the vertices of X_k of d_i·s | |
| P_k | cyl16p's own state | `TemplateMachine._last_tightened` |

The quantity compared is what decides the next sample. The same physical step (M, the ambient segment, the box and
the reachable-set clamps) is applied to each set, and then the as-range of the result is taken **before measurement
k+1**: its two supports in +e2 and −e2.

**The trap (reviewers A and B):** if a set were wrapped in D after the prediction, its ±e2 supports would be exact,
because ±e2 is in D, and it would reproduce the oracle's decision by construction. My earlier "t_H, H rebuilt every
step" test did exactly that. It is withdrawn; it is not a ceiling for any online method.

**The ordering, and so an exact split of the set gap.** For every direction u:

    supp_X(u) ≤ supp_H(u) ≤ supp_P(u).

H is the smallest set with these directions that contains X, and P is one such set. The gap in u splits exactly into
P − H (how loose the recursion got) plus H − X (what these directions cannot say). This is a split of set gaps, not
of detection delays.

## 2. The arms: one start, several continuations

The start is k0 = t* − L, with L in {16, 64, 256}. Every arm processes the same measurements z_{k0+1}, … and runs
until its first inconsistency or the end of the record. The arms:

| arm | start | continued with | answers |
|---|---|---|---|
| A | X_k0 | exact recursion | reference: must detect at the certified t* (a check of the machinery) |
| B | H_k0 | exact recursion, no templating after k0 | what the directions lost at k0 alone |
| E | P_k0 | exact recursion | what cyl16p had already lost before k0, with no new wrapping |
| C | H_k0 | cyl16p's online update (pruned table) | B to C: new wrapping after k0 |
| C_full | H_k0 | online update with the full cyl16 table (38966 entries) | C_full to C: the cost of pruning the bases (reviewer B) |
| D | P_k0 | cyl16p's online update | the real cyl16p from k0 |
| F | P_k0, with h(−e3) set to the exact −min TA of X_k0 | cyl16p's online update | the narrow hypothesis that only the ambient's lower bound is missing (reviewer B) |

**The arms are nested, so the delays telescope exactly.**
- The exact recursion and the template recursion are both monotone in their start set. The template update is a min
  over λ ≥ 0 of λ·h, then mins with the measurement and the clamps.
- Together with X_k0 ⊆ H_k0 ⊆ P_k0 this gives, for every k ≥ k0: A ⊆ B ⊆ C ⊆ D, and B ⊆ E ⊆ D, and
  C_full ⊆ C.
- So t* = t_A ≤ t_B ≤ t_C ≤ t_D, and t_B ≤ t_E ≤ t_D, and t_Cfull ≤ t_C.
- All of this holds in exact arithmetic. The implementation's outward pads depend on max|h| (`GAMMA4`, `_cap`), which
  is not monotone in h, so the nesting holds only up to those pads (about 1e-14 °C). A tie broken the other way at
  that size is reported, not forced.
- H_k0 is built from floating-point vertices of X_k0, so it is not certified to contain X_k0. The arms that start
  from it are diagnostics, like the exact arms.

**The pieces depend on the order of decomposition**, which is reviewer A's warning, taken precisely. Along A→B→C→D,
the delay t_D − t* splits into start geometry, then new wrapping, then earlier slack. Along A→B→E→D it splits into
start geometry, then earlier slack without wrapping, then wrapping from the worse start. The sum is the same; the
pieces need not be. Both orders are reported; when the pieces differ, the effects interact, and that is reported as
such.

## 3. What is recorded

Per arm, per step k from k0 until it detects (and in any case up to t* + 1):
- **The signed margin** of the next measurement against the predicted as-range, in °C: min(z+δ − lower, upper − (z−δ)).
  Negative means detected (reviewer B).
- **The support gaps** against A (B − A, C − A, D − A, E − A) in every direction of D, and in ±M^T e2.
- **The detection time.**

At t* − 1, for arm A only:
- the facets of X that carry the separating support (the dual of the support of ±e2 after the prediction), with their
  weights and normals;
- each normal's **age**: the j for which it lies closest to the plane orthogonal to M^j e3. Computed with forward
  powers of M (stable; reviewer C's warning about (M^-T)^j applies to inverse powers).

## 4. What each explanation predicts (written before anything is run)

| explanation | prediction | what would refute it |
|---|---|---|
| **direction loss** (the template cannot describe the decisive shape) | t_B − t* large for L ≥ 64; H − X large in the deciding direction already at k0 | t_B ≈ t* for every L |
| **wrapping** (lost during the online update) | t_B ≈ t*, t_C ≫ t_B; C_full ≈ C | t_C ≈ t_B |
| **slack accumulated before k0** | t_E ≫ t_B, and D ≫ C | t_E ≈ t_B and t_D ≈ t_C |
| **only the ambient's lower bound** (narrow) | t_F ≈ t_C or better, ≪ t_D | t_F ≈ t_D |
| **intermediate-age directions** (reviewer C's M^-T idea; ages 16–256, slow mode τ = 63.5 samples) | the separating facets at t* − 1 have ages in about 16–256 | ages near 0 (cyl) or ∞ (inv), or spread with no cluster |

Three runs (E0, DEV) are enough to choose a mechanism, not to measure its size. A finding is kept as a mechanism
only if it shows in all three, or the run where it does not is explained.

**Interpretation rules:**
- A narrows the search; it does not prove a cause.
- Latency is ill-conditioned near the detectability boundary, so margins and gaps carry more weight than delays.
- No candidate is built from this. A candidate that follows from it (an aged-cyl family, a better update, a bounded
  online adaptive state with v2 in parallel, a window LP) is evaluated online on DEV seeds not used here, then frozen.

## 5. Runs and numerics

**The runs:**

| run | oracle t* | v2 detects at | cyl16p lag |
|---|---|---|---|
| 430007 / drift_0.002 / rw / E0 | 673 | 1142 | see DEV rows |
| 430019 / drift_0.001 / ramp / E0 | 393 | 1086 | see DEV rows |
| 430010 / drift_0.0005 / ramp / E0 | 695 | 3575 | 2880 (every bounded state) |

Order: 430007 and 430019 first; 430010 is the slowest (its exact set grows to thousands of vertices).

**Numerics:**
- The exact arms (A, B, E) use floating-point vertex enumeration. They are numerical diagnostics, not certified.
- Arm A must reproduce the certified t*. If it does not, the run's exact arms are not used.
- Every margin or support gap below 1e-6 °C is labelled "too close to call".
- The deciding supports at t* − 1 and at k0 are recomputed independently by LP (section 6).

## 6. Independent check (a task for reviewer B, run on Arch in its own clone, no SSH)

The aim is to verify the exact supports by a method that shares no code with the vertex enumeration.

- **Input:** the three runs above (regenerated from `dev_scenarios.py` at this branch's head, DEV seeds), and the
  values written by the diagnosis (`results/v3/diag1/*.json`, when they exist).
- **Task:** for k in {k0 = t* − L for L in 16, 64, 256; and t* − 1}, compute by LP over the full history z[0..k]
  (the oracle's constraint set, b = 0, |v| ≤ δ, the TA box, the rate bound) the exact maximum and minimum of
  as[k+1] after the physical step, and also of TA[k].
  - Use HiGHS through scipy, as in `experiments/oracle`.
  - Report the solver status, and a dual bound where the oracle code computes one.
- **Output:** one JSON per run with those numbers. Compare them with arm A's values; any difference over 1e-6 °C is
  reported.
- **Rules:**
  - No commits.
  - No edits to this repository's files.
  - Write only under a separate folder under `~/Research/sdts-runs/`. The results are imported into this repository and recorded,
    with Can as author.
  - No validation seeds, no freeze files.

## 7. Float32 and the rest, kept apart

Float32 (freeze 1: inv4p float32 D 0.004, cyl16p float32 D 0.212) is its own track and is not mixed into this
diagnosis. The window LP and the bounded online adaptive state stay as candidates for after it.

## Amendment 1 (2026-11-18, ~10:50, written before any arm result)

**What was found when T1 started.**
- Measured on the frozen tables:

  | run | cyl16p lag behind the oracle | v2 lag |
  |---|---|---|
  | 430007 / drift_0.002 / rw / E0 | 119 | 469 |
  | 430019 / drift_0.001 / ramp / E0 | **0** (cyl16p detects at t* = 393) | 693 |
  | 430010 / drift_0.0005 / ramp / E0 | 2880 | 2880 |

- So 430019 is not a case where cyl16p loses anything. The three runs had been named from v2's and inv4's lags.

**The selection table** (`select_runs.py` at `246091f`, Arch: `~/Research/sdts-runs/v3-diag1/selection.json`):
- It covers cyl16p and inv4p on every DEV evaluation row of the three cells (430000–430029, uniform noise, certified
  t*).
- E0 and E1 give identical results in every row. The known command cancels out of z for these cells, so E0 alone is
  used.
- On 53 of the 88 E0 rows, cyl16p's lag equals v2's exactly.

**The rule.** Keep the three named runs, with 430019 as a control (no loss to explain). Add, per cell, the E0 row
with the largest cyl16p lag:

| cell | run | t* | cyl16p lag | v2 lag |
|---|---|---|---|---|
| drift_0.002 / rw | 430027 | 579 | 850 | 850 |
| drift_0.001 / ramp | 430000 | 849 | 1199 | 1199 |
| drift_0.0005 / ramp | 430010 (already named) | 695 | 2880 | 2880 |

The diagnosis runs on 5 runs: 430007, 430019 (control), 430010, 430027 and 430000. The LP check (T2) is wanted for
430027 and 430000 too, at the same points.

**One more output** (reviewer C, H1): for each separating facet normal n, |n·e3| (age 0) and |n·(1,1,1)|/√3
(age ∞) are reported next to the best-matching age j. Directions orthogonal to both e3 and (1,1,1) match at both
ends, so argmin_j alone would mislead.
