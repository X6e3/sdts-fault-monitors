# v3: checks made for the outside review of the preprint (2026-11-22)

**What.** An outside review of preprint v0.2 (the paper and a clean copy of this repository at `f2f9cacb`, no network)
asked for a major revision. It reproduced the main scores from the raw rows with its own scorer, the detection times of
Figure 3 and Table 2 (TS on all 1,320 development rows), and it traced Appendix A to the code. Its report is kept with
the project's notes, outside this repository. This record holds the checks made here in answer, and the findings the
paper now uses. All checks ran on the Mac in the project environment (CPython 3.12.13, numpy 2.5.5, scipy 1.18.1).

## 1. WM's wider slab and exact matrix do not explain any delay of validation 3

**The review's point.** The oracle decides with the binary64 matrix and the noise bound δ; WM uses the exact matrix and
the slab d = fl(δ + η) ≥ δ + η, η = 1e-9 °C. So a record that exceeds δ by less than about η at t* can be flagged
later by WM for that reason alone, not because of what its representation discards. The review built one: a single
sample with z_0 = 2.3000000005 (shifted), which the oracle certifies inconsistent at t* = 0 and WM does not flag.

**Check** (`diag/eta_check.py`): in validation 3, WM detected 7,243 of the 7,255 certified events at t* and 12 after
it. For each of the 12, the oracle's certified bounds on d* at the prefixes z[0:t*] and z[0:t*+1]:

| run (uniform noise) | t* | WM | d_up − δ at z[0:t*] (°C) | d_lo − δ at z[0:t*+1] (°C) |
|---|---|---|---|---|
| 440402 drift_0.0005 E0 ramp | 1414 | 1434 | −4.06e-4 | 1.06e-7 |
| 440402 drift_0.0005 E1 ramp | 1414 | 1434 | −4.06e-4 | 1.07e-7 |
| 440493 drift_0.002 E0 rw | 789 | 988 | −8.26e-4 | 2.60e-6 |
| 440493 drift_0.002 E1 rw | 789 | 988 | −8.26e-4 | 2.60e-6 |
| 440534 drift_0.0005 E0 ramp | 1963 | 1980 | −2.46e-3 | 4.71e-4 |
| 440534 drift_0.0005 E1 ramp | 1963 | 1980 | −2.46e-3 | 4.71e-4 |
| 440558 drift_0.0005 E0 ramp | 2053 | 2077 | −1.47e-3 | 2.29e-6 |
| 440558 drift_0.0005 E1 ramp | 2053 | 2077 | −1.47e-3 | 2.29e-6 |
| 440568 drift_0.001 E0 ramp | 1345 | 1505 | −6.40e-4 | 2.47e-4 |
| 440568 drift_0.001 E1 ramp | 1345 | 1505 | −6.40e-4 | 2.47e-4 |
| 440599 drift_0.0005 E0 ramp | 2120 | 2332 | −3.64e-3 | 2.18e-5 |
| 440599 drift_0.0005 E1 ramp | 2120 | 2332 | −3.64e-3 | 2.18e-5 |

The smallest excess is 1.06e-7 °C, more than 100 times η plus the model gap of 5.0e-13 °C (FREEZE-V2.md section 1).
So with WM's own slab and matrix the full history is already inconsistent at t* in all 12. With the 7,243 events WM
flagged at t*, this covers every certified event: on validation 3, the same event set and the same t* hold under WM's
semantics, and every sample of WM's paired lag (1,264 s) is a loss of the bounded representation or of its primal
gate, not of the allowance. The paper says this in sections 1 and 7.4 and narrows the abstract's claim.

## 2. The scores under other metrics

`diag/metric_sensitivity.py` (recorded rows only, no simulation). Percentiles with linear interpolation.

| monitor (block) | D_paired | all events, miss at N − t* | all events, lag capped at 30 s | lag p90 / p99 (s) | misses / events |
|---|---|---|---|---|---|
| IM (1) | 0 | 0 | 0 | 53.4 / 808.0 | 24 / 7,201 |
| inv4p (1) | 0.15245 | 0.13230 | 0.26258 | 38 / 749.0 | 20 / 7,201 |
| TS (1) | 0.38655 | 0.36751 | 0.38880 | 21 / 526.6 | 16 / 7,201 |
| IM (3) | 0 | 0 | 0 | 55 / 833 | 27 / 7,255 |
| WM (3) | 0.99518 | 0.99600 | 0.99287 | 0 / 0 | 0 / 7,255 |

- The order of the monitors is the same under every metric. The review's own scorer gave the same values.
- IM's lag share of the drift cells: 99.85 % on B (the paired set) in validation 3 and 91.76 % over all certified
  events with misses at N − t* (the set of Figure 4); 99.81 % and 95.13 % in validation 1.
- The three slowest drift cells carry 97.9 % of IM's paired lag in validation 3 (97.0 % in validation 1).

## 3. Counts the paper now states

- **Undetermined oracle runs, validation 3:** 393 in all: 389 of the 800 healthy runs with noise exactly at ±δ, one
  healthy run with uniform noise (440582 E1 ramp) and 3 fault runs.
- **WM step times, validation 3** (wall clock, 14 workers on Arch): the median over runs of each run's median step is
  14.0 ms; the median over runs of each run's longest fold is 396 ms; on 5 of the 9,600 runs a fold took longer than
  1 s, the longest 34.5 s.

## 4. Findings of the review taken into the paper without a check of their own here

- **Theorem 2 needs the unit bases of ±e2 in the a_s-range.** The review replaced only the basis of the positive
  a_s-range support by a looser valid one (e2 = √2 q − e1 with q = (e1 + e2)/√2): with h(e2) = 2 the range's upper end
  became 6, and with z_0 = 3 IM flagged and the modified template did not. The prediction tables were unchanged. The
  frozen tables keep both unit bases, and no candidate was later than IM on validation 1. The statement now has the
  condition.
- **The solver contract.** WM catches six exception types from the solver call; the review raised `OSError` there and
  the call ended the run. Sections 5.4 and A.1 now state the six types and what happens otherwise.
- **Appendix A wording:** "adds pads" (it said "subtracts"); 28 vertices of C and 14 more from the two cuts (it said
  "42 vertices of C"); the extension of explanations past r; the condition on a removed node; the largest box end.
  *Added later the same day:* the vertex count and the invariance are now checked here too, by
  `diag/widebox_vertices.py` (`a196fd68`, written for `WIDEBOX-PLAN.md`). It found 28 + 14 vertices and no step above
  a clamp.
- **The window description, Figure 3's primal edge and centred median, Figure 4's drift share, section 8's "sound but
  incomplete", section 9's iteration cap** were reworded as the review asked.

## What this does not show

- Section 1 holds for validation 3 only; the other blocks were not checked this way.
- The equal-budget comparison with B1–B5 is the block run of `BASELINE-PLAN.md`, not part of this record.
