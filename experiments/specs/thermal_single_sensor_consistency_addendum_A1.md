# Addendum A1 to protocol v2 — baseline calibration, ablations and FINAL rules

Date: 2026-11-17. Applies to `thermal_single_sensor_consistency.md` (v2, frozen at 5e0cc71). It was committed
before any TRAIN run was used for calibration.

- The v2 text is not changed. Nothing in v2 section 5 is changed.
- This addendum fixes the choices v2 left open, so they are made before the data that would decide them.
- A1.1–A1.3 are Can Koç's decisions. The rest follows from them or from v2.

## A1.0 Disclosure

Before this addendum was committed, TRAIN seed 400000 (healthy, E0 and E1) was run once through the
unchanged DMREDA core at its native thresholds. The purpose was to time the core: 44 ms per 3600-sample run.

What was seen:
- **Native events:** E0 at samples 7, 764, 2754; E1 at 8 samples, the first five 7, 145, 254, 383, 735.
- **Maximum d and g after sample 300:** E0 0.544 and 0.197; E1 0.987 and 0.392.

No choice below depends on it: A1.1–A1.3 were fixed before. That seed's runs are part of TRAIN, as all
TRAIN healthy runs are. All other development used CAL seeds.

## A1.1 CUSUM

v2 section 4 says "a CUSUM on first differences of y". This addendum fixes it as a two-sided Page CUSUM on
Δy[k] = y[k] − y[k−1], started at k = 1:

    S+ = max(0, S+ + Δy − a),  S− = max(0, S− − Δy − a),  score[k] = max(S+, S−)

- **Primary:** a = 0. Here the score is the distance from the running extreme, a range statistic.
- **Secondary:** a = ρ_A = 0.002 °C/sample.
- Both are run and reported in full under the same rules. P8 is scored on the primary.

## A1.2 Threshold budget, the same for every variant

For every baseline variant (A1.1, A1.3) and **each arm separately**:
- threshold = 1.05 × max, over the 200 TRAIN healthy runs of that arm (seeds 400000–400199), of the variant's
  statistic on the evaluation window k ∈ [300, N);
- the budget is therefore zero alarms on 200 TRAIN healthy runs per arm. It is empirical, not a
  probability.

Only healthy TRAIN runs are generated. No fault cell is run on TRAIN.

## A1.3 DMREDA

The core is `experiments/baselines/vendor/dmreda_reference_clean.py`, sha256 `0b8bffc7466b7dc6…ceef3e`. It
is called only through its public function, in mode D_or_G, with the default profiles and transitions,
except as stated here.

**Primary: the native mechanism, fast gate plus confirmation.**
- An alarm is a confirmed event (`event_times`).
- **Threshold family:** the four threshold levels of every profile (`th_d`, `th_g`, `th_d2`, `th_a`) are
  multiplied by one factor s > 0 and passed through `profiles=`.
  - Unchanged: windows, `n_min`, confirmation lengths, refractory periods, regime transitions and
    `e_floor`.
- **Statistic of a run:** s* = the largest s with a confirmed event at a sample ≥ 300.
  - Computed by a descending geometric scan (ratio 0.995) from 2·s_fast down to 1e-3·s_fast.
    - s_fast = max over all k of max(d/th_d, g/th_g) at the native profile.
    - The factor 2 covers the weak dependence of g on s, through the step m, which is held while a
      confirmation is pending.
  - Then bisected to 1e-6 relative between the first scan point with an event and the point above it.
  - s* = 0 if no point in the scan gives an event.
- **Threshold:** s_cal = 1.05 × max s* over the arm's TRAIN healthy runs.
- **Direct check:** the mechanism need not be monotone in s, so s_cal is then checked directly: zero
  events at samples ≥ 300 on every TRAIN healthy run of the arm.
  - If the check fails, s_cal is multiplied by 1.05 until it passes. The number of steps is reported.

**Ablation: the fast gate alone** (the `91bda17` adapter).
- Score: max(d/th_d, g/th_g), with the profile active at each sample.
- Alarm when the score exceeds the threshold.
- Calibrated by A1.2.

## A1.4 Alarms, detection, P8 and P1 for the baselines

**Alarms and detection**
- **Alarm time:** the first sample k ≥ 300 at which the variant alarms.
- **On a fault run:**
  - alarms at k < t_f are pre-onset alarms, reported as false alarms;
  - the run is *flagged* if the variant alarms at some k ≥ t_f, whether or not it alarmed before. This is
    the conservative count for P8.

**P8 clause 1** is scored on FINAL:
- for each primary method (CUSUM a = 0; DMREDA native) and each arm: the flagged fraction over the pooled
  drift cells 0.0005, 0.001 and 0.002 °C/s (90 runs per arm);
- P8 holds if all four fractions are ≤ 10 %;
- per-cell fractions, the secondary variant and the ablation are reported with the same rule, not scored.

**P8 clause 2** ("neither produces anything that corresponds to the offset interval") is a category
statement. It is recorded, not scored.

**P1 for the baselines**
- A variant's verdict is alarm or no alarm, with the arm's threshold.
- The closed-loop twins belong to neither arm, so both arms' thresholds are applied to them.
- P1 requires identical verdicts for every variant: primary, secondary and ablation.

## A1.5 Ablations (v2 section 4, reported, not predicted)

Ablations report the full-run verdict per run. Latency t* is computed only for the full oracle and the full
machine.

- **Oracle**, with the same certificates as the full oracle:
  - full;
  - without (b): rate constraint removed, box kept;
  - without (c): box removed, rate kept;
  - without (d): the command P[k] free in [0, 42] at every sample. The model is on y with the full plant
    from the P0 steady state at TA[0]; (a), (b), (c) and (e) are kept.
- **Machine:** full; without (b); without (c). (d) is not defined for the machine.

## A1.6 FINAL, one run, after thresholds are committed

**Seeds**
- 420000–420029 for each of the 38 cell-arms.
- 420100–420299 for healthy runs, both arms.

**Per run**
- oracle full verdict and t*;
- the A1.5 ablations;
- machine verdicts at R = 1 and 3, and its first inconsistent sample;
- the alarm times of every baseline variant.

**Healthy runs:** the oracle offset enclosure and the P6 rule.

**P1 on FINAL seeds 420000–420029**
- Pairs: offset open loop and closed loop, stuck at rest, as in `thermal_twins.py`.
- Machine and all baseline variants run on both members.
- The oracle runs one LP per member and uses the 1-Lipschitz bound |d*(z) − d*(z′)| ≤ ‖z − z′‖∞.

**P2–P6** are scored as in v2 section 5:
- P3 on faulty runs uses the outer box bound;
- P6 uses the healthy FINAL runs.

**P7**
- E0: scored as in v2.
- E1: reported under both readings of the frozen text:
  - inconsistent by k + 30;
  - first inconsistency in [k, k + 30].

  Neither reading is designated after the fact.
- The CAL finding that the Proposition 3 timing clause for E1 is wrong (review record 2026-11-17, section 4)
  stands and is not revised.

## A1.7 Interpretation fixed in advance

- TUTARLI(R) means: every constant-offset explanation has |b| ≤ R. It is not a bound on the sensor error.
  - CAL counterexample: drift_0.001 is TUTARLI at R = 1 with an end-of-run error of 3.0–3.3 °C (record
    section 3; test `test_consistent_bounds_constant_offsets_not_sensor_error`).
- FINAL reports every TUTARLI on a fault cell next to that run's true end-of-run sensor error.
- Healthy consistency (V0) is guaranteed by construction. It is reported as a numerical check, not as a
  result.

## A1.8 Environment

- FINAL runs under the lock in `env/` (CPython 3.12.13, NumPy 2.5.5, SciPy 1.18.1, HiGHS from SciPy).
- The runner refuses to start on any other versions, and records the machine and OS.
- Solver attempts stay isolated per process (`c04305a`).
