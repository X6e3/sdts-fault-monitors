# Record: J713 step test 3, the two-node model class on a real device (2026-11-23)

The verdict below is the frozen evaluation's verdict, as it came out (`PLAN-step3.md` section 4, `eval_step3.py`).
Nothing was rerun, refitted with other settings or rescored.

**Verdict: PASS.** With its rate parameters fitted on step1 and frozen, the two-node model predicted the palm-rest
sensor Ts0P on the fresh run with rms 0.081 °C and largest absolute error 0.205 °C (criterion: rms ≤ 0.25 °C and
largest error ≤ 0.60 °C).

## Provenance

- Plan `PLAN-step3.md`; freeze manifest `PLAN-step3-manifest.txt` (sha256 d84cacf4…), stamped with OpenTimestamps at
  11:59 +0300 before any step3 data existed; addenda 1 (Can's conditions and data release), 2 (the transistor record)
  and 3 (channel identification), each stamped before use.
- Before the evaluation every file of the manifest was checked against it: all equal.
- Run: `run_step3.sh step3`, started detached at 12:01:50 +0300 (`idle0_start`), ended 13:06:58 (`end`); 3,900 samples
  (the plan's infrastructure limit is 3,800); phases idle 600 s, 6 threads 900 s, 1 thread 900 s, idle 1500 s; the
  TB0T guard did not fire (largest TB0T 31.7 °C). On AC power, battery 100 % and charged, at start and end.
- Evaluation: `eval_step3.py step1 step3`, run once, 13:07:18–13:07:23 +0300, with CPython 3.12.13, numpy 2.5.5,
  scipy 1.18.1 (the SDTS repository's virtual environment). Exit 0, nothing on stderr.

```
a9159b62314fe447b8cd2184519ced79ebe5853f9eb5ae9f90328bef778fa574  step3/log.csv
f02f48bbbd1467b7600427ed38b94cb086ac13e45accfdd18d0389d37a2322d4  step3/phases.csv
9fd757c2b7499ec4bbf3a03cb25b2d09a454412d274d9ca139a88a5f0f5c61ef  step3/machine.txt
00ef0d4b4a8ecbf186d6a2e750eb330ba4dd4448c453c4a1e5a1a746233d3c51  step3-eval.json
```

## Result

| sensor | rms (°C) | 99th percentile (°C) | largest error (°C) | refitted TA (°C) | refitted c0 | samples |
|---|---|---|---|---|---|---|
| **Ts0P (criterion)** | **0.081** | **0.186** | **0.205** | 23.08 | 52.52 | 3,900 |
| Ts1P (reported) | 0.101 | 0.236 | 0.319 | 21.92 | 66.55 | 3,900 |

- Ts0P ranged from 25.44 to 29.69 °C (4.25 °C); the measured power PSTR from 5.0 to 33.9 W.
- By phase (PSTR mean; Ts0P at the start and end of the phase): idle 7.0 W, 25.44 → 25.69 °C; 6 threads 22.1 W,
  25.69 → 29.44 °C; 1 thread 13.1 W, 29.44 → 29.06 °C; cooling 5.6 W, 29.00 → 26.06 °C.
- **The error bound the model needs on this device** (addendum 1, item 3): 0.205 °C for Ts0P and 0.319 °C for Ts1P
  over this run. The paper's δ = 0.3 °C bounds measurement noise only; this bound holds the model's error, the
  sensor's quantization and noise, and the ambient's departure from a constant, so the two are compared, not equated.
  For Ts0P it is below 0.3 °C on this run; for Ts1P it is above.
- Development, for contrast (not part of the verdict): the same evaluation from step1 to step2 gave rms 0.160 °C and
  largest error 0.347 °C. Step2 drove the machine harder (10 threads, up to 39.0 W against step1's 25.9 W); step3's
  largest power, 33.9 W, is also above step1's.

## The transistor record (descriptive, addenda 2 and 3; not part of the verdict)

`step3-arch/transistors-step3-partial.csv` (copied from Arch at 13:08, sha256 33566bcf…; the logger was still running):
3,808 samples inside the run, the first 105 s after `idle0_start`. Raw readings, not calibrated:

| phase | a0, under the MacBook (mean raw) | a1, room (mean raw) |
|---|---|---|
| idle | 154,777 | 150,876 |
| 6 threads | 154,600 | 150,896 |
| 1 thread | 154,554 | 150,830 |
| cooling | 154,561 | 150,761 |

a0 moved by about 220 raw units between the idle and loaded phases; a1's phase means stayed within about 135 raw
units. Without a calibration neither the scale nor the sign of these units in °C is established here.

## What this shows, and what it does not

- It shows that the paper's model class, a hidden core heated by a known input, a measured surface node and an
  unknown ambient taken as a constant, predicted a real fanless device's surface sensor on a run it had not seen, with
  a different load profile, within 0.21 °C (Ts0P) and 0.32 °C (Ts1P).
- It does not test the monitors on real data, does not use the paper's parameter values (this device's are fitted),
  does not acquire an ambient box, and covers one device, one placement and one session. Two of the six parameters
  (TA, c0) were refitted on the validation run itself, as the plan states.
