# Diagnosis 1: results (DEV only; 2026-11-18)

**Plan:** `DIAG-1-PLAN.md`, with amendment 1 written before any arm result.

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
- The LP check of 430027 and 430000 is task T2b, pending.

## Detection times (OBSERVED)

"—" means no detection before t* + 300, the cap of the exact arms.

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

## What each explanation predicted, and what happened (INFERRED from the tables above)

| explanation (plan, section 4) | outcome |
|---|---|
| direction loss | **Not at L = 16 or 64:** B = A in all 4 hard runs. **At L = 256, in 2 of 4:** in 430027 it is the largest piece (4.48 of 6.08 mC); in 430010 it is 0.43 mC, enough on its own to undo a 0.39 mC margin. |
| wrapping (the online update) | **Supported as the main mechanism.** Starting from the tightest hull, the online update keeps the decision for 64 steps (C = A at L ≤ 64) but loses it over 256 steps (C ≈ D in 430007, 430000, 430010). |
| slack accumulated before k0 | The same mechanism seen from a later start. For L ≤ 64 all the loss is D − C, i.e. already in P_k0. At L = 256 it is nearly 0 in 430007 and 430000, where E = A: cyl16p's state at t* − 256 still holds the information, and the update after it loses it. |
| only the ambient's lower bound | **Refuted:** F = D everywhere. The upper TA bound and the error-plane directions are as loose. |
| intermediate-age directions | **Refuted in its simple form:** the separating facets at t* are template directions, at age 0. The information missing at t* is in the values of existing directions (fed by the TA bounds), not in missing directions. Whether aged directions would keep those values tighter over time is not tested by this. |
| pruned bases | **No effect:** C_full = C everywhere. |

**The mechanism in one paragraph (INFERRED, 5 runs; plausible, not proven in general).**
- **Where it happens:** in the ambient. The online template update steadily loosens the bounds on TA and on the
  directions that tie TA to the core and the surface.
- **How it unfolds:**
  - From the tightest template hull it keeps the decisive information for at least 64 steps.
  - Within about 256 steps (2–4 times the slow mode's 63.5 samples) it reaches cyl16p's own steady looseness: 25–50 mC
    in TA, 3–26 mC in the as-range at t*.
  - In the measurement window before t* the oracle's margins are 0.4–4.6 mC, so that looseness undoes the decision.
- **What it is not:** what is lost is not the decisive directions themselves. It is the information the measurements
  of the last few hundred samples give about the ambient path, which only an update that keeps TA's coupling exact
  retains.
- **A secondary effect:** in two runs the directions also fall short over 256 steps.

**Not shown:**
- that this holds beyond these 5 runs;
- why the update loosens TA at this rate;
- whether any fixed direction family avoids it.

## What this suggests next (HYPOTHESIS; nothing built)

1. **Directions that carry TA as future measurements see it:** forward orbits (M^T)^j e2 for j up to about 128–256,
   at a geometric spacing. They are the combinations of (ac, as, TA) that the measurement j steps ahead depends on.
   - DEV's orbit families went only to j = 2–4.
   - The `window` family, which did not help, used the backward images (M^-T)^j e2 of past measurements, which is a
     different set.
   - The test: arm C at L = 256 with that family.
2. **An update that re-templates less often:** a block of several steps with offline bases (Hydrogen's suggestion).
   The limit to work out first: the measurement slabs inside the block cannot all be applied offline-exactly.
3. **A bounded online adaptive state, with v2 in parallel,** or a window LP over 256 steps, as the stronger and costlier
   controls.
4. **Before any of these:** the LP check of arms B and E (T2b, Sol), which carry the two direction-loss findings.

## Data for the reviewers

- Step-by-step margins of every arm: `margin_<arm>` in each npz, as rows (k, margin in °C).
- Supports of every arm's predicted set in all 42 directions: `sup_<arm>`, with `ks_<arm>`.
- Gaps against A at k0+1 and at t*: `gaps_vs_A` in each JSON.
- Separating facets, weights, normals and ages: `separating_at_t_star` in each JSON.
- Claude's values for the T2b check: Arch `~/Research/sdts-runs/v3-diag1/run1-6fe3b54/claims-for-T2b.json`
  (sha256 `9552927a…`).
