# v3 freeze 1: two candidates and the rules of their independent validation

Status: PROPOSED (not approved; validation data must not be generated)

Manifest sha256: e8dd60f134252c1855aca040a46836281db57c1ee19da9713f4c7a25d6e18a96

Prepared 2026-11-18 on branch `sdts-v3/template-state` for Can Koç's review. Targets and the reading of a
failure are Can's (2026-11-18); everything else here is a proposal until the status line says APPROVED.
`run_validation.py` refuses to generate validation data until then (section 6).

## 0. What is tested, and what a failure means

Two hypotheses, one per budget. Each is judged on its own. Both are about the **float64 reference implementation** of the frozen tables: Python `TemplateMachine`, which the C float64 build reproduces exactly. The float32 C builds are reported but are not the tested object (section 4).

- **H-inv4.** The frozen `inv4p` state (16 numbers, 231 table entries, ~3.8 KB float32 tables) is sound under
  the model, never later than v2, misses no more oracle-detected events than v2, and reduces v2's paired lag
  (section 4) by **at least 10 %** on fresh seeds of the v3 scenario distribution.
- **H-cyl16.** The same for the frozen `cyl16p` state (42 numbers, 1318 entries, ~20.5 KB) with **at least 25 %**.

**A FAIL rejects that candidate's hypothesis at that budget, and nothing else.** It does not reject:
- Theorems 1–4 (`V3_NOTES.md`): they do not depend on data.
- Other template families, other budgets or other representations.
- The SDTS question itself: how much of the history-dependent information state a bounded, deterministic MCU
  state can keep.

The DEV results stay what they are: DEV results.

**A PASS supports only the hypothesis as written:** the same plant with known parameters, the simulated ambient
and noise laws of `dev_scenarios.py`, and no hardware.

After the result, neither candidate nor any rule changes. A new or modified candidate is a new freeze with the
next unused seed block (440200 onwards).

## 1. The candidates

Both use the same mechanism: template support state with offline basis tables and reachable-set clamps
(`template_state.py`, `TemplateMachine`; theory in `V3_NOTES.md` section 4).

- **Run time:** min over 3-term dot products. No LP, no allocation.
- **Theorem 2 (soundness):** holds for any subset of bases.
- **Theorem 3 (never later than v2):** holds because ±e2 and ±v̂ are directions, the ±e2 predictions keep a
  basis {±e2, ±v̂, x}, and the as-range keeps the unit basis of ±e2. `dominance_bases_present()` checks this on
  both frozen files and returns nothing missing.

| | inv4p | cyl16p |
|---|---|---|
| direction family | `inv`, N = 4: ±e1..3, ±(e1−e2), ±(e2−e3), ±v̂, ±(e1−e3), ±(e1+e2−2e3) (normalised; 2 of the 4 error-plane angles coincide with the differences): 16 | `cyl`, N = 4, L = 16: the 16 of inv4 + 13 new pairs orthogonal to e3 (3 of 16 angles coincide): 42 |
| state numbers (RAM) | 16 (64 B float32) | 42 (168 B float32) |
| plus | S (2 doubles), flag, counter | same |
| table entries (full → pruned) | 1384 → 231 | 38966 → 1318 |
| MAC per sample (3 × entries) | 693 | 3954 |
| C tables, float32 / float64 (codegen estimate) | 3767 B / 6803 B | 20540 B / 37036 B |
| pruning selection set (DEV only) | 430050–430069, 10 cells × 2 arms × 2 ambient laws, uniform noise: 800 runs | the first 120 runs of the same list (430050–430052) |
| pruning rule | keep every basis that was the argmin at least once, plus the Theorem-3 bases | same |
| frozen file | `frozen/inv4p.json` | `frozen/cyl16p.json` |
| sha256 | `e509c855aeb8fa478c68417ebf4843b53a2bad679d7a43a95f640e3802539f8b` | `7f9cc8700fdd70782ddaf4a7e99a2e2c2f5818ce4aafa970f897b40e90a7747e` |

**Plant and assumptions:** those of v2, `thermal.py`, unchanged.
- CC = 30, CS = 12, K = 2, H = 0.8, DT = 1 s;
- δ = 0.3, ρ_A = 0.002 °C/s, TA ∈ [23, 27], start at the P0 = 20 steady state;
- record length 3600 samples.

**The JSON files are the candidates.**
- They hold every float the update reads, as `float.hex`, so they load bit-for-bit anywhere.
- They were built on Arch (linux, Python 3.12.13, numpy 2.5.5, scipy 1.18.1) by `freeze_tables.py` at
  `2830ce8`, from a clean tree (`frozen/build.json`).
- Validation loads them by sha256 and never rebuilds them, because LAPACK may differ in the last bits across
  platforms.
- The C headers are generated from them (`codegen_c.py --frozen`).

**Tie to the DEV numbers in `RESULTS.md`.**
- The frozen files reproduce RESULTS.md exactly on the DEV comparison rows: inv4p 864 / 6 / 28096 and cyl16p
  898 / 4 / 20386 (equal / missed / lag sum, RESULTS.md bookkeeping).
- The forced Theorem-3 bases added no entry: 231 and 1318 are the entry counts evaluated on DEV.

## 2. Code, commits and hashes

| commit | content |
|---|---|
| `2830ce8` | tooling: frozen-table format, validation lock, runner, scoring rules, tests |
| `6396e62` | the two frozen candidates, C headers, first manifest |
| `522d85f` | rehearsal possible before this file exists; manifest updated |
| this commit | validation block 200 seeds; DEV reference and DEV rehearsal results; this file |

`frozen/MANIFEST.json` (sha256 above) fixes:
- the data block, cells and laws, targets and limits;
- every file validation depends on, by sha256.

`run_validation.py` refuses to run if any of them differs.

| file | sha256 |
|---|---|
| `experiments/v3/template_state.py` | `6f8409274cdc583f3ed48aca372fc08fccd9970f106ae516291f39a5a6894666` |
| `experiments/v3/dev_scenarios.py` | `a1b204efde095c4d36d2aab4ca503970386a2761485b3c84f3ec8da2503c363f` |
| `experiments/v3/run_validation.py` | `9cb899ea770dd8b60e37e80c6686a77ef5a662d3b7a5e5f41a294a23111920a3` |
| `experiments/v3/score_validation.py` | `96c347455888d3f8944788941e6920121ef36f444f0e3bcd4a8f105bbb9104da` |
| `experiments/v3/codegen_c.py` | `4f99bd4979abf182b66363f140100decb72ed6ce099b2544fd61121fe7eeff07` |
| `experiments/v3/freeze_tables.py` | `89a13739cf49f8485bfc2865476067c8c9e71cc7551d446403e3f5fbd6a25e6c` |
| `experiments/v3/c/v3_state.c` | `acd3fb60e8fd9c443d7915076416dd9ed6274f56db3b8a8cac8759b09012b961` |
| `experiments/v3/c/v3_state.h` | `df7f9369091cff492bf9e6ed9ef5e3ee11714860170e9153d8ee658df4524878` |
| `experiments/v3/c/harness.c` | `b3cbdd968cd7f53489c5fd9489460282283d4562e6e321f22429c3fa4ca08915` |
| `experiments/v3/frozen/inv4p.json` | `e509c855aeb8fa478c68417ebf4843b53a2bad679d7a43a95f640e3802539f8b` |
| `experiments/v3/frozen/cyl16p.json` | `7f9cc8700fdd70782ddaf4a7e99a2e2c2f5818ce4aafa970f897b40e90a7747e` |
| `experiments/v3/frozen/build.json` | `5ab2d947e8d8831f2bdb4e60cef97a01ec5cb1dd4446dac6d1027e118850ee15` |
| `experiments/v3/frozen/c/tables_inv4p_float.h` | `7fc3c686e2724b18f17e702afa3942ec98acf78a5a58faa98eefbf4c39f46906` |
| `experiments/v3/frozen/c/tables_inv4p_double.h` | `2186d789e2799794183c72222257b0f718a250c7bf01f5a289dbf4f7fc9f8add` |
| `experiments/v3/frozen/c/tables_cyl16p_float.h` | `bd58d7ef83fed4ddb276117f51d327503377bbf48802118216404d6e941c309e` |
| `experiments/v3/frozen/c/tables_cyl16p_double.h` | `00e0a7efd94ef7eebf3be97e9c337bb4b0ff995effed34cd8c50698f21342493` |
| `experiments/generators/thermal.py` | `d742012e138402525382eee26e0d6dba87bd224267dc733a75f1e693f98ce481` |
| `experiments/oracle/thermal_oracle.py` | `7f4b8da3064675e29f88a7f676e8d0318982fdbde1b5b355e1c83d2238f92e74` |
| `experiments/machine/thermal_machine.py` | `0337f7b8520ff581ef8ec7d321de2cd69458396c44c0bbfb43bbdb34a78f2796` |
| `env/thermal_v2_env.py` | `40740690aa7a0cea680e7496b391e1632a796075afcb1206b153e61a873644b6` |
| `env/requirements-thermal-v2.txt` | `7f25d6435e8b664fe179e4cc57ec7c36b61c9f32ad9c7285a1723e3612b4cd2d` |

The v2 oracle, machine, plant and environment files are unchanged since the v2 FINAL code (`da6e4a0`; `git diff da6e4a0 HEAD` on them is empty).

**Environment:** the thermal v2 lock (`env/thermal_v2_env.py`): CPython 3.12.13, numpy 2.5.5, scipy 1.18.1,
HiGHS 1.12.0. It is checked at start and recorded.

**C builds:** compiled by the runner from the frozen headers:
- flags `-O2 -std=c99 -ffp-contract=off -fno-fast-math`;
- compiler version and binary sha256 are recorded in `meta.json`.

## 3. Data

- **Seeds 440000–440199** (200 seeds), generated only after approval, by `run_validation.py`.
  - The generator is the DEV generator with its own seed strings (`v3val:{seed}:...` instead of `v3dev:...`).
  - The laws are identical; the DEV output is unchanged (hash-checked when the namespace was added).
  - 440200–440999 stay reserved and are not generated by this freeze.
- **Per seed (48 runs):**
  - 11 cells (healthy, jump_0.2, jump_0.5, drift_0.0005, drift_0.001, drift_0.002, drift_0.005, drift_0.02,
    noise_x2, stuck, gain_0.01) × arms E0, E1 × ambient laws `rw`, `ramp` with uniform noise: 44 runs;
  - plus healthy × E0, E1 × `rw`, `ramp` with `edge` noise (±δ exactly): 4 runs.
- **Total:** 9600 runs.
- **Expected** (DEV rate, not a prediction): about 7200 oracle-detected events, and about 4 h on Arch with 14
  workers. The oracle dominates the cost.
- **Why 200 seeds and not 100:** the DEV seed-cluster bootstrap (section 5) shows a heavy-tailed paired lag.
  - Near inv4p's DEV point, 100 seeds would give a standard error of about 2.8 points against a 4.7-point margin
    to the target, so about a 5 % chance of a FAIL even if the DEV point were the truth.
  - 200 seeds roughly halves the variance (about 1 %).
  - This is a sample-size choice made on DEV; it does not tune any candidate or target. 100 seeds is a one-line
    change in `make_manifest.py` if preferred.

## 4. Scoring rules (`score_validation.py`, fixed)

**Decision, the same for every method** (certified oracle, v2 machine, candidates, C builds): the first sample
k at which no explanation with b = 0 and |noise| ≤ δ exists. f_m(r) is method m's first such sample on run r,
or None. N = 3600.

**Sets:**
- **F, fault runs:** cell ≠ healthy, uniform noise.
- **U:** runs in F whose oracle t* is not certified. They are excluded from every comparison and counted.
- **R, detection events:** runs in F with a certified oracle t*.
- **A, admissible runs:**
  - every healthy run, both noise laws (ground truth: admissible by construction, whatever the oracle says);
  - every run in F that the oracle certifies consistent.

**Guarantees** (each is a theorem, so any violation is a bug or a broken condition, and the candidate fails):
- **Soundness (Theorem 2):** the candidate flags no run in A, and f_c(r) ≥ t*(r) for every r in R.
- **Dominance over v2 (Theorem 3):** on every run where v2 detects at k, the candidate detects at or before k.
  - The theorem is in exact arithmetic; the implementation rounds outward.
  - A violation within rounding is still counted as a violation: the claim is about the implementation that
    would ship.

**Misses:** r in R with f_m(r) = None. The candidate must have **no more misses than v2** on R.

**How misses enter the lag (the primary metric).**
- **Paired set:** B = {r ∈ R : v2 detects r}.
- L_m = Σ over B of (f_m(r) − t*(r)). A candidate miss inside B (itself a dominance violation) counts as
  N − t*(r).
- **D_paired = 1 − L_cand / L_v2.** The candidate passes this criterion if D_paired ≥ its target: 0.10 for
  inv4p, 0.25 for cyl16p.

Why this form:
- Every term compares the two methods on the same event.
- A candidate cannot lower its lag by missing hard events.
- Events that only the candidate detects give it no credit in D_paired; they show up in the miss count and in
  the secondary metric. D_paired is therefore the conservative reading.

**Secondary, reported, not deciding:**
- **D_censored** over all of R, every miss counted as N − t*. That is a lower bound on a miss's true lag, and
  it depends on the record length.
- Exact matches with the oracle.
- Lag median, p90 and max.
- Per cell and ambient law.
- A seed-cluster bootstrap 95 % interval of D_paired (2000 resamples, rng seed 20261118). It is descriptive;
  the verdict uses the point value.

**Verdict, per candidate:**
- **INCONCLUSIVE:** the run is incomplete (not 9600 rows), the environment check failed, or |U| > 1 % of |F|.
- **FAIL:** any soundness violation, any dominance violation, more misses than v2, or D_paired below target.
- **PASS:** otherwise.

**C builds** (float32 and float64 of each candidate):
- Their soundness violations, runs later than v2, D_paired and agreement with the Python reference are
  reported.
- They do not enter the verdict.
- The claim "the float32 MCU build is sound" holds only if its soundness violations are 0.
- **Theorem 3 is not claimed for float32.** The float32 pads loosen the set at every step, and v2 runs in
  double. The DEV rehearsal (section 8) already has a float32 run 240 s later than v2.
- The float64 C build is the MCU form of the tested object. Codegen estimate: 6.8 KB tables for inv4p and
  37 KB for cyl16p; software double on a Cortex-M4F is slower, but no timing has been measured.

**Already implied.** If Theorem 3 holds as implemented, misses ≤ v2 and D_paired ≥ 0 follow. Those two checks
therefore also test the implementation. The empirical content is the size of D_paired.

## 5. DEV reference under these rules (DEV, not validation)

Inputs:
- the DEV comparison rows (`run_dev.py` at `45cff1d`, seeds 430000–430029, uniform noise, rows sha256
  `f823e50c…`), reusing their certified oracle t* and v2;
- the frozen candidate files.

Output: `results/v3/freeze1/dev_reference.json`, from `dev_reference.py`.

| | v2 | inv4p | cyl16p |
|---|---|---|---|
| detection events R (certified) | 1081 | 1081 | 1081 |
| misses | 8 | 6 | 4 |
| exact match with t* | 805 | 863 | 897 |
| lag median / p90 / max (s) | 0 / 49 / 2880 | 0 / 30 / 2880 | 0 / 19 / 2880 |
| paired set B, L (s) | 1073, 32925 | 28096 | 20222 |
| **D_paired** | — | **0.147** | **0.386** |
| D_censored | — | 0.184 | 0.399 |
| bootstrap 95 % (descriptive, 30 seeds) | — | [0.062, 0.265] | [0.204, 0.603] |
| soundness / dominance violations | 0 | 0 / 0 | 0 / 0 |

Reading:
- **On DEV both targets are met by point value, inv4p by a small margin.** The interval of inv4p reaches below
  0.10.
- **The paired lag is almost entirely slow drift.** Drift cells carry > 99 % of v2's lag; jumps, gain, stuck
  and noise are at or near zero lag for every method. D_paired measures what each state keeps about slow,
  ambient-like faults.
- **One run (430010 drift_0.0005 ramp, 2880 s) is unchanged by every bounded state tried** (RESULTS.md
  section 6). It is part of every L.

**Bookkeeping correction to RESULTS.md.** RESULTS.md counted 1082 oracle-inconsistent DEV runs. One of them
(430003 drift_0.001 E1 rw, t* = 1956) has an uncertified oracle t*. The frozen rules exclude it, which gives
1081. No method's soundness count changes.

## 6. Order of operations

1. **Can reviews this file.** Any change he asks for is made, the manifest regenerated, and this file updated
   before approval.
2. **Approval.** The status line becomes exactly `Status: APPROVED by Can Koç on YYYY-MM-DD` in a commit that
   changes nothing else.
3. **Run.** On Arch: `run_validation.py OUT`. It checks:
   - a clean tree;
   - the environment lock;
   - every manifest hash;
   - the quoted manifest sha256 and the approval line;
   - the seed block.

   Only then does it unlock the validation seeds.
4. **Score.** `score_validation.py OUT`. Then a dated record with the verdicts as they come out, the per-cell
   table, the C build results and the run hashes.
5. **Infrastructure failure** (crash, reboot, incomplete rows):
   - the identical command is rerun on the same block;
   - a needed code change outside the candidates and the rules gets a dated addendum to this file;
   - the candidates, targets and scoring do not change.
6. **No reruns for any other reason, and no second look at another block for the same candidates.**

## 7. What this validation can not show

- **Sensor correctness** beyond the constant-offset class: Theorem 4. A slow drift that an admissible ambient
  path reproduces is invisible to every method.
- **Behaviour under plant-parameter mismatch:** a separate protocol.
- **Timing on a real Cortex-M:** cycle counts are table counts, not measurements.
- **Independence beyond the seeds.** The scenario laws are the ones the candidates were developed under.
  Validation tests generalisation to new draws of the same distribution, not to other plants or ambient
  behaviour.

## 8. DEV rehearsal of the full pipeline (DEV seeds, not validation)

The identical pipeline was run on DEV seeds 430098–430099 (`--rehearsal`; validation stays locked):
- `run_validation.py` at `522d85f` on Arch: oracle, v2, both candidates and four C builds;
- 96 runs (2 seeds × 48) in 175.7 s with 8 workers;
- rows sha256 `9aec25b121aa39b3e9b7dfb5d789ee71c565ce7911780db6ff5355c8c997f9a5`;
- the C builds were compiled by the runner (cc (GCC) 16.2.1 20260810).

The scores were then recomputed with this commit's `score_validation.py`, which only adds the C-build
"later than v2" report. Outputs are in `results/v3/freeze1/rehearsal-dev-430098/`. These two DEV seeds were
not used anywhere before.

Pipeline checks:
- complete (96 of 96 rows);
- 0 uncertified;
- 70 detection events;
- 26 admissible runs, edge-noise healthy runs included.

| | soundness | dominance / later than v2 | D_paired | vs Python |
|---|---|---|---|---|
| inv4p (Python, float64) | 0 | 0 | 0.123 | — |
| cyl16p (Python, float64) | 0 | 0 | 0.254 | — |
| inv4p C float64 | 0 | 0 | 0.123 | same on 96/96 |
| cyl16p C float64 | 0 | 0 | 0.254 | same on 96/96 |
| inv4p C float32 | 0 | **2** | -0.574 | same on 92/96, later on 4 |
| cyl16p C float32 | 0 | 0 | 0.238 | same on 94/96, later on 2 |

What the rehearsal shows:
- **The pipeline works end to end:** generation, oracle, machines, C compile, scoring.
- **The float64 C builds equal Python on every run.**
- **The float32 inv4p build is sound but on 430098 drift_0.002 rw (both arms) detects at 906, against 666 for
  v2 and Python.** That is 240 s later than v2, so its D_paired on these 70 events is negative.
  - This is why section 4 does not claim Theorem 3 for float32.
  - **HYP, not checked:** the static float32 pads accumulate in the directions that only the clamps bound, in
    particular the ambient lower bound. RESULTS.md section 6 shows that latency there is very sensitive to
    looseness.
- **Two DEV seeds say nothing about the targets.** The D_paired values above are not evidence for either
  hypothesis.

