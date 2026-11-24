# Diagnosis 2: what happens at a cut, and do the families B1 and B2 close it? (plan)

**Status:** started on Can's go on 2026-11-18. This plan and its criteria were written and committed
before any DIAG-2 result.

**Scope:** DEV seeds only, the five DIAG-1 runs. Freeze 1, its results and seeds 440200+ are not touched. No candidate
is frozen here.

**Background:** see `DIAG-1-RESULTS.md`, review rounds 1 and 2. In arm C (L = 256), every rise over 1 mC of the TA
gap follows an active measurement cut: 63 events, 565 mC in all. Before a cut, the slack builds in directions the
dynamics does not map back into the template's directions D.

## T1: the cut steps, split exactly (reviewer B's suggestion)

**Events:** the same 63 steps k as in `review1/steps.txt`. A step qualifies when z_k's slab cuts arm C's or arm B's
predicted as-range at k, and the TA gap C − B (±e3) rises by over 1 mC from k to k + 1.

**Sets per event:**
- Q, arm A's exact predicted set at k;
- P_C, arm C's predicted template at k (cyl16p's pruned table, started from hull_D(X_k0) as in DIAG-1);
- S, z_k's slab.

**The exact split (MATH).** Q ⊆ hull_F(Q) ⊆ P_C for F = D, and intersecting with S keeps the order. So the TA gap
right after the cut splits exactly into two non-negative parts:

    supp_{P_C ∩ S}(u) − supp_{Q ∩ S}(u)
      = [supp_{P_C ∩ S}(u) − supp_{hull_D(Q) ∩ S}(u)]     accumulated slack (the state was already looser than the
                                                          tightest D-hull of the exact set)
      + [supp_{hull_D(Q) ∩ S}(u) − supp_{Q ∩ S}(u)]       geometry of the cut (the loss even the tightest D-hull
                                                          has at this cut)

Here u = ±e3, and the supports of template sets are computed by LP.

**Also recorded:**
- **Reviewer B's cut/skip pair:** the TA gap C − A after the next prediction (k + 1), once with z_k applied and once with z_k
  skipped.
- **The geometry part for the other families:** supp_{hull_F(Q) ∩ S}(u) − supp_{Q ∩ S}(u) for F = B1 and B2.

T1 has no pass/fail. It reports the share of each part and how the geometry part changes with F.

## The families B1 and B2 (reviewer C H1)

The rule is the one in reviewer C's `propose_directions_b.py`, re-implemented in `diag2.py`.

**B1 (72 directions):**
- Start from D0 = cyl16p's 42 directions.
- Add M^T d for every d in D0 that lies more than 4.8° from the current set.
- Then add (M^T)^j d for j ∈ {2, 4} and d ∈ D0[2, 6, 20, 22, 24, 36, 38] that lie more than 7.0° from the current set.

**B2 (94 directions):** B1 plus rings at latitude 20° (8 azimuths) and 40° (6 azimuths), kept when more than 12.0°
from the current set.

**Details of the rule:**
- Each addition is a ± pair, signed so that its first non-zero component is positive.
- Before use, the 26 added pairs are checked against reviewer C's posted list (6 decimals).

**The tables:** every family uses its full basis table, `Template(F, invariant=True)`, with no pruning (in DIAG-1,
pruning made no difference). D0 is used the same way.

**Nesting (MATH):** with full tables, a superset of directions is never looser from a tighter-or-equal start, since
hull_{F'}(S') ⊆ hull_F(S) when F ⊆ F' and S' ⊆ S. So C_B2 ⊆ C_B1 ⊆ C_full(D0), up to the outward pads. This is checked.

## T2: the families in the arms (L = 256, five runs)

For F ∈ {B1, B2}:

| arm | start | continued with |
|---|---|---|
| B_F | hull_F(X_k0) | the exact recursion, with F's clamps |
| C_F | hull_F(X_k0) | F's online update (full table) |
| D_F | F's own state from k = 0 | F's online update, to detection (the candidate itself on these runs) |

**Also run:** D_D0, cyl16p's directions with the full table from k = 0, which must reproduce cyl16p's detection.

**Recorded:** for each arm, the detection time and the step-by-step margins, and the supports in the 42 D0 directions
(so that A from DIAG-1 is the common reference).

## Criteria (fixed before any result)

Write g_F(k) = supp_{C_F}(u) − supp_A(u) for u = ±e3. "The TA rise at an event" means g_F(k+1) − g_F(k), summed over
both signs. The reference is C_full(D0) from DIAG-1. The four hard runs are 430007, 430027, 430000 and 430010.

1. **(a) Closes the cut steps:** over the 63 events, the summed TA rises of C_F are at most 50 % of C_full(D0)'s.
2. **(b) Closes the decision loss:** the t* margin loss of C_F against A is at most 50 % of C_full(D0)'s, in at least
   3 of the 4 hard runs.
3. **(c) Recovers the decision:** C_F detects at t* in at least 3 of the 4 hard runs. Reported, not required.

**A family passes DIAG-2 if (a) and (b) both hold.**

**What follows:**
- **If a family passes:** T3 evaluates it online on the DEV evaluation rows, float64 and full table. It is compared
  with cyl16p and v2 on the same rows (D_paired, misses, soundness), and its table size is reported. T3 is DEV only;
  any candidate from it still needs a new freeze and seeds 440200+.
- **If neither passes:** the result is reported. The next candidate is the K/W-budget common-path LP, in its own plan.
  Can decides.

## Numerics and checks

- **Exact sets:** floating-point vertex enumeration, as in DIAG-1. A numerical diagnostic, not certified.
- **Template supports:** LP (HiGHS). Differences below 1e-6 °C are "too close to call".
- **Required checks:**
  - arm A reproduces t* (via the recomputed exact pass);
  - D_D0 reproduces cyl16p's detection;
  - the nesting B_F ⊇ A and C_F ⊆ C_full(D0) holds, within 1e-9 °C;
  - B1 and B2 match reviewer C's posted list.

**Where things run:**
- On Arch, in a separate run clone.
- Outputs go to `~/Research/sdts-runs/v3-diag2/`, then are imported into `results/v3/diag2/`.
