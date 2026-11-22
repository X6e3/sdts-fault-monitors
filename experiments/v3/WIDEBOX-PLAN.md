# v3: the oracle and WM under a wider assumed box (WIDEBOX, plan of 2026-11-22)

**Status: fixed before the run.** This plan and its scripts (`diag/widebox.py`, `diag/widebox_oracle_worker.py`,
`diag/widebox_vertices.py`) are committed before any row of the run is computed. Only the tests below ran before.

## Why

`RECORD-2026-11-21-ambient.md` part (b) widened the assumed ambient box for IM (v2) and TS (cyl16p) only, and
measured their lag against the oracle's t\* **for the frozen box** [23, 27]. Two things were left open, and the
outside review of the preprint asked for both:

1. The oracle was not run with the wider boxes, so each lag mixes what a monitor discards with what the weaker
   assumption no longer gives. With t\* recomputed per box, the lag against the same box's oracle measures the first
   part alone, and t\*(box) − t\*(frozen) measures the second.
2. WM was not run with a wider box, so the share of its D_paired = 0.995 that comes from the box is not known.

A descriptive study on development seeds: no hypothesis, no pass or fail, nothing tuned. Every number is reported as
it comes out.

## Data

- The 1320 DEV comparison rows (seeds 430000–430029, 11 cells, arms E0 and E1, ambients rw and ramp, uniform noise)
  and the 80 healthy edge-noise rows (seeds 430070–430089), as in freeze 3's DEV checks.
- The data are generated as before, with the true ambient inside [23, 27]. Only the box the oracle and the monitors
  assume changes.
- No validation seed is read.

## What runs, per row and per assumed box b ∈ {[22, 28], [21, 29]}

| what | how |
|---|---|
| oracle | `thermal_oracle.first_inconsistent(z)` with the box set to b, in the parent and in each solver child; t\*(b) and its status (certified or undetermined) |
| IM @ b | v2 with box b, as `diag/ambient_study.py` part (b) |
| TS @ b | cyl16p with its clamps and start supports recomputed for b, as `ambient_study.py` part (b) |
| WM @ b | F3 (W = 256, K = 64) at the post-freeze code (`a04ec554`), with every box-dependent quantity rebuilt for b |

**WM @ b is a variant, not the validated object.** The box enters F3's LP bounds, its alarm test by the box alone,
the a priori fallbacks of the as-range and the base update, the clamps of its invariant set, the start supports and
the underflow term (general for any box since fix 4 of `RECORD-2026-11-22-postfreeze-fixes.md`).

**How the box is set.** Four modules bind the shifted box when imported (`template_state`, `diag1`, `diag3`,
`diag3_cw`); the generator, the oracle and v2 read `thermal.TA_LO` and `TA_HI` when called. `widebox.box(b)` sets
all of them and stops if any other module of `experiments/` holds a box of its own. The data are generated inside
`box([23, 27])`. The oracle solves each LP attempt in a fresh interpreter, which imports `thermal.py` again; the
script points that child at `diag/widebox_oracle_worker.py`, which takes the box from the parent and writes it next
to the attempt's result, and every attempt's box is checked. **Found in testing:** the first version of the script
left the child at the frozen box, so at a wider box the LP was solved at [23, 27] and the dual bound computed at b.
The bounds stayed valid but loose (430013 drift_0.002 E0 rw: undetermined at both wider boxes); with the worker the
same row is certified, with d\* − δ = 0.898 m°C at 499 samples against 3.882 m°C at the frozen box.

**The vertex check of Appendix A.5, as a script.** The check that the clamp set C is invariant under one step (every
vertex of C and of the two pieces cut by T_A = ±(hi − ρ), both ends of w, every direction, rational arithmetic) was
made in reviews and is not in this repository. `diag/widebox_vertices.py` does it, first at the frozen box, where it
must find the paper's 28 + 14 vertices and no step above a clamp, then at each b on the rebuilt clamps. If it finds a
step above a clamp at b, WM @ b is not run at that box and the record says so.

## Checks before the run (`widebox.py check`; `run` refuses without a passing one at the same commit)

- **The vertex check** at the three boxes: 28 + 14 vertices at [23, 27], no step above a clamp, both ends of the
  start segment in C.
- **IM and TS against part (b):** at all three boxes, on all 1320 rows, equal to the recorded `v2@…` and `cyl16p@…`
  of `results/v3/ambient/amb-443d8b30-mac/`.
- **The frozen box through the same script,** on the 48 rows with the smallest sha256 keys (the baselines' rule):
  - the data's sha256 equals the data generated without the script's box switch;
  - the oracle's t\* and status equal `results/v3/dev-45cff1d/rows.jsonl`, and IM and TS the recorded ones;
  - WM's detection and certificate equal F3's DEV reference (`results/v3/diag3/amend10-r1r2-0ce80072-arch/R-none`),
    the certified margin within 1e-3 m°C (`MARGIN_TOL_E`).

**Tests before the commit** (Mac, not results): the check with 4 and 40 rows, no difference (F3's certified margin
within 2.3e-13 m°C of the Arch reference); the run on 4 rows and on 430000 drift_0.0005 E0 ramp and 430013
drift_0.002 E0 rw at both wider boxes.

## Measures (per box)

- **The oracle:** certified events; events certified at the frozen box that are no longer detected within N; the
  assumption's own delay Σ (t\*(b) − t\*(frozen)) over the events certified at both; undetermined runs.
- **Each monitor**, against t\*(b): paired lag over the events IM @ b detects, D_paired against IM @ b, misses, detections at
  t\*(b), alarms on admissible rows, alarms before t\*(b). Admissible as in freeze 3: healthy rows, and fault rows the
  box-b oracle certifies consistent.
- **Against the frozen t\***, the same lags, so the table continues part (b)'s.
- **Per cell** for the three slowest drift cells (drift_0.0005, 0.001, 0.002), where part (b) found the whole change.
- **WM's cost:** median step, longest fold, LP size, kept measurements, fallbacks, and certificates of every alarm.

## Cost and where it runs

From validation 3's recorded times (wall clock, 14 workers on Arch): oracle 9.9 s per uniform run and 19 s per edge
run on average; F3 36 s and 167 s. Per box: 1320 × (10 + 36) s + 80 × (19 + 167) s ≈ 21 CPU-hours; both boxes about
42, and with a margin for later t\* and wider LP boxes about 60 CPU-hours. The checks add under one CPU-hour.

| option | machine | duration |
|---|---|---|
| both boxes | Arch, 14 workers, after the baselines block | about 3 to 4.5 h |
| [21, 29] only | Arch, 14 workers | about 1.5 to 2.5 h |
| both boxes | Mac, 8 workers, `nice 10` | about 5 to 8 h |

One machine for the whole run; Mac and Arch outputs are not mixed.

**Chosen:** both boxes on Arch, 14 workers, after the baselines block, [21, 29] first; from a clean clone at the
commit of this plan:

```
python -B experiments/v3/diag/widebox.py check OUT --workers 14
python -B experiments/v3/diag/widebox.py run OUT --workers 14
python -B experiments/v3/diag/widebox.py summary OUT
```

## What this will not show

- Anything on validation seeds, or on a second plant.
- A slow excursion of the true ambient out of the box (the true ambient stays in [23, 27]).
- That WM @ b is sound on fresh data: it is a DEV variant, and Theorem A.8 covers it only through the vertex check
  above.
- How the box would be obtained for a real thermal set-up.
