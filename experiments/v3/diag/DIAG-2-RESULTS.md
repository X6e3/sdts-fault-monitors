# Diagnosis 2: results (DEV only; 2026-11-18)

**Plan:** `DIAG-2-PLAN.md`, commit `2b79e8f`, with its criteria fixed before any result.

**Run:**
- `diag2.py` at `2b79e8f` on Arch, clean tree, 20 jobs, 11:34–11:38.
- Outputs are in `results/v3/diag2/run1-2b79e8f/`.
- `summary.json` comes from `diag2.py summary` after one later change. That change fixed the JSON types (numpy bools had
  been written as strings) and added the exact split of the rise at a cut. The criteria's logic is unchanged.

**Freeze 1** and seeds 440200+ are untouched. **Labels:** OBSERVED, INFERRED and HYPOTHESIS, as in DIAG-1.

**In short:**
- **Neither family passes DIAG-2.** B2 closes 60 % of the TA rises at cuts, but it halves the decision loss at t* in
  only 1 of the 4 hard runs.
- **T1 corrects the round-2 picture.** 95 % of what a cut costs is lost even by the tightest D-hull of the exact
  set. It is the geometry of the representation at the cut, not slack the recursion has piled up.

## Checks (OBSERVED, all pass)

- **B1 and B2** equal reviewer C's posted list: 26 pairs, largest difference 4.8e-7.
- **Arm A,** recomputed, reproduces t* in all 5 runs.
- **Arm C,** recomputed, matches DIAG-1 within 6e-11 mC.
- **D_D0** (cyl16p's directions, full table, from k = 0) reproduces cyl16p's detection in all 5 runs.
- **C with D0's full table** reproduces DIAG-1's C_full exactly (the event rises agree to all printed digits).
- **Nesting:**
  - A ≤ B_F within 7e-10 mC;
  - C_F ≤ C_full(D0) within 1e-10 mC.

## T1: what a cut costs (OBSERVED, the 63 events of `review1/steps.txt`)

Sums over the events of the TA gap against A, both signs (±e3), in mC:

| run | events | rise at the cut | geometry, D0 | beyond geometry | geometry, B1 | geometry, B2 |
|---|---|---|---|---|---|---|
| 430007 | 13 | 140.4 | 120.6 | 19.8 | 113.2 | 42.2 |
| 430027 | 11 | 121.6 | 120.2 | 1.3 | 110.3 | 19.4 |
| 430000 | 17 | 120.4 | 129.7 | −9.3 | 110.6 | 40.5 |
| 430010 | 11 | 84.4 | 83.5 | 0.9 | 73.0 | 37.4 |
| 430019 | 11 | 116.1 | 102.5 | 13.6 | 91.9 | 20.1 |
| all | 63 | **582.9** | **556.5 (95 %)** | **26.4 (5 %)** | 499.1 | 159.6 |

**The columns:**
- **Rise at the cut:** the TA gap of C against A just after the cut minus just before it. It is the same at k + 1.
- **Reviewer B's pair:** with z_k skipped, the gap does not rise at all (< 1e-9 mC in total). So the whole rise comes with the
  cut, now measured rather than inferred.
- **Geometry:** supp_{hull_F(Q) ∩ S} − supp_{Q ∩ S}, the rise that even the tightest F-hull of A's exact pre-cut set Q
  would have at this cut. Before the cut, that hull has no TA gap, because ±e3 ∈ F.
- **Beyond geometry:** rise − geometry(D0), exactly (MATH, the plan's split). It is the part due to C's own state
  being looser than that tightest hull. It can be negative.

**INFERRED, a correction to review rounds 1 and 2.**
- **Where the exposed slack comes from:** not mainly from the recursion. The tightest D0-hull of the exact set
  already has it; it is the exact set's shape that the directions cannot express.
- **Re-templating:** each step discards that shape. Between cuts this costs nothing in TA or in the as-range. At a cut
  it costs TA.
- **Reviewer C's d[36] growth is real, but small:** the slack C piles up beyond the tightest hull accounts for 5 % of
  the rises.
- **The earlier wording, "the slack builds up beforehand, in other directions":** true only for that 5 %.

**More directions reduce the geometry part:** B1 by 10 %, B2 by 71 %.

## T2: the families in the arms (OBSERVED, L = 256)

**Detection times** ("—": none before t* + 300):

| run | t* | cyl16p | B: D0 / B1 / B2 | C: D0 / B1 / B2 | D_F from k = 0: D0 / B1 / B2 |
|---|---|---|---|---|---|
| 430007 | 673 | 792 | 673 / 673 / 673 | 792 / 792 / **765** | 792 / 792 / **765** |
| 430027 | 579 | 1429 | — / **579** / **579** | 1429 / 1429 / 1429 | 1429 / 1429 / 1429 |
| 430000 | 849 | 2048 | 849 / 849 / 849 | 2048 / 2048 / 2048 | 2048 / 2048 / 2048 |
| 430010 | 695 | 3575 | — / **695** / **695** | 3575 / 3575 / **3539** | 3575 / 3575 / **3539** |
| 430019 (control) | 393 | 393 | 393 | 393 | 393 |

**C's margin at t*, and its loss against A** (mC):

| run | A | C, D0 (loss) | C, B1 (loss) | C, B2 (loss) |
|---|---|---|---|---|
| 430007 | −4.186 | 21.304 (25.49) | 15.060 (19.25) | 4.891 (**9.08**) |
| 430027 | −4.101 | 1.539 (5.64) | 1.302 (5.40) | 0.965 (5.07) |
| 430000 | −4.625 | 5.554 (10.18) | 4.378 (9.00) | 2.819 (7.44) |
| 430010 | −0.389 | 3.928 (4.32) | 3.928 (4.32) | 3.928 (4.32) |
| 430019 | −4.509 | −0.240 | −0.791 | −1.671 |

**TA rises of C at the 63 events:** C_full(D0) 582.9 mC, B1 455.1 mC (0.78 of it), B2 230.8 mC (0.40 of it).

## The criteria (as fixed in the plan)

| family | (a) closes the cut steps (≤ 0.5) | (b) halves the t* loss in ≥ 3 of 4 | (c) C detects at t* | passes |
|---|---|---|---|---|
| B1 (72 directions) | no (0.78) | no (0 of 4) | 0 of 4 | **no** |
| B2 (94 directions) | yes (0.40) | no (1 of 4: 430007) | 0 of 4 | **no** |

**Per the plan:**
- T3 (DEV online evaluation) is not run.
- The next candidate is the K/W-budget common-path LP, in its own plan. Can decides.

## What else the run shows (OBSERVED)

- **Direction loss at k0 is fixed by more directions.** B_F detects at t* in 430027 and 430010 for both families;
  with D0 it did not. So DIAG-1's B − A piece is a matter of directions. The update loss is not, with these
  families.
- **The candidates themselves (D_F, from k = 0):**
  - B2 detects 27 samples earlier in 430007 and 36 earlier in 430010, and the same elsewhere.
  - B1 changes nothing.
  - **Table sizes:** B1 559,660 entries and B2 1,619,250 (both full), against 38,966 full and 1,318 pruned for cyl16p.
- **In 430010, C's margin at t* is the same for all three families,** to 1e-9 mC. Something these directions do not
  touch sets it. Not identified.
  - HYPOTHESIS: a basis common to all three, such as the measurement slab with the as-velocity direction. That would
    also explain why every bounded state ties with v2 there.

## What this suggests (INFERRED and HYPOTHESIS; nothing built)

- **INFERRED:** fixed families shrink the per-cut loss (B2: −71 % of the geometry part). The decision at t* barely
  moves (1 of 4 runs), at a table cost 40 times the full cyl16p table. What a cut needs is the exact set's shape near
  the cut, and a fixed family approximates that only coarsely and expensively.
- **HYPOTHESIS: two ways to keep that shape,** both forms of the bounded online adaptive state (with v2 in parallel):
  1. **The K/W-budget common-path LP:** keep the recent cuts exactly. Dropping the oldest cut is sound (DIAG-1, round
     2); how tight it stays is the question.
  2. **Directions chosen online at each cut** from the facets that carry the TA extreme: an adaptive template. Its
     soundness needs the same outward wrapping when directions change.
- **Not shown:**
  - anything beyond these 5 runs, which were chosen for the diagnosis;
  - the cause of 430010's fixed margin;
  - why C keeps the decision through the last 64 steps (DIAG-1) although cuts there have the same geometry.
