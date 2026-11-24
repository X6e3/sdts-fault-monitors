# J713 thermal step tests: released columns (CC BY 4.0)

Three runs on one laptop, a fanless MacBook Air with an Apple M4 (model identifier Mac16,12; Apple's board name J713),
under macOS 27.0, on mains power with the battery full. They test whether the paper's two-node model class describes
a real device's surface sensor; they are not fault-detection data. Plan, record and scripts: `experiments/j713/`.

| file | run | samples | load profile |
|---|---|---|---|
| `step1.csv`, `step1-phases.csv` | development, 2026-11-22 | 3,131 | idle, 2 threads, 4 threads, idle (cut short) |
| `step2.csv`, `step2-phases.csv` | development, 2026-11-22 | 3,360 | idle, 10 threads, idle |
| `step3.csv`, `step3-phases.csv` | test run of `PLAN-step3.md`, 2026-11-23 | 3,900 | idle 600 s, 6 threads 900 s, 1 thread 900 s, idle 1,500 s |

## Columns of `stepN.csv`

| column | unit | meaning |
|---|---|---|
| `t_mono` | s | time since the logger's first sample (monotonic clock); samples about 1 s apart (largest gap 1.010 s) |
| `t_unix` | s | Unix time of the sample (UTC), the clock of the phases files |
| `PSTR` | W | measured system power, SMC key `PSTR`; the model's input P |
| `Ts0P` | °C | palm-rest temperature sensor, SMC key `Ts0P`; the model's output s and the sensor of the criterion; reported in steps of 1/16 °C |
| `Ts1P` | °C | a second surface temperature sensor, SMC key `Ts1P`; reported beside Ts0P, in steps of 1/16 °C |
| `TB0T` | °C | battery temperature, SMC key `TB0T`; used only by the run's guard (load stops above 40 °C; it never did), in steps of 0.1 °C |

Values are as the logger (`experiments/j713/thermlog.c`, read-only, 1 Hz) wrote them; no row was dropped or edited
(every row of the logs is complete).

## Columns of `stepN-phases.csv`

`phase`, `t_unix` (s): the Unix time at which each phase of the run script began (`idle0_start`, `load2_start`,
`load6_start`, …, `idle_cool_start`, `end`). Step 1 has no `end` line: its last phase was cut short.

## Provenance

These are the columns `t_mono`, `t_unix`, `smc:PSTR`, `smc:Ts0P`, `smc:Ts1P` and `smc:TB0T` of the full logs, renamed
without the `smc:` prefix. The full logs also hold the device's other temperature and power sensors, which are not
released (PLAN-step3 addendum 1). Their sha256 are in `experiments/j713/PLAN-step3-manifest.txt` (step 1 and 2) and
`RESULT-step3-manifest.txt` (step 3), both stamped with OpenTimestamps (`*.ots`).

## Reproducing the result

```
python3 -I -B experiments/j713/reproduce_step3.py
```

fits the model on step 1, freezes its four rate parameters, refits only the ambient TA and the initial core state c0
on step 3, and compares the result with the frozen evaluation's output `experiments/j713/step3-eval.json` (numpy and
scipy as in the repository's environment). The core is not measured, so the six fitted quantities are identifiable
only up to a one-parameter family that leaves TA and the fitted Ts0P unchanged; the individual rates and c0 depend on
where the optimizer stops, which differs slightly between platforms. The script therefore checks TA, the residual
statistics and the invariants of the step-1 fit (within 1e-4 degC and 1e-3 relative), and also refits step 3 with the
frozen step-1 rates of `step3-eval.json`. With `--figdata FILE` it also writes the measured and fitted Ts0P of step 3
and their difference.

License: CC BY 4.0. Cite the paper and this repository.
