# Record: checks of review r3's points used in the paper (2026-11-23)

Descriptive checks, no verdict changes. Mac, CPython 3.12.13, numpy 2.5.5, scipy 1.18.1, tree at 3b363394 plus the
scripts named below. Sections 3–6 were revised after review r5 of the first draft; sections 7 and 8 were written after
it and read by review r6, and section 9 follows r6's proposal, the same day.

## 1. IM has the S gap of the frozen template

- `experiments/v3/diag/im_s_gap.py` runs `experiments/machine/thermal_machine.py` (IM) on the healthy witness record of
  RECORD-2026-11-22-review2.md (`results/v3/review2/witness-42W.txt`, sha256 83011769e62e98ad...).
- Output:

```
witness sha256 83011769e62e98adc21b4a71192d3e6e80895a9b69b2364722be85408e1cc86b
box 23.0 27.0 DELTA 0.3
IM flags at sample 309 feasible (27.000000000000004, 27.0)
```

- IM flags at the same sample as freeze 1's Python template (309). In the code, `observe` widens z and z ± δ outward
  by one ulp each; the command part S (`self._ts`, from `T.step`) is binary64 with no pad. The statements about IM
  in exact arithmetic are not affected. On validation 3, IM (v2 in the records) flagged none of the 2,342 admissible
  runs (RECORD-2026-11-21-validation.md, line 92).

## 2. Corollary A.9's terms

- The ambient term 6.4e-12 °C is 3599 × 2^-49 (FREEZE-V2.md line 98: an increment can exceed ρ by half an ulp of
  27, and the projection moves T_A, and so a_s, by at most 3599 times that). It grows with the record's length; the
  corollary now says "on records of 3,600 samples".
- The start state's rounding: FREEZE-V2.md lines 94–95 ("the float start (the steady state, three operations) adds a
  few ulps, which the recurrence does not amplify"). Checked: the (a_c, a_s) block F of `baselines.MX` is
  nonnegative with row sums 1 and 0.9333, so ‖F^k‖∞ ≤ 1; (I − F)^-1 has row sums 67.5 and 52.5, as the paper says.

## 3. Percentile and margin definitions (read in the code)

- `score_validation.py` `q()`: the order statistic at index int(p (n − 1) + 0.5) (nearest index).
  `diag/metric_sensitivity.py` `pct()`: linear interpolation between neighbouring order statistics. For IM's p90 on
  validation 3 both give 55 s (RECORD-2026-11-21-validation.md; Table "other metrics").
- The alarm's certified margin (`F3.alarm_certificate.certified_margin_mC`, `diag/diag3_cw.py` lines 658–660): the
  signed distance from WM's certified bounds on a_s to the slab z ± self.delta rounded outward, with self.delta =
  DELTA_F = δ + η (η = 1e-9 °C) in the validated, hardened WM. Largest over the 7,258 alarms of validation 3:
  −0.014672562867357186 m°C. The primal margin `F3.margin_at_detect_mC` (`diag1.margin`, WM's a_s-range against radius
  δ; on validation 3 written by `diag3_cw_dev.online`) has its largest at −0.014673832420042388 m°C; the paper does
  not use it. (A first draft of the paper's sentence took the recorded margin to be the primal one; review r5 found
  this, and the paper keeps "certified margin" with its definition.)

## 4. The oracle's room on the 742 certified-consistent runs

From `results/v3/oracle-margin-c8c4971c/margins.jsonl` (RECORD-2026-11-23-oracle-margin.md): the 742 runs without t*
have consistent room at least 5.149699551224018e-4 °C; the 7,255 events have at least 2.895884610720767e-6 °C before
t* and 1.0749178069868748e-7 °C after. The 12 late events' 1.06e-7 (RECORD-2026-11-22-review-checks.md, `eta_check.py`,
Mac) and 1.07e-7 here are both lower bounds on the same d*, from different multipliers.

## 5. z on the prefixes the oracle judged (Sterbenz)

The oracle shifts z by 25 before its LPs; z − 25 is exact for z ≥ 12.5 (Sterbenz up to 50; above 50 it is a multiple
of z's ulp below 2^53). `experiments/v3/diag/z_prefix_check.py 8` (Mac, 3.5 s) regenerated the 7,997 certified fault
runs of validation 3 (data only):

```
{
 "runs": 7997,
 "events": 7255,
 "consistent": 742,
 "min_z_event_prefix": 22.327046020042165,
 "below_12.5_event_prefix": 0,
 "min_z_consistent": 22.702998920716063,
 "below_12.5_consistent": 0,
 "min_z_all_samples": -2.928145238660889,
 "argmin_event_prefix": "440438-stuck-E1-rw-uniform"
}
```

Every z on z[0:t*+1] of the events and on z[0:N] of the consistent runs is at least 22.3, so the shift is exact there.
Over all samples it is not: after t* a stuck sensor under E1 reads down to −2.93 (review r5 found this on DEV runs).
The bisection may test longer prefixes, but a certified t* rests on z[0:t*] and z[0:t*+1] alone (consistency of
prefixes is monotone), and those are the prefixes measured here and in RECORD-2026-11-23-oracle-margin.md.

## 6. The plant's states are bounded (Corollary A.9)

`experiments/generators/thermal.py` `step`: F = [[1 − K/CC, K/CC], [K/CS, 1 − (K + H)/CS]] ≥ 0 and the inputs enter as
p/CC and H·ta/CS, nonnegative; P ∈ [0, 42], T_A ∈ [23, 27]. Started at a steady state, the states stay between 0 and
the largest steady state: t_s ≤ 27 + 42/0.8 = 79.5 °C, t_c ≤ 79.5 + 42/2 = 100.5 °C, below the 250 the proof uses.

## 7. `check_c_state.py` K2: the underflow term and |h| ≤ HMAX

K2's need now carries 4 · tiny (tiny = 2^-1075 in binary64, 2^-150 in binary32): the C state's dot product
(`c/v3_state.c` `support`) has three products, each losing at most tiny beyond the relative model under gradual
underflow, carried through two additions (3 (1 + u)^2 tiny < 4 tiny). The criterion's docstring records the addition
and the |h| ≤ HMAX argument: `v3_observe` keeps every h_i ≤ CAP_i (largest 2.9981327522311334 for cyl16p) and the
start supports are clamped (largest 2.828); while the exact set is nonempty, h_i is at least its support in d_i,
inside [-2, 2]^3, so at least −2‖d_i‖_1 (2 max‖d_i‖_1 = 3.265986323710904); HMAX = √3 · 2.2 = 3.8105.

Rerun on the Mac (14 s each), outputs in `results/v3/c-state/k2-underflow-20261123/`:
- `check_c_state.py` (the frozen C state): every field equals `results/v3/c-state/check-1c4cb409.json`, K2 included
  (no entry uncovered in either precision; smallest slack 87.3 % of the pad in binary64, 74.8 % in binary32);
  verdict OPEN as before (K5, the start supports, MCU-NOTES).
- `check_c1.py` (the revised C state): every field equals `results/v3/c-state/c1-b68f865d/y123.json`; Y1–Y3 hold.

## 8. The oracle's upper certificate (the paper's lemma `lem:ocert`)

Read in `experiments/oracle/thermal_oracle.py`:
- `_project`: each step clips to [nextafter(fl(p − ρ), p), nextafter(fl(p + ρ), p)], inside [p − ρ, p + ρ] exactly,
  then to the box, which contains p; so the projected path meets (b) and (c) in exact arithmetic. The start is
  (T_A0, T_A0).
- The matrix (A11, A12; A21, A22, B2) is nonnegative; read as rationals its rows sum to 1 + 2^-56 and 1 + 3·2^-56
  (checked with `fractions`).
- `_residual_range`: per step a_c from two products and one addition, a_s from three products and two additions;
  the residual z − a_s one subtraction; pad = 32·EPS·(m + 1)·scale, scale = max(1, max|T_A|, max|z|), one rounding;
  `_forward` rounds the final distance up by one ulp.
The lemma's bound: the computed a_s is within 3.01·m·u·σ of the exact a_s of the binary64 matrix along the projected
path, and the residual and the pad add 4.2·u·σ, against a pad of 64·(m + 1)·u·σ. The prefixes are shifted exactly
(section 5).

Review r6 read the lemma: correct; the statement now names d_up (the oracle calls `_forward` with offset 0.0,
line 370) and the induction covers the computed states as well as the exact ones; "shifted exactly" is not needed for
the lemma (it is about the prefix as the oracle reads it).

A numerical sanity check, not part of the proof: `experiments/v3/diag/ocert_check.py TYPE 1` (Mac, about 65 s each)
calls the oracle's `_project`, `_residual_range` and `_forward` on five path types of 3,600 samples and compares with
the binary64 matrix in exact arithmetic along the projected path:

```
walk seed 1: admissible True, exact residuals inside [low, high] True, max|exact| <= d_up True, worst |err| / (u sigma) 7.413, bound 10840.2, pad / (u sigma) 230464, sigma 1.7840731044807883, 64.3 s
top seed 1: admissible True, exact residuals inside [low, high] True, max|exact| <= d_up True, worst |err| / (u sigma) 8.967, bound 10840.2, pad / (u sigma) 230464, sigma 2.3, 64.6 s
bottom seed 1: admissible True, exact residuals inside [low, high] True, max|exact| <= d_up True, worst |err| / (u sigma) 8.967, bound 10840.2, pad / (u sigma) 230464, sigma 2.3, 65.3 s
fault seed 1: admissible True, exact residuals inside [low, high] True, max|exact| <= d_up True, worst |err| / (u sigma) 0.059, bound 10840.2, pad / (u sigma) 230464, sigma 350.0, 63.1 s
ramp seed 1: admissible True, exact residuals inside [low, high] True, max|exact| <= d_up True, worst |err| / (u sigma) 32.068, bound 10840.2, pad / (u sigma) 230464, sigma 2.0, 64.6 s
```

(A first version of the script, with the walk only and its own copy of the loop, gave 7.396 for a walk drawn from
another random stream.)

## 9. The oracle's lower certificate (the paper's lemma `lem:olow`)

Review r6 proposed a lemma for `_dual_bound` without a code change; the paper's version keeps its argument with
constants checked here. Read in `experiments/oracle/thermal_oracle.py` (margin LP, box and rate):
- `_build`: n_v = 3m + 2 variables; A_eq has 2m rows and 7m − 3 nonzeros, at most 3 per column; A_ub has 4m − 2 rows
  and 10m − 4 nonzeros, at most 2m per column (the offset and d columns); c has a single 1 at d. `terms` has
  (4m − 2) + 2m + 2 (3m + 2) = 12m + 2 entries.
- `_optimum_caps`: T_A 2, states 2 (1 + 8 eps (m + 1)), offset 0 (fixed in margin mode), d max|z|, all times 1 + 8 eps;
  the zero shifted ambient path is admissible and gives a_s = 0, so d* ≤ max|z|.
- `_dual_bound` forms about 52m products (A_ub^T y and A_eq^T y twice, the 12m + 2 terms, the scale and correction
  products), below the lemma's 60m.
- `_adjacent_rate_bound`: 2 d ≥ |z_k − z_{k−1}| − ρ − pad, pad = 64 eps (m + 1) max(1, max caps). The differences of the
  states follow the same nonnegative recurrence driven by the increments of T_A, starting from (row sum − 1) T_A0, so
  |Δa_s| ≤ ρ (1 + 3·2^-56)^m.

A numerical sanity check, not part of the proof: `experiments/v3/diag/olow_check.py` (Mac) regenerated the two events
with the smallest inconsistent room (440402 drift_0.0005 E0/E1 ramp, t* 1414), solved the oracle's LP on z[0:1415]
with each of its attempts, and compared `_dual_bound` with the same weak-duality bound in exact arithmetic:

```
440402 drift_0.0005 E0 ramp m=1415 highs-ds presolve=False: d_lo 0.30000010616821116, exact bound 0.3000001164070187, d_lo - delta 1.061682e-07, exact - d_lo 1.024e-08, float <= exact True
440402 drift_0.0005 E0 ramp m=1415 highs-ipm presolve=False: d_lo 0.3000000474834482, exact bound 0.3000000577222559, d_lo - delta 4.748345e-08, exact - d_lo 1.024e-08, float <= exact True
440402 drift_0.0005 E0 ramp m=1415 highs-ds presolve=True: d_lo 0.3000000894620707, exact bound 0.30000009970087865, d_lo - delta 8.946207e-08, exact - d_lo 1.024e-08, float <= exact True
440402 drift_0.0005 E0 ramp highs-ipm True no solution
440402 drift_0.0005 E1 ramp m=1415 highs-ds presolve=False: d_lo 0.30000010749145467, exact bound 0.30000011773026247, d_lo - delta 1.074915e-07, exact - d_lo 1.024e-08, float <= exact True
440402 drift_0.0005 E1 ramp m=1415 highs-ipm presolve=False: d_lo 0.3000001180621246, exact bound 0.3000001283009321, d_lo - delta 1.180621e-07, exact - d_lo 1.024e-08, float <= exact True
440402 drift_0.0005 E1 ramp m=1415 highs-ds presolve=True: d_lo 0.3000001039569913, exact bound 0.3000001141957989, d_lo - delta 1.039570e-07, exact - d_lo 1.024e-08, float <= exact True
440402 drift_0.0005 E1 ramp m=1415 highs-ipm presolve=True: d_lo 0.29999999245066883, exact bound 0.3000000026894764, d_lo - delta -7.549331e-09, exact - d_lo 1.024e-08, float <= exact True
```

Every float value is below the exact bound, by 1.024e-8 (the code's relative pad). The first attempt on the Mac gives
1.0617e-7 for E0, as `eta_check.py` did (1.06e-7); Arch's run gave 1.0749e-7 (the solvers' multipliers differ between
the machines); all are lower bounds on the same d*.

## Open from r3

- None. (The lower certificate's lemma covers d_lo ≥ 2^-900, so every inconsistent verdict; `_dual_bound` itself has
  no explicit underflow term.)
