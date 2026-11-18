# Diagnosis 1: results (DEV only; 2026-11-18)

**Plan:** `DIAG-1-PLAN.md`, with amendment 1 written before any arm result.

**Revised the same day after review round 1** (GPT R1, Hydrogen H1, Sol T2b). What changed, and why, is listed in
the last section. The main correction: the loss arrives in single steps at measurement cuts, not as a steady drift.

**Run:**
- `diag1.py` at `6fe3b54` on Arch, clean tree.
- 5 runs × L ∈ {16, 64, 256}, 10 workers, a few minutes.
- Outputs in `results/v3/diag1/run1-6fe3b54/`: per job, a JSON summary and an npz with the step-by-step margins and
  supports of every arm, plus the run log. The base pickles stay on Arch.

**Freeze 1** and seeds 440200+ are untouched.

**Labels:** OBSERVED (measured, with the file); INFERRED (follows from the observations); HYPOTHESIS (not shown).

## Checks (OBSERVED)

**Built-in checks, all passing in all 15 jobs:**
- arm A detects at the certified t*;
- arm D reproduces the frozen cyl16p's detection;
- the nesting of the supports holds (A ≤ B ≤ C ≤ D, B ≤ E ≤ D, C_full ≤ C, within 1e-9 °C).

**Independent check (Sol, DIAG1-T2):** the vertex enumeration of arm A was compared with Sol's full-history LP (HiGHS)
at 12 points of 430007, 430010 and 430019. Sol's files are in `results/v3/diag1/codex-T2/` and their hashes match its
`DONE.txt`.
- Per point the comparison covers as[k+1] min/max and TA[k] min/max.
- The largest difference is **8.4e-9 °C** (threshold 1e-6).
- The LP's margins at t* are −4.186, −4.509 and −0.389 mC; arm A gives the same values.

**Independent check, part 2 (Sol, DIAG1-T2b):** in `results/v3/diag1/codex-T2b/`; all 18 hashes match its
`DONE.txt`. My values for it are `run1-6fe3b54/claims-for-T2b.json` (sha256 `9552927a…`).
- **Full-history LP for 430027 and 430000**, at k0 for L = 16, 64, 256 and at t* − 1: as[k+1] and TA[k] agree with
  arm A within 1.4e-11 °C.
- **16 finite-window LPs started from the exported B and E start sets** (the four hard runs, L = 64 and 256):
  - every margin at t* agrees with mine within 9.6e-9 °C;
  - every verdict "detected at t* or not" matches (32 of 32 comparisons, A included);
  - every extremum has a dual bound and a verified feasible path.
- **So the two direction-loss findings stand.** At L = 256, B's margin is +0.375 mC in 430027 and +0.045 mC in 430010,
  against −4.101 and −0.389 mC for A. Started from H_k0, the t* measurement stays consistent even when everything after
  k0 is exact.

## Detection times (OBSERVED)

"—" means no detection before t* + 300, the cap of the exact arms. Those times are right-censored, so the delay of
such a row cannot be split into pieces. The margin split in the next section is complete in every row (GPT R1).

| run | L | t* | A | B | E | C | C_full | D | F |
|---|---|---|---|---|---|---|---|---|---|
| 430007 drift_0.002 rw | 16 / 64 | 673 | 673 | 673 | 792 | 673 | 673 | 792 | 792 |
| | 256 | | 673 | 673 | 673 | 792 | 792 | 792 | 792 |
| 430027 drift_0.002 rw | 16 / 64 | 579 | 579 | 579 | — | 579 | 579 | 1429 | 1429 |
| | 256 | | 579 | — | — | 1429 | 1429 | 1429 | 1429 |
| 430000 drift_0.001 ramp | 16 / 64 | 849 | 849 | 849 | — | 849 | 849 | 2048 | 2048 |
| | 256 | | 849 | 849 | 849 | 2048 | 2048 | 2048 | 2048 |
| 430010 drift_0.0005 ramp | 16 / 64 | 695 | 695 | 695 | — | 695 | 695 | 3575 | 3575 |
| | 256 | | 695 | — | — | 3575 | 3575 | 3575 | 3575 |
| 430019 drift_0.001 ramp (control) | all | 393 | 393 | 393 | 393 | 393 | 393 | 393 | 393 |

## Margins at t*, and their split (OBSERVED)

The margin is the signed margin of the measurement at t* against each arm's predicted as-range, in mC (1e-3 °C);
negative means detected. Because the arms are nested, the pieces telescope exactly; the split still depends on the
order (plan, section 2).

| run | L | A | B | C | D | E | geometry B−A | new wrapping C−B | earlier slack D−C | other order: E−B, D−E |
|---|---|---|---|---|---|---|---|---|---|---|
| 430007 | 16, 64 | −4.186 | −4.186 | −4.186 | 21.606 | 21.606 | 0 | 0 | **25.792** | 25.792, 0 |
| 430007 | 256 | −4.186 | −4.186 | 21.304 | 21.606 | −4.186 | 0 | **25.490** | 0.302 | 0, 25.792 |
| 430027 | 16, 64 | −4.101 | −4.101 | −4.101 | 1.979 | 1.979 | 0 | 0 | **6.080** | 6.080, 0 |
| 430027 | 256 | −4.101 | 0.375 | 1.539 | 1.979 | 1.081 | **4.476** | 1.164 | 0.440 | 0.706, 0.898 |
| 430000 | 16, 64 | −4.625 | −4.625 | −4.625 | 5.674 | 5.674 | 0 | 0 | **10.299** | 10.299, 0 |
| 430000 | 256 | −4.625 | −4.625 | 5.554 | 5.674 | −4.625 | 0 | **10.179** | 0.120 | 0, 10.299 |
| 430010 | 16, 64 | −0.389 | −0.389 | −0.389 | 5.027 | 5.027 | 0 | 0 | **5.417** | 5.417, 0 |
| 430010 | 256 | −0.389 | 0.045 | 3.928 | 5.027 | 4.561 | 0.434 | **3.883** | 1.099 | 4.515, 0.467 |
| 430019 (control) | 256 | −4.509 | −4.509 | −0.240 | −0.227 | −4.509 | 0 | 4.269 | 0.014 | 0, 4.282 |

At every start, F (P with the exact TA lower bound restored) gives the same margin as D, within 0.2 mC.

- **One side decides throughout.** At t*, every arm of every run is decided by the upper side (+e2). The lower-side
  margins are 627–705 mC (`review1/steps.txt`). Each split above is therefore the split of one support; the deciding
  side never switches (GPT R1 asked).
- **Zero delay is not zero loss.** In the control 430019 at L = 256, C loses 4.27 mC of margin and still detects at t*
  (GPT R1).

## Where cyl16p's state is loose (OBSERVED, `base-*.pkl`, at k0)

P_k0 against H_k0, the tightest set with the same directions, per direction class:
- **TA (±e3):** P looser in both bounds, not only the lower one: the lower bound by 26–53 mC in every case, the
  upper by 5–40 mC.
- **Error-plane directions (d·(1,1,1) = 0, which couple TA with ac/as):** up to 46 mC.
- **Directions orthogonal to e3 (ac/as only):** up to 26 mC, median 5–13 mC.

At t* the gap of D against A is again largest in ±TA (24–40 mC), and 3–26 mC in ±e2.

## The separating support at t* (OBSERVED, arm A, the same in every run)

The support of +e2 that rejects the measurement at t* rests on two facets of the exact predicted set, with NNLS
residual ≤ 3e-17:
- **n ≈ (−0.71, 0.71, 0), weight ≈ 1.42:** the bound on as − ac.
- **n = (1, 0, 0), weight ≈ 1.0:** the upper bound on ac.
- In 430019 the two facets are (−0.82, 0.57, 0) and (0.93, 0.37, 0).

Both have n·e3 = 0 and coincide with directions of D (largest |n·d| = 0.9998–1.0000).

**Their ages are 0 or ∞, not intermediate (corrected after GPT R1; Hydrogen's amendment-1 caveat applies here).**
`review1/ages.txt` has the numbers.
- **The as − ac facet** has |n·(1,1,1)|/√3 = 0.001–0.017 in four runs (0.143 in 430019). Its normal lies in both
  the age-0 plane and the age-∞ plane, so "age 0" alone was the wrong label.
- **Between those two ages it does not fit.** |n·M^j e3| / |M^j e3| peaks at about 0.13 near j = 10.
  - For n ⊥ e3 and n ⊥ (1,1,1) this quantity is a multiple of λ1^j − λ2^j (MATH), with λ1 = 0.9844 and λ2 = 0.7156.
  - λ1^j − λ2^j is 0 at j = 0, tends to 0 as j grows, and peaks near j = ln(ln λ2 / ln λ1) / ln(λ1/λ2) ≈ 9.6.
- **The ac upper facet** fits age 0 only (0.577 at age ∞).

## What each explanation predicted, and what happened (INFERRED from the tables above)

| explanation (plan, section 4) | outcome |
|---|---|
| direction loss | **Not at L = 16 or 64:** B = A in all 4 hard runs. **At L = 256, in 2 of 4:** in 430027 it is the largest piece (4.48 of 6.08 mC); in 430010 it is 0.43 mC, enough on its own to undo a 0.39 mC margin. Confirmed by Sol's LP (T2b). |
| wrapping (the online update) | **Supported as the main mechanism.** Starting from the tightest hull, the online update keeps the decision through the last 64 steps (C = A at L ≤ 64). It loses it when the window reaches back 256 steps (C ≈ D in 430007, 430000, 430010). The loss arrives in single steps at measurement cuts (next section), not as a drift. |
| slack accumulated before k0 | The same mechanism seen from a later start. For L ≤ 64 all the loss is D − C, i.e. already in P_k0. At L = 256 it is nearly 0 in 430007 and 430000, where E = A: cyl16p's state at t* − 256 still holds the information, and the update after it loses it. |
| only the ambient's lower bound | **Refuted:** F = D everywhere. The upper TA bound and the error-plane directions are as loose. |
| intermediate-age directions | **Refuted in its simple form:** the separating facets at t* are template directions, at age 0 (the as − ac facet equally at age ∞), and neither fits an intermediate age. The information missing at t* is in the values of existing directions (fed by the TA bounds), not in missing directions. Whether other directions would keep those values tighter over time is not tested by this (GPT R1). |
| pruned bases | **No effect:** C_full = C everywhere. |

**The mechanism (INFERRED, 5 runs; plausible, not proven in general; revised after review round 1).**
- **Where it happens:** in the ambient. The online template update loosens the bounds on TA and on the directions
  that tie TA to the core and the surface.
- **When it happens:** in single steps, at measurement cuts (next section). It is not a steady drift.
  - Between cuts no new TA slack appears. The slack grows in directions that the dynamics does not map back into D
    (seen for d[36] in 430007 and 430010).
  - The next measurement that actually cuts the predicted set turns that slack into TA slack at once.
  - The TA slack then reaches the as-range through the dynamics over the following steps.
- **Why the window length matters:** L = 64 against L = 256 shows which cuts the window contains, and how much slack
  is waiting when each one comes. It does not show a gradual loss. The TA gap is not monotone either: in 430027 it is
  24 mC at dk = 32–64 and 1.7 mC at t*.
- **Why it decides:** in the measurement window before t*, the oracle's margins are 0.4–4.6 mC. A few such steps
  (up to 31 mC each in TA, 9 mC on average) are enough to undo the decision.
- **What it is not:** the decisive directions themselves are not missing. What is lost is what a few far-apart
  measurements say about the common ambient path, the same sparse, long-range kind of evidence the inconsistency
  proofs use (`RESULTS.md`: median 6 measurements, spans of 270–480 samples).
- **A secondary effect:** in two runs the directions also fall short over 256 steps (B ≠ A, confirmed by T2b). That
  slack of H_k0 shows up at cuts in the same way (B, too, takes TA steps at cuts).

**Not shown:**
- that this holds beyond these 5 runs;
- what sets the size of each step;
- whether any fixed direction family avoids it.

## When the loss happens (OBSERVED, `review1/steps.txt`; read from the T1 npz, no new run)

Hydrogen's H1 found this first in 430007. It is reproduced here from the npz and extended to all five runs.

**Every TA step follows an active cut.** In the 256 steps before t* (L = 256), the measurement's slab cuts arm C's
predicted as-range at 27–33 steps.
- Every rise over 1 mC of the TA gap C − B (±e3) follows a step at which the slab cuts C's or B's predicted as-range:
  63 rises, 565 mC in all.
- No rise follows any other step.

**Between cuts the slack grows elsewhere, unseen.** Take 430007, k0 = 417:
- In k = 418–423 the gaps C − A and B − A are 0 in ±e3 and ±e2 (below 1e-5 mC).
- In the same steps the gap in d[36] = (−0.83, 0.56, 0) grows: from 0.61 to 3.14 mC in C, and to 1.70 mC in B.
  - C's growth beyond B: M^T d[36] lies 5.95° away from every direction of D, so C bounds the support of d[36]
    after a step through the template, not exactly.
  - B's growth: B is exact after k0, but H_k0 already had slack in the direction M^T d[36].

**Then an active cut converts it into TA slack.** At k = 423 the slab (z + δ = −0.5597, shifted) cuts below A's
as-range top (−0.5290).
- A's TA maximum falls by 52.65 mC from one prediction to the next (k = 423 to 424).
- C's TA maximum ends 18.59 mC above A's, and B's ends 4.23 mC above.

**The same pattern in 430010:** at k = 446, C's TA minimum is 18.06 mC looser than A's, and B's is 7.14 mC looser.

## The slack of H_k0 outside D (OBSERVED, `review1/k0gaps.txt`; Hydrogen's H1 numbers, reproduced on Arch)

The largest gaps hull_D(X_k0) − X_k0 over the facet normals of X_k0, at k0 = t* − 256, are 5.5–8.2 mC. They fall
into two groups:

| group | examples | angle from D | angle from the arc ±(M^T)^j e2 |
|---|---|---|---|
| ac-heavy, TA of opposite sign | (0.76, 0.17, −0.63), (0.86, −0.06, −0.51) | 9.5–14.5° | 51–60° |
| as-heavy, with a TA part | (−0.04, 0.97, −0.22), (0.24, 0.92, −0.30), (0.10, −0.92, 0.38) | 12.6–22.6° | 12.8–27.1°, never closer than D |

**The arc (MATH).**
- M is entrywise ≥ 0 and its rows sum to 1.
- So (M^T)^j e2, which is row 2 of M^j, lies in the positive octant for every j.
- It runs from e2 towards e3: row 2 of M^256 is (0.011, 0.003, 0.986).

Hydrogen's "51–60° from the arc" holds for the first group only. For the second group the arc is no closer than D
already is.

## What this suggests next (HYPOTHESIS; nothing built; revised after review round 1)

1. **Forward orbits of e2 alone (weakened).** The orbit lies on the positive-octant arc, and it covers none of the
   slack directions above better than D does. It stays only as a control (Hydrogen's proposal A).
2. **Directions that close the cut steps (Hydrogen's proposal B):**
   - the forward images (M^T)^j d, j ∈ {1, 2, 4}, of the directions active at cuts (such as d[36] and the as − ac
     face);
   - mid-latitude rings (|d_3| about 0.2–0.6, both TA signs).
   - **The test:** arm C at L = 256 with such a family. **The prediction:** the TA steps after cuts shrink.
3. **A state that keeps the recent active cuts (new).**
   - The loss arrives only with active cuts, at 27–33 of 256 steps (11–13 %), and the proofs need only a handful of
     measurements. A state that keeps the last few active cuts exactly, beside the template, aims at it directly.
   - **The constraint:** it must keep them as a small LP with one common ambient path. Transported halfspaces each
     pay their own worst-case ambient step, which is why the `window` family failed (`RESULTS.md`).
   - **Cost:** it is paid per cut, not per step. Cortex-M timing is open.
   - This is the bounded online adaptive state (with v2 in parallel), narrowed to cut events.
4. **An update that re-templates less often** (a block of steps with offline bases): unchanged. The limit to work out
   first is that the measurement slabs inside a block cannot all be applied offline-exactly.
5. **The decision rule Hydrogen proposes (not adopted; Can decides):** if a family like 2 still leaves C ≈ D at
   L = 256, go to 3 instead of searching more fixed families.

## Data for the reviewers

- Step-by-step margins of every arm: `margin_<arm>` in each npz, as rows (k, margin in °C).
- Supports of every arm's predicted set in all 42 directions: `sup_<arm>`, with `ks_<arm>`.
- Gaps against A at k0+1 and at t*: `gaps_vs_A` in each JSON.
- Separating facets, weights, normals and ages: `separating_at_t_star` in each JSON.
- Claude's values for the T2b check: `run1-6fe3b54/claims-for-T2b.json` (sha256 `9552927a…`).
- Sol's T2b outputs: `codex-T2b/`.
- The review-round readings: `review1/steps.txt`, `ages.txt`, `k0gaps.txt`, all from `diag1_review.py` (sha256
  `f74c1cfe…`, stamped in each file). They are read-only analyses of the T1 outputs; `k0gaps` needs the base pickles,
  which are on Arch.

## Changes in review round 1 (2026-11-18)

| what | before | after | from |
|---|---|---|---|
| independent check of B and E | pending | done; both direction-loss findings confirmed | Sol T2b |
| how the online update loses TA | "steadily loosens, over about 256 steps" | single steps at active cuts; slack builds unseen in directions not closed under the dynamics | Hydrogen H1 (reproduced); GPT R1 asked for the step profile |
| ages of the separating facets | "age 0" | age 0 or ∞ for the as − ac facet; neither is intermediate | GPT R1 |
| censored delays, deciding side | not stated | stated (delays of "—" rows cannot be split; +e2 decides throughout) | GPT R1 |
| forward orbits of e2 as next family | first suggestion | weakened to a control (MATH: the orbit stays in the positive octant) | Hydrogen H1 |
