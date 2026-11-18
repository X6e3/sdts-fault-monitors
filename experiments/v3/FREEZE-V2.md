# v3 freeze 2: the compressed window F, and the rules of its independent validation

Status: DRAFT, not approved

Manifest sha256: TBD (written by `make_manifest_v2.py` at the freeze commit)

Prepared 2026-11-18 on branch `sdts-v3/template-state` for Can Koç's review. The target and the reading of a failure
are Can's to set. Everything here is a proposal until the status line says APPROVED. `run_validation_v2.py` refuses
to generate validation data until then (section 6).

**Open items, to be filled from results before review:**
- the amendment 6 and 7 results (section 5);
- the DEV rehearsal (section 8);
- the manifest sha256.

## 0. What is tested, and what a failure means

**One hypothesis, H-F.** It is about the **float64 reference implementation**: Python, with HiGHS through scipy, in
`diag/diag3_cw.py`, variant F.

The frozen compressed window F:
- is sound under the model: no alarm on an admissible run, and none before the oracle's t*;
- certifies every alarm it raises;
- misses no more oracle-detected events than v2;
- and reduces v2's paired lag (section 4) by **at least 80 %**;

all on fresh seeds of the v3 scenario distribution.

**A FAIL rejects H-F at this configuration (W = 256, B = 16, K = 64), and nothing else.** It does not reject:
- freeze 1's results (H-inv4 and H-cyl16, validated on 440000–440199);
- the DIAG-3 analysis;
- other window lengths, caps or formulations;
- the SDTS question itself: how much of the history-dependent information state a bounded, deterministic state can
  keep.

The DEV results stay what they are: DEV results.

**A PASS supports only the hypothesis as written:**
- the same plant with known parameters;
- the simulated ambient and noise laws of `dev_scenarios.py`;
- a float64 desktop implementation.

It says nothing about an MCU, float32, a real plant or model mismatch (section 7).

After the result, neither the candidate nor any rule changes. A new or modified candidate is a new freeze with the next
unused seed block (440300 onwards).

## 1. The candidate

**The state between samples:**
- a base template at τ: cyl16p's 42 directions and its clamps (`frozen/cyl16p.json`, the freeze 1 file, unchanged);
- the measurements kept in the window, at most K = 64;
- τ itself.

**The window LP** (DIAG-3 amendments 3, 4 and 6):
- It runs over the samples τ … t, with t − τ ≤ W + B = 272.
- **Exact step between nodes:** x_b = M^L x_a + Σ_{k<L} M^k e3 w_{b−1−k}, with |w_j| ≤ ρ explicit.
  - (ac, as) are kept at the nodes and TA at every sample.
  - The nodes are τ, the kept measurements, τ + 16 and the objective sample.
  - Between nodes ac and as stay in the box by convexity, so the only box rows needed there are TA's.
- **Measurements:** a measurement redundant at arrival is dropped. Dropping is sound, and lossless on DEV.
- **The cap:** above K kept measurements, the one inactive longest (its bound with a zero multiplier) is evicted. A
  newly kept measurement counts as active at arrival, and ties go to the oldest. Eviction is sound.
- **The fold, every B = 16 samples:**
  - It uses the smoothing rule, with the measurements up to the fold sample.
  - Each of the 42 supports is max(LP value + 1e-6, certified dual bound), then clamped.
- **The alarm at t:**
  - It is computed from the measurements up to t − 1.
  - z_t is kept, evicted and folded only after the alarm check.
  - Each alarm is certified: the certified as-range excludes z_t ± δ.
- **The certificate:**
  - weak duality with the solver's multipliers;
  - every variable is boxed;
  - float rounding is bounded explicitly;
  - the coefficients' own rounding is enclosed (each is correctly rounded from its exact value);
  - the measurement slabs are rounded outward.

  So the bound holds for the LP with exact coefficients, whatever the solver's tolerance.
- **An empty window LP** cannot happen with sound folds. If it does, it is recorded as an uncertified alarm, which is
  a FAIL.

**What is a theorem and what is not:**
- **Soundness** holds by construction under the model: certified folds, certified alarms, and only sound drops and
  evictions.
- **There is no dominance theorem over v2** (freeze 1's Theorem 3 was about the template state). Runs where F is later
  than v2 are reported, not judged.

**Plant and assumptions:** those of v2, `thermal.py`, unchanged.
- CC = 30, CS = 12, K = 2, H = 0.8, DT = 1 s;
- δ = 0.3, ρ_A = 0.002 °C/s, TA ∈ [23, 27], start at the P0 = 20 steady state;
- record length 3600.

**The ambient box matters to the result** (DIAG-3 amendment 5). In the slow-drift cells, the alarm often comes
when z exceeds the box's top plus δ: the healthy explanation has to push TA against the wall. In every N-late run,
z reached 2.22–2.30 in the 256 samples before t*. The box is part of the model being tested.

## 2. Code, commits and hashes

TBD at the freeze commit: the commit table, and `frozen/MANIFEST-V2.json` with every file the validation depends on,
by sha256.

The files are listed in `make_manifest_v2.py`:
- the runner and the scorer, and freeze 1's runner and scorer, which they import unchanged;
- `template_state.py` and `dev_scenarios.py`;
- `diag1.py`, `diag3.py`, `diag3_dev.py`, `diag3_cw.py` and `diag3_cw_dev.py`;
- `frozen/cyl16p.json`;
- the v2 plant, oracle and machine;
- the environment lock.

**Environment:** the thermal v2 lock (`env/thermal_v2_env.py`): CPython 3.12.13, numpy 2.5.5, scipy 1.18.1 and
HiGHS 1.12.0. It is checked at start and recorded.

## 3. Data

**Seeds 440200–440299** (100 seeds), generated only after approval, by `run_validation_v2.py`. They use freeze 1's
validation namespace (`v3val:`) and laws. 440300–440999 stay reserved.

**Per seed, 48 runs, as in freeze 1:**
- 11 cells × arms E0, E1 × ambient `rw`, `ramp` with uniform noise;
- plus healthy × E0, E1 × `rw`, `ramp` with `edge` noise.

That is 4800 runs in total.

**Why 100 seeds and not 200** (freeze 1 used 200 for inv4p's small margin):
- On DEV, F's point is 0.999 against a target of 0.80, and the seed-bootstrap lower end is 0.997.
- The margin is wide, so 100 seeds is ample. The other 100 seeds stay unused for a later freeze.
- **Cost:** about 2 h of oracle and about 5 h of F on Arch with 14 workers (estimate from DEV).

## 4. Scoring rules (`score_validation_v2.py`, fixed)

**Decision, the same for every method:** the first sample at which no explanation with b = 0 and |noise| ≤ δ
exists. N = 3600.

**Sets, as in freeze 1:**
- F (fault runs), U (uncertified oracle), R (detection events) and A (admissible runs);
- every healthy run is admissible, edge noise included.

**Paired lag, as in freeze 1:**
- B = {r ∈ R : v2 detects r}.
- L_m = Σ over B of (f_m − t*). An F miss in B counts as N − t*.
- **D_paired = 1 − L_F / L_v2.**

**Verdict:**
- **INCONCLUSIVE:** the run is incomplete, the environment check failed, or |U| > 1 % of |F|.
- **FAIL:** any of the following:
  - a soundness violation (an alarm on a run in A, or an alarm before t*);
  - an uncertified alarm;
  - more misses than v2;
  - D_paired < 0.80.
- **PASS:** otherwise.

**Reported, not deciding:**
- runs later than v2;
- D_censored, exact matches with t*, lag quantiles, per cell and ambient law;
- the seed-cluster bootstrap (2000 resamples, rng seed 20261118);
- evictions, kept measurements, the largest LP size, and folds raised to their dual bound;
- the subgroups drift_0.0005/ramp and rw (pre-specified).

**For Can to decide:** whether "later than v2 on any run" should be a FAIL rather than reported. On DEV it is 0 for
F. There is no theorem behind it, and D_paired already counts every late detection.

## 5. DEV reference (DEV, not validation)

**Amendment 4 (E, no cap, on the Mac), on 1320 DEV rows:**
- D_paired 0.9992, with bootstrap [0.997, 1.0];
- 0 misses, 0 soundness findings, every alarm certified;
- equal to the dense S256 of 2a on every row.
- An independent scorer agrees to the last digit.

**TBD from amendment 6:**
- the audit (A1) and the pilot equality (A2);
- F with K = 64 on all 1320 rows (K1, K2), and K = 40 and 32 (the margin of the cap).

**TBD from amendment 7:** F on 80 edge-noise healthy runs (E1).

## 6. Order of operations

1. **Can reviews this file.** Any change he asks for is made, the manifest regenerated, and this file updated before
   approval.
2. **Approval.** The status line becomes exactly `Status: APPROVED by Can Koç on YYYY-MM-DD` in a commit that changes
   nothing else.
3. **Run.** On Arch: `run_validation_v2.py OUT`. It checks:
   - a clean tree;
   - the environment lock;
   - every manifest hash;
   - the quoted manifest sha256 and the approval line;
   - the seed block.

   Only then does it unlock the validation seeds.
4. **Score.** `score_validation_v2.py OUT`. Then a dated record with the verdict as it comes out, the per-cell table
   and the run hashes.
5. **Infrastructure failure** (a crash, a reboot, incomplete rows):
   - the identical command is rerun on the same block;
   - a needed code change outside the candidate and the rules gets a dated addendum here;
   - the candidate, the target and the scoring do not change.
6. **No reruns for any other reason, and no second look at another block for the same candidate.**

## 7. What this validation can not show

- **An MCU:** F solves about 4.6 LPs of up to about 400 rows per sample in Python. Nothing here measures memory or
  time on a microcontroller.
- **float32 or fixed point:** the certificate is float64.
- **Model mismatch or a real plant:** same plant, known parameters, simulated laws.
- **The ambient box:** detection of slow drifts leans on TA ∈ [23, 27] (section 1). A wider true range would make
  those detections later.
- **Sensor faults that an admissible ambient path reproduces:** they are invisible to every method (Theorem 4).
- **Independence beyond the seeds:** F was developed on DEV draws of the same laws.

## 8. DEV rehearsal of the full pipeline (DEV seeds, not validation)

TBD at the freeze commit: `run_validation_v2.py --rehearsal --seeds 430096 430097` (96 runs, edge noise included),
scored by `score_validation_v2.py`. These two DEV seeds have not been used before.
