# AMBIENT: how the v3 trackers depend on the ambient assumptions (plan, 2026-11-21)

Status: written and committed before any run of it. DEV seeds only; a descriptive study (no pass or fail).

Author: Can Koç. Branch `sdts-v3/template-state`.

## 0. Why

An independent review of `df40c058` named the ambient box as a weak point: slow-drift detection leans on
TA ∈ [23, 27] °C (FREEZE-V2 section 1, DIAG-3 amendment 5), and a real plant can break the assumptions. Two
questions, on simulated data:
- **(a)** When the true ambient breaks (b) or (c), how often and how soon do the methods alarm on a healthy sensor?
  (Such an alarm is correct about the model, wrong about the sensor.)
- **(b)** If the assumed box is wider than the truth needs, how much later are faults detected?

## 1. (a) Broken assumptions, healthy sensor

Healthy runs, the methods with the frozen assumptions (box [23, 27], ρ_A = 0.002). Seeds 430000–430029 × E0, E1,
uniform noise (60 runs per scenario). The command and noise are `dev_scenarios`'; the ambient path is generated
here, from its own random stream (`{seed}:ambient-study:{scenario}`):
- **A0** control: the frozen law (random walk in [23, 27], rate ≤ ρ_A);
- **A1** box broken: random walk in [20, 30], rate ≤ ρ_A, starting uniform in [20, 30];
- **A2** rate broken ×2: random walk in [23, 27], steps uniform in [−2ρ_A, 2ρ_A];
- **A3** rate broken ×5: as A2 with ±5ρ_A;
- **A4** a step: the A0 path plus +1 °C from sample 1000 on (a door opened).

Methods: v2, cyl16p (freeze 1, as validated), F3 (freeze 3, as frozen). Reported per scenario and method: the share
of runs that alarm, the first alarm sample (median, min), and for A1 whether the true TA was outside [23, 27] at
the alarm.

## 2. (b) A wider assumed box, faults inside the frozen one

The 1320 DEV fault and healthy comparison rows (true ambient in [23, 27]). v2 and cyl16p with the assumed box
[23, 27] (frozen), [22, 28] and [21, 29]: for cyl16p the clamps and the start supports are recomputed for the wider
box (the directions, bases and pads are kept; the reachable-set part of the clamps does not depend on the box).
Reported: paired lag against the oracle's t\* of the frozen box, misses, detections per cell (drift cells
separately), alarms on admissible rows.

F3 is not run in (b): its box enters the window LP, the certificates and the a priori fallbacks in many places,
and a variant would be a new candidate. That it is left out is reported.

## 3. What this can show, and what it cannot

- **Can show:** how the frozen methods behave when the ambient assumptions are broken, and what a looser box costs
  v2 and cyl16p, on simulated DEV data.
- **Cannot show:** real ambient behaviour; F3 under a wider box; anything on validation data.
