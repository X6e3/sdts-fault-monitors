# Thermal protocol v2 — from addendum A1 to the FINAL start, 2026-11-17/18

Follows `RECORD-2026-11-17.md`. Labels as there: **MATH**, **CAL**, **HYP**, **OPEN**.
- Commits are local and not pushed.
- Run outputs are outside the repo, in `~/Downloads/sdts-runs/` on the Mac and `~/Research/sdts-runs/` on
  Arch. Their hashes are listed in section 8.

## 1. Decisions and order

Can Koç decided the three open TRAIN choices:
1. **CUSUM:** a = 0 primary, a = ρ_A secondary; both reported.
2. **Thresholds:** per arm, with the same zero-alarm budget.
3. **DMREDA:** the native fast gate plus confirmation is primary; the fast gate alone is an ablation.

They are fixed in `experiments/specs/thermal_single_sensor_consistency_addendum_A1.md`, committed as
`9f6eeab` before any TRAIN calibration. The order of work after that:

| Commit | Content |
|---|---|
| `29a8bc4` | Environment lock |
| `29d5f93` | (d) ablation |
| `385eee3` | Ablation CAL check |
| `a902aba` | Baseline variants |
| `1bcdc3f` | FINAL runner and scorer |
| `390a20c` | TRAIN thresholds, frozen |
| `c8ee09a` | Baseline P1 check |
| `a101dbd`, `da6e4a0` | Rehearsal checks and the solver fallback |

## 2. Errors and slips (reported, none changed a frozen rule)

- **TRAIN seed run before A1 was committed.** TRAIN seed 400000 (healthy, E0 and E1) was run once through the
  native DMREDA core, to time it. This is disclosed in A1.0, with what was seen. Every later development step
  used CAL seeds.
- **Wrong source commit in the ablation CAL summary.** That `summary.json` read `git_head` when the run
  *ended* (`a902aba`, dirty), but the run started at `385eee3`.
  - The files the run imports are identical between the two commits; checked with `git diff`.
  - Since `1bcdc3f` every script records its source commit when the run starts. The TRAIN calibration and the
    FINAL runner also refuse to run from a dirty tree.
- **Sight of P8 on CAL.** The rehearsal scorer printed P8 = false on the CAL rehearsal seeds (3 per cell). The
  thresholds (`390a20c`) and every rule (A1) were already frozen. Nothing was changed after it.
- **Comparison tolerance too strict.** The rehearsal-vs-CAL check compared P6 offset intervals at 1e-9.
  - Measured differences: inner witness intervals up to 3.1e-3 °C (they depend on the solver's extreme path);
    outer bounds up to 6e-7 °C.
  - P6 labels are identical on all 26 healthy runs. The P6 rule does not score runs within δ = 0.3 of the
    boundary.

## 3. Environment lock (A1.8)

`env/requirements-thermal-v2.txt` and `env/thermal_v2_env.py`: CPython 3.12.13, NumPy 2.5.5, SciPy 1.18.1,
HiGHS 1.12.0. Two environments pass the check:
- the Mac (arm64, macOS 27);
- a fresh offline uv venv on Arch (x86_64, Linux 7.3.4).

## 4. Ablations (A1.5)

`verdict_free_command(y)` drops (d): the command is free in [0, 42] and the model runs on y with the full plant.
It carries the same certificates. The dual caps come from the plant being a positive system (**MATH**). Tests
show three things:
- with P pinned to the applied command, it reproduces the z LP;
- it is a relaxation of the full LP;
- it explains a healthy run and still excludes a 10 °C step.

**CAL check** (`validate_ablations_cal.py`; 5 seeds × 38 cell-arms; 347 s):
- 0 undetermined in any variant;
- 0 violations of the relaxation relations;
- full verdicts equal to Sol's CAL map.

**CAL pattern** (reported, not predicted; 5 seeds):
- Without (d), stuck/E1 becomes consistent (5/5).
- Without (d), gain_0.05 stays inconsistent: its onset is a ~2.5 °C step the plant cannot follow.
- Without (d), drift_0.002/E0 becomes consistent: with P free, P sets the level and the box no longer binds.
- Without (b), jumps of 0.2 and 0.5 °C are mostly absorbed. The machine then misses most 1 and 2 °C jumps
  that the oracle still catches. That gap is the smoothness (s).

## 5. Baselines and TRAIN (A1.1–A1.4)

`thermal_baselines.py` holds the four variants. For `dmreda_native`, one scale s multiplies
th_d/th_g/th_d2/th_a through the core's `profiles=` argument; the core file is unchanged (sha256 checked).
Its statistic s* comes from the A1.3 scan and bisection; on CAL 410000 healthy it took about 29 s per run.

**TRAIN** (`calibrate_train.py` at `1bcdc3f`, clean tree, healthy only, 400000–400199 per arm, 1717 s, frozen
in `390a20c`):

| variant | role | E0 threshold | E1 threshold |
|---|---|---|---|
| cusum_a0 | primary | 0.859525 | 33.038614 |
| cusum_rhoA | secondary | 0.626990 | 31.740654 |
| dmreda_native | primary | s = 1.711108 | s = 4.312149 |
| dmreda_fast_gate | ablation | 2.709419 | 5.204786 |

- No variant needed a raise step: zero TRAIN alarms at threshold.
- **MATH check:** with a = ρ_A under E0, the CUSUM score is at most 2δ = 0.6, because S is constant and A rises
  by at most ρ_A·(k−j). The TRAIN maximum is 0.597.

**Baseline P1 on all 2000 CAL twin pairs** (`check_p1_cal.py`): every variant, with each arm's threshold, gives
the same alarm verdict on both members of every pair (0 pairs differ).

## 6. FINAL runner, rehearsals and the solver fallback

`run_final.py` (A1.6) and `score_final.py`.
- **Rehearsal set:** CAL 410000–410002 × 38 cell-arms, healthy 410100–410109 × 2, twins on 410000–410001.
  That is 134 runs and 20 pairs.
- **First rehearsal, Mac (`c8ee09a`, 633 s):** every decision equals the earlier CAL evidence (114 full
  verdicts, 114 t*, 12 P4, 3 P7, 134 machine, 114 per ablation).
- **First rehearsal, Arch (`a101dbd`, 332 s, fresh clone, fresh venv):** 2 decision differences, both
  undetermined on Arch. Both no-presolve methods returned HiGHS status 4 there:
  - 410000 jump_2 E1 without (b);
  - 410105 healthy E1 without (c).

  HiGHS status 4 also occurs on the Mac (50 of 1836 attempts against Arch's 67 of 1852). Which LP is affected
  differs by platform.
- **Fix (`da6e4a0`):** presolve attempts were added as the 3rd and 4th fallbacks. They are safe now that every
  attempt runs in its own process. Because every answer is certified independently, a fallback can only turn
  undetermined into a decision (**MATH**). Tests pin the order, and check that a decided LP makes exactly one
  attempt.
  - On Arch the fallback decided both LPs, as the Mac had.
- **Second rehearsals (`da6e4a0`, Mac 575 s, Arch 326 s):**
  1. Mac vs the CAL evidence: 0 decision differences.
  2. Arch vs Mac: 0 decision differences over 7568 compared fields. Largest float differences: d_up 2.3e-3,
     d_lo 5.7e-7, inner interval 3.1e-3, outer 6.0e-7.
  3. Mac `c8ee09a` vs Mac `da6e4a0`: identical (the fallbacks never ran on the Mac).
  4. The scorer ran on both and gave identical `scores.json` (meta excluded).

## 7. FINAL started

Can approved: start FINAL on Arch if the rehearsals held, including for the code after the fallback fix.
- **Started:** 2026-11-18 00:02:29 +0300 on Arch (Ryzen 7 7700, 14 workers).
- **Source:** fresh clone `~/Research/sdts-final-da6e4a0` at `da6e4a0`, clean tree.
- **Thresholds:** `results/thermal_v2/train/thresholds.json`, sha256 `7cb86186…78e22`.
- **Workload:** 1540 runs and 300 twin pairs.
- **Seeds:** 420000–420029 per cell-arm, 420100–420299 healthy, twins on 420000–420029.
- **Output:** `~/Research/sdts-runs/FINAL-da6e4a0/`.
- FINAL runs once. Its scoring and report follow in the next record.

## 8. Hashes (sha256, first 16 hex)

| File | sha256 |
|---|---|
| `cal-ablations-385eee3/rows.jsonl` | `cf43e696b37c6f22` |
| `cal-p1-baselines-c8ee09a/P1_baselines.jsonl` | `b2c9742b4addce56` |
| `rehearsal-c8ee09a/runs.jsonl` | `2539e9cacabb3ab3` |
| `rehearsal-da6e4a0/runs.jsonl` | `951adf43763e1ac1` |
| twins, Mac (both rehearsals) | `bf16fc243868f0b4` |
| `arch-rehearsal-a101dbd/runs.jsonl` | `ce2f1ea3cad57a56` |
| `arch-rehearsal-da6e4a0/runs.jsonl` | `ab26e419cf26ea67` |
| twins, Arch (both rehearsals) | `1aa3c2cba851a13c` |
| `results/thermal_v2/train/thresholds.json` | `7cb86186a5d0e36f` |
| `results/thermal_v2/train/train_statistics.jsonl` | `e0a029f7ae3acfad` |

- The two Mac runs files differ only in the `seconds` field.
- Twins files differ between machines in floats only (d_lo/d_up), not in decisions.

## 9. Open

- **FINAL scoring and the full report**, including the reported maps:
  - oracle–machine gap;
  - ablations;
  - baselines per cell;
  - TUTARLI against the true error.
- **Next protocol (proposed with Can, not started):** a budgeted sound state measured against the same oracle.
  The close/continue criterion is to be written before results; see Can's goal notes.
