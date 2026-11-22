# Record: the oracle and WM under a wider assumed box (WIDEBOX, 2026-11-22)

Plan `WIDEBOX-PLAN.md`, fixed at `a196fd68` before the run (approved 2026-11-22: Arch, 14 workers, after the baselines
block, [21, 29] first). A descriptive study on DEV seeds: no hypothesis, no pass or fail, nothing tuned.

## Provenance

- **Run:** `diag/widebox.py check`, `run` and `summary` on Arch from a clean clone at `a196fd68`
  (`~/Research/sdts-v3-wb-a196fd68`), 14 workers, `nice 19`, the venv of `0ce80072` (CPython 3.12.13, numpy 2.5.5,
  scipy 1.18.1, HiGHS 1.12.0). Check 05:41:08 to 05:47:46, run 05:47:47 to 09:07:10 (+0300); check, run and summary
  exited 0. A guard that stops the run if Tctl stays above 90 °C for 60 s was on from 05:41:07 to 09:07:12 and never
  fired. The same machine ran a sensor logger (sysfs, once a second, for a separate thermal study) throughout.
- **Outputs:** `results/v3/widebox-a196fd68/`: `meta.json`, `check.json`, `summary.json`, `split.json`,
  `rows-21-29.jsonl.gz`, `rows-22-28.jsonl.gz`, `rows-check-23-27.jsonl.gz` (one JSON line per row, sorted by key;
  sha256 of each plain file in `rows.sha256.json`), `run.sh`, `check.log`, `run.log`, `summary.log`, `guard.log`.
- **Mac copy:** all 138,277 files of the run, with the logs, were copied to the Mac and checked against a sha256
  manifest made on Arch (manifest sha256 `47b8c656…679c`). The oracle's solver attempts (260 MB, every attempt with its
  box) stay outside this repository with that manifest.
- `split.json` comes from `diag/widebox_split.py`, written after the run; it reads the stored rows only.

## Checks before the run (all passed)

- **Vertex check of Appendix A.5** (`diag/widebox_vertices.py`, rational arithmetic): at [23, 27], [22, 28] and
  [21, 29], 28 vertices of C and 14 of the cuts, 3,528 steps checked, no step above a clamp (largest step minus clamp
  0), both ends of the start segment in C. WM @ b therefore ran at both wider boxes.
- **IM and TS against part (b)** of `RECORD-2026-11-21-ambient.md`: equal on all 1,320 rows at all three boxes.
- **The frozen box through the same script** (48 rows): data, oracle t\* and status, IM and TS equal to the records;
  F3's detection and certificate equal to its DEV reference, largest certified-margin difference 0.0 m°C.

## The oracle at each box

1,081 events are certified at the frozen box. Data are generated with the true ambient in [23, 27]; only the assumed
box changes.

| box | events | frozen events no longer detected | t\* later | delay on the events kept (s) | own delay against the frozen t\* (s) | undetermined |
|---|---|---|---|---|---|---|
| [22, 28] | 1,056 | 26 | 55 | 59,625 | 78,477 | 48 of 80 edge rows, 0 uniform |
| [21, 29] | 1,032 | 49 | 32 | 40,830 | 106,732 | 48 of 80 edge rows, 0 uniform |

- The own delay counts an event no longer detected as N − t\* (N = 3,600). The delay on the events kept is smaller at
  [21, 29] because more of the late events are lost there.
- No t\* is earlier than at the frozen box, and every event of [21, 29] is an event of [22, 28] with a t\* no earlier
  (checked on all rows). The events lost are in drift 0.0005 and 0.001 °C/s; of the delay on the events kept, all but
  24 s is in the three slowest drift cells (the 24 s: two drift 0.005 events).
- One event of [22, 28] is not a frozen event: 430003 drift 0.001 E1 rw, undetermined at the frozen box, certified at
  [22, 28] with t\* = 2,971 (and certified consistent at [21, 29]).

## The monitors against the oracle of the same box

Paired set: the events IM @ b detects (1,050 at [22, 28], 1,026 at [21, 29]; 1,073 at the frozen box).

| monitor | box | paired lag (s) | D_paired | lag, all events (s) | misses | detections at t\*(b) |
|---|---|---|---|---|---|---|
| IM (v2) | [23, 27] | 32,925 | 0 | 44,363 | 8 | 805 |
| IM (v2) | [22, 28] | 36,793 | 0 | 48,179 | 6 | 789 |
| IM (v2) | [21, 29] | 36,605 | 0 | 47,991 | 6 | 783 |
| TS (cyl16p) | [23, 27] | 20,222 | 0.386 | 26,680 | 4 | 897 |
| TS (cyl16p) | [22, 28] | 24,112 | 0.345 | 30,518 | 2 | 866 |
| TS (cyl16p) | [21, 29] | 24,380 | 0.334 | 30,786 | 2 | 846 |
| WM (F3) | [23, 27] | 26 | 0.9992 | 26 | 0 | 1,079 |
| WM (F3) | [22, 28] | 26 | 0.9993 | 26 | 0 | 1,054 |
| WM (F3) | [21, 29] | 26 | 0.9993 | 26 | 0 | 1,030 |

- The frozen-box rows are computed by `widebox_split.py` from the same references as the check (dev rows, part (b),
  F3's DEV reference).
- WM's 26 s are the same two rows at every box: 430027 drift 0.0005 ramp, E0 and E1, t\* = 512, detected at 525.
- **Soundness:** no monitor alarmed on an admissible row (healthy, or certified consistent at that box) or before
  t\*(b), at either box. All of WM's alarms are certified (1,056 and 1,032).

## The split of part (b)'s lags (`split.json`)

Over the 1,081 frozen events: lag against the frozen t\* = the oracle's own delay at b + the monitor's lag against
t\*(b). The split is exact (asserted in the script).

| monitor | box | against the frozen t\* (s) | the assumption's own (s) | the monitor's (s) | assumption's share |
|---|---|---|---|---|---|
| IM | [22, 28] | 126,606 | 78,477 | 48,129 | 62 % |
| IM | [21, 29] | 154,723 | 106,732 | 47,991 | 69 % |
| TS | [22, 28] | 108,995 | 78,477 | 30,518 | 72 % |
| TS | [21, 29] | 137,518 | 106,732 | 30,786 | 78 % |
| WM | [22, 28] | 78,503 | 78,477 | 26 | 100 % |
| WM | [21, 29] | 106,758 | 106,732 | 26 | 100 % |

## WM's cost at the wider boxes

| box | median step (ms, median over runs) | longest fold (ms) | runs with a fold over 1 s | LPs | retries | fallbacks |
|---|---|---|---|---|---|---|
| [22, 28] | 14.9 | 691 | 0 | 7,912,814 | 69 | 0 |
| [21, 29] | 13.7 | 1,096 | 2 | 8,045,918 | 78 | 0 |

At most 65 measurements kept, 445 LP rows and 679 variables, as at the frozen box. Wall time with 14 workers on 8
cores (16 threads).

## OBSERVED

- Most of the lag that part (b) measured against the frozen t\* is the assumption's own cost: 62 to 69 % of IM's and
  72 to 78 % of TS's. Against the oracle of the same box, IM's lag over all events goes from 44,363 s to about
  48,000 s and TS's from 26,680 s to about 30,600 s.
- WM's lag against the oracle of the same box is 26 s at all three boxes, on the same two rows; its D_paired is 0.999
  at each. With a wider box WM loses what the exact detector loses, and nothing more.
- TS's D_paired against IM falls from 0.386 to 0.345 and 0.334: the gap between TS and IM shrinks a little (12,703 s
  of paired lag at the frozen box, 12,681 and 12,225 s at the wider boxes) while IM's own lag grows.
- The exact detector loses 26 and 49 of the 1,081 events and detects 55 and 32 others later, all in drift cells.

## What this does not show

- Anything on validation seeds, or on a second plant.
- A slow excursion of the true ambient out of the box (the true ambient stays in [23, 27]).
- That WM @ b is sound on fresh data: it is a DEV variant, covered by Theorem A.8 only through the vertex check above.
- How the box would be obtained for a real thermal set-up.
