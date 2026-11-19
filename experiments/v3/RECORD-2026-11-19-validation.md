# v3 freeze 2: independent validation on seeds 440200–440399 (2026-11-19)

The verdict below is the frozen scoring rules' verdict, as it came out (`FREEZE-V2.md` section 4,
`score_validation_v2.py`). Nothing was rerun, retuned or rescored with other rules.

**Verdict: FAIL.** On one healthy run, F stopped at a fold whose LP the solver could not solve. The frozen code
records that as an uncertified alarm. Under the frozen order, that row decides the verdict before any accuracy rule
is reached.

## Provenance

**Freeze:**
- `FREEZE-V2.md`, approved by Can Koç on 2026-11-19. The approval commit `35b344df` changes only the status line.
- Manifest sha256 `cc7adffa240b6ab4eab9b45652f4437ce582f784123b1b1cac8341f4db303385`.
- `FREEZE-V2.md` as run: sha256 `79389a0e8f49ea4c387a2c22be11a93eb519289638b44a462dc030dbb404e134`.

**Run:**
- `run_validation_v2.py` on Arch, from a clean worktree at `35b344df`. It ran from 2026-11-19 06:57:26 to 18:30:49 +03
  (41603.4 s) with 14 workers.
- The tracked tree was clean, and the runner's checks passed: environment lock, manifest, approval line and seed
  block.
- Environment: CPython 3.12.13, numpy 2.5.5, scipy 1.18.1, HiGHS 1.12.0.

**Outputs** (`results/v3/freeze2/validation-440200-440399-35b344df/`):

```
4ad0b493c11079c6bfc61714a2da89fde7abfad2409602d0502ad620398738de  rows.jsonl
d35e2b09a852254f52e67b294b70772157a697876e7f1e5d1819ca05b28be6f1  scores.json
1ac5a6bbdaa25ecba017923433437febefa0ab3166e09df0a1c30e5a0ab3cb16  meta.json
72180760d128decc1779c6bd512d174abdece671cd7ea26c162442d9592fd836  run.log
19ee3640033a60de2881a9168318b11512c5c3cb3796bab9d8bd9faf6b2295dd  v3-validation2-35b344df-solver_attempts.tar.gz
```

- The archive holds the oracle's `solver_attempts/` (9.1 MB). It is not in the repository. Copies are in
  `~/Downloads/sdts-runs/` on the Mac and `~/Research/sdts-runs/v3-freeze2/` on Arch.
- The rows were scored again on the Mac with the frozen `score_validation_v2.py`, from a clean copy of `35b344df`.
  The resulting `scores.json` is byte-identical.
- **An independent scorer** scored the same files again. It was written from section 4 alone and imports only the
  Python standard library. It reproduces every number in this record, the cell table, the bootstrap, the deciding
  row and the verdict.
  - It also checks the manifest's 17 files at the commit and in the run's worktree, and that the approval commit
    changes only the status line.
  - It finds a finite, negative certified margin on each of the 7,270 certified alarms. This checks the recorded
    margins; it does not recompute the certificates.
  - Its output is on Arch, not in the repository (`independent-score.json`, sha256
    `2811e6326c2746b40a7ff4127fd618b670b4deae3f1c17af13df6eb053acd631`).

## Verdict

| | target | D_paired | seed bootstrap 95 % (descriptive) | misses (v2: 14) | soundness | uncertified alarms | verdict |
|---|---|---|---|---|---|---|---|
| F (W = 256, B = 16, K_cap = 64) | 0.80 | 0.995 | [0.987, 1.000] | 0 | **1** | **1** | **FAIL** |

**The scorer's reasons:** `1 soundness violations`, `1 uncertified alarms`. Both refer to the same row:

| seed | cell | arm | ambient | noise | F's alarm | the oracle |
|---|---|---|---|---|---|---|
| 440243 | healthy | E0 | ramp | edge | 945, not certified | certified consistent (no t*) |

The alarm's record reads: `LP status 4: The HiGHS status code was not recognized. (HiGHS Status 15: model_status is
Unknown; primal_status is Feasible)`.

Section 4 decides in a fixed order. An uncertified alarm, and an alarm on an admissible run, are a FAIL at step 2,
before completeness and before the misses and D_paired rules. The D_paired of 0.995 and the 0 misses are reported
below. They do not decide.

**Data:**
- 9600 of 9600 runs. Identity and integrity checks passed: none missing, duplicated or extra.
- 8000 fault runs:
  - 7265 detection events (certified oracle t*);
  - 730 certified consistent;
  - 5 not certified (0.06 %, against a limit of 1 %).
- Paired set (events that v2 detects): 7251.
- Admissible runs: 2330 (every healthy run, plus the certified-consistent fault runs).
  - v2 flagged none of them.
  - F flagged one, 440243 above.

## The deciding row

**OBSERVED** (the row, the frozen code and the run):
- The run has edge noise, so F's cap is full. It evicted 881 measurements in 944 samples.
- Its LPs needed 7 retries in all, and 2 of its folds were raised to their dual bound.
- t = 945 is a fold sample: 945 = 273 + 16 · 42.
- In the frozen code, `solve()` tries three times: dual simplex without presolve, interior point without presolve,
  then dual simplex with presolve. If none returns optimal or infeasible, it raises `RuntimeError("LP status …")`.
- `diag3_cw_dev.online()` catches a `RuntimeError` only around the fold. It records the error as an uncertified alarm
  at that sample and stops the run (amendment 8, `0e28951`).
- An error at an as-range or alarm LP is not caught, and would have stopped the whole run. The run finished, and this
  row's reason is the text of `solve()`'s error.
- F made 54,535,429 LPs on the block:
  - 693 retries on 302 runs;
  - 671 of them on 280 of the 800 edge-noise runs;
  - 22 on uniform-noise runs, each solved at the second attempt.
- On DEV there were 4 retries on the 1320 comparison rows, and 49 on 26 of the 80 edge-noise runs. No LP failed all
  three attempts on DEV.
- These are counts, not a failure rate. The runs are not independent trials, and the retries concentrate on edge
  noise.

**INFERRED:**
- One LP of the fold at t = 945 did not end optimal or infeasible in any of its three attempts. This follows from the
  code.
- Only the last attempt's message is recorded: HiGHS reported the model status as unknown and the primal status as
  feasible. scipy maps that to its generic status 4.
- The window was not shown to be empty, and the run is healthy. So the recorded cause is the implementation's
  solver-failure path, not a counterexample to the certificate. It is not, on its own, evidence that the
  certificates are correct either; that rests on section 1 and the DEV audits.
- This is the float64 reference implementation stopping on a solver failure.
- H-F is a hypothesis about exactly that implementation: Python, with HiGHS through scipy (section 0). So the FAIL is
  a FAIL of H-F as written.
- Section 1 foresaw an empty window LP at a fold, recorded as an uncertified alarm, which is a FAIL. It did not name a
  solver that returns no answer. The code treats both the same way, and the rules count the row the same way.

**UNKNOWN:** which of the fold's 42 directions failed, why, and whether it fails again. The F record does not keep
the LP, and nothing was replayed.

## Secondary, reported (not deciding)

| | v2 | F |
|---|---|---|
| exact match with the oracle's t* (of 7265) | 5189 | 7251 |
| misses | 14 | 0 |
| lag p90 / max (s) | 61 / 2831 | 0 / 241 |
| paired lag L (s) | 265602 | 1362 |
| D_paired | — | 0.9949 |
| D_censored (misses at N − t*) | — | 0.9952 |
| runs later than v2 | — | 0 |
| unproved LP alarms | — | 0 |

- **F's alarms:** 7271 in total.
  - 7265 are on the detection events;
  - 5 are on the undetermined fault runs, each at the oracle's candidate t*;
  - 1 is the deciding row.
- **The window:**
  - 2,825,330 evictions, all on the 800 edge-noise runs;
  - at most 65 kept, as on DEV edge noise;
  - at most 445 LP rows and 679 variables, as on DEV edge noise;
  - 18 folds raised to their dual bound, on 7 runs.
- **Pre-specified subgroups:**
  - drift_0.0005 / ramp: 369 events, D_paired 0.987, no misses;
  - rw: 3498 events, D_paired 0.997, no misses.

**Against the DEV reference** (`FREEZE-V2.md` section 5, measured before validation data existed): D_paired was
0.99921 on DEV; it is 0.9949 here. There was no soundness violation and no uncertified alarm on DEV, including the
80 edge-noise runs.

## Per cell (lag sums over detected events, misses)

| cell / ambient | v2 | F |
|---|---|---|
| drift_0.0005 / ramp | 64948 s, 10 missed | 840 s |
| drift_0.0005 / rw | 2618 s, 2 missed | 0 s |
| drift_0.001 / ramp | 36988 s | 98 s |
| drift_0.001 / rw | 7148 s, 2 missed | 0 s |
| drift_0.002 / ramp | 8144 s | 0 s |
| drift_0.002 / rw | 138466 s | 424 s |
| drift_0.005 / ramp | 4242 s | 0 s |
| drift_0.005 / rw | 2056 s | 0 s |
| drift_0.02 / ramp | 378 s | 0 s |
| drift_0.02 / rw | 206 s | 0 s |
| gain_0.01 / ramp | 14 s | 0 s |
| gain_0.01 / rw | 10 s | 0 s |
| jump_0.2 / ramp | 148 s | 0 s |
| jump_0.2 / rw | 114 s | 0 s |
| jump_0.5 / ramp | 14 s | 0 s |
| jump_0.5 / rw | 14 s | 0 s |
| noise_x2 / ramp | 34 s | 0 s |
| noise_x2 / rw | 8 s | 0 s |
| stuck / ramp | 20 s | 0 s |
| stuck / rw | 32 s | 0 s |

The drifts carry 99.8 % of v2's lag. F has lag left in three cells: drift_0.0005 / ramp, drift_0.001 / ramp and
drift_0.002 / rw. The full table is `by_cell` in `scores.json`.

## The oracle at the noise boundary

- Of the 800 healthy runs with edge noise, 412 are certified consistent and 388 are undetermined (freeze 1: 427 and
  373).
- Of the 800 healthy runs with uniform noise, 799 are certified consistent and 1 is undetermined: 440322, E1, ramp.
  Freeze 1 had none.
- The frozen rules judge healthy runs by ground truth (admissible by construction), so this does not touch the
  verdict.
- The deciding row, 440243 E0 ramp edge, is among the certified-consistent ones.

## Infrastructure

- 16 of the oracle's solver attempts died by SIGSEGV:
  - 10 interior point (one with presolve), 6 dual simplex;
  - 15 on uniform-noise fault runs, 1 on a healthy edge-noise run.
- Each ran in its own process, and the oracle went on with its next attempt.
  - 14 of those runs ended with a certified status.
  - 2 ended undetermined: 440326 drift_0.001 E0 and E1 ramp, both among the 5 undetermined fault runs.
- The oracle's attempts also returned status 4 3,338 times, out of 118,348 that returned.
- F's own LPs run in the worker's process. None crashed.
- Nothing here is an infrastructure failure in the sense of `FREEZE-V2.md` section 6: no crash, no reboot, no
  incomplete rows. Nothing was rerun.

## What this rejects, and what it does not

**Rejected:** H-F at this configuration (W = 256, B = 16, K_cap = 64), as section 0 states. On 200 fresh seeds, the
frozen float64 reference implementation raised one uncertified alarm, on a healthy run.

**Not rejected** (section 0):
- freeze 1's results (H-inv4 and H-cyl16, validated on 440000–440199);
- the DIAG-3 analysis;
- other window lengths, caps or formulations;
- the SDTS question itself.

**Measured, and reported with the verdict:** the frozen candidate measured D_paired 0.995, no misses and never later
than v2 on this fresh block. They may be reported, always together with the FAIL and its cause. H-F is a joint
hypothesis, so these numbers do not validate it, and freeze 2 is not a PASS. The block is no longer a holdout for any
later candidate.

**Not tested:** everything in section 7 (an MCU, float32, model mismatch, the ambient box, detection under edge noise,
independence beyond the seeds).

**Open, not started** (each is Can's decision):
- **A diagnosis of the failing fold.** This would replay 440243 E0 ramp edge up to t = 945 and keep the fold's 42
  LPs, to see which direction fails and whether it fails every time. It generates validation-seed data again, so it
  is outside section 6 and needs an explicit decision. It cannot change the verdict.
- **What F should do when an LP returns no usable answer.** The frozen code records the case at a fold as an alarm,
  and at an as-range it would stop the run. Neither is a sound way to go on. A solver failure, a certified alarm and
  a normal step have to be separate outcomes. Any change is a new freeze, with seeds from 440400 onwards (reserved,
  never generated). The candidate and the rules of freeze 2 do not change.
  - HYPOTHESIS, not tested: for a failed fold direction, use a support that is proved at the new base time. The
    exact clamps are one such support. Carrying the old base's numbers forward is not the same thing. The cost in
    lag, misses, memory and time is unmeasured.

## Diagnosis of the deciding fold (plan; after the verdict)

Can Koç decided on 2026-11-19, after the verdict was recorded, to replay the deciding run. The replay cannot change
the verdict. It is outside section 6 and is labelled as a diagnosis.

- **Script:** `diag/diag_fold_440243.py`. It replays (440243, healthy, E0, ramp, edge) with the frozen F up to the
  fold at t = 945, after checking the frozen files against `MANIFEST-V2.json`.
- **Where:** on Arch, in the validation's environment (the lock is checked and recorded), from a clean worktree of
  this commit. It is not run on the validation's own worktree or output.
- **Questions, fixed before the run** (Q1–Q5 in the script):
  - Does the replay reproduce the row?
  - Does the fold fail again, and at which direction, with which status in each attempt?
  - Do the fold's other directions solve?
  - Is the failure repeatable, in this process and in a fresh one?
  - Informational: how does the LP behave under HiGHS's other settings, and how far is the failing direction's a
    priori support from what the fold needed?
- No other validation run is replayed.
