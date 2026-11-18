# v3 freeze 1: independent validation on seeds 440000–440199 (2026-11-18)

The verdicts below are those of the frozen scoring rules (`FREEZE-V1.md` section 4, `score_validation.py`), as they came
out. Nothing was rerun, retuned or rescored with other rules.

## Provenance

**Freeze:**
- `FREEZE-V1.md`, approved by Can Koç on 2026-11-18. The approval commit `8e58991` changes only the status line.
- Manifest sha256 `e8dd60f134252c1855aca040a46836281db57c1ee19da9713f4c7a25d6e18a96`.
- `FREEZE-V1.md` as run: sha256 `d240b4bb9597dca50f017bc008c84d8a58ddca2c793c618a3455aa914202a5de`.

**Run:**
- `run_validation.py` on Arch, 2026-11-18 06:09:28 to 09:48:01 +03 (13113.5 s), 14 workers.
- Tracked tree clean; the run's checks passed (manifest, approval line, seed block).
- Environment: CPython 3.12.13, numpy 2.5.5, scipy 1.18.1, HiGHS 1.12.0.
- The C builds were compiled by the runner with GCC 16.2.1 (`-O2 -std=c99 -ffp-contract=off -fno-fast-math`).

**Outputs** (`results/v3/freeze1/validation-440000-440199/`):

```
0d5c5013d5084f168381eea4769b84804ebce04d85dd62a236e72f42f6cbe1e3  rows.jsonl
ec9c2c6e2db5e0c82b9bb833f90025083b0a8a2a9de44cbdd2cc4e0684efcba9  scores.json
a01d880d39711e3906348f7bdfe7c8c0479a0540ade643dc00cf2fe591fa01a4  meta.json
71e3479266ef257338c4908355912557e523935e3bc0732e2a2e45a319f973f8  v3-validation1-8e58991-solver_attempts.tar.gz
```

- The archive holds `solver_attempts/` and `c_build/` (9.4 MB). It is not in the repository; it is in
  `~/Downloads/sdts-runs/` on the Mac and `~/Research/sdts-runs/` on Arch.
- The rows were scored again on the Mac with the frozen `score_validation.py`. The resulting `scores.json` is
  byte-identical.

## Verdicts

| | target | D_paired | seed bootstrap 95 % (descriptive) | misses (v2: 24) | soundness | dominance | verdict |
|---|---|---|---|---|---|---|---|
| inv4p | 0.10 | **0.152** | [0.107, 0.205] | 20 | 0 | 0 | **PASS** |
| cyl16p | 0.25 | **0.387** | [0.323, 0.453] | 16 | 0 | 0 | **PASS** |

**Data:**
- 9600 of 9600 runs.
- 8000 fault runs:
  - 7201 detection events (certified oracle t*);
  - 795 certified consistent;
  - 4 not certified (0.05 %, against a limit of 1 %).
- Paired set (events that v2 detects): 7177.
- No method flagged any of the 2395 admissible runs (every healthy run, plus the certified-consistent fault runs).

**Secondary, reported (not deciding):**

| | v2 | inv4p | cyl16p |
|---|---|---|---|
| exact match with the oracle's t* (of 7201) | 5229 | 5722 | 5959 |
| lag p90 / max (s) | 53 / 2527 | 38 / 1936 | 21 / 1936 |
| paired lag L (s) | 233441 | 197853 | 143205 |
| D_censored (misses at N − t*) | — | 0.132 | 0.368 |

**Against the DEV reference** (FREEZE-V1.md section 5, measured before validation data existed): D_paired 0.147 and
0.386 on DEV; 0.152 and 0.387 here.

## Per cell (lag sums over detected events, misses)

The slow drifts carry 99.8 % of the lag for all three methods:

| cell / ambient | v2 | inv4p | cyl16p |
|---|---|---|---|
| drift_0.0005 / ramp | 42328 s, 16 missed | 33334 s, 16 missed | 27436 s, 14 missed |
| drift_0.0005 / rw | 2062 s, 2 missed | 444 s, 0 missed | 410 s, 0 missed |
| drift_0.001 / ramp | 40886 s | 33052 s | 25876 s |
| drift_0.001 / rw | 5916 s, 2 missed | 876 s, 0 missed | 806 s, 0 missed |
| drift_0.002 / ramp | 9522 s | 6350 s | 5190 s |
| drift_0.002 / rw | 125638 s | 119452 s | 80656 s |
| drift_0.005 / ramp | 4046 s | 1672 s | 1140 s |
| drift_0.005 / rw | 1938 s | 1780 s | 1090 s |
| jump_0.2 / ramp | 120 s, 2 missed | 70 s, 2 missed | 74 s, 0 missed |
| jump_0.2 / rw | 200 s, 2 missed | 196 s, 2 missed | 152 s, 2 missed |

The rest are near zero for every method. The full table is `by_cell` in `scores.json`.

**What the cells say:**
- inv4p's gain is spread unevenly. It is large where the ambient is a random walk (drift_0.0005 and drift_0.001 rw:
  −78 % and −85 % lag, and no misses). It is small on drift_0.002 / rw (−5 %).
- cyl16p, with the faces orthogonal to TA, takes drift_0.002 / rw down by 36 %.
- This matches the DEV finding that the remaining loss is the ambient's lower bound.

## The C builds (reported; not the tested object)

| build | soundness violations | same as Python | later than Python | misses Python's detection | later than v2 | D_paired | misses |
|---|---|---|---|---|---|---|---|
| inv4p float64 | 0 | 9600 | 0 | 0 | 0 | 0.152 | 20 |
| cyl16p float64 | 0 | 9600 | 0 | 0 | 0 | 0.387 | 16 |
| inv4p float32 | 0 | 9352 | 240 | 8 | 130 | 0.004 | 28 |
| cyl16p float32 | 0 | 9292 | 304 | 4 | 52 | 0.212 | 20 |

- **The float64 builds equal the Python reference on every run.**
- **The float32 builds are sound,** including all 800 healthy runs with noise exactly at ±δ. "The float32 MCU build is
  sound" holds on this block.
- **But float32 gives back almost all of inv4p's gain:**
  - D_paired drops to 0.004;
  - it misses 28 events, more than v2's 24;
  - it is later than v2 on 130 runs.
- **cyl16p loses part of its gain the same way:** D_paired 0.212, below the 0.25 that its float64 form passed.
- Neither float32 build was the object of a hypothesis (FREEZE-V1.md section 4). Had they been, inv4p float32 would
  fail on misses and on its target, and cyl16p float32 on its target.
- **Precision is a budget axis of its own.** This is the effect the DEV rehearsal showed on one run, now on many.
  HYP, not checked: the static float32 pads accumulate in the directions that only the clamps bound.

## The oracle at the noise boundary

- All 800 healthy runs with uniform noise are certified consistent.
- Of the 800 healthy runs whose noise is exactly ±δ, 427 are certified consistent and **373 are undetermined**. Those
  records sit on the constraint itself, and the oracle does not certify either way there.
- DEV never ran the oracle on edge noise, so this is new.
- The frozen rules judge healthy runs by ground truth (admissible by construction), so it does not touch the
  verdicts. It is a limit of the oracle, not of the candidates.

## Infrastructure

- Eight solver attempts died, out of all the attempts of 9600 runs:
  - seven of HiGHS without presolve, by SIGSEGV (five IPM, two dual simplex);
  - one by SIGKILL (an attempt timed out and was killed).
- Each ran in its own process. The oracle went on with its next attempt (the presolve fallbacks of `da6e4a0`), and
  **all eight runs ended with a certified t\***.
- None of them is among the 4 uncertified fault runs:
  - 440004 drift_0.0005 E0 ramp;
  - 440041 drift_0.0005 E0 and E1 ramp;
  - 440102 drift_0.0005 E1 ramp.
- Nothing here is an infrastructure failure in the sense of FREEZE-V1.md section 6. Nothing was rerun.

## What this supports, and what it does not

**Supported:** H-inv4 and H-cyl16 as written. On 200 fresh seeds of the v3 scenario distribution, the frozen float64
template states:
- are sound under the model;
- are never later than v2;
- miss fewer events than v2;
- cut v2's paired lag by 15 % (16 numbers, 231 table entries) and 39 % (42 numbers, 1318 entries).

**Not supported, or not tested:**
- the float32 MCU builds' accuracy (see above: sound, not accurate enough);
- timing on a Cortex-M;
- a plant whose parameters differ from the model's;
- other plants or other ambient behaviour than the two laws;
- anything about sensor correctness beyond the constant-offset class (Theorem 4);
- closing the residual gap to the oracle (both candidates still miss 14–16 drift_0.0005 ramp events that the oracle
  detects).

**Next, not started:**
- The candidates and rules of freeze 1 do not change.
- A float32-aware variant, or more TA-orthogonal faces, would be a new freeze with seeds from 440200 onwards (reserved,
  never generated).
