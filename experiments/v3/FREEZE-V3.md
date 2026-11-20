# v3 freeze 3: F3, the compressed window with a sound path for solver failures, and the rules of its validation

Status: DRAFT, not approved

Manifest sha256: 0a40cbdf863da6eb046a1c76726d53bf2e967bfa3e0056b1ac15b87cbc7b85c7

Prepared 2026-11-20 on branch `sdts-v3/template-state` for Can Koç's review. The target and the reading of a failure
are Can's to set. Everything here is a proposal until the status line says APPROVED. `run_validation_v3.py` refuses
to generate validation data until then (section 6).

**Before review: every item is in.** Section 5 holds each record, section 8 the rehearsal.
- I2a, I2b and I2c pass, and so does I3, so R1–R3 stand for the frozen code. U1, U2 and U3 pass.
- The fourth and fifth addenda (reviews M1 and M2, Can's decisions 2026-11-20): U0b and U0c pass. Review M3 is in.
- U5 and U5b: the slab rule's condition is met (section 4).
- The scorer tests (section 4): review M2's 20 constructed row sets, at the frozen scorer, all as expected.
- The independent summary of the R runs (review K7d) agrees.
- The manifest at the frozen code (section 2), and the DEV rehearsal at the manifest's commit: passes (section 8).

**Decided by Can Koç on 2026-11-20:**
- the slab rule (section 4): reported, not deciding, on the conditions written there;
- the seed block (section 3): 440400–440599, 200 seeds, as freeze 1 and 2;
- the target (0.80), W = 256, B = 16 and K_cap = 64: unchanged;
- the fourth addendum: solver exceptions and non-finite answers are failures with their own reason codes; our own
  errors are raised, never counted as fallbacks;
- no approval before I2, U0b, U1–U3, U5 and the scorer tests are in.

## 0. What is tested, and why there is a freeze 3

**Freeze 2 failed** (`RECORD-2026-11-19-validation.md`).
- On 440200–440399, F reached D_paired 0.995 against a target of 0.80, with no miss and never later than v2.
- On one healthy edge-noise run (440243 E0 ramp), one fold LP failed in HiGHS (status 15, "Unknown", in all three
  attempts). F recorded it as an uncertified alarm, as its rules said, and freeze 2's verdict is FAIL.
- The diagnosis (same record) found the failure deterministic and the rest of the fold sound. The other 41 faces
  bound the failed direction at −0.209 °C. What F lacked was a sound path for an LP the solver does not solve.

That verdict stands. Freeze 3 is a new candidate with a new seed block, as FREEZE-V2.md section 0 requires.

**One hypothesis, H-F3.** It is about the **float64 reference implementation**: Python, with HiGHS through scipy, in
`diag/diag3_cw.py`, variant F3.

The frozen F3:
- is sound under the model: no alarm on an admissible run, and none before the oracle's t*;
- certifies every alarm it raises;
- misses no more oracle-detected events than v2, in total;
- and reduces v2's paired lag (section 4) by **at least 80 %**;

all on fresh seeds of the v3 scenario distribution. The target, W = 256, B = 16 and K_cap = 64 are freeze 2's,
unchanged (Can's decision, 2026-11-19).

**A FAIL rejects H-F3 at this configuration, and nothing else.** It does not reject:
- freeze 1's results (H-inv4 and H-cyl16, validated on 440000–440199);
- the DIAG-3 analysis;
- other window lengths, caps or formulations;
- the SDTS question itself.

**A PASS supports only the hypothesis as written:**
- the same plant with known parameters;
- the simulated ambient and noise laws of `dev_scenarios.py`;
- a float64 desktop implementation.

It says nothing about an MCU, float32, a real plant or model mismatch (section 7).

After the result, neither the candidate nor any rule changes. A new or modified candidate is a new freeze with the
next unused seed block (440600 onwards).

## 1. The candidate

**F3 is F (FREEZE-V2.md section 1, unchanged and not repeated here) with two additions:** a sound path for every LP
the solver does not solve (DIAG-3 amendment 10, its N2 and AG1 addenda), and an exact memory bound (its third
addendum).

**The solver path.** Every LP that F3 solves has two outcomes only. It is **solved** (scipy status 0, after at most
the three attempts of F: `highs-ds` without presolve, `highs-ipm` without presolve, `highs-ds` with presolve), or it
has **failed** (any other status, an empty slab included). F3 never uses a value from a failed LP.

| what the solver returns | F3's outcome | what F3 may use from it |
|---|---|---|
| status 0 (optimal) | solved | an alarm bound: its certified weak-duality bound (`certified_max`). A fold bound: max(value + PAD, certified bound), never below the certified bound, on which its soundness rests. An as-range side: its value, as a gate only (below) |
| status 2 (infeasible) | failed | nothing. A solver's "infeasible" is not a certificate, and on admissible data the window is never empty, so F3 never reads it as a proof of a fault |
| status 4, any other status | failed | nothing |
| an empty slab, before any solve | failed (kind `slab`) | nothing |
| an exception from the solver call (`RuntimeError`, `ValueError`, `IndexError`, `OverflowError`, `ZeroDivisionError`, `FloatingPointError`) | failed (kind `exception`; fourth addendum) | nothing |
| status 0 with a non-finite value or multiplier, or a non-finite certified bound | failed (kind `nonfinite`; fourth addendum) | nothing |
| a non-finite or inconsistent LP input, `MemoryError`, any error outside the solver call | not a solver outcome: our own error. It is raised, never counted as a fallback. A `RuntimeError` (or a subclass) raised in a fold ends the run with an uncertified alarm (scored FAIL). Any other error, in a fold or elsewhere, stops the run. The gaps review M2 found at `8c55e19e` are closed by the fifth addendum (`b57b5a39`; review M3a). Known limits that remain (review M3a), none of which F3's own LP builders can produce: an LP with no variables passes the check and is counted as a solver `exception`; a solver answer with no multiplier field at all raises `AttributeError` and stops the run | nothing |

F and F3 differ here on purpose. F read status 2 as "the window is empty" and stopped. F3 has no third outcome:
infeasible is one more way to fail. An alarm needs a certified separation, never a solver's claim.

| where the LP fails | what F3 uses instead | why it is sound |
|---|---|---|
| one side of the as-range | that side's box bound (HI = 2 or LO = −2); z_t is not kept | the box contains every state |
| one side of the alarm certificate | that side's box bound | the same |
| one direction of a fold | the certified maximum over P_J ∩ box, J = the solved faces of the same fold; if that 3-variable LP fails too, the a priori clamp | the ideal window's states lie in P_J ∩ box |
| every direction of a fold | an atomic reset: base = the a priori clamps, no kept measurements, τ += B | the clamps hold under the exact recurrence |

- The as-range values and the certificate bounds are always clipped to the box (N2 addendum). A z_0 outside the box
  raises a box-certified alarm at t = 0.
- The as-range is a gate, not a bound (review M1, G3). Its solved side is the LP's primal value, not certified. It
  decides only whether to try a certificate and whether to keep z_t. No alarm and no fold bound uses it, and both of
  its decisions are sound whatever the value: an alarm still needs its certificate, keeping z_t adds a constraint that
  admissible data satisfy, and dropping it only widens the window.
- An empty slab cannot occur after t = 0: a z_t whose slab misses the box fails the alarm test against the clipped
  range and is never kept (N2 addendum). It is counted all the same (section 4).
- Every fallback is counted by its kind (status 2, status 4, slab, exception, nonfinite, other) in the record's
  `failsafe` field.

**The memory bound** (third addendum). The eviction comes before the keep, and the eviction record is pruned with
the window. So, at every point of every step, at most K_cap + 1 = 65 measurements are held. At the end of every step
the eviction record has no key outside them; inside an eviction or a fold, between two assignments, it briefly can
(review M1, G4; the third addendum's "at every point" is too strong for this half). Neither change alters a
decision (section 5, I1).

**What is a theorem and what is not:**
- **Soundness** holds by construction under the model, by FREEZE-V2.md's invariant chain with one more link: each
  fallback above is a superset bound of what it replaces. The written proof, checked against the code, is review M1
  (section 5). It proves S1 (no alarm on an admissible run) and S3 (every alarm separates z_t's slab from a certified
  outer bound) under the model and a stated floating-point model, with the solver reporting every failure as a
  status. Its gaps G1 and G2 are where that last condition can break. The fourth addendum closes them in part and
  the fifth closes the rest (reviews M2 and M3a; table above).
- **The floating-point model** (fifth addendum): IEEE binary64, round to nearest with ties to even, gradual
  underflow. A product's error beyond the relative model is at most 2^−1075, sums and differences need no absolute
  term, and `math.fsum` is correctly rounded and not regrouped. Under this model and the candidate's sizes (W = 256,
  B = 16, every box within ±2), every finite strict bound is an upper bound of the ideal LP: L1 restated with the
  underflow term (review M3b). The term's exactness is shown for these sizes only. For other boxes it must be shown
  again (review M3a).
- **The audit variant F3a** is a check of F3, not part of the candidate. One of its extra statistics (the
  coefficient term) is evaluated outside the error-state guard of the strict bound. Under `np.errstate(all="raise")`
  it can raise; every run used numpy's default state (review M3a).
- **No alarm on a healthy run, and none before t\*:** as FREEZE-V2.md section 1. The fallbacks only widen F3's sets,
  so they can only remove or delay alarms.
- **Outside the chain:** the solver's tolerance, and how often the solver fails. Freeze 2 saw one failed fold LP
  among 54,535,429 LPs. That is a count, not a rate.
- **There is no dominance theorem over v2.** Runs where F3 is later than v2 are reported, not judged.

**Plant and assumptions:** those of v2 and of freeze 2, unchanged (`thermal.py`, δ = 0.3, ρ_A = 0.002 °C/s,
TA ∈ [23, 27], start at the P0 = 20 steady state, record length 3600). The ambient box matters to the result, as in
freeze 2.

## 2. Code, commits and hashes

| commit | content |
|---|---|
| `84a2639e`, `9d7cf058` | freeze 2's validation record, FAIL, and its independent scoring |
| `6bff6e9b`, `66fcfcc5` | the diagnosis of the deciding fold |
| `e1b30ca7` | DIAG-3 amendment 10, the plan: F3, the runs R0–R4 and the criteria U0–U4 |
| `17a1dc69`, `e52f5192` | its code and the R4 script (the runs at `17a1dc69` were stopped unread after review N2) |
| `84b3c234`, `0ce80072` | the N2 addendum and the code after it |
| `8d5ba0e7`, `f9dcb508`, `6c3af845` | the AG1 addendum, two precisions, and the exact criteria in the summary; F3's code unchanged |
| `000cd215` | the third addendum: the memory bound (F3 only) |
| `d207c9d1` | R0, R4 and I1a results |
| `b25aae66` | `run_validation_v3.py`, `score_validation_v3.py`, `make_manifest_v3.py` and this file |
| `8e9357fe` | the slab rule and the seed block decided; review M1 folded in |
| `8c55e19e`, `1c0439cd` | the fourth addendum (the solver boundary), and the U5 script before it ran |
| `8eae9517` | U0b, R0 and I2a pass; U5 fails as written |
| `a6f6af87` | R1 and R2 results (U1 and U2 pass) |
| `44c95dbe` | review M2 folded in; the fifth addendum proposed |
| `b57b5a39` | the fifth addendum applied: `diag3_cw.py` as frozen, with the U0c and I3 scripts |
| `1ca4df40` | I2b as set by Can, and its script, before it ran |
| `1798a822` | review M3 folded in; no sixth addendum |
| `855d7f8a` | R3 (U3 passes) and the fifth addendum's tests (U0c, I2a, I3 and I2c pass) |
| `44ddd682`, `d2683a02` | U5b, its script before it ran, and its result (passes) |
| `d3b4f61c` | the slab rule's U5 condition met (Can's decision) |
| `e81c549b` | the manifest at the frozen code; the DEV rehearsal ran at this commit |
| this commit | I2b, review K7d and the rehearsal recorded |

**The tooling is freeze 2's, with F3 in place of F.**
- `run_validation_v3.py` is `run_validation_v2.py` with the V3 manifest and document, the record key `F3`, and the
  `failsafe` counters added to the record.
- `score_validation_v3.py` calls `score_validation_v2.score()` unchanged, with F3's record in F's place. Scored on
  freeze 2's own rows, it gives freeze 2's scores, field for field (checked when it was written).

`frozen/MANIFEST-V3.json` fixes the following. Its sha256 is above. It was generated on 2026-11-20 at the frozen
code, with `diag3_cw.py` as at `b57b5a39`.

It fixes:
- the data block, cells and laws;
- the candidate (variant F3, W = 256, B = 16, K_cap = 64, pad 1e-6, cyl16p's directions by sha256) and its target;
- every file the validation depends on, by sha256: freeze 2's list, with the V3 runner and scorer, and the V2 scorer
  that the V3 scorer imports.

`run_validation_v3.py` refuses to run if any of them differs.

| file | sha256 |
|---|---|
| `experiments/v3/run_validation_v3.py` | `b834073700ef7784fdcd14df09acb95f821e610362b1b1e63f886ba598c7f3f9` |
| `experiments/v3/score_validation_v3.py` | `f32d74931b7b714aa3cf1b65d25d7c8908c26838c7619195793f07e52bc70696` |
| `experiments/v3/score_validation_v2.py` | `c46c092b8c2574cc62daf25d7f12e9967f27bf1475cec710d08ce68d6d1e2ba5` |
| `experiments/v3/run_validation.py` | `9cb899ea770dd8b60e37e80c6686a77ef5a662d3b7a5e5f41a294a23111920a3` |
| `experiments/v3/score_validation.py` | `96c347455888d3f8944788941e6920121ef36f444f0e3bcd4a8f105bbb9104da` |
| `experiments/v3/template_state.py` | `6f8409274cdc583f3ed48aca372fc08fccd9970f106ae516291f39a5a6894666` |
| `experiments/v3/dev_scenarios.py` | `a1b204efde095c4d36d2aab4ca503970386a2761485b3c84f3ec8da2503c363f` |
| `experiments/v3/diag/diag1.py` | `698cb0b0ad81d1501caebf458db4aad924b888cb14b9b81794a31300dfdd382b` |
| `experiments/v3/diag/diag3.py` | `ce64b0ef2d6d477715252f0a0285b2400f585083f34b1f37a6305c07f54b3ad1` |
| `experiments/v3/diag/diag3_dev.py` | `0dbba0562ae633807615d043c481db70b71167f4666be6de6ed0fdf309efcfb9` |
| `experiments/v3/diag/diag3_cw.py` | `1d68dc6b586c4928bdde098019a60eb57e3d84072643cd89b6ed92909be51fb3` |
| `experiments/v3/diag/diag3_cw_dev.py` | `a911bf9969fc156f3191d2b946ad5654d79615532b699d3622c41879e894dce4` |
| `experiments/v3/frozen/cyl16p.json` | `7f9cc8700fdd70782ddaf4a7e99a2e2c2f5818ce4aafa970f897b40e90a7747e` |
| `experiments/generators/thermal.py` | `d742012e138402525382eee26e0d6dba87bd224267dc733a75f1e693f98ce481` |
| `experiments/oracle/thermal_oracle.py` | `7f4b8da3064675e29f88a7f676e8d0318982fdbde1b5b355e1c83d2238f92e74` |
| `experiments/machine/thermal_machine.py` | `0337f7b8520ff581ef8ec7d321de2cd69458396c44c0bbfb43bbdb34a78f2796` |
| `env/thermal_v2_env.py` | `40740690aa7a0cea680e7496b391e1632a796075afcb1206b153e61a873644b6` |
| `env/requirements-thermal-v2.txt` | `7f25d6435e8b664fe179e4cc57ec7c36b61c9f32ad9c7285a1723e3612b4cd2d` |

Validation block: seeds 440400–440599; 440600–440999 stay reserved. Record length 3600 samples.

**Environment:** the thermal v2 lock: CPython 3.12.13, numpy 2.5.5, scipy 1.18.1 and HiGHS 1.12.0. It is checked at
start and recorded.

## 3. Data

**Seeds 440400–440599** (200 seeds; Can's decision, 2026-11-20), generated only after approval, by `run_validation_v3.py`. They use the
validation namespace (`v3val:`) and the laws of freeze 1 and 2. 440600–440999 stay reserved.

**Per seed, 48 runs, as in freeze 1 and 2:** 11 cells × E0, E1 × `rw`, `ramp` with uniform noise (44 runs, 4 of them
healthy), plus healthy × E0, E1 × `rw`, `ramp` with edge noise (4 runs). That is 9600 runs: about 7300 detection
events and 1600 healthy runs, 800 of them with edge noise.

**Why 200 seeds again:**
- the same design as freeze 1 and 2, so the three validations compare directly;
- freeze 2's single failure came from 800 edge-noise runs, where F3's fallbacks matter most. 200 seeds give 800 again;
- cost: about 12–13 h on Arch with 14 workers (freeze 2: 11.6 h).

**Freeze 2's block (440200–440399) is not reused.** Its run 440243 was replayed for R4, so that block is no longer
a holdout for anything.

## 4. Scoring rules (`score_validation_v3.py`, fixed)

**Freeze 2's rules, unchanged** (FREEZE-V2.md section 4), with F3 in place of F:
- the decision, the sets F, U, R and A, every healthy run admissible;
- the paired lag, D_paired = 1 − L_F3 / L_v2 over B = {r ∈ R : v2 detects r}, an F3 miss in B counting N − t*;
- the identity and integrity checks;
- the verdict order: INCONCLUSIVE (integrity) → FAIL (a soundness violation or an uncertified alarm) → INCONCLUSIVE
  (missing rows, |U| > 1 % of |F|) → FAIL (more misses than v2, D_paired < 0.80) → PASS.

**Reported, not deciding:** as freeze 2, plus F3's `failsafe` counters summed over the rows, the number of rows with
any fallback, the count of empty-slab failures, and each row that has one.

**The slab rule** (Can's decision, 2026-11-20): an empty slab after t = 0 is reported, not deciding. F3 handles it
soundly, like any failed LP, and the hypothesis is about soundness and lag, not about which path ran. Two conditions
come with it:
- **Any empty slab in the validation is an invariant violation.** Section 1 says it cannot happen. The scorer lists
  each row that has one, with its count by counter (role). The sample is found by replaying the row, which is
  deterministic. The cause is found and written down before any claim is made from the result. The verdict does not
  change.
- **U5 passes before approval.** U5 forces the empty-slab path on DEV rows and checks that the fallback keeps the true
  state (below). **Met** (Can, 2026-11-20). U5 failed as written, but only on two fault rows the oracle itself does not
  detect. Its healthy part passed, and U5b passed the fault part on rows the oracle detects, with nothing else
  changed.

**U5, the forced-fallback coverage test** (DEV seeds 430000 and 430001, F3a, its plan committed before it runs):
- **Rows:** the 16 healthy rows of the two seeds (8 uniform noise, 8 edge noise) and 4 fault rows.
- **Forcing:** at t = 300, 1000 and 2000, a measurement whose slab misses the box is put into the window directly,
  past the keep gate (as R0 does). Every LP that holds it fails with kind `slab`, until the next fold resets.
- **Truth:** the generator's own states in the model's coordinates, x = (Tc − Sc, Ts − Ss, TA) − 25, with S the
  known command response at zero ambient.
- **Pass if all hold:**
  - no alarm on a healthy row, and every alarm on a fault row certified;
  - at every fold, the true state at τ satisfies d_i·x ≤ base_i + 1e-9 °C for all 42 directions;
  - at every alarm certificate computed, the true a_s at t lies inside its two certified bounds;
  - each forcing leads to slab failures and one full reset, and the counters say so;
  - every fault row detects after the last reset (the lag is reported);
  - the exact audit finds no violation.

**Tests of the scorer** (before approval): small constructed row sets, one for each branch of the verdict order and
one for each counter (failsafe totals, rows with a fallback, the slab list). Each expected output is written down
before the test runs. Freeze 2's rows, scored again, give freeze 2's numbers exactly (done: FAIL, 0.9949).

## 5. DEV reference (DEV, not validation)

All of this is in `diag/DIAG-3-RESULTS.md`. The plans and criteria were committed before each run.

**F3 without failures equals F (U1, R1): passes.** Arch, at `0ce80072`, on the 1320 DEV comparison rows and the 80
edge-noise rows.
- F3 detects at the same sample as F on every row, with the same certified margin.
- 1082 certified alarms, all on fault rows; none on a healthy or edge-noise row.
- No fallback occurred.
- D_paired is 0.99921 with no miss: F's DEV reference in FREEZE-V2.md section 5.

**F3 with simulated failures (U2, R2): passes.** Settings a–f.
- Every setting:
  - is complete;
  - has no alarm on an admissible row, no early alarm, and no uncertified alarm;
  - keeps at most 65 measurements;
  - has counters equal to the injection log on every row;
  - has no slab failure.
- Every fallback counter is above 0 for both injected status kinds.
- In setting d, 1,019 fault rows detect after a full reset.
- Reported:
  - a, b and e (fold directions failing, with the P_J or the a priori fallback) change no detection;
  - c: D_paired 0.944, 18 later detections, 37,122 measurements dropped;
  - d: −5.19, 40 misses;
  - f: −29.33, 232 misses.
- Each failure made a detection later or missed it, never wrong. Setting f fails every upper certificate. An alarm
  that only the upper side can prove then waits until z leaves the box.

R1 and R2 ran at `0ce80072`. They stand for the frozen code only if every I2 record is equal (below). I2a, I2b and
I2c pass, so they do.

**The exact audit (U3, R3 on the Mac): passes.** F3a on settings a, b and e: 12,572,172 bounds audited in exact
rational arithmetic, 425,757 of them P_J bounds, with no violation. The smallest slack is 8.2e-16 °C, and 1.7e-14 °C
for a P_J bound. On all 4,200 rows F3a on the Mac detects at the same sample as F3 on Arch.

**The path tests (U0, R0): 13 of 13 pass.**

**440243 (U4, R4): passes.** F3a runs all 3599 steps with no alarm. At t = 945 direction 40 fails, as in freeze 2,
and the fallback takes the P_J bound −0.20897 °C from the 41 solved faces (a priori 1.683 °C). The exact audit of
9,634 bounds, the P_J bound among them, finds no violation.

**The memory bound (I1).**
- I1a (Mac): with and without the third addendum's change, 16 records on 8 rows under settings none and d are equal
  in every field but wall-clock time.
- With the change, |zs| ≤ 65 and the eviction record ⊆ zs at all 48,460 checks, taken after each step. Without it,
  66 and 317.
- I1b is replaced by I2 (fourth addendum), which compares the frozen code with 0ce80072 directly:
  - **I2a (Mac): passes.** The 16 records of I1a, new code against 0ce80072: equal in every field but wall-clock
    time; |zs| ≤ 65 and the record ⊆ zs at all 48,460 checks.
  - **I2a again at `b57b5a39`** (the fifth addendum): passes.
  - **I2c (Arch, `b57b5a39`): passes.** For 440243 with F3a, these equal R4 of the R1–R2 drive:
    - the record, but for wall-clock time;
    - the audit of 9,634 bounds;
    - the implied-bound log.
  - **I3 (`b57b5a39`): passes.** 90,153 strict bounds are equal bit for bit to the fourth addendum's, on R0's and
    I2a's rows.
  - **I2b (Arch, at `1ca4df40`, which holds `b57b5a39`'s code): passes.** 1,860 records, selected before the run:
    - all 1,400 of setting none;
    - 140 each of b, d and e (every tenth job);
    - 20 more each of d and e, those with the most fallback events in R2.

    Every one equals the `0ce80072` record in every field but wall-clock time. 10 workers, 11:30–13:37.
- **U0b: passes, 10 of 10**, and R0 13 of 13 at `8c55e19e`, and both again at `b57b5a39`. Solver exceptions and
  non-finite answers take their fallbacks under their own reason codes. Our own errors (a NaN input, a `TypeError`
  in a fold, a `MemoryError`) propagate.
- **U0c: passes, 4 of 4** at `b57b5a39`. These are M2's witnesses:
  - malformed inputs raise before any solver call;
  - multiplier arrays of the wrong length fail as `nonfinite`;
  - the underflow LP's strict bound is 15 · 2^−1074 ≥ 2^−1076;
  - the overflow case returns NaN under `np.errstate(all="raise")`.
- **U5: fails as written, on 2 of 7 criteria, both about fault rows.** Two of its four fault rows (stuck, E0) have no
  oracle detection, so no sound method can detect them, and F3 does not, forced or not. Everything about the
  fallback passes: no alarm on 16 healthy rows; the true state inside the new base at all 3,388 checked folds
  (closest −0.00023 °C); one full reset per forcing; no audit violation; the two drift rows detect at the oracle's t*,
  forced or not. The certificate-coverage check was never exercised.
- **U5b: passes, all 8 criteria** (Can's OK, at the frozen code). This is U5's fault part on four rows the oracle
  detects: 430000 and 430001 × drift_0.002 E0 and stuck E1.
  - Each forcing at 250 gives one full reset, 23 samples later.
  - The true state stays inside the base at every fold before the onset (closest −0.00026 °C).
  - Every row detects at the oracle's t*, certified, after the reset, forced or not.
  - The exact audit finds no violation.
  - The certificate check again had no case. No certificate was computed up to an onset.
  - Can, 2026-11-20: U5's healthy part and U5b together meet the slab rule's condition (section 4). U5 stays
    recorded as failed as written.

**Independent reviews:**
- **N2 (code) and AG1 (documents against code):** their findings were closed by the addenda before any R1–R3 result
  was read. F3's code changed only after N2.
- **K7 (robustness, an independent harness):**
  - 85 pre-registered cases with 259,416 simulated solver failures and 1,668 full resets;
  - no alarm on an admissible run, no early alarm, no crash and no slab;
  - all 27 alarms re-certified by an independent rational checker;
  - 95,963 P_J bounds checked by exact vertex enumeration, none below the exact maximum;
  - 440243's fallback confirmed independently: exact maximum −0.208974, bound −0.208973.
  - Its two memory findings are what the third addendum closes.
  - **K7d, the independent summary of R1–R2: agrees.** It was computed from the raw row records alone, with its own
    code:
    - all 7 settings are complete, 1,400 keys each, none missing, extra or repeated;
    - the 2,453,323 injected LP failures in 9,800 rows equal the `failsafe` counters row by row. No LP was lost to a
      natural failure, and there was no slab;
    - U1 passes: D_paired 0.9992103, 1,082 alarms all certified, no difference from F;
    - U2 passes: in a–f no alarm on an admissible row, no early or uncertified alarm, at most 65 kept, every path
      reached; in d, 1,019 rows detect after a reset;
    - the injections per setting equal R2's above.
- **M1 (the written proof, traced to 000cd215 line by line):**
  - lemmas L1–L8 and the theorem: S1, S3 and |zs| ≤ 65 under the model and a stated floating-point model;
  - a new exact check: the frozen clamp set is invariant under one step of the exact recurrence (all 42 vertices,
    rational arithmetic);
  - its own reruns: R0 13 of 13 at 000cd215;
  - seven gaps. G1 (a solver exception in a fold becomes an uncertified alarm) and G2 (no finiteness check on a
    status-0 answer) concern the solver boundary: closed by the fourth addendum. G3 (the as-range is a gate) and G4
    (the record's subset holds after each step, not inside it) are wording, fixed in section 1. G5 (W, K and the
    template are the caller's) is closed for the validation by the manifest. G6 and G7 are scope and record-keeping
    notes for the write-up.
- **M2 (the fourth addendum checked, at 1c0439cd):**
  - **G1 and G2: closed only in part.** Solver exceptions and non-finite status-0 answers now take their fallbacks,
    as U0b showed. Three paths remain:
    - **Wrong shapes.** An LP input of the wrong rank passes `_check_inputs`, and so does a right-hand side given
      without its matrix. scipy then raises `ValueError`, which is counted as a solver `exception`, not raised as
      our error.
    - **Empty multipliers.** A status-0 answer whose multiplier arrays are empty passes `_usable`. The activity
      update then raises `IndexError` and stops the run.
    - **Underflow.** The certificate's error terms are relative. In a constructed one-variable LP with a subnormal
      objective (−2^−1074), the strict bound returns 0 where the exact maximum is 2^−1076.
  - All three were reproduced here on the Mac. No natural case of any of them is known:
    - F3's LP builder only ever passes rank-1, paired inputs;
    - R1 and R2 ran about 60 million LPs with no exception (at `0ce80072` one would have stopped the run or raised an
      uncertified alarm);
    - whether a multiplier on F3's data can be small enough to underflow is not shown.
  - Fixed by the fifth addendum (DIAG-3-PLAN; Can's decision 2026-11-20, `b57b5a39`), checked by review M3.
  - **Wording, fixed in section 1:**
    - a `RuntimeError` in a fold becomes an uncertified alarm, but any other error stops the run;
    - a fold uses max(value + PAD, certified), never less than the certified bound.
  - **The other new results:**
    - the no-event identity, checked line by line, and F/Fa unchanged (`strict=False` bit-identical);
    - scorer tests: 20 constructed row sets, expectations hashed before the run, 20 of 20 as expected. They were
      rerun here: identical.
    - a scipy/HiGHS note: the status table, the exception translation and the marginal signs. scipy status 2 also
      covers HiGHS `kModelError`.
    - a literature note on certified LP bounds: Neumaier and Shcherbina 2004; Jansson 2003, 2004; Applegate et al.
      2007; Cook et al. 2013; Steffy and Wolter 2013; Higham 2002. All 7 DOIs were confirmed here on OpenAlex or
      Crossref.
- **M3 (the fifth addendum checked, at b57b5a39):**
  - **M3a, closure: all four findings of M2 are closed.** 19 comparisons on constructed LPs and DEV 430000, each
    expected outcome derived from the code first, all as expected. The new checks reject no natural LP: F3's two LP
    builders were read for shapes, and 662 LPs of a control run passed.
  - **M3b, L1 restated.** Under the floating-point model of section 1 and the candidate's sizes, every finite strict
    bound is an upper bound of the ideal LP. The proof covers the underflow of the final pad's own products. With
    every box within ±2 and N ≤ 14,795 products, the term is exactly 5N · 2^−1074.
  - **New findings, all reproduced here on the Mac. None gives a wrong bound:**
    - an LP with no variables passes `_check_inputs` and is counted as a solver `exception`;
    - a solver answer with no multiplier field raises `AttributeError` in `_usable` and stops the run (whether
      scipy can return one is not known);
    - F3a's audit evaluates one statistic outside the strict bound's error-state guard (section 1);
    - the plan's "the term is exact" holds for the candidate's boxes only. Counterexample: N = 10 and
      max|x| = 2^−54 give 10 units of 2^−1074 where 11 are needed;
    - two sentences were wrong: a strict bound "equals the non-strict one", and the term "changes no value". I3 is
      a measurement on its rows, not a proof.
  - **Decision (Can, 2026-11-20): no sixth addendum.**
    - The first three are listed as known limits in section 1. F3's LP builders cannot produce them, and none makes
      a bound wrong.
    - The wording is corrected in section 1 and DIAG-3-PLAN.
    - `diag3_cw.py` stays byte for byte as at `b57b5a39`, the file every test of the fifth addendum and I2b ran. Its
      two docstrings that state the wrong sentences stay as they are until after the freeze.
    - The general fixes wait until after the freeze, for the code release and the next plant:
      - the two docstrings;
      - a check for at least one variable;
      - a missing multiplier field counted as a failed attempt;
      - an exact term for any box;
      - the guard extended to F3a's audit.

## 6. Order of operations

As freeze 2 (FREEZE-V2.md section 6), with the V3 files:
1. **Can reviews this file.** Any change he asks for is made, the manifest regenerated, and this file updated before
   approval.
2. **Approval.** The status line becomes exactly `Status: APPROVED by Can Koç on YYYY-MM-DD` in a commit that changes
   nothing else.
3. **Run.** On Arch: `run_validation_v3.py OUT`, from a clean checkout. It checks the tree, the environment lock,
   every manifest hash, the quoted manifest sha256 and the approval line, and the seed block. Only then does it
   unlock the validation seeds.
4. **Score.** `score_validation_v3.py OUT`. Then a dated record with the verdict as it comes out.
5. **Infrastructure failure:** the identical command, on the same block, into a new output directory. A needed code
   change outside the candidate and the rules gets a dated addendum here. The candidate, the target and the scoring
   do not change.
6. **No reruns for any other reason, and no second look at another block for the same candidate.**

## 7. What this validation can not show

Everything in FREEZE-V2.md section 7 holds for F3: no MCU, no float32, no real plant or model mismatch, the ambient
box, detection at the noise bound, sensor faults an ambient path reproduces, independence beyond the seeds.

In addition:
- **How often the solver fails.** The validation will meet whatever failures occur naturally, perhaps none. The
  fallback paths were exercised on DEV with simulated failures (R2, K7), not on validation seeds.
- **The cost of a fallback.** A fallback bound is looser than the LP it replaces, so it can delay a detection. R2
  measures that on DEV under the injection rates of settings a–f, which are not a model of real failure rates.
- **The memory bound is a count of measurements,** not a measurement of bytes or time on a microcontroller.

## 8. DEV rehearsal of the full pipeline (DEV seeds, not validation)

**Passes.** Arch, at `e81c549b` (the manifest's commit), clean tree, 2026-11-20 12:59–13:24.
- **Command:** `run_validation_v3.py --rehearsal --seeds 430096 430097 --workers 4`, then `score_validation_v3.py`.
- **Outputs:** `results/v3/freeze3/rehearsal-dev-430096-e81c549b/`.
- **The record:** the runner checked every file against the manifest. It wrote the manifest's sha256 (`0a40cbdf…`),
  this file's, the environment and the commit into the record. `approval` is null, as a rehearsal's must be.
- **Identity:** 96 runs, none missing, extra or repeated, and no integrity problem.
- **F3: PASS.** D_paired 1.0 against the 0.80 target, with no miss, no soundness violation and no uncertified alarm.
  All 74 events are detected at the oracle's t*. No row took a fallback, and there was no slab.
- **Against freeze 2's rehearsal** on the same seeds (`rehearsal-dev-430096-9dc1af3`, F):
  - every score and every cell's table is the same, field for field, with F3 in F's place;
  - row by row, all 96 rows are the same except for three fields: the oracle's wall-clock seconds, F3's `failsafe`
    counters (all 0) and the certificate's new `box_sides` (empty).
- **Time:** 1,501 s against freeze 2's 468.5 s. That run had 14 workers; this one had 4, on a machine shared with
  I2b.
