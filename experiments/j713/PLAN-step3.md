# J713 step test 3: does the paper's two-node model class describe a real device's surface sensor?

Status: proposed 2026-11-23; criterion approved by Can Koç on 2026-11-23. Frozen when the manifest below is stamped
(OpenTimestamps) and before any step3 data exist. Any later change is a new version with its stated reason.

## 0. Question

Control Engineering Practice asks that a simulation-only study show that its simulation model is representative of a
genuine application. The paper's plant is a two-node thermal model: a hidden core heated by a known input, a measured
surface node, an unknown ambient. This study asks one narrow question: with its rate parameters fitted on earlier runs
and then frozen, does that model class predict the surface sensor of a real fanless device on a fresh run, and what
noise bound would a monitor need on that device?

It does not test the monitors on real data, does not identify the paper's parameter values (the simulated plant's
parameters are not this device's), and does not acquire an ambient box. Those belong to paper 2.

## 1. Device, signals, model

- Device: J713, MacBook Air M4 (Mac16,12), macOS 27.0, fanless; on AC power, battery at 100 % and charged.
- Logger: `thermlog` (source `thermlog.c`), read-only, 1 Hz, every HID temperature sensor and every SMC `flt ` T/P key.
- Input P: SMC key PSTR (measured power, W). Sensor s: SMC key Ts0P (palm rest); Ts1P reported as a second sensor.
- Model (`analyze.py`, `simulate`), 1 s steps:
  `c[k+1] = c[k] + kc (s[k] - c[k]) + bc P[k]`, `s[k+1] = s[k] + ks (c[k] - s[k]) + hs (TA - s[k])`,
  core c not measured, TA a constant.
- Fit (`analyze.py`, `fit`): output error on s by open-loop simulation from the first sample, all six of
  (kc, bc, ks, hs, TA, c0) fitted with bounds.

## 2. Development data (already recorded and looked at)

- step1, 2026-11-22: idle 600 s, 2 threads 1200 s, 4 threads 900 s, idle (cut short; 3,131 samples).
  Own fit on Ts0P: rms 0.077 °C, largest error 0.191 °C.
- step2, 2026-11-22: idle 300 s, 10 threads 1200 s, idle 1800 s (3,360 samples). Its own fit and a cross-prediction
  were looked at in the working session of 2026-11-22; the output was not saved.
- Rehearsal of this plan's evaluation on development data (2026-11-23, `dev-rehearsal-step1-step2.json`): rate
  parameters fitted on step1, only TA and c0 refitted on step2. Ts0P: rms 0.160 °C, 99th percentile 0.316 °C, largest
  error 0.347 °C; Ts0P moved by 4.44 °C during step2. Under the criterion of section 4 this rehearsal passes. The
  criterion was chosen after this rehearsal, on development data only.

## 3. Validation run (step3)

- `run_step3.sh step3`, recorded only after the freeze: idle 600 s, 6 threads 900 s, 1 thread 900 s, idle 1500 s
  (3,900 s). This load profile was not used in step1 or step2.
- Guard: if the battery hotspot TB0T exceeds 40 °C, the load stops (phase `guard_stop`) and the idle phase begins.
  A guard stop does not invalidate the run; it is evaluated as recorded.
- Conditions: on AC, lid open, same place on the desk, no other heavy work on the machine during the run. The room's
  temperature is not controlled; it is the unknown ambient of the model.
- Infrastructure failure: the logger records fewer than 3,800 samples, the machine sleeps, or AC power is lost. Then
  one new recording is allowed, in a new directory, with the failure recorded. Nothing else allows a rerun.

## 4. Evaluation and criterion (fixed)

`eval_step3.py step1 step3`, run once:
- The rate parameters (kc, bc, ks, hs) are fitted on step1 and frozen; on step3 only TA and c0 are refitted.
- Primary reported quantity: the largest absolute error of Ts0P on step3, "the noise bound this device would need".
- **PASS** if, for Ts0P, rms ≤ 0.25 °C **and** largest absolute error ≤ 0.60 °C. Otherwise **FAIL**.
- Reported either way: rms, 99th percentile and largest error for Ts0P and Ts1P, the refitted TA and c0, the Ts0P
  range, and the comparison with the paper's δ = 0.3 °C.
- The verdict is reported as it comes, in a dated record. A FAIL is published too; then the paper does not claim that
  the model class represents this device.

## 5. Data release (to be decided by Can)

Proposed: the columns used (time, PSTR, Ts0P, Ts1P, TB0T) of step1, step2 and step3, with the phases files, under
CC BY 4.0, in the SDTS repository with this plan and the scripts. The other sensor columns stay private.

## 6. Manifest (sha256, at proposal)

```
327c1760de7f877f6b07dbd2a056a3de18b87cd2a9ab2c6c11ed61c3b24d8830  analyze.py
487616eab98a6345921f1ca1469ef3a22f37cfe89d300a2ec283df3a8bfa2065  eval_step3.py
f8057c12f3cafd8000495f71f3b0cb7720eb9e1b13dfde58543dad8e6bd266b2  run_step3.sh
a0e71cbd5fd57e0601bb883c15bb07296ccafba2584eeb5bc570db6c68ccf420  thermlog.c
65d5942ca5275c9aa7b992db9ca967f40ad397e14bac562d0e90e76935b0c06c  thermlog
5c28961ccfc02a05b8a812623b40246287d806b6582636b400929b026e5e2e4c  step1/log.csv
a1976262fe1de8c7598200ebd69c8b0175b6d5bd04d37b8e63a68a328ea1c453  step1/phases.csv
4a678f3a895f488c2b999ef183fb7c5758da1ac0b0bc3f7d718d7fd3ccd34156  step2/log.csv
39f2a49f107fac559c2c6b05c9cc36ca76ca5af2b04ac7fc55abab8bd5f4ec8c  step2/phases.csv
```

The freeze manifest (`PLAN-step3-manifest.txt`) adds this file's own sha256 and is the file that is stamped.
