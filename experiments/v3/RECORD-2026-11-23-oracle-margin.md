# Record: the oracle's margins at t*, validation 3 (2026-11-23)

Plan `ORACLE-MARGIN-PLAN.md` (committed at e2772d92 before the run; descriptive, no pass or fail).

## Provenance

- Run on Arch from a clone at c8c4971c (`~/Research/sdts-v3-c8c4971c`, CPython 3.12.13, numpy 2.5.5, scipy 1.18.1),
  `experiments/v3/diag/oracle_margin_check.py`, 14 workers, nice 19; started 2026-11-23 14:08 +0300, last row written
  14:33:37. Exit with the summary below; no exception.
- Outputs, copied to `results/v3/oracle-margin-c8c4971c/` and checked against Arch:

```
5dc9dc2d98d7543d9b465334cf66135bc1881b011bca49dce0666502b780afe3  margins.jsonl
dfb1fb7c97863a085fa1ac74a9a7470c81eddcd0bba59bc48e6bb34142cdb387  run.log
```

## Result

All 7,997 certified fault runs of validation 3: 7,255 with a certified t* and 742 certified consistent.

| side | runs | smallest room (°C) | ≤ 5.0e-13 | ≤ 1e-9 | ≤ 1e-6 |
|---|---|---|---|---|---|
| consistent: δ − d_up at z[0:t*], or at z[0:N] | 7,997 | 2.90e-6 (440506 drift_0.0005 E1 ramp, t* 3433) | 0 | 0 | 0 |
| inconsistent: d_lo − δ at z[0:t*+1] | 7,255 | 1.07e-7 (440402 drift_0.0005 E0/E1 ramp, t* 1414) | 0 | 0 | 2 |

- No recomputed verdict differs from the recorded status (`verdict_changed` empty).
- The two smallest inconsistent rooms are the events eta_check.py had measured (1.06e-7 there).
- Total oracle time 20,966 s over the runs (largest single run 71.3 s).

## What this settles

The binary64 LP and the exact model give values of a_s within 5.0e-13 °C over 3,600 steps for every admissible
ambient path, so their smallest explaining noise bounds differ by at most that much. Every certified event has at
least 1.07e-7 °C of room on its inconsistent side and at least 2.90e-6 °C on its consistent side, more than 2×10^5
times the gap: on validation 3 the oracle's certified t* is the exact model's t*, and the 742 certified-consistent fault
runs are consistent under the exact model. The rooms are the oracle's own certified bounds; their own floating-point
error (r3 asks for an underflow term in `_dual_bound`) is of order 1e-14 °C, far below the smallest room.

Not covered here: the healthy runs (judged admissible by construction, not by the oracle) and validations 1 and 2.
