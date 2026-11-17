# Thermal protocol v2 — FINAL results, 2026-11-18

Protocol v2 (5e0cc71) with addendum A1 (9f6eeab). This is the single FINAL run. Nothing in the protocol,
the thresholds or the scorer was changed after it ran. Failures are recorded as they came out.

## Provenance

| Item | Value |
|---|---|
| Machine | Arch (Ryzen 7 7700, x86_64, Linux 7.3.4) |
| Environment | CPython 3.12.13, NumPy 2.5.5, SciPy 1.18.1, HiGHS 1.12.0; passes the A1.8 lock |
| Run | 14 workers; 2026-11-18 00:02:29 → 01:05:46 +0300 (3796 s) |
| Source | `da6e4a0`, clean tree, fresh clone |
| Thresholds | `results/thermal_v2/train/thresholds.json`, sha256 `7cb86186…78e22` (frozen at `390a20c`) |
| Seeds | 420000–420029 for each of the 38 cell-arms; 420100–420299 healthy for both arms; twins on 420000–420029 |
| Size | 1540 runs, 300 twin pairs |

**Result files.** They are in `results/thermal_v2/final/`, copied from Arch. The sha256 values match those
FINAL recorded itself:

| File | sha256 (first 16 hex) |
|---|---|
| `runs.jsonl` | `a2b5ddd29fd511b1` |
| `twins.jsonl` | `ca3d00387d70a8d8` |
| `meta.json` | `5d5c9b0fdb8f0b34` |

**Scoring.** `scores.json` (`b5f5861d3058f3d7`) comes from `experiments/final/score_final.py`, which is
unchanged since `1bcdc3f`. The solver logs are kept outside the repo: `FINAL-da6e4a0-solver_attempts.tar.gz`,
sha256 `53fd0827…57b7e`, 1.8 MB, on Arch (`~/Research/sdts-runs/`) and on the Mac (`~/Downloads/sdts-runs/`).

**Oracle completeness.** No oracle verdict was undetermined: full and ablations, 0 of 1540 each. All t* are
certified.

## Predictions (protocol section 5, scored with A1)

| | Result | Numbers |
|---|---|---|
| P1 exact twins | **holds** | 300 pairs, max \|Δy\| 6.4e-14; 0 differing verdicts for the oracle, the machine and all 4 baseline variants under both arms' thresholds |
| P2 command independence | **holds** | 450 additive pairs; oracle 0 and machine 0 differing; 0 undetermined |
| P3 machine soundness | **holds** | 460 healthy runs, 0 TUTARSIZ; TUTARLI corroborated 14 (R=1), 294 (R=3), contradicted 0 |
| P4 large jumps at t_f | **holds** | 120/120 (oracle before/at, and machine first inconsistency = t_f) |
| P5 offsets without (c) | **holds** | 120/120 consistent (oracle and machine) |
| P6 certification rule | **holds** | R=1: 460/460 scored agree. R=3: 322/322 scored agree, 138 boundary (not scored) |
| P7 E0 | **holds** | 30/30 stuck runs consistent |
| P7 E1, deadline reading | 30/30 = 100 % | inconsistent by k+30 |
| P7 E1, window reading | 6/30 = 20 % | first inconsistency in [k, k+30]; 24/30 were already inconsistent before k |
| **P8** | **fails** | see below |

**P7 E1.** Both readings are reported as A1.6 requires; neither is designated. As on CAL, what fails is the
timing clause in Proposition 3 ("case iii applies at the next command change"). Under E1 the plant is in
command transient at t_f, so case (iii) applies from t_f.

**P8 (scored on cusum_a0 and dmreda_native, both arms; holds only if all four fractions are ≤ 10 %).**
Flagged among the drift runs ≤ 0.002 °C/s (90 per arm):

| variant | E0 | E1 |
|---|---|---|
| cusum_a0 (primary) | **90/90 (100 %)** | 0/90 |
| dmreda_native (primary) | 0/90 | 0/90 |
| cusum_rhoA (secondary) | 25/90 (all 25 are drift_0.002, which equals ρ_A) | 0/90 |
| dmreda_fast_gate (ablation) | 0/90 | 0/90 |

- No pre-onset alarms on these runs.
- P8 fails because of CUSUM a = 0 under E0. This is the direction A1 section 6 expected analytically:
  - With a = 0 the CUSUM is a range statistic.
  - Its TRAIN threshold (0.86 °C) reflects how little the generator's ambient moves in one run. That is far
    less than assumption (b) allows.
  - A drift of 0.0005 °C/s accumulates about 1.5 °C, so it is flagged.
- **Per protocol section 6, recorded:** own history, calibrated on the data distribution, sees slow drift at
  this budget under constant command. The worst-case machine and oracle see it only through the box (c).
- The same methods are blind under E1. There the TRAIN thresholds are set by command swings: CUSUM 33 °C;
  DMREDA s = 4.3.
- P8 clause 2 (no interval output) is a category statement and is not scored.

## Reported, not predicted

**Healthy false alarms.** The budget was zero on TRAIN. On the 230 FINAL healthy runs per arm:
- cusum_a0 and cusum_rhoA: 0/230 under E0, 1/230 under E1;
- DMREDA variants: 0 in both arms.

**Oracle–machine gap (same semantics, b = 0).**
- The machine is never earlier than the oracle (0 negative lags).
- Its lag is largest on drift_0.002: median 338 s, maximum 1617 s (420018, both arms). Other large lags: 1005
  s (420005) and 869 s (420001).
- **Misses:** 420004 drift_0.001 (E0 and E1) is inconsistent for the oracle; the machine never flags it.

**The TUTARLI counterexample repeats on FINAL.** drift_0.001 has TUTARLI at R = 1 on 7 seeds per arm (420002,
420004, 420005, 420011, 420018, 420021, 420027). The true end-of-run sensor error on those runs is
3.06–3.29 °C.
- 420004 is one of them, and the oracle finds that run inconsistent.
- So the machine's information loss can give an offset certificate on a run that full information refutes.

Read TUTARLI(R) only as in A1.7: a bound on constant-offset explanations.

**Ablations (oracle, full-run verdicts).**
- **Without (d):**
  - stuck/E1 becomes consistent 30/30;
  - drift_0.002/E0 becomes consistent 30/30 (P sets the level, so the box no longer binds);
  - gain_0.01 is mostly consistent (E0 26/30, E1 22/30);
  - gain_0.05, noise and jumps of 2 and 5 °C stay inconsistent.
- **Without (b):**
  - jump_0.2: 26/30 consistent; jump_0.5: 14/30; jump_1: 1/30;
  - drift is unaffected.

  The filter smoothness (s) alone still exposes jumps of 1 °C or more.
- **Without (c):** every offset and drift ≤ 0.001 is consistent; drifts ≥ 0.002 are still caught by (b).

**Baselines per cell.**
- Under E0, cusum_a0 flags every fault cell except stuck (0/30) and jump_0.2 (10/30). DMREDA native flags:
  - jumps ≥ 1 °C;
  - noise_x4;
  - gain_0.05;
  - drift_0.1 (29/30);
  - noise_x2 (20/30).
- Under E1 all baselines are nearly blind: only cusum on drift_0.02/0.1 and on drift_0.005 (17/30).

## What this does and does not say

**It says:**
- The algebra, the oracle and the machine behave as derived (P1–P6, P7 E0).
- The machine never claims more than the data allow under the assumptions.
- The P7 timing clause is wrong for E1.
- P8 is falsified for CUSUM a = 0 under E0.

**It does not say:**
- that any method is "better";
- that TUTARLI means the sensor is accurate.

The oracle–machine gap (up to 1617 s, plus two misses) is information the v2 machine discards. Whether that
can be recovered with small memory is v3's question (branch `sdts-v3/template-state`). v3 uses only its own
DEV seeds; nothing in this FINAL was used to build or tune it.
