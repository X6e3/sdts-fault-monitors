# Record: how the v3 trackers depend on the ambient assumptions (AMBIENT, 2026-11-21)

Plan `AMBIENT-PLAN.md`, committed with its script before any run (`443d8b30`). DEV seeds only; a descriptive study
with no pass or fail. Nothing below was rerun or retuned.

## Provenance

- **Run:** on the Mac (Apple M4, 8 workers, `nice 10`, `caffeinate`), from a clean worktree at `443d8b30`
  (`~/Downloads/sdts-runs/v3-amb-mac-443d8b30`), the project's Python environment (CPython 3.12.13, numpy 2.5.5,
  scipy 1.18.1). First result 15:59, part (a) done 17:08, part (b) and the summary done 17:11 (+0300). Every step
  exited 0.
- **Outputs:** `results/v3/ambient/amb-443d8b30-mac/`: 300 part-(a) files, 1320 part-(b) files, `summary.json`
  (the plan's script) and the logs (`a.log`, `b.log`, `summary.log`).
- **Report:** `report.json`, from `diag/ambient_report.py` (`a5dccc14`). It was written after the run and committed
  before it was run, for the items the plan lists that `summary` does not compute: whether TA had left the box at
  an A1 alarm, F3's certificates, the A4 delays, and the per-cell figures of part (b). It reads the run's files only.
- F3's 300 runs of part (a) took 34,071 s of CPU in all, at most 185.6 s for one run.

## (a) Broken assumptions, healthy sensor

Healthy runs, the frozen assumptions (box [23, 27] °C, ρ_A = 0.002 °C/s); 30 DEV seeds × 2 arms per scenario.

| scenario | what is broken | v2 alarms | cyl16p alarms | F3 alarms | first alarm |
|---|---|---|---|---|---|
| A0 control | nothing | 0 / 60 | 0 / 60 | 0 / 60 | — |
| A1 box [20, 30] | (c) | 42 / 60 | 42 / 60 | 42 / 60, all certified | 0 to 3 samples after TA left the box |
| A2 rate ×2 | (b) | 0 / 60 | 0 / 60 | 0 / 60 | — |
| A3 rate ×5 | (b) | 0 / 60 | 0 / 60 | **4 / 60**, all certified | 482 (430015, both arms), 3111 (430012, both arms) |
| A4 +1 °C step at sample 1000 | (b) | 60 / 60 | 60 / 60 | 60 / 60, all certified | 1 to 10 samples after the step |

**OBSERVED:**
- **A1.** All three methods alarm on the same 42 runs, and these are exactly the runs whose TA ever left [23, 27].
  Every alarm comes at or after that sample. In all 42 the path *starts* outside the box (start uniform in [20, 30]);
  no path that started inside left it, since a random walk at rate ≤ ρ_A moves little in 3600 samples. So A1 tested
  a start outside the box, not a slow excursion out of it. The latter is not covered by this study.
- **A2.** Twice the rate bound gives no alarm on any run for any method.
- **A3.** Five times the rate bound: v2 and cyl16p never alarm; F3 alarms on two seeds, in both arms at the same
  sample (the arms share the ambient path and the noise, and z removes the command). F3's alarms are certified: on
  these records the model with ρ_A = 0.002 is provably violated, and only the method with the most information
  proves it.
- **A4.** A 1 °C step breaks the rate bound 500-fold at one sample; every method alarms on every run within 1 to 10
  samples.
- No alarm in A0, as on every admissible DEV run before.

Each of these alarms is correct about the model and wrong about the sensor: the sensor is healthy in every run of
part (a).

## (b) A wider assumed box, faults inside the frozen one

The 1320 DEV comparison rows (true TA in [23, 27]); 1081 certified detection events; lag measured against the
oracle's t\* **for the frozen box**. v2 at the frozen box equals the recorded v2 on all 1320 rows (identity check).

| method @ assumed box | lag, all events (s) | lag, drift cells (s) | misses | detections at t\* | alarms on admissible rows |
|---|---|---|---|---|---|
| v2 @ [23, 27] | 44,363 | 38,070 | 8 | 805 | 0 |
| v2 @ [22, 28] | 126,606 | 120,313 | 32 | 767 | 0 |
| v2 @ [21, 29] | 154,723 | 148,430 | 55 | 767 | 0 |
| cyl16p @ [23, 27] | 26,680 | 20,404 | 4 | 897 | 0 |
| cyl16p @ [22, 28] | 108,995 | 102,719 | 28 | 824 | 0 |
| cyl16p @ [21, 29] | 137,518 | 131,242 | 51 | 824 | 0 |

**Per cell** (lag in s / misses; cells not listed have the same figures at every box):

| cell (events) | v2 @ 23–27 | v2 @ 22–28 | v2 @ 21–29 | cyl16p @ 23–27 | cyl16p @ 22–28 | cyl16p @ 21–29 |
|---|---|---|---|---|---|---|
| drift_0.0005 (78) | 14,632 / 6 | 54,706 / 14 | 61,624 / 28 | 7,598 / 2 | 47,900 / 10 | 54,832 / 24 |
| drift_0.001 (103) | 8,134 / 0 | 45,501 / 16 | 66,382 / 25 | 5,574 / 0 | 42,941 / 16 | 64,128 / 25 |
| drift_0.002 (120) | 14,424 / 0 | 19,226 / 0 | 19,544 / 0 | 6,894 / 0 | 11,540 / 0 | 11,944 / 0 |

Unchanged at every box: drift_0.005 (v2 840 s, cyl16p 322 s), drift_0.02 (40, 16), jump_0.2 (6,288 / 2 misses,
6,272 / 2), noise_x2 (4, 4), stuck (1, 0), gain_0.01 and jump_0.5 (0, 0).

**OBSERVED:**
- Widening the box by 1 °C on each side nearly triples v2's lag and multiplies cyl16p's by four; by 2 °C, 3.5 and
  5.2 times. Misses go from 8 to 32 to 55 (v2) and from 4 to 28 to 51 (cyl16p).
- The whole increase is in the three slowest drift cells. The faster faults do not depend on the box.
- cyl16p's lag stays below v2's by about the same number of seconds at every box (17,683, 17,611 and 17,205 s); as
  a share of v2's lag its gain falls from 40 % to 14 % and 11 %.
- No method alarms earlier than t\* or on an admissible row, and cyl16p is never later than v2, at any box. A wider
  box is a weaker assumption, so this is expected (Theorems 2 and 3 hold for any box).

**What the lag here mixes:** t\* is the oracle's for the frozen box. With a wider box the exact detector itself is
later, so these lags combine the information a method discards with the information the weaker assumption no
longer gives. The wider-box oracle was not computed, so the two parts are not separated.

**F3 is not in part (b),** as the plan says: its box enters the window LP, its certificates and its a priori
fallbacks, and a variant would be a new candidate.

## What this shows, and what it does not

- **Shows** (simulated DEV data): slow-drift detection by v2 and cyl16p depends strongly on how tight the assumed
  ambient box is, and faster faults do not. Broken assumptions cause alarms on a healthy sensor when the break is
  large (a start outside the box, a 1 °C step, five times the rate bound for F3 on 2 of 30 paths); twice the rate
  bound caused none.
- **Does not show:** real ambient behaviour; a slow excursion out of the box; F3 under a wider box; the wider-box
  oracle; anything on validation seeds.
