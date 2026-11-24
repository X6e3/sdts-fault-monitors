# Oracle margins at t*: the bridge from the binary64 LP to the exact model (descriptive, 2026-11-23)

Status: approved by Can Koç on 2026-11-23, before the run. Descriptive: no hypothesis, no
pass or fail, no verdict of any validation changes.

## Question

The oracle decides prefixes with an LP built on the binary64 matrix (rows summing to 1 + 2^-56 and 1 + 3·2^-56); the
paper's exact model takes the simulator's parameters as exact rationals. For every admissible ambient path the two
give values of a_s within 5.0e-13 °C over 3,600 steps (checked in exact rational arithmetic; Appendix, Corollary on
WM). So the smallest explaining noise bound d* of the two models differs by at most that much, and the oracle's t*
is also the exact model's t* on every event where

- the consistent side holds with room: δ − d_up(z[0:t*]) > 5.0e-13 °C, and
- the inconsistent side holds with room: d_lo(z[0:t*+1]) − δ > 5.0e-13 °C,

with d_up and d_lo the oracle's own certified bounds. The rows of validation 3 keep t* and its status, not these
bounds. The review of 2026-11-23 (r2) asked for the bridge on the inconsistent side; this check measures both.

## Method

`diag/oracle_margin_check.py`, modelled on `diag/eta_check.py` (which did the same for 12 events): for every fault
run of validation 3 (`results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl`) whose oracle status is
certified, regenerate the run (`dev_scenarios.run`, the validation block unlocked with the approved manifest's
sha256, as the runner and eta_check do) and call `thermal_oracle.margin` at m = t* and m = t* + 1; for a certified
consistent fault run (t* none) call it at m = N. The oracle code is the frozen code at the commit of this plan.

## Reported

Per event: δ − d_up at t*, d_lo − δ at t* + 1 (or δ − d_up at N); the smallest of each over all events; the number
of events below 5.0e-13 °C, below 1e-9 °C (η) and below 1e-6 °C; any event whose recomputed verdict differs from the
recorded status (that would be a reproducibility finding and is reported, not fixed).
