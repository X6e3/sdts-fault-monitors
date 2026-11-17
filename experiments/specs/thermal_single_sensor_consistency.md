# Experiment — what a single temperature sensor can certify about itself

Status: frozen protocol v1 (preregistration), 2026-11-17. The assumption values (eps_A, rho_A, delta) and
the requirement levels R = 1 °C and 3 °C were confirmed by the author before commit. No method has been
implemented or run against this protocol. Any later change is a new version with its own commit and a stated
reason; it never follows a look at FINAL data.
Simulation only. Timebox: 3 weeks from the start of implementation.

## 0. Position

This experiment sits outside the C0–C5 ladder of `docs/RESEARCH_CHARTER.md`. It uses an explicit physical
model and a known actuator command, so its results are not claims about a model-free temporal state `S_t`.

It asks a narrower question that the earlier work never isolated. With one sensor, the plant model and the
known command, which properties of that sensor can be certified from its history, and which can not be
certified at all? It also asks whether an own-history temporal state, using no model, adds anything there.

Related known fields: analytical redundancy, set-membership and interval observers, diagnosability and
active fault diagnosis. This protocol does not claim novelty over them.

## 1. Plant (data-generating process)

The two-node thermal plant of `sdts_thermal_microtest` (2026-10-23), taken as exact in discrete time
(Euler, `DT = 1 s`). The discrete equations are the plant; there is no discretization mismatch.

```text
Tc[k+1] = Tc[k] + DT * (P[k] - K*(Tc[k] - Ts[k])) / CC
Ts[k+1] = Ts[k] + DT * (K*(Tc[k] - Ts[k]) - H*(Ts[k] - TA[k])) / CS
y[k]    = Ts[k] + f_k(Ts) + v[k]        (sensor; f is the fault, zero when healthy)
```

Parameters: `CC = 30`, `CS = 12`, `K = 2`, `H = 0.8`, nominal ambient 25 °C, `P` in [0, 42] W.

- **Known command:** `P[k]` is the controller's own command and is known to every method (primary arm).
- **Ambient `TA[k]`:** unknown to every method. Admissible set: `|TA - 25| <= eps_A = 2 °C` and
  `|TA[k+1] - TA[k]| <= rho_A = 0.002 °C/s`. Healthy runs draw TA as a bounded random walk inside this set.
- **Noise:** primary arm `v` uniform in `[-delta, +delta]`, `delta = 0.3 °C` (bounded, so soundness is
  testable). Secondary arm: Gaussian `sigma = 0.1 °C`, with methods told `delta = 5*sigma`.
- **Initial state:** steady state for `P = 20` and the run's initial TA, known to methods within ±1 °C per state.
- **Excitation arms:**
  - **E1:** P piecewise constant, redrawn uniformly in [0, 42] every 15 s.
  - **E0:** P constant at 20 W.
- **Run:** 3600 samples. Fault onset `t_f` uniform in [300, 600]. Samples before 300 are warm-up for every
  method and are excluded from all counts.

## 2. Algebra done before any method (computed 2026-11-17, pure Python)

| Quantity | Value |
|---|---|
| Discrete eigenvalues | 0.98437 and 0.71563, i.e. time constants 63.5 and 3.0 steps (continuous: 64.0 s and 3.52 s) |
| Steady state | `Ts = TA + P/H`, `Tc = Ts + P/K`; for P = 20: Ts 50, Tc 60 |
| Shift invariance | shifting Tc, Ts and TA by the same Δ shifts the next state by exactly Δ (residual 3e-15) |
| TA→Ts impulse response | nonnegative, sum 1.000000 (a convex filter of TA) |
| TA→Ts ramp lag | 52.5 s |
| Max \|ΔTs\| per step under E1 | 0.551 °C |
| Initial-state error to Ts | worst-case gain per unit box: 1.0 at k=0, 0.30 at k=64, 0.035 at k=200, 0.007 at k=300 |

Consequences:

- **W1. A constant sensor offset is exactly an ambient offset.**
  - By shift invariance, `y = Ts + b + v` with ambient TA is the same signal as a healthy sensor with
    ambient `TA + b` and initial state shifted by b.
  - So an offset `|b|` is indistinguishable whenever `TA + b` is admissible, in both excitation arms.
  - No method can certify the sensor's absolute offset more tightly than the ambient uncertainty.
    This is predicted and is not tuned away.
- **W2. Stuck sensor under E0.**
  - At steady state with constant P, a sensor stuck at its current value (noise kept) gives the same
    signal as a healthy sensor. It is indistinguishable under E0.
  - Under E1 the model predicts movements of tens of degrees, so it must become detectable.
- **Envelope soundness.**
  - Because the TA→Ts response is nonnegative with gain 1, any admissible TA path keeps the
    ambient-driven part of Ts inside [23, 27] (plus the decaying initial-state term).
  - A long-horizon envelope check on `y - y_nominal(TA = 25)` is therefore sound with bound
    `eps_A + delta + initial-state term`.

## 3. Definitions

- **Admissible healthy set `Y(P)`:** all outputs `y[0:T]` produced by some admissible initial state, ambient
  path and noise sequence, with the known command P and a healthy sensor.
- **Consistent up to t:** `y[0:t]` is the prefix of some element of `Y(P)`.
- **Oracle:**
  - Offline, full-history linear-program feasibility of the above, which is exact for this linear plant
    with polyhedral sets.
  - It gives, for every run, the first time `t*` at which no admissible healthy explanation exists
    (`t* = never` if the run stays consistent).
  - The oracle is ground truth for distinguishability. It is not a method under test.
- **Indistinguishable fault (for a run):** a faulty run that the oracle finds consistent over the whole run.
  No sound method can flag it.

## 4. Faults

Each fault starts at `t_f` unless stated otherwise. Healthy runs carry no fault.

| Class | Magnitudes |
|---|---|
| constant offset from t = 0 | b = 1 °C (≤ eps_A), 3 °C (> eps_A) |
| jump (step offset at t_f) | 0.2, 0.5, 1, 2, 5 °C |
| stuck (value frozen at t_f, noise kept) | — |
| noise increase | ×2, ×4 delta |
| gain (y = (1+g)·Ts + v) | g = 1 %, 5 % |
| drift (offset ramp from t_f) | 0.0005, 0.001, 0.002, 0.005, 0.02, 0.1 °C/s |

This gives 19 cells (including healthy) × 2 excitation arms × 2 noise arms = 76 cells.

## 5. Methods under test

All methods are causal and see only `y` and the known P. Each is fully specified and frozen before any
FINAL data is generated.

- **M — multi-horizon consistency checker.** Three sound tests under the stated assumptions.
  - **h1 (one step):** propagate a state box with the model and the known P, intersect with
    `[y - delta, y + delta]`. An empty intersection means violated.
  - **h2 (12-sample window, about 4 fast time constants):** a fixed-size Chebyshev feasibility problem
    over the window. The unknowns are window initial state and constant TA within its box. Violated if the
    minimum worst-case residual exceeds delta.
  - **h3 (64-sample window, about one slow time constant):** the envelope check of section 2 on
    `y - y_nominal(TA = 25)`, with the sound bound stated there.
  - **Output per sample:**
    - integrity `OK` or `VIOLATED(h)`, naming the first horizon that fired;
    - a certified absolute-offset bound `r_t`: the largest sensor offset the data cannot exclude.
      By W1, `r_t >= eps_A` always.
  - **Verdict against a requirement R:**
    - TUTARSIZ (inconsistent) if integrity is violated;
    - TUTARLI (consistent) if `r_t <= R`;
    - AYIRT EDİLEMEZ (indistinguishable) otherwise.
    - R is evaluated at 1 °C and at 3 °C.
- **B-model.** A Kalman filter with the same model and TA as a random-walk state, with an innovation
  chi-square test. A classical model-based residual.
- **B-own-1.** The unchanged DMREDA core (`gold_line/core/dmreda_reference_clean.py`, sha256 0b8bffc7…).
  A confirmed event counts as "inconsistent".
  - Its known defects are handled by the harness, not by editing the core:
    - warm-up is not enforced inside the core, so evaluation masks the warm-up;
    - non-finite input poisons the core, but this protocol never feeds non-finite input.
- **B-own-2.** A CUSUM on first differences of `y`, centred on an EWMA. No model.

**Calibration of the statistical baselines** (B-model, B-own-1, B-own-2):
- Thresholds are set on healthy TRAIN runs to a matched healthy alarm budget.
- **Bounded arm:** zero alarms on TRAIN healthy runs, using the maximum statistic plus a 5 % margin.
- **Gaussian arm:** about 1 alarm per 100 healthy run-hours.
- The achieved rate on CAL healthy runs is reported.

## 6. Predictions (frozen)

- **P1, soundness.** M declares TUTARSIZ on no healthy run in the bounded-noise arm. In the Gaussian arm,
  its healthy rate is reported.
- **P2, agreement with the oracle.**
  - In every cell, M's final integrity verdict matches the oracle's in ≥ 90 % of runs.
  - M is never inconsistent where the oracle is consistent (that would break P1).
  - Latency is reported as `t_M − t*`.
- **P3, horizon specificity (E1).**
  - The first horizon to fire is h1 for jumps ≥ 2 °C and for noise ×4.
  - h2 fires first for stuck and gain 5 %.
  - Drift 0.0005–0.002 °C/s fires only at h3, at about the time the accumulated drift leaves the
    remaining ambient envelope.
  - Ablation: removing h3 loses the slow drifts, and removing h2 loses stuck and gain under E1.
- **P4, exact witnesses.**
  - Offset 1 °C against its ambient-shift twin, and stuck under E0 against its healthy twin.
  - Every method must give the same verdict on each twin pair, sample for sample. Any difference is a bug
    in that method or in the harness.
- **P5, limit of own history.**
  - At the matched budget, B-own-1 and B-own-2 detect drift ≤ 0.002 °C/s within the run in ≤ 10 % of runs.
  - M detects ≥ 90 % of the drift-0.001 runs whose oracle `t*` falls within the run.
- **P6, value of knowing the command.**
  - Secondary arm: P is unknown to the methods and only bounded in [0, 42].
  - Stuck and gain faults under E1 become mostly undetectable for M and for the oracle.
  - Reported as the drop in oracle-detectable fraction.

## 7. Decision rules

- **P1 fails:** stop. The assumptions or the implementation are wrong. Fix them before reading any other
  result.
- **P3's ablation fails (a horizon adds nothing):** the t1/t2/t3 decomposition is redundant for this plant.
  A single recursive set-membership observer is enough. Record this as a negative result.
- **B-model matches M at the matched budget in every cell, with no worse latency:** M's contribution
  reduces to soundness under the stated bounds and the explicit certified bound `r_t`. Record exactly that,
  and nothing more.
- **P5 fails (own history detects slow drift at the matched budget):** the claim that own history cannot
  see slow drift is false here. Record it.
- **B-own-1 adds nothing over B-own-2 in any cell:** there is no DMREDA-specific contribution to this
  question. Record it.
- **All of P1–P5 hold:** support for a narrow statement only. For this plant and these bounds, one sensor
  with the model and the known command certifies its dynamic integrity at three distinct horizons and can
  state that it cannot certify its absolute offset below the ambient uncertainty; own-history state does
  neither. The next step is the physical bench of `docs/ROADMAP.md` Phase 8, under a new protocol.

## 8. Data discipline

- **Seeds:** TRAIN 400000–400199, CAL 410000–410199, FINAL 420000–420029 per cell, plus 420100–420299 for
  healthy runs. They are disjoint from all earlier seed ranges.
- **FINAL:** generated only after every method and threshold is frozen and committed. It is never used for
  tuning. Any post-hoc look is labelled as post-hoc.
- **Splits:** at the run level.
- **Package:** source commit, environment lock, configuration, seed list, result hashes.
- **Failures:** a failed prediction stays in the repository with this protocol (`VALIDATION_RULES.md` §8).

## 9. Order of work

1. Oracle and generator, then the computed oracle map for every cell on CAL seeds. Freeze the map before
   M exists.
2. Exact-witness checks (P4) on the generator alone.
3. M, then the baselines, then their calibration on TRAIN.
4. FINAL, once.

## 10. Out of scope (version 1)

- Uncertain plant parameters (the next version adds parameter boxes, which make "sensor fault" and
  "model no longer valid" partly indistinguishable).
- Nonlinear plants.
- Any MCU timing claim.
- Hardware.
- MGDE.
- Hypothesis generation, which is a separate experiment after this one.
