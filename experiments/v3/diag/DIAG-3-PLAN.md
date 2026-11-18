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

## Amendment 1: phase 2a, the DEV-wide evaluation (2026-11-18, written before any 2a result)

**Status:** run on Can's go. GPT, Sol and Hydrogen all chose 2a before 2b.

**Rows:** every row of the DEV evaluation set, `results/v3/dev-45cff1d/rows.jsonl`: seeds 430000–430029, both arms,
1320 runs. Freeze 1's DEV reference (cyl16p D_paired 0.386) was computed on these same rows.

**Variants:**
- **S128 and S256,** exactly as in phase 1 (B = 16, pad 1e-6), online from k = 0, until detection or N.
- **cyl16p,** recomputed on the same runs as a check.

**Scoring:** Freeze 1's functions in `score_validation.py`:
- `paired_delta`, over the runs v2 detects; a miss counts as N − t*;
- `_soundness`: alarms on admissible runs, and detections before t*;
- `describe`, `by_cell` and the seed-cluster `bootstrap`, the last descriptive only.

**Also reported:**
- misses against v2;
- detections later than v2;
- the margin at detection;
- everything both with and without the 10 rows of the five diagnosis runs, which were used to design the window.

**Reading rule (fixed now):**
- If S256 reaches D_paired ≥ 0.80 with no soundness finding, an 80 % gain is reachable at the architecture level, on
  DEV.
- This is not a freeze. Seeds 440200+ stay untouched, and any candidate still needs its own freeze and validation.

## Amendment 2: the 2a rows on a second platform (2026-11-18, written before any result of it)

**Question:** do 2a's results depend on the machine? The method is meant to be deterministic, so the same code on the
same rows should give the same detections on a different CPU and OS.

**Machines:**
- **Reference:** the 2a run itself, on Arch (x86-64, Linux), at `6c1190f`.
- **Second:** a MacBook Air (Apple M4, arm64, macOS).
- **Both:** Python 3.12.13, numpy 2.5.5 and scipy 1.18.1, so the same bundled HiGHS. The compilers, the BLAS and the
  floating-point contraction can differ.

**Rows:** the 264 rows of the 2a set with (seed − 430000) mod 5 = 0. That is six seeds in each of the 44 strata (cell ×
arm × ambient). The rule is fixed now.

**Run:** `diag3_platform.py run`. It calls `diag3_dev.job` unchanged, from a clean checkout of this commit; the code
that computes is the same as at `6c1190f`. The outputs stay on the Mac, apart from the reference run.

**Criteria (fixed now):**
- **Detections:** the same for cyl16p, S128 and S256 on every row of the subset.
- **Margins** at detection and at t*: any difference above 1e-3 mC (the 1e-6 °C fold pad) is a finding. The largest
  difference is reported either way.
- **LP counts:** n_lp should agree. n_retry is reported, because the fallback can depend on the solver's path.

**Reading rule:**
- **Pass:** every detection the same and no margin finding.
- **Otherwise:** each difference is recorded and looked at before 2b (is it a near tie? a fallback?). Determinism
  across platforms is then an open requirement for any candidate.
- The 2a score is the reference run alone. This check does not change it, and the second machine's rows never enter it.

**Amendment 2 is withdrawn** (2026-11-18, about 15:40). It was stopped before any row finished, so no result of it was
seen. Two machines agreeing in float64 says little about the MCU, which will use float32 and another solver, and
soundness rests on certified bounds, not on bit equality. `diag3_platform.py` is kept for the record only.

## Amendment 3: the compressed window, a pilot on the five diagnosis runs (2026-11-18, written before any result)

**Question:** can S256 be written with far fewer variables, with nothing lost?
- Today S256 carries 3 states per sample: 822 variables × 1134 rows.
- The independent check (T3c) found that about 88 % of the measurements are redundant when they arrive.

**The exact step.** The window LP's model is x_{j+1} = M x_j + e3 w_j with |w_j| ≤ ρ, since M's third row is e3ᵀ. For
two nodes a < b with L = b − a:

  x_b = M^L x_a + Σ_{k<L} M^k e3 w_{b−1−k}.

- M^L is computed from exact rational powers of the float64 M.
- The ambient increments w_j stay explicit, as variables bounded by ±ρ. So the segment's zonotope Z_L is represented
  exactly with 3 equality rows.
- Its facets are not enumerated: that takes L(L−1) rows, and the zonotope is degenerate for L ≤ 2.
- No template of it is used either, since a template is an outer approximation.

**Nodes:** τ, the kept measurements, τ + B (the fold), the objective state and t_end.

**The box between nodes:**
- **ac and as stay in it automatically.** Rows 1–2 of M are convex combinations, so if the nodes and the TA path are
  in the box, every state between them is too.
- **Only the TA box is at stake.** Between nodes, TA can leave the box by at most ⌊L/2⌋ρ.

**Variants** (W = 256, B = 16, smoothing fold, all in `diag3_cw.py`):
- **A:** the dense S256 of `diag3.Window`.
- **E:** (ac, as) at the nodes only, TA at every sample. Measurements redundant at arrival are dropped. Apart from the
  dropped measurements, E has A's feasible set.
- **N:** as E, but with TA at the nodes only. This drops the TA box between nodes, which is sound and only looser.

**Redundant measurements:**
- **The rule:** a measurement is redundant at arrival if its slab contains the as-range computed from the measurements
  before it. In E and N such a measurement is dropped.
- **Dropping is always sound.** It is not lossless in general. After a fold, the template base is looser than the
  constraints it replaced, so a dropped measurement could become active again.
- **What it costs is measured,** as E against A.
- **K:** no limit and no eviction in this pilot. The largest number kept is reported.

**Certified folds, in every variant:**
- Each support written is max(LP value + pad, dual bound), then clamped as before.
- The dual bound comes from weak duality with the solver's multipliers, over the boxed variables, with the
  floating-point rounding bounded explicitly.
- The alarm at detection is certified the same way.

**Order (as in phase 1):** the alarm at t uses the measurements up to t − 1. z_t is added, and the fold applied, after
the alarm check.

**Runs:**
- **Rows:** the five diagnosis runs, with phase 1's horizon (stop at detection, else at t_cyl16p + 300).
- **Machine:** the MacBook (Apple M4). All variants are timed on that same machine.

**Check, before the criteria (C0):** E with every measurement kept, run in lockstep with `diag3.Window` up to t*. The
as-range and the fold supports must agree within 1e-6 °C.

**Criteria (fixed now):**
- **C1:** A detects at t* in all five runs. In 430010, its margin at detection is within 0.01 mC of the independent
  certified replay (695, −0.2855 mC). The tolerance allows for two certification procedures that raise supports by
  different amounts, up to the size of the shortfalls seen (7.3e-6 °C).
- **C2:** E detects at the same time as A in all five runs, with the margin at t* within 1e-3 mC (1e-6 °C).
- **C3:** no variant alarms before t*, and every alarm of A and E is certified.

**Reported without a criterion:**
- N's detections and margins, which give the cost of dropping the TA box between nodes;
- the folds raised to their dual bound;
- the largest number of kept measurements and nodes;
- variables and rows;
- LP counts;
- the median, p95 and maximum step time, and the largest fold-step time.

**Reading rule:**
- **If C0–C3 pass:** E is an exact compressed form of S256 on these runs. The next amendment runs E and N on DEV, on
  the Mac, and compares them row by row with 2a's S256. The ramp cells are reported apart, because TA there runs close
  to the box walls.
- **If C2 fails:** find out why (re-activated measurements, or the implementation) before anything else.
- **The cost figures** are Python and HiGHS on the Mac, not MCU figures. Variants are compared only on the same
  machine.

## Amendment 4: E and N on DEV (2026-11-18, written before any result of it)

**Status:**
- Run on Can's go, after the pilot.
- The pilot's C0 failed as fixed. The post-hoc probe placed that failure in the dense reference (DIAG-3-RESULTS.md).
- Going on to DEV on that basis was Can's decision.

**Rows:** every row of the 2a set: `results/v3/dev-45cff1d/rows.jsonl`, seeds 430000–430029, both arms, 1320 runs.

**Variants:**
- E and N exactly as in amendment 3: W = 256, B = 16, certified folds, measurements redundant at arrival dropped, no
  K limit.
- Both run online from k = 0, until detection or N.

**Run:** `diag3_cw_dev.py run`, on the Mac, 8 workers, from a clean checkout. The rows that stop early run first.

**Scoring:**
- as in amendment 1, with Freeze 1's functions: `paired_delta`, `_soundness`, `describe`, `by_cell`, `bootstrap`;
- with and without the ten rows of the five diagnosis runs.

**Comparisons:**
- E against 2a's S256 (the Arch run), row by row, once 2a has finished;
- N against E, row by row, by cell and ambient.

**Criteria (fixed now):**
- **D1:** E's detection equals 2a's S256 on every row. Every row that differs is listed, with both margins.
- **D2:** no soundness finding for E or N, and every alarm certified.

**Reported:**
- D_paired, misses, detections later than v2, by cell, bootstrap, for E, N and (once available) S256 and cyl16p;
- the kept measurements (median, p95, max);
- the largest number of nodes, variables and rows;
- the largest p95 step time and fold-step time;
- the folds raised to their dual bound, and the fallback LPs.

**Reading rule:**
- **The 80 % question.** Amendment 1's rule applies to E and to N: D_paired ≥ 0.80 with no soundness finding means
  an 80 % gain is reachable at the architecture level, on DEV.
- **If D1 fails,** each differing row is examined (is it a near tie? the dense LP's error?) before E stands in for
  S256.
- **N as the MCU form.** N is taken as the MCU form only if it detects no later than E on every row. Otherwise the TA
  box between nodes stays, as in E or with its rows added only where TA can reach the wall.
- **Not a freeze.** Seeds 440200+ stay untouched.

## Amendment 5: lazy TA rows (L), and the window length (2026-11-18 evening, written before any result of it)

**Status:** run on Can's go, after amendment 4.

**L: N plus only the TA box rows that the solution needs.**
- **Each LP:** solve N's LP, reconstruct the TA path between nodes from the solution, and add the box rows it
  violates (by more than 1e-9 °C). Repeat until none is violated.
- **Rows found once stay** while their sample is in the window.
- **Why it is exact:** every LP on the way is a relaxation of E's LP, so it is sound. The last optimum is feasible for
  E's LP, so it is E's optimum.
- **Everything else is as E:** certified folds, measurements redundant at arrival dropped, no K limit.
- **Smoke test** (two healthy ramp runs outside the evaluation rows, 430037 and 430030, with TA at the wall):
  - L equals E within 7e-8 °C;
  - N is off by up to 10 mC there;
  - up to 148 lazy rows were needed.

**The window length:** E with W = 64, 128 and 192, with B = 16 as before. This gives the size–loss curve of the exact
compressed window, next to W = 256 from amendment 4.

**Rows:** all 1320 DEV rows, as in amendments 1 and 4.

**Machines:**
- **L:** the Mac, 8 workers. It is compared with amendment 4's E, which ran on the same machine.
- **The W curve:** Arch, 14 workers. E at W = 128 is compared with 2a's S128, which also ran on Arch.

**Criteria (fixed now):**
- **L1:** L's detection equals E's (amendment 4) on every row.
- **L2:** no soundness finding for L, and every alarm certified.
- **W1:** E at W = 128 detects as 2a's S128 does, on every row. Any row that differs is listed.
- **W2:** no soundness finding for any W, and every alarm certified.

**Reported:**
- **For L:** rows (largest), lazy rows (largest), re-solves per LP, and step times, against E and N on the Mac.
- **For each W:** D_paired, misses, by cell, bootstrap, kept measurements, size and time.

**Reading rule:**
- **If L1 and L2 pass,** L is the exact form at the lowest cost so far, and the formulation that the MCU work starts
  from.
- **The W curve is descriptive.** It shows how much of the oracle's gain each window length keeps. The choice of W for
  a candidate is made later, at a freeze.
- **Not a freeze.** Seeds 440200+ stay untouched.
