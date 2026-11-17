# Experiment — what a single temperature sensor can certify about itself

Status: frozen protocol v2 (preregistration), 2026-11-17. v1 (commit 5737bb3) was pushed before the
author's review arrived; v2 replaces it. No method has been implemented or run, and no data has been
generated under either version. Any later change is a new version with its own commit and a stated
reason, and never follows a look at FINAL data.
Simulation only. Timebox: 3 weeks from the start of implementation.

## 0. Question and position

Can a machine determine, from the history of its single sensor, which conclusions about that sensor it
can draw and which it can not? The setting is one plant, one sensor, a known plant model and a known
actuator command.

This experiment sits outside the C0–C5 ladder of `docs/RESEARCH_CHARTER.md`: it uses an explicit model and
the known command. Related known fields are analytical redundancy, set-membership estimation and
diagnosability. No novelty is claimed. No new method family is introduced. The machine under test is the
standard exact recursion of section 4.

## 1. Plant and assumptions

The two-node thermal plant of `sdts_thermal_microtest` (2026-10-23), exact in discrete time (Euler,
`DT = 1 s`):

```text
Tc[k+1] = Tc[k] + (P[k] - K*(Tc[k] - Ts[k])) / CC
Ts[k+1] = Ts[k] + (K*(Tc[k] - Ts[k]) - H*(Ts[k] - TA[k])) / CS
y[k]    = Ts[k] + v[k]                    (healthy sensor)
```

Parameters: `CC = 30`, `CS = 12`, `K = 2`, `H = 0.8`. `P[k]` is in [0, 42] W.

The assumptions define the admissible healthy set. There is one world: bounded noise and bounded ambient.
No distributional assumption is made anywhere.

- **(a) Noise:** `|v[k]| <= delta = 0.3 °C`. Generated uniform in that interval.
- **(b) Ambient rate:** `|TA[k+1] - TA[k]| <= rho_A = 0.002 °C/s`.
- **(c) Ambient box:** `23 <= TA[k] <= 27 °C`. Generated as a bounded random walk satisfying (b) and (c).
- **(d) Command:** `P` is known to the machine (it is the controller's own command).
- **(e) Initial state:** steady state for `P = 20` at the unknown initial ambient
  (`Ts = TA[0] + 25`, `Tc = TA[0] + 35`). No absolute temperature is given to the machine.
  v1 gave ±1 °C, which leaked an absolute reference.

**Excitation arms:**
- **E1:** P redrawn uniformly in [0, 42] every 15 s.
- **E0:** P constant at 20 W.

**Run:** 3600 samples. Fault onset `t_f` uniform in [300, 600]. Samples before 300 are excluded from all
counts.

## 2. Algebra, done before any method

Numbers were checked in pure Python on 2026-11-17.

**Plant constants.**
- Discrete eigenvalues 0.98437 and 0.71563: time constants 63.5 and 3.0 steps.
- The TA→Ts impulse response is nonnegative and sums to 1.
- TA→Ts ramp lag is 52.5 s.

**Decomposition.**
- By linearity and (e), `Ts[k] = S[k] + A[k]`.
- `S` is the response to the known command from the `P = 20` steady state at zero ambient. It is fully
  known to the machine.
- `A` is the ambient part. It is a convex filter of TA, started at equilibrium.
- It follows that A stays in [23, 27] and `|A[k+1] - A[k]| <= rho_A`. In 200 random admissible runs,
  A ranged over [23.004, 26.995] with a largest step of 0.00062.
- Define `z[k] = y[k] - S[k]`. For a healthy sensor, `z = A + v`.
- Every consistency question is therefore one-dimensional: does there exist a sequence A satisfying (b) and
  (c), plus the filter's own smoothness, with `|z - A| <= delta`?

**Proposition 1 — additive faults do not see the command.**
- Let `y = Ts + f + v` for an additive fault `f` (offset, jump, drift, noise increase).
- The run is consistent iff some admissible ambient deviation and noise explain `f`. The command P cancels
  from this condition.
- This holds for every command sequence, including closed loop on `y`: a faulty run and its healthy twin
  produce the same `y`, so they produce the same P.
- Consequence: for additive faults the verdict is identical under E0 and E1 for the same
  `(TA, v, f)` realization.

**Corollary 1a — constant offset ≡ ambient shift, for every input sequence.**
- Shifting Tc, Ts and TA by the same `b` shifts the whole trajectory by `b`, because `A·1 + B_T = 1`.
- So `y = Ts + b + v` under ambient TA equals, sample for sample, a healthy sensor under ambient `TA + b`.
- Checked numerically on 200 runs with random commands, half of them closed loop on `y`: largest difference
  5.7e-14.
- The offset is indistinguishable exactly when `TA + b` stays inside [23, 27] for the whole run.
- Excitation can not break this.

**Proposition 2 — offset certification depends on where the ambient went.**
- Let `A_min` and `A_max` be the extremes of A over the run.
- A healthy run is consistent with every constant offset in `[A_max - 27, A_min - 23]`, up to slack δ.
  The hypothesis "offset b" needs an ambient part `A - b` that stays inside the box.
- The machine can therefore certify `|offset| <= R` only if `A_min <= 23 + R` and `A_max >= 27 - R`.
  - For `R = 1`: A must have visited both ≤ 24 and ≥ 26.
  - For `R = 3`: A must not have stayed entirely above 26 or entirely below 24.
- **Correction of v1:** v1's statement "`r_t >= eps_A` always" was wrong. An ambient that sweeps its box
  pins the offset.

**Proposition 3 — stuck sensor: steady state versus transient.**
- A sensor stuck at `t_f` gives `z[k] = A[t_f] - D[k] + v[k]`, where `D[k] = S[k] - S[t_f]` is the
  command-driven motion after `t_f`.
- **(i) Command part at steady state, ambient at rest:** an exact twin exists (ambient frozen at
  `TA[t_f]`). Stuck is indistinguishable.
- **(ii) Command part at steady state, ambient moving at t_f:**
  - The exact twin needs ambient steps of up to 0.005 °C/s, above `rho_A`. It is not admissible.
  - The rate-respecting twin misses by about 0.03 °C, well inside the noise slack (δ = 0.3).
  - So stuck is indistinguishable up to noise. The true temperature is not constant here, but its motion is
    ambient motion, which the twin can absorb.
- **(iii) Command transient after t_f:** `D` is not ambient-explainable.
  - Example: stuck 50 s into a 20→30 W step. The twin would need the ambient between 18.98 and 23.59, which
    is outside the box.
  - Stuck becomes distinguishable once `|D|` exceeds what admissible ambient and slack can absorb.
  - Under E0, case (i) or (ii) applies. Under E1, case (iii) applies at the next command change.

**Proposition 4 — the "horizons" are not independent; the assumption families are.**
- The admissible set is one polyhedron, so consistency is one feasibility problem. An exact recursive
  solution uses all past data. A 12- or 64-sample window can only be a relaxation of it, never a source of
  additional information. v1's three-window checker therefore added no independent constraint, and its
  predictions P3 and P5 are withdrawn.
- What is independent is the assumption family. Removing one family enlarges the indistinguishable set by
  a specific fault class:
  - **Without (c):** the constraint set is invariant to adding a constant to A. Constant offsets of any
    size, and drifts the ambient rate can follow, become consistent forever. (c) is the only family that
    bounds absolute level.
  - **Without (b):** the ambient may jump within its box. Jumps and fast drifts are absorbed until the box
    is exhausted. (b) is the only family that exposes changes faster than `rho_A`.
  - **Without (a):** nothing is ever inconsistent. With (a), noise increase is exposed.
  - **Without (d):** P is free in [0, 42], so `S` is unknown. Stuck and gain faults can be explained by a
    different command. (d) is the only family that exposes them.
  - **Filter smoothness (s):** this is the plant's own property; it is not one of the declared assumptions.
    It is in the oracle but not in the machine. A is a filtered TA, so even an unbounded ambient jump moves
    A by at most `DT·H/CS = 0.0667` of it in one step (≤ 0.27 °C across the whole box). So (s) partly
    overlaps (b): the families are not perfectly independent. How much (s) adds is measured as the
    oracle-versus-machine gap. It is not predicted.
- Each family binds on its own time scale. These are derived sufficient conditions for the machine, not
  predictions:
  - (a): per sample.
  - (d): within a few steps of a command change (fast mode, 3 steps).
  - (b): after about `2·delta / (rho - rho_A)` samples. For 0.005 that is 200 s, for 0.02 it is 33 s, for
    0.1 it is 6 s. A jump `j > 4·delta + 2·rho_A ≈ 1.2 °C` is exposed at the first sample.
  - (c): after the accumulated drift exceeds the remaining box room, about `room / rho`. For 0.002 that is
    about 1000 s, for 0.001 about 2000 s. For 0.0005 it is beyond the run.

## 3. Faults

| Class | Magnitudes | Additive? |
|---|---|---|
| constant offset from t = 0 | 1, 3 °C | yes |
| jump at t_f | 0.2, 0.5, 1, 2, 5 °C | yes |
| drift from t_f | 0.0005, 0.001, 0.002, 0.005, 0.02, 0.1 °C/s | yes |
| noise increase at t_f | ×2, ×4 delta | yes |
| stuck at t_f (noise kept) | — | no |
| gain from t_f, `y = (1+g)·Ts + v` | 1 %, 5 % | no |

19 cells including healthy, × 2 excitation arms = 38 cells.

## 4. What runs

- **Oracle (offline, ground truth).**
  - An exact linear program on the full plant: dynamics, (a)–(c) and (e), with the filter smoothness
    included.
  - It gives the first inconsistent time `t*` per run, and the exact constant-offset interval that cannot
    be excluded (two LPs).
  - A variant drops (d) by making P a decision variable in [0, 42]. Further variants drop (b) and (c), for
    the ablation.
- **Machine (online, bounded, deterministic).**
  - The model `S` driven by the known command, plus the exact one-dimensional interval recursion for
    (a)(b)(c): `I[k] = (I[k-1] ⊕ [-rho_A, rho_A]) ∩ [z[k] - delta, z[k] + delta] ∩ [23, 27]`.
    Inconsistent when `I[k]` is empty.
  - The recursion is exact for the relaxed set (chain constraints in one dimension) and sound for the
    plant, because the relaxation only drops smoothness.
  - It also outputs a sound outer bound of the non-excludable offset interval: the running intersection
    of `[F_lo - 27, F_hi - 23]` over k, where `F` is the same recursion without (c).
  - Verdict against `R` (1 °C and 3 °C):
    - TUTARSIZ (inconsistent) if inconsistent;
    - TUTARLI (consistent) if consistent and the outer offset interval lies inside `[-R, R]`;
    - AYIRT EDİLEMEZ (indistinguishable) otherwise.
  - State: two interval pairs, two model states and the running extremes.
- **Own-history baselines (no model).** The unchanged DMREDA core (`gold_line/core/dmreda_reference_clean.py`,
  sha256 0b8bffc7…) and a CUSUM on first differences of `y`.
  - Thresholds give zero alarms on TRAIN healthy runs (maximum statistic plus 5 %). This is an empirical
    budget, not a probabilistic one.
  - The DMREDA core's known defects are handled by the harness:
    - warm-up is masked in evaluation;
    - only finite input is ever fed.
- **Removed from v1:**
  - **The Kalman χ² baseline and the Gaussian arm.** A χ² threshold carries a distributional meaning that
    does not exist in a bounded-noise world. A probabilistic version belongs in a separate protocol, with
    its own assumptions.
  - **The three-window checker:** see Proposition 4.

## 5. Predictions (frozen)

Only statements derived in section 2, plus one genuine empirical hypothesis about own-history methods
(P7), are predicted. Everything else is computed and reported, without a prediction.

- **P1 — exact twins.**
  - Corollary 1a (all commands, open and closed loop) and Proposition 3(i) hold to ≤ 1e-9 in the generator.
  - The oracle, the machine and both baselines give identical verdicts on each twin pair.
  - Any difference is a bug.
- **P2 — command independence (Proposition 1).** For every additive-fault run, the oracle and the machine
  each give the same verdict under E0 and E1 for the same `(TA, v, f)`.
- **P3 — soundness of the machine.**
  - No TUTARSIZ on any healthy run.
  - No TUTARLI where the oracle's exact offset interval is not inside `[-R, R]`.
- **P4 — large jumps.**
  - Jumps of 2 and 5 °C give `|z[t_f] - z[t_f - 1]| > 2·delta + rho_A`, since `j > 4·delta + 2·rho_A`.
  - So the oracle and the machine are both inconsistent at `t_f` exactly, in every run.
- **P5 — the ambient box is what bounds absolute level.** With (c) removed, every constant-offset run is
  consistent for the oracle and for the machine. This follows exactly from Corollary 1a.
- **P6 — certification depends on the ambient (Proposition 2).** On healthy runs whose `A_min` and `A_max`
  satisfy or violate the Proposition 2 conditions by more than δ, the oracle's verdict at `R = 1` and
  `R = 3` follows the rule. Runs within δ of the boundary are reported, not scored.
- **P7 — stuck.**
  - Under E0, every stuck run is consistent (Proposition 3, case i exactly, case ii with a 0.03 °C miss
    against the 0.3 °C slack).
  - Under E1, ≥ 95 % are inconsistent within 30 s after the first command change of at least 5 W after
    `t_f`.
- **P8 — limit of own history (the empirical hypothesis).**
  - At the empirical zero-alarm budget, DMREDA and CUSUM flag drift ≤ 0.002 °C/s within the run in ≤ 10 % of
    runs.
  - Neither produces anything that corresponds to the offset interval.

**Reported, not predicted:**
- the oracle-versus-machine gap (latency and offset interval);
- the drift and small-jump map;
- gain faults;
- the (b) and (d) ablations, including how much the plant's smoothness (s) covers for (b);
- removing (c) for drifts.

## 6. Decision rules

- **P1, P2, P3 or P4 fails:** stop. The generator, the algebra or the machine is wrong. Fix it before reading
  anything else.
- **P5, P6 or P7 fails:** a proposition is wrong for this plant. Record which, and why.
- **The reported ablations show a family redundant:** record it. The map of "which assumption buys which
  conclusion" is the result either way.
- **P8 fails** (own history sees slow drift at that budget): record it.
- **All hold:** the answer to section 0 is yes for this plant and these assumptions, in the narrow sense of
  P1–P7:
  - an online, bounded machine never claims more than the data and the assumptions allow (P3);
  - it states exactly when its absolute accuracy can not be certified (P6);
  - its known limits (P1, P5, P7) are where the algebra says they are.
  The reported maps then show, per fault class, which assumption makes it detectable and how far the
  machine falls short of the oracle. The next step is a new protocol: uncertain plant parameters, where
  sensor fault and model change start to overlap.

## 7. Data discipline

- **Seeds:** TRAIN 400000–400199, CAL 410000–410199, FINAL 420000–420029 per cell, plus 420100–420299 for
  healthy runs. They are disjoint from all earlier seed ranges.
- **FINAL:** generated only after the machine, the baselines and their thresholds are frozen and
  committed. It is never used for tuning.
- **Splits:** at the run level.
- **Package:** source commit, environment lock, configuration, seed list, result hashes.
- **Failures:** a failed prediction stays in the repository with this protocol.

## 8. Order of work

1. Generator and the P1 twin checks. Then the oracle and its full verdict map on CAL. Freeze both.
2. The machine. Then P2–P4 on CAL, as an implementation check only.
3. Baselines and their thresholds on TRAIN.
4. FINAL, once.

## 9. Out of scope (v2)

- Uncertain plant parameters.
- Probabilistic noise models.
- Nonlinear plants.
- MCU timing.
- Hardware.
- MGDE.
- Hypothesis generation.
