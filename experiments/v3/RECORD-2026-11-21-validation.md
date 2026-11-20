# v3 freeze 3: independent validation on seeds 440400–440599 (2026-11-21)

The verdict below is the frozen scoring rules' verdict, as it came out (`FREEZE-V3.md` section 4,
`score_validation_v3.py`). Nothing was rerun, retuned or rescored with other rules.

**Verdict: PASS.** F3 had no soundness violation and no uncertified alarm, and it missed no event. It reached a
D_paired of 0.995 against a target of 0.80.

**F3's solver-failure path never ran on this block.** Every failsafe counter is 0: on these seeds no LP of F3 failed
all its attempts. That path is what F3 adds to F. Its soundness rests on the written proof and on the DEV tests with
simulated failures (`FREEZE-V3.md` sections 1 and 5), not on this validation. Section 7 of the freeze foresaw this:
"perhaps none".

## Provenance

**Freeze:**
- `FREEZE-V3.md`, approved by Can Koç on 2026-11-20. The approval commit `948b46b0` changes only the status line.
- Manifest sha256 `0a40cbdf863da6eb046a1c76726d53bf2e967bfa3e0056b1ac15b87cbc7b85c7`.
- `FREEZE-V3.md` as run: sha256 `1016a46266b234911fb38e00d23d054ca1ceedda73ffdb0b3b6de65ba7f9e5f3`.
- Both hashes in the run's `meta.json` equal the files at `948b46b0`.

**Run:**
- `run_validation_v3.py` on Arch, from a clean clone at `948b46b0`. It ran from 2026-11-20 13:53:56 to
  2026-11-21 00:56:18 +03 (39742.0 s) with 14 workers. `score_validation_v3.py` ran right after it, in the same
  script.
- The tracked tree was clean, and the runner's checks passed: environment lock, manifest, approval line and seed
  block.
- Environment: CPython 3.12.13, numpy 2.5.5, scipy 1.18.1, HiGHS 1.12.0 (as freeze 2).
- **The machine during the run:**
  - no reboot (up since 2026-11-16 22:35);
  - two package transactions, 25 packages installed, none upgraded or removed:
    - at 14:42, 13 packages (among them a second kernel, linux-lts, installed but not booted, and shell tools);
    - at 00:34, a media player and its 11 dependencies.
  - The run's Python environment is a virtual environment that pacman does not manage.
  - The KDE file indexer (Baloo) was turned off at about 15:26 and its index deleted.

**Outputs** (`results/v3/freeze3/validation-440400-440599-948b46b0/`):

```
d9b90cef1c9b932468888fa375ff11c8373520ce0d972337b5631cbee3f6988f  rows.jsonl
ea0b4b8b618af45a53dcf74eb3d675e31945c87642bd263ab23b80a0eced1f67  scores.json
ce04b06f72498ab63d36700d85ea2022a6b61bd73aafda74bcfc69780c165ff2  meta.json
58eb03d5c995bf2a920ff5963b3257aec61fafe5a00aef98815cd3eb47a876a8  run.log
6beb4a778c53e96c92b02497e961c0a91b58e752abae6707200b15f1f673f565  v3-validation3-948b46b0-solver_attempts.tar.gz
```

- `run.log` is the runner's log followed by the scorer's, as written on Arch. `.gitignore` excludes `*.log`, so it
  is not tracked, as with freeze 2. It is kept next to the tracked files and in both copies below.
- The archive holds the oracle's `solver_attempts/` (117,606 attempts, 30.1 MB). It is not in the repository. Copies
  are in `~/Downloads/sdts-runs/` on the Mac and `~/Research/sdts-runs/v3-freeze3-948b46b0/` on Arch. The copy was
  checked file by file against Arch (sha256 of the sorted concatenation).
- The rows were scored again on the Mac with the frozen `score_validation_v3.py`, from a clean worktree at
  `948b46b0`, with the same Python, numpy and scipy versions. The resulting `scores.json` is byte-identical.

## Verdict

| | target | D_paired | seed bootstrap 95 % (descriptive) | misses (v2: 27) | soundness | uncertified alarms | verdict |
|---|---|---|---|---|---|---|---|
| F3 (W = 256, B = 16, K_cap = 64) | 0.80 | 0.9952 | [0.9899, 0.9995] | 0 | 0 | 0 | **PASS** |

Section 4 decides in a fixed order. Each step, as scored:
1. Integrity: no problem.
2. Soundness: no alarm on an admissible run, none before the oracle's t*, and every alarm certified.
3. Completeness: no row missing, and 3 undetermined fault runs of 8000 (0.04 %, against a limit of 1 %).
4. Misses: 0 (v2: 27). D_paired: 0.9952, at least 0.80.

**Data:**
- 9600 of 9600 runs. Identity and integrity checks passed: none missing, duplicated or extra.
- 8000 fault runs:
  - 7255 detection events (certified oracle t*);
  - 742 certified consistent;
  - 3 not certified.
- Paired set (events that v2 detects): 7228.
- Admissible runs: 2342 (every healthy run, plus the certified-consistent fault runs). Neither v2 nor F3 flagged any
  of them.

## F3 on this block

**OBSERVED:**
- **Alarms:** 7258, all certified. Each has a finite, negative certified margin; the largest is −0.0147 mC. None used
  a box side.
  - 7255 are on the detection events;
  - 3 are on the undetermined fault runs (below).
- **The undetermined fault runs.** The oracle gives a candidate t* there, without a certificate. They are outside the
  scored sets.

  | seed | cell | arm | ambient | the oracle's candidate t* | F3's alarm | v2 |
  |---|---|---|---|---|---|---|
  | 440418 | drift_0.0005 | E1 | ramp | 3521 | 3527 | 3535 |
  | 440430 | drift_0.001 | E0 | rw | 3282 | 3282 | 3293 |
  | 440506 | drift_0.0005 | E0 | ramp | 3402 | 3433 | none |

- **No fallback.** Every failsafe counter is 0, summed over all 9600 rows:
  - no fold direction fell back to P_J or to the a priori clamp, and no fold reset;
  - no as-range side and no certificate side fell back to the box;
  - no box-certified alarm, no measurement dropped, no empty slab.
- **LPs and retries:**
  - F3 made 53,968,652 LPs;
  - 722 retries on 320 runs, at most 10 on one run:
    - 692 on 294 of the 800 edge-noise runs;
    - 26 on 24 uniform-noise fault runs;
    - 4 on 2 uniform-noise healthy runs.
  - Every LP was solved within its three attempts. Freeze 2's failure, a fold LP that failed all three, did not occur
    on this block.
- **The window:**
  - 2,827,891 evictions, all on the 800 edge-noise runs;
  - at most 65 kept (per-run maximum: median 36, p95 65), as on DEV and in freeze 2;
  - at most 445 LP rows and 679 variables, as in freeze 2;
  - 4 folds raised to their dual bound, on 2 healthy edge-noise runs:
    - 440471 E0 ramp: 3, the largest raise 4.8e-5 °C;
    - 440570 E1 ramp: 1, 4.2e-6 °C.

These counts are not rates. The runs are not independent trials, and the retries concentrate on edge noise.

## Secondary, reported (not deciding)

| | v2 | F3 |
|---|---|---|
| exact match with the oracle's t* (of 7255) | 5257 | 7243 |
| misses | 27 | 0 |
| lag p90 / max (s) | 55 / 2215 | 0 / 212 |
| paired lag L (s) | 262482 | 1264 |
| D_paired | — | 0.9952 |
| D_censored (misses at N − t*) | — | 0.9960 |
| runs later than v2 | — | 0 |
| unproved LP alarms | — | 0 |

**Pre-specified subgroups:**
- drift_0.0005 / ramp: 378 events, D_paired 0.990, no misses;
- rw: 3477 events, D_paired 0.997, no misses.

**Against the DEV reference** (`FREEZE-V3.md` section 5, measured before validation data existed): D_paired was
0.99921 on DEV, with no miss; it is 0.9952 here. Freeze 2's F reached 0.9949 on another block (440200–440399).

## Per cell (lag sums over detected events, misses)

| cell / ambient | v2 | F3 |
|---|---|---|
| drift_0.0005 / ramp | 55912 s, 15 missed | 546 s |
| drift_0.0005 / rw | 2918 s, 2 missed | 0 s |
| drift_0.001 / ramp | 46560 s | 320 s |
| drift_0.001 / rw | 5931 s, 2 missed | 0 s |
| drift_0.002 / ramp | 10850 s | 0 s |
| drift_0.002 / rw | 134870 s | 398 s |
| drift_0.005 / ramp | 2746 s | 0 s |
| drift_0.005 / rw | 1746 s | 0 s |
| drift_0.02 / ramp | 276 s | 0 s |
| drift_0.02 / rw | 268 s | 0 s |
| gain_0.01 / ramp | 10 s | 0 s |
| gain_0.01 / rw | 18 s | 0 s |
| jump_0.2 / ramp | 112 s, 8 missed | 0 s |
| jump_0.2 / rw | 90 s | 0 s |
| jump_0.5 / ramp | 12 s | 0 s |
| jump_0.5 / rw | 8 s | 0 s |
| noise_x2 / ramp | 32 s | 0 s |
| noise_x2 / rw | 38 s | 0 s |
| stuck / ramp | 32 s | 0 s |
| stuck / rw | 53 s | 0 s |

The drifts carry 99.8 % of v2's lag. F3 has lag left in three cells: drift_0.0005 / ramp, drift_0.001 / ramp and
drift_0.002 / rw, the same three as F in freeze 2. The full table is `by_cell` in `scores.json`.

## The oracle at the noise boundary

- Of the 800 healthy runs with edge noise, 411 are certified consistent and 389 are undetermined (freeze 1: 427 and
  373; freeze 2: 412 and 388).
- Of the 800 healthy runs with uniform noise, 799 are certified consistent and 1 is undetermined: 440582, E1, ramp.
  Freeze 2 had one as well (440322, E1, ramp); freeze 1 had none.
- The frozen rules judge healthy runs by ground truth (admissible by construction), so this does not touch the
  verdict.

## Infrastructure

**OBSERVED:**
- 8 of the oracle's 117,606 solver attempts died by SIGSEGV:
  - all 8 interior point (`highs-ipm`), 7 without presolve and 1 with it;
  - all on the `margin` problem, with 2700 to 3600 samples, after 8.1 to 14.7 s;
  - all on uniform-noise fault runs, 7 runs in all (440506 drift_0.0005 E1 ramp had two).
- Each attempt's stderr shows a segmentation fault inside scipy's HiGHS wrapper (`_highs_wrapper`), called from
  `thermal_oracle.py`.
- The attempts by method:
  - interior point: 12,617 attempts, 8 crashed;
  - dual simplex: 104,989 attempts, none crashed.
- Freeze 2 had 16 such crashes, 10 interior point and 6 dual simplex. The DEV rehearsal of this freeze had none in
  1,214 attempts.
- Each attempt ran in its own process, and the oracle went on with its next attempt.
  - 6 of the 7 runs ended certified, with t*. F3 detected each of them at the oracle's t*.
  - 1 ended undetermined: 440506 drift_0.0005 E0 ramp, one of the 3 undetermined fault runs above.
- The oracle's attempts also returned status 4 2,940 times, out of 117,598 that returned (freeze 2: 3,338 of
  118,348).
- F3's own LPs run in the worker's process. None crashed.
- Nothing here is an infrastructure failure in the sense of `FREEZE-V3.md` section 6: the run did not crash, the
  machine did not reboot, and no row is incomplete. Nothing was rerun.

**UNKNOWN:**
- whether the crash is what left 440506 E0 undetermined. Not examined.
- why HiGHS crashes on these LPs, and whether it crashes every time. The attempt records do not keep the LP.

## What this supports, and what it does not

**Supported:** H-F3 as written (section 0). The frozen float64 reference implementation, F3 at W = 256, B = 16 and
K_cap = 64, was sound and certified every alarm on 200 fresh seeds. It missed no event and reduced v2's paired lag by
99.5 %. The setting is the same plant with known parameters, under the simulated ambient and noise laws of
`dev_scenarios.py`, in Python with HiGHS through scipy.

**Not shown by this validation:**
- **The solver-failure path.** It did not run on this block (above). How often the solver fails, and what a fallback
  costs in lag, are unmeasured on validation seeds (section 7).
- Everything else in section 7: an MCU, float32, a real plant or model mismatch, the ambient box, detection at the
  noise bound, sensor faults an ambient path reproduces, independence beyond the seeds, and the memory bound in bytes
  or time.

**Unchanged:**
- freeze 2's FAIL (`RECORD-2026-11-19-validation.md`);
- freeze 1's results (`RECORD-2026-11-18-validation.md`).

The block 440400–440599 is now used. 440600–440999 stay reserved.

## Open, not started

- **An independent re-scoring** of these rows, as was done for freeze 2. It would check the numbers, not change the
  verdict.
- **The post-freeze code fixes** listed in `FREEZE-V3.md` section 5:
  - the two docstrings;
  - a check for at least one variable;
  - a missing multiplier field counted as a failed attempt;
  - an exact underflow term for any box;
  - the error-state guard extended to F3a's audit.

  They change no decision in the frozen candidate, and they come before any release of the code.
- **The oracle's crashes.** Replaying the 7 runs would regenerate validation-seed data. That is outside section 6,
  so it needs an explicit decision, and it cannot change the verdict.
