# J713 monitor pilot, development data only (2026-11-24)

Purpose: decide whether a preregistered test of the paper's monitors on a real device's record is worth planning. Not
a test: only the development runs step 1 and step 2 were read; step 3 (the model-fit test run) was not. The result is
kept for the second paper; the first paper does not use it (decision of 2026-11-24: no new experiments in paper 1).

Script: `pilot_monitors.py` (sha256 46fc0043...), run as committed with this note; outputs in
`results/j713/pilot-dev-2026-11-24/`. Margin check of the +0.5 jump: `pilot_jump_margin.py`.

Setup. The J713 two-node model with the four rates frozen from step 1 (`step3-eval.json`, Ts0P), mapped onto
`experiments/generators/thermal.py` in the process before import; no frozen file changed. Input P = PSTR, output
Ts0P. The oracle's LPs are solved in-process (the frozen oracle solves each in a fresh interpreter, which would rebuild
the simulated plant). TS is the cyl16 family (42 directions, N = 4, L = 16) rebuilt for this plant with its full basis
tables and start supports computed for the box; WM is F3 (W = 256, B = 16, K = 64) on that template. Start: steady
state of the mean P of the first 60 s (the first sample instead changes d* by under 0.02 degC).

## Healthy records: the smallest noise bound d* (oracle, box 19-25 degC)

| rho (degC/sample) | step 1 | step 2 |
|---|---|---|
| 0.0002 | 0.461 | 0.357 |
| 0.0005 | 0.398 | 0.330 |
| 0.001 | 0.292 | 0.285 |
| 0.002 | 0.144 | 0.202 |

With the paper's own delta = 0.3 and rho = 0.002 both development records are consistent. A smaller rho needs a larger
delta: T_A here also absorbs the model's error.

## Injected faults on step 2 (delta 0.3, rho 0.002, box 19-25), onsets 200 (idle), 900 (10 threads), 2200 (cooling)

39 runs: per onset the healthy record and 12 additive faults (drifts of 0.0005, 0.001, 0.002, 0.005 degC/s and jumps of
0.5 and 1.0 degC, both signs). Every oracle verdict was certified; no monitor alarmed on a run the oracle certified
consistent; every WM alarm was certified. WM took 1 to 90 s per run of 3,360 samples.

21 certified events. Lag against t*, a miss counted as 3,360 - t*: IM 11,380 s (2 misses), TS 2,856 s (1 miss),
WM 2,852 s (1 miss), so TS and WM remove about 75 % of IM's lag on these runs.

Observations:
- Drifts at or below rho (0.0005 both signs, +0.001 at every onset; more at onset 2200) were consistent for the oracle
  over the whole record: Proposition 2's twin on a real record.
- WM detected within 4 s of TS on every event: on this plant (time constants about 350 and 630 samples) the window of
  256 samples gave no gain over the template. Not examined further.
- Onset 200 (idle): TS and WM at t* on every drift event (lag 0 or 1 s), IM 72 to 1,723 s later.
- Jump +0.5 at 900: t* = 900, missed by all three. The jump raises d* from 0.2016 to 0.3003 degC, 0.3 mdegC above
  delta; a jump of 0.4 gives 0.2695 (consistent). A boundary case, not a large loss of information.
- Jump -0.5 at 200: t* = 200; TS and WM at t*, IM missed.

## What this does and does not show

It shows that the oracle and the three monitors run on the device's record and model without redesign, and that on
the two development records the paper's delta and rho hold. It does not show soundness on a fresh record (delta and rho
were not fixed before these records were seen), it injects faults into one record only, and the healthy record is
the same in the three onset groups. A test would need delta, rho, the box, the start rule and the fault set fixed
before a fresh run, as in PLAN-step3.
