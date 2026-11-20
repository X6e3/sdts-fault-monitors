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

## Amendment 6: the freeze-candidate code (F) and a cap on kept measurements (2026-11-18 night, written before any result of it)

**Why:**
- **The certificate.** A review pointed out that it covers the float64 copy of the LP. The compressed coefficients
  (powers of M) are rounded, so it does not cover the LP with exact coefficients.
- **K.** DEV's 45 kept measurements are an observation, not a bound. A fixed-memory candidate needs a cap, and a
  deterministic rule for what happens when the cap is reached.

**F = E, plus:**
- **A coefficient term in the certificate.** Each coefficient is correctly rounded from its exact value, so it is off
  by less than 2u|a|. The bound adds Σ_j max|x_j| · 2u (|A|ᵀ|λ|)_j, and so holds for the LP with exact coefficients.
- **Measurement slabs rounded outward,** by one ulp each side.
- **A cap K on the kept measurements in the window** (τ itself is not counted). When the cap is exceeded, the
  measurement that has been inactive longest is evicted.
  - A measurement is active in an LP when its bound has a nonzero multiplier.
  - A newly kept measurement counts as active at arrival. Ties go to the oldest.
  - Evicting a measurement is always sound.

**The audit (`diag3_cw.py` variant Fa):**
- F with no cap, on the five diagnosis runs.
- Every fold bound, every alarm bound, and every eighth as-range bound is also evaluated exactly: rational arithmetic
  on the float data, with the same multipliers and the coefficient enclosure.

**DEV runs (`diag3_cw_dev.py --variants F --K ...`):**
- K = 64 on Arch, after the W curve.
- K = 40 and K = 32 on the Mac, after L.

**Criteria (fixed now):**
- **A1:** on every audited LP, the float bound is at least the exact one.
- **A2:** F with no cap detects as amendment 3's E on the five runs, with margins at t* within 1e-3 mC, and every alarm
  certified.
- **K1:** F with K = 64 detects as amendment 4's E on every DEV row. Evictions are reported.
- **K2:** no soundness finding for any K, and every alarm certified.

**Reported:** for K = 40 and 32: D_paired, misses, rows later than E, rows with evictions, and the eviction count.

**Smoke test** (430037, healthy ramp, outside the rows, 309 samples):
- 202 audited bounds, with a smallest slack of 7e-15 °C and no violation;
- the coefficient term at most 3e-14 °C;
- F = E within 3.4e-12 °C.

It ran as a single process for about a minute, during amendment 5's L run, so L's timings may be very slightly
affected.

**Reading rule:**
- **If A1, A2, K1 and K2 pass,** F with K = 64 is the freeze candidate. It is written up as FREEZE-V2 for Can's
  approval.
- **K = 40 and 32** show how much margin K = 64 has, and what the eviction rule costs.

## Amendment 7: F on edge noise (2026-11-18 night, written before any result of it)

**Why:**
- The validation design (freeze 1's, kept for freeze 2) includes healthy runs with edge noise, |noise| = δ exactly.
  Every measurement then sits on its slab's boundary.
- No compressed window has been run on such data. It is the hardest case for a false alarm.

**Runs:** `diag3_cw_edge.py`, F with W = 256 and K = 64.
- Healthy, edge noise, DEV seeds 430070–430089, arms E0 and E1, ambient rw and ramp: 80 runs.
- None of these seeds has been used by the DEV rows, the pruning set (430050–430069) or the smoke tests.
- Every run is admissible by construction.

**Criterion E1 (fixed now):** no F alarm on any of the 80 runs.

**Reading:** E1 is a precondition of the freeze. A failure is a soundness bug, to be found before anything else.

## Amendment 8: F raises certified alarms only (2026-11-19, written before any result of it)

**Why:** a review of the freeze-2 code (`cfb7f18`) found three gaps.
1. **The alarm comes from the LP values, not the bound.** `online()` stops on the LP values (`upper < z − δ`) and only
   then asks for the certificate. A solver value slightly off at a boundary would record an uncertified alarm on a
   healthy run. Such a run counts as a soundness violation and an uncertified alarm, so one such slip would fail the
   whole validation. The 400 edge-noise runs of a 100-seed block make this more likely.
2. **The alarm's certificate does not round z_t ± δ outward,** while the LP slabs do. The float 0.3 is 1.1e-17 below
   3/10.
3. **An empty fold LP raises an exception** and stops the worker. The freeze document says it is recorded as an
   uncertified alarm.

**The change, for F only** (E, N and L behave as they ran):
- **An alarm is raised only if it is certified.** LP values that point to an alarm the bound cannot prove raise no
  alarm. z_t is then dropped, which is sound, and the case is counted (`unproved_primal_alarms`).
- **`certify_alarm` rounds the slab of z_t outward.**
- **An empty fold LP** is recorded as an uncertified alarm.
- **The freeze-2 scorer also reports** the largest positive t_F − t_v2 and the rows where v2 detects and F misses.

**Runs:** F with K = 64 on all 1320 DEV rows, and on amendment 7's 80 edge-noise runs (Arch, 14 workers, from a
clean checkout of this commit).

**Criteria (fixed now):**
- **T1:** F's detection equals amendment 6's F (K = 64) on every DEV row. The number of unproved LP alarms is reported.
- **T2:** there is no alarm on the 80 edge-noise runs.
- The freeze-2 rehearsal is rerun at the new freeze commit.

## Amendment 9: F's model is the exact recurrence; the data's float error is enclosed (2026-11-19, written before any result of it)

**Why:** a review of the freeze-2 draft (`0162658`) found a gap between the model and the certificate. Checked before
writing this:
- **The float matrix M is not a convex combination.** Read as exact rationals, its first two rows sum to 1 + 2⁻⁵⁶
  and 1 + 3·2⁻⁵⁶ (each entry is rounded separately). Under that matrix the fixed point with TA = +2 has
  ac = 2 + 2.7e-15 and as = 2 + 2.3e-15. So the ac and as boxes [−2, 2], which F takes from convexity, do not hold for
  the matrix whose exact powers F uses.
- **The recurrence of `thermal.py`, `step()`, in exact arithmetic with its float parameters** (CC, CS, K, H, DT taken
  exactly) has row sums exactly 1. Under it the boxes hold by convexity. Its powers differ from those of the float M
  by up to 54 u (relative, L ≤ 292), which is more than the 2u coefficient term of the certificate.
- **The clamps of cyl16p** (`cap_inv`) hold under the exact recurrence: all 42, with the smallest slack 2.2e-15 °C.
  This was checked with 60-digit decimals, 6000 exact terms and a tail bound below 1e-41.
- **The simulated data are not exact either.** The harness computes z from two float64 simulations, `Ts` and the
  known part `S`. Against the exact recurrence on the same inputs (80-digit decimals, 64 healthy DEV runs, both arms,
  rw and ramp, uniform and edge noise), |zs_float − zs_exact| reaches 1.2e-13 °C. That is more than the one-ulp
  outward rounding of the slabs (4.4e-16).

**The change, for F only** (E, N and L behave as they ran):
1. **The model is the exact recurrence.** F's powers M^L and M^k e3 are the exact powers of the exact-recurrence
   matrix, each rounded once. The coefficient term of the certificate then covers them, as it is written.
2. **The data allowance η = 1e-9 °C.** F's measurement slabs, and the slab of z_t in the alarm certificate, use
   δ + η, rounded outward. The primal alarm and redundancy tests of `online()` use the same δ + η.
   - **The a priori bound:** each float step of `step()` errs by at most 10·u·250 ≈ 2.8e-13 per state, with every
     intermediate below 250 in magnitude. The error then propagates through the exact recurrence, whose 2×2 part
     is nonnegative with (I − M22)⁻¹ row sums 67.5 and 52.5. So each simulation is within 1.9e-11 of exact, and zs
     within about 4e-11 after the two simulations and three float operations.
   - η is 25 times that bound. It is also below the smallest certified alarm margin on DEV (2.3e-5 °C) by a factor
     of 2·10⁴.
   - **With η the chain closes:** the float data lie within η of data that the exact model explains with
     |noise| ≤ δ. So F's certified alarm proves that no admissible explanation exists for the run's true data.
3. **The checks are kept as a script,** `diag/check_model.py`: the row sums, the single rounding of each exact power,
   the 42 clamps, and the measured data error.
4. **Scorer** (`score_validation_v2.py`), from the same review:
   - **Run identity:** in validation mode the seeds are the manifest's block. Every expected key
     (seed, cell, arm, ambient, noise) occurs exactly once, with no extra keys.
   - **Integrity:** meta's mode, the manifest sha256, the rows sha256 (recomputed), the finished stamp, a clean
     tracked tree, the approval (in validation mode), and the environment against `thermal_v2_env.LOCK` field by
     field. Before, env_ok only checked that meta's env was not empty.
   - **Precedence:** an integrity failure gives INCONCLUSIVE. Otherwise a soundness violation or an uncertified alarm
     on a valid row is a FAIL, even if rows are missing. Otherwise missing, duplicate or extra rows, or |U| > 1 % of
     |F|, give INCONCLUSIVE. Then the misses and D_paired rules apply. If L_v2 = 0, D_paired is undefined, which is a
     FAIL, as the code already does.

**Runs:** F with K = 64 on all 1320 DEV rows, and on amendment 7's 80 edge-noise runs (Arch, 14 workers, from a clean
checkout of the code commit).

**Criteria (fixed now):**
- **T1′:** F's detection equals amendment 8's F on every DEV row, with no uncertified alarm. A difference does not
  stop the amendment, since the change is a correctness fix, but each one is reported and explained before the
  freeze.
- **T2′:** there is no alarm on the 80 edge-noise runs.
- **S1:** the new scorer reproduces the amendment-8 rehearsal's verdict and numbers. On constructed inputs (a
  missing row, a duplicate, an extra key, a wrong rows sha, an environment mismatch, a soundness violation with a
  missing row) it gives the verdicts above.
- The manifest is regenerated and the freeze-2 rehearsal rerun at the new freeze commit.

## Amendment 10: F3, F with a sound path for solver failures (2026-11-19 night, written before any result of it)

**Why:** freeze 2's validation failed (`RECORD-2026-11-19-validation.md`).
- On one healthy edge-noise run, one fold LP (direction 40) ended in all three attempts with HiGHS status 15
  (unknown). It does so every time.
- The frozen code records a failed fold as an uncertified alarm. A failed as-range or alarm LP is not caught at
  all, and would stop the run.
- The diagnosis (`6bff6e9b`, `66fcfcc5`) showed three things about that fold:
  - the other 41 directions solve;
  - the failed attempts return neither multipliers nor a point;
  - the other faces imply d₄₀·x ≤ −0.209, against an a priori 1.683.

**The candidate F3:** F as frozen in freeze 2, with W = 256, B = 16, K_cap = 64, cyl16p, the exact recurrence and
δ + η unchanged. One principle is added: **F3 uses no solver result it cannot certify.**

**Two outcomes per LP:**
- **Solved:** status 0, then used with its certificate, as in F. Only status 0 ends the frozen three attempts.
- **Failed:** every other ending after the three attempts. That includes status 2 (infeasible), which comes with no
  infeasibility certificate.
- Failures are counted by the status of the last attempt: 2, 4, or other. A slab that is empty before any solve
  counts as its own kind.

**The invariant.** At every step, the window's set contains every exact-model explanation of the data it holds:
the ideal set 𝔛 of FREEZE-V2 §1. Each fallback below keeps that inclusion, and no fallback is built from another
fallback.

**The a priori box.** ac, as and TA lie in [LO, HI] = [−2, 2] under the exact recurrence (convexity; amendment 9).
So max as ≤ HI and max(−as) ≤ −LO hold without any LP.

**What F3 does with a failure:**
- **An as-range side fails at t.** That side becomes its box bound: upper = HI, or lower = LO.
  - The alarm test and the alarm certificate then run as in F.
  - So if z_t ± (δ + η), rounded outward, lies outside [LO, HI], the alarm is certified by the box alone. No LP is
    needed.
  - **z_t is not kept,** because only a measurement checked against a solved range enters the window. Dropping a
    measurement is sound.
  - This is a change from the draft. Keeping an unchecked z_t could make the window empty: lb > ub, or an
    infeasible window on a fault run.
  - The cost of a failed as-range is a later alarm or a miss. It is counted, and it shows in the lag.
- **An alarm-certificate LP fails.** That side's certified bound becomes the box bound (HI, or −LO for the lower
  side). The alarm is certified if either side proves it, as in F. Otherwise it is unproved: no alarm, z_t is
  dropped, as in F.
- **A fold direction d_i fails.** Its new base value is a certified upper bound of max d_i·x over P_J ∩ box.
  - J is the set of directions of the same fold that solved. P_J = {x : d_j·x ≤ h_j, j ∈ J}, where h_j is the
    value the fold stores for j.
  - The bound is a 3-variable LP, solved with the same three attempts and certified by `certified_max(harden=True)`.
    That is weak duality, d_i = D_Jᵀλ + μ with λ ≥ 0, where μ is the box residual, rounded outward.
  - This is sound: 𝔛(τ + B) ⊆ P_J ∩ box, because each h_j is at least its certified support.
  - The stored value is max(v + PAD, bound), as for a solved direction. It is then clamped.
  - If that LP fails too, the value is the a priori support: `cap_inv` with the boxes, checked exactly in
    `check_model.py`.
- **Every direction of a fold fails (a full reset).** The fold is atomic:
  - τ ← τ + B;
  - base ← the a priori support in every direction, `tp.clamp(+∞)`;
  - every kept measurement is dropped;
  - the activity record is cleared.
  - This is not the start of the run. The base stays defined (not `None`), so the equalities ac = as = TA of the
    first segment are not used again, and the steady state is not assumed. The new set contains 𝔛(τ + B) because
    the a priori support holds at every time.
  - After a reset the window is the box set plus new measurements, so its LPs are not empty.
- **Counted and reported** (not in the verdict):
  - `fold_dir_fallbacks`, split by status 2, 4 and other;
  - `fold_apriori_fallbacks`;
  - `fold_full_resets`;
  - `range_fallbacks`, one side and both sides;
  - `cert_fallbacks`;
  - `box_alarms`;
  - `measurements_not_kept`.
- **Unchanged:**
  - the alarm rule: F3 raises only certified alarms;
  - F itself, whose code paths stay as frozen;
  - the scoring rules, the verdict order and the D_paired target of 0.80;
  - the scenario laws.

**Runs** (Arch, 14 workers, from a clean checkout of the code commit; R3 on the Mac):
- **R0, path tests.** Constructed cases, one per branch:
  - an as-range failing on one side, and on both;
  - a box-certified alarm;
  - a certificate LP failing on one side, and on both;
  - a fold direction falling back to P_J, and to the a priori support;
  - a full reset;
  - a pre-solve empty slab.
- **R1.** F3 on all 1320 DEV rows and on amendment 7's 80 edge-noise runs (DEV seeds 430070–430089).
- **R2, failure injection.** A harness outside the candidate's code makes chosen LPs fail in all three attempts.
  - The choice is a deterministic hash of (row, t, LP role, direction). It is fixed here, before any result.
  - Half of the injected failures return status 2 and half status 4.
  - The harness logs every injection.
  - Settings, each on all 1320 DEV rows and the 80 edge-noise runs:
    - (a) 1 % of fold-direction LPs;
    - (b) 10 % of fold-direction LPs;
    - (c) 1 % of as-range LPs and 1 % of certificate LPs;
    - (d) every direction of every fourth fold, which forces full resets;
    - (e) 10 % of fold-direction LPs, together with every P_J fallback LP, which forces the a priori path;
    - (f) every certificate LP on the upper side, which forces box-sided certificates.
- **R3, the audit.** A1's exact rational audit, extended to every P_J fallback bound, on settings (a), (b) and (e).
- **R4, regressions** on freeze 2's block. It is no longer a holdout, so these test the code and are not evidence.
  - The saved `lp-dir40.npz` through the fallback.
  - F3 on (440243, healthy, E0, ramp, edge) over the whole run.

**Criteria (fixed now):**
- **U0:** every R0 case behaves as specified above.
- **U1:** on R1:
  - F3 detects at the same sample as freeze 2's F on every DEV row, with every alarm certified;
  - there is no alarm on the 80 edge-noise runs;
  - no fallback occurs (DEV had no LP that failed all three attempts). If one occurs, it is reported and explained.
- **U2:** on every R2 setting:
  - **soundness:** no alarm on an admissible row (the 120 healthy, the 118 certified-consistent and the 80
    edge-noise rows), no alarm before t*, and every alarm certified;
  - **memory:** at most K_cap + 1 = 65 kept measurements, as in F;
  - **the injections:** the window's failure counters equal the harness's log, role by role;
  - **the paths:** across the settings, every counter above is greater than 0, each status kind included;
  - **recovery:** in setting (d), at least one fault row detects after a full reset. The number is reported.
- **U3:** R3 finds no violation: every audited bound is at least its exact rational evaluation.
- **U4:**
  - the fallback on `lp-dir40.npz` gives a certified bound that R3's exact evaluation confirms;
  - on 440243 (healthy, so admissible) F3 runs all 3600 samples with no alarm;
  - its t = 945 fold takes the P_J bound for direction 40.
  - Matching −0.209 is not a criterion.
- **Reported, not deciding:**
  - per setting against R1: D_paired on DEV, misses, lag, resets, measurements not kept;
  - the per-run LP counts and time.

**Scope of H-F3, to be stated in FREEZE-V3.md:**
- The validation block tests F3 in normal operation on fresh seeds, including whatever solver failures occur
  there.
- Robustness to injected failures is DEV evidence only, unless an injection setting is frozen with it and run on the
  block too. That is decided in FREEZE-V3.md, before approval.

If U0–U4 hold, FREEZE-V3.md is written:
- it covers F3, a manifest, a DEV rehearsal and the block 440400–440599 (reserved, never generated);
- Can approves it before any validation data exist.

### Amendment 10, addendum after the code review N2 (2026-11-19 night, written before any R1–R3 result)

A referee review of `17a1dc69` (N2) checked 13 items against the code. It found two defects, both confirmed here
in the code:
- **The summary's admissible set (`amend10.py`)** left out healthy rows whose oracle is undetermined. FREEZE-V2 §4
  counts every healthy run as admissible. On DEV every healthy row is certified, so no DEV result depends on it,
  but the rule is the frozen one.
  - The U2 flags did not require a complete run.
  - The misses were counted over different sets for F3 and F.
- **The window could take a measurement that its box excludes.** Each later LP then ends "slab", before any solve.
  1. z_0 is kept without a check.
  2. An as-range value can exceed the box by the solver's tolerance. A z_t whose slab lies just outside [LO, HI],
     and inside that overshoot, then passes the alarm test and is kept.
  - Neither path can occur on an admissible run: there, as lies in the box, so every slab meets it. Both can occur
    on a fault run, or with a fault present at t = 0.
  - The "slab" failures were left out of the counter match and of U2, so they would not have shown.

**The changes** (F3 only; F, E, N and L unchanged):
- **The as-range is clipped to the box:** lower ← max(lower, LO), upper ← min(upper, HI). The certificate's bounds
  are clipped the same way: cup ← min(cup, HI), cdn ← min(cdn, −LO). Both are a priori bounds, so this is sound.
  - A slab outside the box then fails the alarm test against the clipped range.
  - The certificate proves the alarm by the box alone.
  - Such a z_t is never kept.
- **z_0:** if its slab (δ + η, rounded outward) misses [LO, HI], F3 raises an alarm at t = 0, certified by the box.
  Otherwise z_0 is kept, as before.
- **The summary:**
  - every healthy row counts as admissible;
  - the U2 flags require a complete run;
  - the misses of F3 and F are counted over the same events;
  - "slab" failures are reported.

**Criteria, amended:**
- **U0** adds two cases:
  - z_0 outside the box: a certified box alarm at t = 0;
  - an as-range value above HI: clipped, and a z_t above the box gives a box-certified alarm and is not kept.
- **U1:** the margins equal F's, except where F's certified bound lies outside the box. Each such case is listed.
- **U2** adds: no "slab" failure in any setting. With these changes it cannot occur after t = 0.
- **The runs:**
  - The runs at `17a1dc69` were stopped before any result was read: R1 partial, R3 setting (a) partial.
  - R0 and R4 at `17a1dc69`/`e52f5192` passed, but they are repeated too.
  - Every run R0–R4 is repeated at the code commit of this addendum.

### Amendment 10, second addendum after the review AG1 (2026-11-19 night, written before any R1–R3 result was read)

A documentation-to-code review of `0ce80072` (AG1) found gaps in how the criteria are computed and stated. None of
them is in F3's code: they are in `amend10.py`'s summary and path tests, `amend10_r4.py`, and this document.
`summary()` only reads the per-row records, so the R1–R3 runs going on at `0ce80072` are kept. Their summaries are
recomputed with the corrected code, and nothing in the old summaries is read first. R0 is repeated. R4 is
re-evaluated from its output.

**The criteria, made exact:**
- **What counts as a fallback (U1).** A fallback is a failed LP and what follows from it:
  - `fold_dir_fallbacks`, `fold_apriori_fallbacks`, `fold_full_resets`, `range_fallbacks`, `range_failures`,
    `cert_fallbacks`, `measurements_not_kept`, and `fold_implied`, which occurs only after a failed fold direction.
  - The box clipping of the N2 addendum is part of F3's normal step, not a fallback.
  - `box_alarms` counts alarms that only a box-clipped or box-fallback side proves. That can happen with no failure.
  - `U1_no_fallback` uses the fallback counters only.
- **The margin exception (U1).** For each alarm whose certified margin differs from F's, the side that decides the
  margin must have been clipped. This is checked by replaying the row with F (DEV, cheap): F's certified bound on
  that side must lie outside the box, and F3's margin must equal the clipped one. Each such case is listed.
- **U2 completeness:** the set of row keys equals the expected set (1320 DEV keys and the 80 edge-noise keys), not
  only their number.
- **U2 paths:** over settings (a)–(f) together, each fallback counter is greater than 0 for each injected status
  kind (2 and 4).
  - `fold_implied` and `fold_full_resets` have no status kind, so they need only be greater than 0.
  - "other" is never injected, and "slab" must stay 0 (the N2 addendum). Neither belongs in this criterion.
- **U2 recovery:** in setting (d), the number of event rows that detect after at least one full reset is greater
  than 0.
- **U3:** the audit ran (n > 0, n_implied > 0) on a complete run, with no violation.
- **U4:**
  - The fallback at the t = 945 fold of 440243 is computed from the fold's other faces, not from `lp-dir40.npz`. That
    LP is the one that fails.
  - The criterion is therefore: the P_J bound for direction 40 is not None, is below its a priori support, and is
    confirmed by R4's exact audit (n_implied > 0, no violation).
  - The `lp-dir40.npz` clause of the first plan is withdrawn as ill-posed.
- **U0** adds:
  - the overshoot case run through `online()`: the z_t is not kept, and the alarm is certified with the box side;
  - `last_active` is empty after a full reset;
  - `measurements_not_kept` is 1 when both sides fail;
  - the unproved alarm is counted when both certificate sides fail.

**Facts the review found undocumented** (code unchanged):
- The three attempts, in order: `highs-ds` without presolve, `highs-ipm` without presolve, `highs-ds` with presolve.
  A failed LP adds 3 to `n_retry` and 1 to `n_lp`.
- A kept measurement is active in an LP when a bound multiplier of its slab exceeds 1e-12 in magnitude.
- F3 also counts:
  - `fold_implied`, the P_J bounds used;
  - `range_failures`, failed as-range LPs by status kind.
  - The other counters with a kind are also split by kind (2, 4, slab, other).
- At t ≥ 1, an alarm still runs both certificate LPs; the box bound replaces a side only when that side fails or is
  looser. Only at t = 0 is z_0 judged by the box alone. Such an alarm has no `margin_at_detect_mC` (there is no
  as-range at t = 0); its certificate carries the margin.
- `measurements_not_kept` counts a z_t dropped because a range side failed and no alarm test fired. A z_t whose alarm
  is unproved counts under `unproved_primal_alarms`, as in F.
- The R2 hash is over (row, t, role, direction or side, setting).
- In F and F3 alike, the eviction record keeps entries of measurements that have left the window. They are never
  read again. For an MCU port they would be pruned with the window; that changes no decision.
- Two precisions to the above, made while writing the code and before any result was read:
  - **U3's n_implied > 0** is over R3's settings together. Setting (e) fails every P_J LP by design, so its own
    n_implied is 0.
  - **U2 paths leaves out `box_alarms`.** Whether a DEV fault drives a slab outside the box at a step whose LP fails
    depends on the data, not on the failure path. The box-proved alarm is covered by U0's constructed cases. It is
    reported for each setting.

### Amendment 10, third addendum: memory accounting (2026-11-20, written before the identity check was run)

**What K7 found** (two findings, neither a false alarm):
- Inside a step, `zs` reaches K_cap + 2 = 66 entries, because `online()` inserts z_t before it evicts. Between steps
  the count is at most 65, as reported.
- `last_active` keeps the entries of measurements that the fold has dropped. The second addendum listed this as
  undocumented. On 430000 E0 ramp uniform, 180 entries at t = 1600, 149 of them stale. The auxiliary state is
  therefore not bounded by K or W.

**The change (F3 only; F, E, N and L are untouched):**
- `Failsafe.fold`, after it prunes `zs`, prunes `last_active` to the keys that remain in `zs`.
- `online()`, for a failsafe variant: when z_t is to be kept and the kept count above τ already equals K, the evict
  comes first, and the keep second.

**Why no decision changes (MATH):**
- `last_active` is read only by `evict`, and only for keys in `zs`. A key that the fold drops never returns, because
  new keys are samples t > τ. `lp()` marks activity only for keys of `zs` (`meas ⊆ zs`).
- In the old order, the new measurement's eviction key is (last_active = t, j = t). Every other candidate has
  last_active ≤ t and j < t, so it wins the tie. The new measurement is therefore never evicted while another
  candidate exists, and one always exists (count ≥ K ≥ 1). Both orders evict the same measurement. The activity
  updates of step t come from the as-range, which runs before either order.
- After the change, at every point of a step: |zs| ≤ K + 1 = 65 (K above τ, plus z_τ), and the keys of
  `last_active` are a subset of the keys of `zs`.

**Identity criterion I1** (written before it ran):
- **I1a, Mac, now:** 4 healthy edge rows and 4 DEV fault rows, under settings none and d, run with the old code
  (0ce80072) and the new code on the Mac. Every field of every record is equal, except the wall-clock fields
  `seconds`, `step_ms` and `fold_step_ms`. An instrumented run of the new code also shows |zs| ≤ 65 at every point
  and keys(last_active) ⊆ keys(zs) after every step.
- **I1b, Arch, after all.done:** the new code on all 1400 rows of R-none, against R-none at 0ce80072 on Arch, by the
  same rule. Mac and Arch outputs are not mixed.
- **If any field differs:** the change is withdrawn. F3 stays at 0ce80072, and FREEZE-V3 says: at most 65 between
  steps, 66 inside a step, and an eviction record that grows.
- **If I1 holds:** freeze 3's candidate is the new commit, and R1–R3 at 0ce80072 stand for it, because no record can
  differ.

### Amendment 10, fourth addendum: the solver boundary, and U5 (2026-11-20, written before any of its tests ran)

**What review M1 found** (`~/Research/sdts-runs/v3-proof/M1/GAPS.md` on Arch, checked against the code at 000cd215):
- **G1.** `solve_f3` turns every status into `Failed`, but an exception raised inside `linprog` is not caught. In a
  fold it reaches `online()`'s `except RuntimeError` and becomes an uncertified alarm, which freeze 2's rules score
  as FAIL. In an as-range or a certificate LP it stops the run. F3's own code raises nothing on these paths. M1 showed
  the branch with an injected exception on DEV 430000; no natural case is known. scipy 1.18.1 returns HiGHS errors as
  statuses (`_linprog_highs.py`), but its compiled HiGHS module translates C++ exceptions into Python ones
  (`RuntimeError`, `ValueError`, `IndexError`, `OverflowError`, `MemoryError`).
- **G2.** After status 0, nothing checks that the value and the multipliers are finite. In a fold,
  `max(v + PAD, nan)` returns v + PAD: a primal value with no certificate, which could tighten the base below the
  true support. In an alarm certificate a NaN only removes the alarm.
- **Also seen while checking G1:** scipy maps HiGHS `kModelError` to status 2. Status 2 is not always "infeasible".
  F3 already reads status 2 as a failure, never as a proof, so nothing changes.

**The change (F3 and F3a only; F, Fa, E, N and L are untouched):**
- `solve_f3`, before the attempts: every input array (objective, both right-hand sides, bounds, matrix entries) is
  checked for finite values and consistent shapes. A failed check raises `ValueError`. It is our own error, not a
  solver failure, and it stops the run.
- `solve_f3`, each attempt: an exception of type `RuntimeError`, `ValueError`, `IndexError`, `OverflowError`,
  `ZeroDivisionError` or `FloatingPointError` raised inside the `linprog` call ends that attempt as failed. With the
  inputs checked, these can only come from the solver. `MemoryError`, `TypeError` and everything raised outside the
  call are not caught.
- `solve_f3`, each attempt: status 0 counts as solved only if the value and every multiplier the LP has (inequality,
  equality, lower and upper bound) are finite. Otherwise the attempt has failed.
- The attempts, `n_retry` and `n_lp` are counted as before. After three failed attempts the LP returns
  `Failed(status)` for the last attempt, with status `"exception"` or `"nonfinite"` where that is how it failed.
  `Failed.kind()` reports both under their own names: 2, 4, slab, exception, nonfinite, other.
- `certified_max(harden, strict=False)`: with `strict=True` (F3 and F3a only) it returns NaN when any term is not
  finite or the final sum overflows. `Failsafe.lp_cert` and `Failsafe.implied` treat a non-finite certified bound as
  `Failed("nonfinite")`, so that LP takes its fallback. `AuditedF3` audits only finite bounds.
- `online()` is unchanged. Any other error in a fold is still recorded as an uncertified alarm and scored FAIL, and
  any other error elsewhere still stops the run. Neither is hidden.

**Why no decision changes when no such event occurs (MATH):** on an LP whose inputs are finite, whose attempts raise
nothing and whose status-0 answer and certificate are finite, every line of the new path computes what the old one
did, in the same order: the same attempts, counters, return value and `Failed` status. The records can differ only
where an exception or a non-finite value occurred. Each such event now takes a fallback that section "Amendment 10"
already proves sound.

**U0b, the solver-boundary path tests** (R0's harness style, DEV 430000, constructed by patching `rec_linprog` or
`certified_max` for one chosen LP; expected outcomes written here before the run):
1. exception on the first attempt of one fold direction, none after: solved by the second attempt; `n_retry` one
   higher than without the exception; no failsafe counter changes;
2. exception on all three attempts of one fold direction: `fold_dir_fallbacks["exception"] == 1`, the P_J bound is
   taken for it (`fold_implied == 1`), no alarm;
3. status 0 with a NaN inequality multiplier on all three attempts of one fold direction:
   `fold_dir_fallbacks["nonfinite"] == 1`, no alarm;
4. finite multipliers that make the certified bound overflow, on one fold direction:
   `fold_dir_fallbacks["nonfinite"] == 1`, no alarm;
5. a non-finite certificate on the "up" side of an alarm certificate on the fault row: `cert_fallbacks["nonfinite"]
   == 1` and `"up"` in `box_sides`; any alarm raised is certified;
6. exception on all attempts of one as-range side: `range_failures["exception"] == 1`, that z_t is not kept;
7. a NaN in an LP's input: `solve_f3` raises `ValueError`; it does not return `Failed`;
8. a `TypeError` raised by our own code in a fold (a patched `Failsafe._cub`): it propagates out of `online()`;
9. a `MemoryError` raised inside `linprog`: it propagates;
10. `Failed("exception").kind() == "exception"` and `Failed("nonfinite").kind() == "nonfinite"`.
U0b passes if all ten hold. R0's 13 path tests are run again at the new commit and must still pass.

**Identity criterion I2** (as I1, written before it ran; the comparison is every field except `seconds`, `step_ms`
and `fold_step_ms`):
- **I2a, Mac, now:** the 16 records of I1a (4 edge and 4 fault rows, settings none and d), new code against the
  0ce80072 records already on the Mac.
- **I2b, Arch, after all.done:** the new code on all rows of R-none, R-d and R-e, against the same settings at
  0ce80072 on Arch. This replaces I1b, which would have compared an intermediate commit.
- **I2c, F3a:** R4 (440243, unlocked with freeze 2's manifest as before) with the new code: the record and the audit
  equal d207c9d1's R4 except wall-clock time.
- **If every record is equal:** R1–R3 at 0ce80072 stand for the new commit, and the new commit is freeze 3's
  candidate.
- **If any record differs:** the change is not withdrawn (it closes G1 and G2). The difference is written down, and
  every R setting that differs is run again in full at the new commit; U1–U3 are judged on those runs.

**U5, the forced-fallback coverage test** (FREEZE-V3.md section 4, the condition of the slab rule; at the new commit):
- **Rows:** DEV seeds 430000 and 430001: their 16 healthy rows (E0 and E1, rw and ramp, uniform and edge noise) and
  4 fault rows (430000 and 430001 × cells drift_0.002 and stuck, E0, rw, uniform), all with F3a, W = 256, K = 64.
- **Forcing:** on healthy rows at t = 300, 1000 and 2000, on fault rows at t = 250 (onsets are 300–600), a
  measurement 10 °C above the box is written into the window at key t, just before step t + 1, past the keep gate,
  as R0's `slab_empty` does. It replaces z_t if z_t was kept. Every LP that holds it fails with kind `slab`, so no
  z is kept and nothing is evicted until the next fold, where every direction fails and the full reset removes it.
- **Truth:** the generator's states in the model's coordinates: x_t = (Tc_t − Sc_t, Ts_t − Ss_t, TA_t) − 25, with
  (Sc, Ss) the known response to the same command at zero ambient from the P0 = 20 steady state.
- **Pass if all hold:**
  - no alarm on a healthy row; every alarm on a fault row certified;
  - at every fold, the true state at the new τ satisfies d_i · x ≤ base_i + 1e-9 °C for all 42 directions;
  - at every alarm certificate computed, the true a_s at t lies inside its two certified bounds (+1e-9 °C);
  - on fault rows these two checks apply only while every measurement used precedes the onset (fold at t < t_f,
    certificate at t ≤ t_f): after the onset the data has no admissible explanation, so the plant state need not
    lie in the window;
  - each forcing is followed by slab failures and exactly one full reset, and the counters say so;
  - every fault row detects after its last forced reset (the lag is reported);
  - the exact audit finds no violation.
- **Reported, not deciding:** the measurements dropped, the samples from forcing to reset, and each fault row's lag
  against the same row without forcing.

**U5b, proposed after U5's result was read (2026-11-20 05:40; not run, needs Can's OK).** U5 failed two criteria
because two of its four fault rows (stuck, E0) have no oracle detection, so no sound method could detect them
(DIAG-3-RESULTS). U5b repeats only U5's fault part, unchanged in every other respect (F3a, the forcing at t = 250,
the same checks and tolerances), on the four fault rows: 430000 and 430001 × (drift_0.002, E0, rw, uniform) and
(stuck, E1, rw, uniform), whose oracle t* are 506, 652, 412 and 596. Its fault-row criteria apply to rows with an
oracle t*, as they should have in U5. The healthy part of U5 passed and is not repeated. U5 stays recorded as failed.
