# SDTS v3 — first results (night of 2026-11-18)

Branch `sdts-v3/template-state`. Theory and labels are in `V3_NOTES.md`.
- **Data:** DEV seeds only (430000–430099). No v2 FINAL, CAL or TRAIN data was used. The VALIDATION seeds
  (440000–440999) were never generated.
- **Runs:**
  - main comparison `run_dev.py` at `45cff1d`, on Arch: 1320 runs, 2067 s, rows sha256 `f823e50c…6bd0`;
  - template evaluations and pruning on the same rows;
  - C checks on the Mac.

## 1. Question and yardstick

How close can a bounded, deterministic, online state get to the full-history information, and at what RAM,
flash, cycle and precision cost?

- **Yardstick:** the certified v2 oracle (full-history LP).
- **Decision, identical for every method:** the first sample at which no explanation with b = 0 and
  |noise| ≤ δ exists. Only 1 of 1320 oracle t* is uncertified (430003 drift_0.001 E1 rw).
- **Scenarios:**
  - 30 seeds;
  - 11 cells (healthy plus 10 fault cells);
  - arms E0 and E1;
  - two ambient laws: the v2 random walk, and full-rate ramps;
  - noise uniform in ±δ.

  This gives 1082 runs that the oracle finds inconsistent.

## 2. What is kept and what is lost (MATH, checked numerically)

**Theorem 1.** The full-history information is a 3-D convex polytope X_k over (ac, as, TA).
- **Check:** an independent exact online recursion by vertex enumeration (`exact_vrep.py`) reproduces the
  oracle's certified t* on 5 of 5 DEV runs: 673, 393, 579, 695, 467.
- **Size:** X_k has a median of 3–7 thousand vertices and up to ~16 thousand (float diagnostic). An exact
  state is not MCU-sized.

**The v2 machine** keeps the 1-D projection of X_k on as. It loses the error state (ac − TA, as − TA). Its lag
behind the oracle is therefore pure representation loss, not decision-rule difference.

**Inconsistency proofs** (the oracle's dual at t*, `certificate_span.py`):
- They are **sparse**: median 6 measurements, at most 14.
- They are **long-range**: the median span is 270–480 samples per cell, at most 1285.
- **More raw history is not what is needed; shape is.** The proof combines a handful of extreme measurements
  far apart in time, coupled through the same ambient path.

**Where a template loses it** (430007, k = 660, just before t*):
- The largest support gaps against the exact X_k are in directions dominated by −TA, i.e. the lower bound on
  the ambient: 0.058 °C too loose.
- Windows of transported past-measurement normals (up to 32 samples, 629k table entries) changed nothing.
  Each transported halfspace pays its own worst-case ambient step, and M⁻¹ amplifies that exponentially. The
  exact set uses one common ambient path.
- What helped were directions orthogonal to TA: the faces that the Minkowski sum with the ambient segment
  creates.

## 3. Resource vs fidelity (DEV, 1082 oracle-inconsistent runs; healthy and soundness checks on all 1320)

Unsound events (a healthy run flagged, or a detection earlier than the oracle) are **0 for every method**.

| method | state numbers | table entries | flash f32 | MAC/sample | = oracle | missed | lag p90 (s) | lag sum (s) |
|---|---|---|---|---|---|---|---|---|
| v2 machine | 2 | — | — | ~6 | 805 | 8 | 49 | 32953 |
| box (no invariants) | 6 | 22 | 0.5 KB | 66 | 181 | 261 | 1152 | 287324 |
| box + diff (no v-direction) | 10 | 186 | 4 KB | 558 | 701 | 8 | 55 | 37076 |
| inv2 + I | 14 | 814 | 12 KB | 2442 | 864 | 6 | 30 | 28096 |
| inv4 + I | 16 | 1384 | 21 KB | 4152 | 864 | 6 | 30 | 28096 |
| inv4 + I, pruned to used bases (selection DEV 430050–069) | 16 | 231 | 3.7 KB | 693 | 864 | 6 | 30 | 28096 |
| inv4 + I, pruned top-3 per direction | 16 | 74 | 1.3 KB | 222 | 843 | 8 | 34 | 31309 |
| inv4 + I, pruned top-1 per direction | 16 | 40 | 0.8 KB | 120 | 807 | 8 | 49 | 32947 |
| inv16 + I / inv8 + orbit4 + I | 40 | 35–62k | 0.8–1.4 MB | 0.1–0.2 M | 864–866 | 6 | 30 | 28072–28096 |
| cyl8 + inv4 + I | 26 | 8110 | 187 KB | 24k | 880 | 6 | 27 | 25224 |
| cyl16 + inv4 + I | 42 | 38966 | 896 KB | 117k | 898 | 4 | 19 | 20386 |
| cyl16 + inv4 + I, pruned to used bases (selection: 120 DEV runs, 430050–052) | 42 | 1318 | 20 KB | 4k | 898 | 4 | 19 | 20386 |
| cyl16 + inv4 + I, pruned top-3 per direction | 42 | 201 | 3.5 KB | 0.6k | 807 | 8 | 49 | 32885 |
| cyl24 + inv4 + I | 58 | 107966 | 2.5 MB | 324k | 904 | 2 | 19 | 20188 |
| window8 + inv4 + I (past-measurement normals) | 32 | 26224 | 0.6 MB | 79k | 866 | 6 | 30 | 28016 |
| sphere30 (generic dense directions) | 70 | 478378 | 11 MB | 1.4M | 850 | 2 | 25 | 20095 |

What the table says:
- **Structure beats size.**
  - Without the reachable-set invariants (offline, flash only), 5× more state numbers than v2 does *worse*
    than v2.
  - With them, 14 numbers are provably never later than v2 (Theorem 3). On DEV they give −15 % total lag,
    +59 exact matches and 2 fewer misses.
- **Generic directions saturate.** From 14 to 40 numbers in the error plane or orbits nothing changes.
- **Directions orthogonal to TA keep improving:** cyl8 −23 %, cyl16 −38 % total lag. That is a real budget
  curve, but at large flash cost before pruning.
- **Flash can be cut hard without loss.** Keeping the bases ever used on a disjoint DEV selection set takes
  inv4 from 1384 to 231 entries with *identical* results. Cutting further walks back towards v2. Pruning can
  never break soundness: a min over fewer bases is still an upper bound.

## 4. MCU implementation (C, `experiments/v3/c/`)

**Design:**
- `v3_state.c`: fixed arrays, no allocation, no LP. The state is n reals, plus the known command part S in
  double.
- **Why S is double:** a float32 S accumulates unbounded error over 3600 steps that no pad covers.

**Tables:** generated by `codegen_c.py`, with per-direction static pads for the dot-product rounding, the
residual and the λ rounding. Constants are rounded upward.

**Checks against Python** (`check_c.py`, DEV 430030–430034, 156 detections, healthy runs including ±δ edge
noise and full-rate ramps):

| build | flash (float32) | double vs Python | float32 vs Python | unsound |
|---|---|---|---|---|
| inv4 full | 21 KB | identical | identical on 148; 12–390 s later on 8 | 0 |
| inv4 pruned | 175 entries, ~2.9 KB | identical | identical on 154; 22 s later on 2 | 0 |

The pruned build has 64 B of state plus S. "Unsound" counts healthy runs flagged and detections earlier than
Python.

**Precision is a budget axis of its own.** Float32 is sound, but in a few boundary cases it gives up
information.

**Cycle estimate (counts, not measured):** the pruned inv4 needs ~525 MAC per sample, which is well under
1 ms at 1 Hz on a 64 MHz Cortex-M4F. Hardware timing is OPEN.

## 5. Alternative explanations and what no budget can fix

**Constant offset as a 4th dimension** (`template_offset.py`, `eval_offset.py`, DEV 430060–079, 200 runs, 89
oracle-consistent):
- Excess width over the oracle's exact offset interval:
  - v2 (2 numbers): mean 0.020 °C, max 0.093;
  - 4-D template (24 numbers): mean 0.017 °C, max 0.091.
- R = 1 and R = 3 certification agree with the oracle on 89 of 89 for both.
- **The offset class is cheap to represent. The compression loss lives in the dynamics, not in the offset.**

**Theorem 4 (impossibility).** A sensor error that an admissible ambient path can reproduce cannot be bounded
by any method, with any memory.
- **DEV witnesses:** 430056 and 430059 (drift_0.001). The certified full-history oracle gives *exact* offset
  intervals [−0.70, 0.12] and [−0.48, 0.24], so |b| ≤ 1 is certified. The true end error is 3.17 and
  3.18 °C.
- The v2 "drift certificate" is a property of the hypothesis class, not of compression.
- What compression does add (v2 FINAL 420004): a certificate on a run that full information refutes.

## 6. The budget curve, after pruning

Lag is the total over 1082 runs. Pruning uses selection sets disjoint from the evaluation seeds.

| point | RAM state | flash (float32) | = oracle | missed | total lag |
|---|---|---|---|---|---|
| v2 | 2 numbers | — | 805 | 8 | 32953 s |
| inv4 + I, used bases | 16 numbers | ~3–4 KB (C build ~2.9 KB) | 864 | 6 | 28096 s (−15 %) |
| cyl16 + inv4 + I, used bases | 42 numbers | ~20 KB | 898 | 4 | 20386 s (−38 %) |
| cyl24 + inv4 + I, not pruned | 58 numbers | 2.5 MB | 904 | 2 | 20188 s (−39 %) |

- **The curve is real:** more of the *right* shape (faces orthogonal to TA) buys accuracy.
- **Pruning to the bases actually used costs nothing measurable** on DEV and shrinks flash 6–30×.
- **Pruning harder collapses to v2**: top-k per direction loses the rarely used but decisive bases.
- **Generic dense directions (sphere30)** reach a similar total lag but match the oracle exactly less often
  (850): they spend budget on directions that do not matter.
- **The largest single lag (2880 s, drift_0.0005 ramp)** survives every bounded state tried. It is OPEN.
  - Diagnostic for 430010 at k = 690, five samples before t* = 695: the cyl24 state holds the ambient lower bound
    0.023 °C looser than the exact X_k. Every top gap is a −TA-dominated direction.
  - For a fault this close to the detectability boundary (0.0005 °C/s), 0.023 °C of set looseness costs 2880 s
    of latency.
  - **Latency is a very ill-conditioned function of representation error near the boundary.** Budget studies
    should also report set tightness (support gaps), not only latency.

## 7. Honest summary

**Shown:**
- The full-history information of this problem fits a 3-D state (proof, plus an independent numerical check).
- Its exact description is too large for an MCU: thousands of vertices.
- A sound, LP-free, fixed-memory state of 16 numbers, ~3 KB flash and ~500 MAC per sample is never later
  than v2 (proof) and closer to the oracle on DEV.
- Better directions (orthogonal to TA) move it further towards the oracle: 42 numbers and ~20 KB flash give
  −38 % total lag and half of v2's misses.

**Not shown:**
- that any bounded template reaches the oracle in general: a residual of hundreds of seconds remains on some
  drift runs;
- anything under plant-parameter mismatch;
- anything on hardware;
- anything on independent data.

**Refuted or limited along the way:**
- "more numbers help" (without structure they hurt);
- "a longer window of past measurements helps" (it did not);
- "sensor error can be certified against slow drift" (impossible, for any memory).

**Not claimed:** novelty of the ingredients (template polyhedra, set-membership, mRPI sets, basis
enumeration).
