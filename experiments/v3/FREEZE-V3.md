# v3 freeze 3: F3, the compressed window with a sound path for solver failures, and the rules of its validation

Status: DRAFT, not approved

Manifest sha256: [written when the manifest is generated at the frozen code]

Prepared 2026-11-20 on branch `sdts-v3/template-state` for Can Koç's review. The target and the reading of a failure
are Can's to set. Everything here is a proposal until the status line says APPROVED. `run_validation_v3.py` refuses
to generate validation data until then (section 6).

**Open items before review** (each is filled in from its own record, as it comes out):
- I1b: the third addendum's change, on all of R-none on Arch (section 2);
- R1–R3 and the criteria U1–U3 (section 5);
- the independent summary of the R runs (review K7d) and the written proof (review M1) (section 5);
- the manifest at the frozen code, and the DEV rehearsal at the freeze commit (sections 2 and 8).

**Decisions for Can** (proposals in brackets):
- the slab rule (section 4) [reported, not deciding];
- the seed block and its size (section 3) [440400–440599, 200 seeds, as freeze 1 and 2].

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

| where the LP fails | what F3 uses instead | why it is sound |
|---|---|---|
| one side of the as-range | that side's box bound (HI = 2 or LO = −2); z_t is not kept | the box contains every state |
| one side of the alarm certificate | that side's box bound | the same |
| one direction of a fold | the certified maximum over P_J ∩ box, J = the solved faces of the same fold; if that 3-variable LP fails too, the a priori clamp | the ideal window's states lie in P_J ∩ box |
| every direction of a fold | an atomic reset: base = the a priori clamps, no kept measurements, τ += B | the clamps hold under the exact recurrence |

- The as-range and certificate bounds are always clipped to the box (N2 addendum). A z_0 outside the box raises a
  box-certified alarm at t = 0.
- An empty slab cannot occur after t = 0: a z_t whose slab misses the box fails the alarm test against the clipped
  range and is never kept (N2 addendum). It is counted all the same (section 4).
- Every fallback is counted by its kind (status 2, 4, slab, other) in the record's `failsafe` field.

**The memory bound** (third addendum). The eviction comes before the keep, and the eviction record is pruned with
the window. So, at every point of every step, at most K_cap + 1 = 65 measurements are held, and the eviction record
has no key outside them. Neither change alters a decision (section 5, I1).

**What is a theorem and what is not:**
- **Soundness** holds by construction under the model, by FREEZE-V2.md's invariant chain with one more link: each
  fallback above is a superset bound of what it replaces. The written proof, checked against the code, is review M1
  (section 5). [Its summary goes here once checked.]
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
| this commit | `run_validation_v3.py`, `score_validation_v3.py`, `make_manifest_v3.py` and this file |

**The tooling is freeze 2's, with F3 in place of F.**
- `run_validation_v3.py` is `run_validation_v2.py` with the V3 manifest and document, the record key `F3`, and the
  `failsafe` counters added to the record.
- `score_validation_v3.py` calls `score_validation_v2.score()` unchanged, with F3's record in F's place. Scored on
  freeze 2's own rows, it gives freeze 2's scores, field for field (checked when it was written).

`frozen/MANIFEST-V3.json` [sha256 above, once generated] fixes:
- the data block, cells and laws;
- the candidate (variant F3, W = 256, B = 16, K_cap = 64, pad 1e-6, cyl16p's directions by sha256) and its target;
- every file the validation depends on, by sha256: freeze 2's list, with the V3 runner and scorer, and the V2 scorer
  that the V3 scorer imports.

`run_validation_v3.py` refuses to run if any of them differs.

[The file table goes here, from the manifest.]

**Environment:** the thermal v2 lock: CPython 3.12.13, numpy 2.5.5, scipy 1.18.1 and HiGHS 1.12.0. It is checked at
start and recorded.

## 3. Data

**Seeds 440400–440599** (200 seeds), generated only after approval, by `run_validation_v3.py`. They use the
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
any fallback, and the count of empty-slab failures.

**The slab rule** [proposal, Can decides]: an empty slab after t = 0 is reported, not deciding. F3 handles it soundly,
like any failed LP, and the hypothesis is about soundness and lag, not about which path ran. The alternative is to
make it a FAIL, as an "impossible" case that would show a gap in the reasoning of section 1.

## 5. DEV reference (DEV, not validation)

All of this is in `diag/DIAG-3-RESULTS.md`. The plans and criteria were committed before each run.

**F3 without failures equals F.** [U1, R1: on the 1320 DEV comparison rows and the 80 edge-noise rows, F3's
detections equal F's, and its margins equal F's or F's clipped to the box. F's DEV reference is FREEZE-V2.md section
5: D_paired 0.99921, no miss, no soundness violation, 1082 certified alarms.]

**F3 with simulated failures** [U2, R2: settings a–f, every status kind in every role, soundness, the memory bound,
counters equal to the injections, no slab, recovery after full resets in setting d. D_paired per setting, reported.]

**The exact audit** [U3, R3 on the Mac: settings a, b and e with F3a, no violation].

**The path tests (U0, R0): 13 of 13 pass.**

**440243 (U4, R4): passes.** F3a runs all 3599 steps with no alarm. At t = 945 direction 40 fails, as in freeze 2,
and the fallback takes the P_J bound −0.20897 °C from the 41 solved faces (a priori 1.683 °C). The exact audit of
9,634 bounds, the P_J bound among them, finds no violation.

**The memory bound (I1).**
- I1a (Mac): with and without the third addendum's change, 16 records on 8 rows under settings none and d are equal
  in every field but wall-clock time.
- With the change, |zs| ≤ 65 and the eviction record ⊆ zs at all 48,460 checks. Without it, 66 and 317.
- [I1b, Arch: all of R-none.]

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
  - [K7d: the independent summary of R1–R2.]
- [**M1:** the written proof and its trace to the code.]

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

[To run at the freeze commit: `run_validation_v3.py --rehearsal --seeds 430096 430097` on Arch, then
`score_validation_v3.py`, against freeze 2's rehearsal on the same seeds (`rehearsal-dev-430096-9dc1af3`).]
