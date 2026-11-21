# v3: the post-freeze fixes of the window code (2026-11-22)

**What.** The general fixes that `FREEZE-V3.md` section 5 (review M3, decision of 2026-11-20) deferred until after the
freeze, "for the code release and the next plant". All five are in `experiments/v3/diag/diag3_cw.py`. None changes a
decision of the candidate; the checks below show it on the candidate's boxes and on development rows.

**The frozen code stays the validated object.** The three validations ran at their approval commits (`8e589911`,
`35b344df`, `948b46b0`). `frozen/MANIFEST-V3.json` pins `diag3_cw.py` at
`1d68dc6b586c4928bdde098019a60eb57e3d84072643cd89b6ed92909be51fb3`, so `run_validation_v3.py` refuses to run on this
commit or any later one, as designed. To rerun a validation, check out its approval commit.

## The fixes

1. **Two docstrings.** `certified_max` said that finite terms give the strict bound "the same value as without it";
   with the underflow term the strict bound is larger by that term, up to rounding. `_underflow_term` said that the
   term "is exact"; that holds for the candidate's boxes only. Both now say what holds.
2. **An LP with no variables** is rejected by `_check_inputs` as our error (`ValueError`). Before, it passed the check
   and the solver's exception was counted as a failed attempt. F3's LP builders never build one.
3. **A solver answer without a multiplier field**, or a field without `marginals`, makes `_usable` return `False`, so
   the attempt fails like any other (`_marginals`). Before, `_usable` raised `AttributeError` and the run stopped.
   Whether scipy can return such an answer is still not known.
4. **The underflow term for any box.** The number of units 2^-1074 is now the exact ceiling of N (1 + 2 max|x|), in
   rational arithmetic, and the float returned is rounded up. The frozen code formed `N * (1.0 + 2.0 * xmax)` in
   binary64, exact for the candidate's boxes only: N = 10 with max|x| = 2^-54 gave 10 units where 11 are needed (review
   M3a), and a product that overflowed gave `inf` where a finite term exists. `inf` is now returned only for a
   max|x| that is not finite.
5. **The audit's guard.** F3a's statistic `max_coefficient_term_C` evaluates the loose bound under
   `np.errstate(all="ignore")`, as the strict bound already was. A statistic only; no decision uses it.

## Checks (Mac, the project environment: CPython 3.12.13, numpy 2.5.5, scipy 1.18.1)

- **Unit tests,** `tests/test_v3_postfreeze.py`, 7 tests, pass:
  - the term equals the frozen code's for max|x| in {2, 1, 0.5} (the candidate's boxes have max|x| = 2), N from 1
    to 14,795 in steps of 13; a separate sweep of every N from 1 to 14,795 at the same three values found no
    difference;
  - the counterexample: 10 units before, 11 now;
  - 2,000 random (N, max|x|) with max|x| from 1e-300 to 1e300: the term is at least its exact value;
  - an LP with no variables raises; answers with missing fields are not usable; a well-formed one is.
  - With max|x| = 0.002 the two differ (from N = 250): there the frozen evaluation was too small, another case of
    fix 4. No LP of the candidate has that largest box end.
- **The existing tests** `tests/test_v3_freeze.py` and `tests/test_v3_freeze2_scorer.py`: 20 pass.
- **Identity on development rows.** F3 online (`diag3_cw_dev.online("F3", zs, 256, 64)`) on six DEV rows, once with
  the code at `f2f9cacb` (frozen `diag3_cw.py`) and once with these fixes:
  430000 drift_0.001 E0 ramp, 430010 drift_0.0005 E0 ramp, 430007 drift_0.002 E1 rw, 430027 drift_0.002 E0 rw (all
  uniform noise), 430003 healthy E0 rw edge, 430019 jump_0.2 E1 ramp uniform.
  - Detections 849, 695, 673, 579, none, 383 in both.
  - Of the 203 recorded fields, only the five wall-clock fields (`step_ms` median, p95 and max, `fold_step_ms` median
    and max) differ; every other field (certificates, counters, fallbacks, evictions, kept measurements) is equal.
  - The script and its two outputs are not kept in the repository; the command is
    `python -B ident.py <code root>` with the six rows above, four workers.

## What this does not show

- The fixes are not validated on fresh seeds; the validated object is the frozen code.
- Fix 3 is not exercised by a real solver answer: none without the field has been seen.
