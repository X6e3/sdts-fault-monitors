# v3 freeze 2: the compressed window F, and the rules of its independent validation

Status: DRAFT, not approved

Manifest sha256: 31d470aee8921a90fbaccd17c349ea7bb0e7fe868eaaa7e306458b6d971fa4a8

Prepared 2026-11-18 on branch `sdts-v3/template-state` for Can Koç's review. The target and the reading of a failure
are Can's to set. Everything here is a proposal until the status line says APPROVED. `run_validation_v2.py` refuses
to generate validation data until then (section 6).

**Open item:** the rehearsal is rerun at this freeze commit (section 8).

**Decided by Can Koç on 2026-11-19, after the team's review:**
- 200 seeds (section 3);
- "later than v2" is reported in full and does not decide (section 4).

This is not the approval of the freeze. That comes after the manifest is regenerated and the rehearsal rerun, as a
separate status-line commit (section 6).

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
unused seed block (440400 onwards).

## 1. The candidate

**The state between samples:**
- a base template at τ: cyl16p's 42 directions and its clamps (`frozen/cyl16p.json`, the freeze 1 file, unchanged);
- the measurements kept in the window, at most K = 64;
- τ itself.

**The window LP** (DIAG-3 amendments 3, 4, 6 and 8):
- It runs over the samples τ … t, with t − τ ≤ W + B = 272.
- **Exact step between nodes:** x_b = M^L x_a + Σ_{k<L} M^k e3 w_{b−1−k}, with |w_j| ≤ ρ explicit.
  - M^L is the exact rational power of the float64 matrix M, the same M as the simulator's and the oracle's, rounded
    once.
  - (ac, as) are kept at the nodes and TA at every sample.
  - The nodes are τ, the kept measurements, τ + 16 and the objective sample.
  - Between nodes ac and as stay in the box by convexity, so the only box rows needed there are TA's.
- **Measurements:** a measurement redundant at arrival is dropped. Dropping is sound, and lossless on DEV.
- **The cap:** above K kept measurements, the one inactive longest (its bound with a zero multiplier) is evicted. A
  newly kept measurement counts as active at arrival, and ties go to the oldest. Eviction is sound.
  - K counts the window after τ.
  - The reported `max_kept` also counts the measurement at τ, which the base already holds, so it can read K + 1.
- **The fold, every B = 16 samples:**
  - It uses the smoothing rule, with the measurements up to the fold sample.
  - Each of the 42 supports is max(LP value + 1e-6, certified dual bound), then clamped.
- **The alarm at t:**
  - It is computed from the measurements up to t − 1.
  - z_t is kept, evicted and folded only after the alarm check.
  - **F raises an alarm only when it is certified:** the certified as-range excludes z_t ± δ, with the slab rounded
    outward.
  - LP values that point to an alarm the bound cannot prove raise no alarm. z_t is then dropped, which is sound, and
    the case is counted (`unproved_primal_alarms`, reported).
- **The certificate:**
  - weak duality with the solver's multipliers;
  - every variable is boxed;
  - float rounding is bounded explicitly;
  - the coefficients' own rounding is enclosed (each is correctly rounded from its exact value);
  - the measurement slabs are rounded outward.

  So the bound holds for the LP with exact coefficients, whatever the solver's tolerance.
- **An empty window LP** cannot happen with sound folds. If it does, at an as-range or at a fold, it is recorded as
  an uncertified alarm, which is a FAIL.

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

| commit | content |
|---|---|
| `66429e2` | F: the hardened certificate, outward slabs, the cap K and the eviction rule; the audit variant (DIAG-3 amendment 6) |
| `b74de88` | the freeze 2 runner, scorer and manifest writer; `diag3_cw_dev.online()` (same behaviour, checked on DEV rows) |
| `0e28951` | F raises certified alarms only, the alarm slab rounded outward, an empty fold LP recorded as an uncertified alarm; the scorer's later-than-v2 report (DIAG-3 amendment 8) |
| `ad8ed35`, `1ab76fd` | this file: 200 seeds, the review fixes, Can's decisions |
| `1fa5180` | amendment 8's checks T1 and T2 (DIAG-3-RESULTS) |
| this commit | `frozen/MANIFEST-V2.json` regenerated (block 440200–440399, the code of `0e28951`), and this file |

The frozen code is that of `0e28951`. No file in the manifest changed after it, so amendment 8's checks ran the
frozen code.

`frozen/MANIFEST-V2.json` (sha256 above) fixes:
- the data block, cells and laws;
- the candidate (variant F, W = 256, B = 16, K = 64, pad 1e-6, the direction file by sha256) and its target;
- every file the validation depends on, by sha256.

`run_validation_v2.py` refuses to run if any of them differs.

Freeze 1's files below are unchanged: their hashes are those of freeze 1's manifest.

| file | sha256 |
|---|---|
| `experiments/v3/run_validation_v2.py` | `860f2e4ba72ac4627bab7d8f55f343ac461f653f73b8e46152ad40360583a0e1` |
| `experiments/v3/score_validation_v2.py` | `2db2de5eb37cd094f7116400fdaa7d9593658b2f9bfeaae5bcd768e7247a0da6` |
| `experiments/v3/run_validation.py` | `9cb899ea770dd8b60e37e80c6686a77ef5a662d3b7a5e5f41a294a23111920a3` |
| `experiments/v3/score_validation.py` | `96c347455888d3f8944788941e6920121ef36f444f0e3bcd4a8f105bbb9104da` |
| `experiments/v3/template_state.py` | `6f8409274cdc583f3ed48aca372fc08fccd9970f106ae516291f39a5a6894666` |
| `experiments/v3/dev_scenarios.py` | `a1b204efde095c4d36d2aab4ca503970386a2761485b3c84f3ec8da2503c363f` |
| `experiments/v3/diag/diag1.py` | `698cb0b0ad81d1501caebf458db4aad924b888cb14b9b81794a31300dfdd382b` |
| `experiments/v3/diag/diag3.py` | `ce64b0ef2d6d477715252f0a0285b2400f585083f34b1f37a6305c07f54b3ad1` |
| `experiments/v3/diag/diag3_dev.py` | `0dbba0562ae633807615d043c481db70b71167f4666be6de6ed0fdf309efcfb9` |
| `experiments/v3/diag/diag3_cw.py` | `e88e2b78a127e49e722edfb2f4e1115ad584c5e30541811b2e833215881763d0` |
| `experiments/v3/diag/diag3_cw_dev.py` | `3af34bcf9cba5f79b2ffb0061e2acce4a9fd2d87d8560f216811ae4cd339c03e` |
| `experiments/v3/frozen/cyl16p.json` | `7f9cc8700fdd70782ddaf4a7e99a2e2c2f5818ce4aafa970f897b40e90a7747e` |
| `experiments/generators/thermal.py` | `d742012e138402525382eee26e0d6dba87bd224267dc733a75f1e693f98ce481` |
| `experiments/oracle/thermal_oracle.py` | `7f4b8da3064675e29f88a7f676e8d0318982fdbde1b5b355e1c83d2238f92e74` |
| `experiments/machine/thermal_machine.py` | `0337f7b8520ff581ef8ec7d321de2cd69458396c44c0bbfb43bbdb34a78f2796` |
| `env/thermal_v2_env.py` | `40740690aa7a0cea680e7496b391e1632a796075afcb1206b153e61a873644b6` |
| `env/requirements-thermal-v2.txt` | `7f25d6435e8b664fe179e4cc57ec7c36b61c9f32ad9c7285a1723e3612b4cd2d` |

**Environment:** the thermal v2 lock (`env/thermal_v2_env.py`): CPython 3.12.13, numpy 2.5.5, scipy 1.18.1 and
HiGHS 1.12.0. It is checked at start and recorded.

## 3. Data

**Seeds 440200–440399** (200 seeds), generated only after approval, by `run_validation_v2.py`. They use freeze 1's
validation namespace (`v3val:`) and laws. 440400–440999 stay reserved.

**Per seed, 48 runs, as in freeze 1:**
- 11 cells × arms E0, E1 × ambient `rw`, `ramp` with uniform noise;
- plus healthy × E0, E1 × `rw`, `ramp` with `edge` noise.

That is 9600 runs in total: about 7400 detection events at the rehearsal's rate, and 1600 healthy runs (800 of them
with edge noise).

**Why 200 seeds:**
- **The 80 % target alone would not need them.** On DEV, F's point is 0.999 and the bootstrap lower end is 0.997.
  That bootstrap resamples DEV's 30 seeds, though, and says nothing about behaviour DEV never showed.
- **The weak spot is the tail.** W = 256 fails only on very slow drifts whose deciding cut comes more than 256 samples
  before t*; DEV had one such seed in 30. 200 seeds sample that tail about twice as well as 100.
- **The healthy runs.** If none of the 1600 healthy runs alarms, the per-run false-alarm rate is below about 0.19 %
  at 95 % (rule of three). Soundness itself rests on the certificate, not on this count.
- **The same block size as freeze 1,** so the two validations have the same design.
- **Cost:** about 12.6 h on Arch with 14 workers, at the rehearsal's rate (section 8). 600 seeds stay unused.

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
- runs later than v2, each with its cell and the delay; the largest positive t_F − t_v2; and the runs where v2 detects
  and F misses (which also count in the misses rule);
- the unproved LP alarms (section 1);
- D_censored, exact matches with t*, lag quantiles, per cell and ambient law;
- the seed-cluster bootstrap (2000 resamples, rng seed 20261118);
- evictions, kept measurements, the largest LP size, and folds raised to their dual bound;
- the subgroups drift_0.0005/ramp and rw (pre-specified).

**Why "later than v2" does not decide:** there is no theorem behind it, and D_paired already counts every late
detection. On DEV it is 0 for F. It is reported in full (above).

## 5. DEV reference (DEV, not validation)

All of this is in `diag/DIAG-3-RESULTS.md`. The plans and criteria were committed before each run.

**The candidate itself:** F, K = 64, on the 1320 DEV comparison rows (`results/v3/diag3/cwdev-F-K64-66429e2/`, Arch,
at `66429e2`). At the frozen code (`0e28951`, amendment 8) it detects identically on every row, with all 1082 alarms
certified and no unproved LP alarm (`cwdev-F-K64-0e28951/`).

| | v2 | cyl16p (freeze 1) | **F** |
|---|---|---|---|
| detection events R (certified) | 1081 | 1081 | 1081 |
| misses | 8 | 4 | **0** |
| exact match with t* | 805 | 897 | **1079** |
| lag max (s) | 2880 | 2880 | **13** |
| paired set B, L (s) | 1073, 32925 | 20222 | **26** |
| **D_paired** | — | 0.386 | **0.99921** |
| without the 10 diagnosis rows | — | 0.512 | 0.99875 |
| bootstrap 95 % (descriptive, 30 seeds) | — | [0.20, 0.60] | [0.997, 1.0] |
| soundness violations / uncertified alarms | 0 | 0 | 0 / 0 |
| runs later than v2 | — | 0 | 0 |
| evictions | — | — | 0 (at most 45 kept) |

**The checks behind it:**
- **Equal to the uncompressed window.** F equals E (amendment 4, the Mac) on every row, and E equals 2a's dense S256
  (Arch) on every row. An independent scorer, and an independent implementation of E on 42 selected rows, agree.
- **The certificate audit (A1, A2).** 5,676 bounds were checked in exact rational arithmetic, with no violation (the
  smallest slack is 4.4e-15 °C). A second, independent exact audit of 84 alarm bounds also found none.
- **The cap.**
  - With K = 40, F evicts 420 measurements on 161 rows and still equals E on every row.
  - With K = 32 (informational), F evicts 21,821 measurements on 960 rows and still equals E on every row.
- **Edge noise (E1).** There is no alarm on 80 healthy edge-noise runs (DEV seeds 430070–430089), at `ca407ca` and
  again at the frozen code. Under edge noise
  no measurement is redundant at arrival, so F runs with the cap full and evicts one measurement per sample. LP rows
  reach at most 445.
- **The window length.** For W = 64, 128 and 192, D_paired is 0.643, 0.815 and 0.824 (0.904, 0.980 and 0.986 without
  the diagnosis runs). W = 256 is the shortest window tried that holds 430010's deciding cut, 227 samples before t*.

**How W = 256 and K = 64 were chosen.**
- W was chosen on five DEV runs (DIAG-3 phase 1) and confirmed on all of DEV.
- K = 64 is the DEV maximum (45) plus a margin. Edge noise shows that the cap can be reached.
- Neither was tuned on any seed outside DEV.

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
   - the identical command is rerun on the same block, into a new output directory (the runner refuses an existing
     one);
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
- **Detection under noise at its bound:** with edge noise the cap is full and F evicts at every sample. The
  validation's edge-noise runs are healthy, so they test soundness only, not detection.
- **Sensor faults that an admissible ambient path reproduces:** they are invisible to every method (Theorem 4).
- **Independence beyond the seeds:** F was developed on DEV draws of the same laws.

## 8. DEV rehearsal of the full pipeline (DEV seeds, not validation)

The identical pipeline was run on DEV seeds 430096–430097 (`--rehearsal`; validation stays locked).

**Run:**
- `run_validation_v2.py` at `cfb7f18` on Arch, from a clean checkout, 14 workers.
- The checks passed: the manifest `ae2e10c9…` and the environment lock (CPython 3.12.13, numpy 2.5.5, scipy 1.18.1,
  HiGHS 1.12.0).
- 96 runs (2 seeds × 48) in 453 s. Rows sha256 `d5b352faf42ecf0f4e4ea36c66a40f890e7a429f7f8abf85ada36c7071c0e6f5`.
- Scored with `score_validation_v2.py`. The outputs are in `results/v3/freeze2/rehearsal-dev-430096/`. The solver
  attempts (4.8 MB) stay on Arch.
- These two DEV seeds had not been used before.

**Pipeline checks:**
- complete: 96 of 96 rows;
- 0 uncertified oracle runs;
- 74 detection events;
- 22 admissible runs, the 8 edge-noise healthy runs included.

| | soundness | uncertified alarms | misses | later than v2 | D_paired | detections equal to t* |
|---|---|---|---|---|---|---|
| F (W = 256, K = 64) | 0 | 0 | 0 (v2: 0) | 0 | 1.0 (L_v2 = 994 s) | 74 of 74 |

**What the rehearsal shows:**
- **The pipeline works end to end:** generation, oracle, v2, F and scoring.
- **On the 8 edge-noise runs F evicts at every sample** (28,280 evictions; up to 65 kept and 445 rows), with no
  alarm, as in amendment 7.
- **Two DEV seeds say nothing about the target.** D_paired = 1.0 here is not evidence for H-F.
- **Expected validation time:** 4800 runs at this rate is about 6.3 h on Arch with 14 workers.
