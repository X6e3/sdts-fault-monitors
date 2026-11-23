# Record: checks of review r3's points used in the paper (2026-11-23)

Descriptive checks, no verdict changes. Mac, CPython 3.12.13, numpy 2.5.5, scipy 1.18.1, tree at 3b363394 plus the
scripts named below. Sections 3–6 were revised after review r5 of the first draft (same day).

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

## Open from r3 (not done here)

- The oracle's upper-certificate pad (32·eps·(m+1)·scale) is used without a written lemma (review r5 sketches one with
  more than 20 times room for m ≤ 3,600; the paper now says "under the oracle's binary64 certificates").
- `check_c_state.py` K2: the gradual-underflow term (r2) and the |h| ≤ HMAX induction in the proof.
