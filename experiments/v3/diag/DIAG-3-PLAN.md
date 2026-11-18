# Diagnosis 3: a window LP that folds into a template (plan, phase 1)

**Status:** started on Can's go, 2026-11-18 ("başlayalım"). This plan and the phase-1 criteria were written and
committed before any DIAG-3 result.

**Scope:** DEV seeds only, the five DIAG-1 runs. Freeze 1, its results and seeds 440200+ are not touched. No candidate
is frozen. This is not yet an MCU design: phase 1 asks whether the architecture can work at all.

**Why this test** (`DIAG-2-RESULTS.md` and the team's round-3 comments):
- **The loss is mainly geometric.** 95 % of a cut's TA loss happens even for the tightest D-hull of the exact set.
  Fixed families do not close it (B1, B2).
- **The decisive +e3 losses come early:** 83–250 steps before t* (Hydrogen, checked). TA's eigenvalue is 1, so a loss
  is carried unchanged to t*.
- **The start matters (Sol).** Arm E, the exact recursion from cyl16p's own state with every later measurement, misses
  t* in 430027 and 430010 even at L = 256. A window that starts from cyl16p's kind of summary cannot recover those
  runs. The window's own summary has to be tighter.

## The architecture

**The state:**
- a base template b at time τ (cyl16p's 42 directions D0): {x_τ : D0 x_τ ≤ b};
- the measurements z_{τ+1}, …, z_t of a window of W to W + B samples (B = 16).

**The window LP** has variables x_τ, …, x_t (3 per sample) and these constraints:
- the plant: rows 1 and 2 of x_{j+1} = M x_j exactly, and |TA_{j+1} − TA_j| ≤ ρ;
- the boxes: TA, ac and as in [LO, HI];
- the measurements: |z_j − as_j| ≤ δ;
- the start: D0 x_τ ≤ b, or, before the first fold, the exact initial segment ac = as = TA at time 0.

There is one common ambient path, with no transported halfspaces.

**The step at sample t:**
1. Two LPs give the predicted as-range at t, from the measurements up to t − 1.
2. If z_t's slab misses that range, the run is detected at t. Otherwise z_t joins the window.

**The fold:** when t − τ > W + B, the base moves to τ' = τ + B:

    b'_i = max { d_i · x_τ'  over the window LP }   (+ a pad of 1e-6 °C), then the template's clamps

The fold comes in two variants:
- **smoothing (S):** the LP keeps every measurement in the window, through t, so later measurements tighten the
  base;
- **filter (F):** only the measurements up to τ'. This is a B-step block update of the template, the control for the
  value of smoothing.

**Soundness (MATH; GPT and Sol, round 2):**
- Every constraint holds for every trajectory consistent with the full history.
- By induction, the base contains the projection of the full-history set onto x_τ. So the window LP's set at t
  contains X_t, and no run can be detected before t*.
- The pad only loosens. HiGHS's tolerances make this a numerical diagnostic, not a certificate.

**Window length W = ∞** (no fold) is the full-history LP, i.e. the oracle. It must detect at exactly t*; this is the
check of the machinery.

## Runs

- **The five runs:** 430007, 430027, 430000, 430010, and 430019 (the control).
- **The variants:** W ∈ {64, 128, 256} × {S, F}, plus W = ∞.
- **Online from k = 0,** until detection or t_cyl16p + 300.

**Recorded per run and variant:**
- the detection time;
- the margin at every step;
- the LP sizes (variables, rows), the number of LPs, and the time.

## Criteria (fixed before any result)

**The score:** for a hard run, R = (t_cyl16p − t_det) / (t_cyl16p − t*), the share of cyl16p's lag recovered. R is 1 at
the oracle, 0 at cyl16p, and negative when worse.

**Phase 1 passes for a smoothing variant W** when all three hold:
1. R ≥ 0.5 in at least 3 of the 4 hard runs (430007, 430027, 430000, 430010);
2. no detection before t* in any of the 5 runs;
3. 430019, the control, detects at t* (393).

**Required checks:**
- W = ∞ detects at exactly t* in all 5 runs;
- no LP fails other than as "infeasible = detected".

**The F variants have no criterion.** Their difference from S is the measured value of smoothing.

**What follows:**
- **If phase 1 passes for some W:** phase 2 is written as an amendment before it runs. It covers:
  - at most K kept cuts;
  - compressed transitions between them (one common ambient path, GPT's q_Δ summaries);
  - the resources (RAM, flash, worst-case time per sample, numerical margins).
- **If it does not pass:** the result is reported, and Can decides. The options are adaptive directions at cuts,
  larger W, or stopping this line.
