# SDTS v3: MCU feasibility notes (phase 2b, exploratory; 2026-11-19)

**Status:** exploratory. These are not pre-registered, and every row below is labelled.
- **Source:** an independent analysis on 430010 (t = 300–695, plus one edge-noise run, 430070), at `0e28951`, on Arch,
  single process, HiGHS 1.12.0.
- **Outputs:** `results/v3/mcu/N1-430010/` (report, results JSON, script, DONE.txt hashes checked).
- **Spot-checked against the results file:** the warm-start counts and the mixed-precision replays.

## Numbers

**Dense B⁻¹ (OBSERVED, arithmetic):**

| | float32 | float64 |
|---|---|---|
| F, m = 409 | 669 kB (653 KiB) | 1307 KiB |
| F under edge noise, m = 445 | 774 KiB | – |
| N, m = 183 | 131 KiB | – |

So a dense inverse is out for F.

**Sparse LU fill** (OBSERVED, scipy `splu`, on the optimal bases, COLAMD ordering):

| | nnz(L+U), median / max | fill |
|---|---|---|
| F step | 2,658 / 2,992 | about 3× |
| F fold | 2,771 / 3,064 | about 3× |
| F under edge noise, max | 3,279 | – |
| N step | 684 / 790 | about 1.8× |

The MMD ordering is about 30 % worse.

**Static solver SRAM** (INFERRED, an estimate, not measured on a device): uint16 indices, a 1.25× LU margin, a
50-pivot eta file, and two warm bases.

| | float32 | float64 |
|---|---|---|
| F | 84 KiB, about 105–115 KiB with the refactorisation workspace | 140 KiB |
| N | 46 KiB, about 60–70 KiB | – |

**Warm-started dual simplex iterations** (OBSERVED, HiGHS with `setBasis`; 430010, t = 1–695; all 1,334 consecutive
bases mapped, with no failure):

| | median | mean | p95 | max |
|---|---|---|---|---|
| F step, cold | 387 | 347 | 498 | 720 |
| **F step, warm** (separate bases for up and dn) | **0** | **0.87** | **3** | **62** |
| F step, warm, one shared basis | 36 | 38.5 | – | 119 |
| N step, warm | 0 | 0.71 | 2 | 43 |
| F fold, 42 LPs, cold | 16,157 | – | 16,603 | 16,906 |
| **F fold, 42 LPs, warm, directions in a nearest-neighbour order** | **557** | – | **651** | **678** |

- Warm primal is slower than warm dual.
- Warm primal also hit a non-optimal status once, in F and in N.

**Certificates on 430010** (OBSERVED):
- **A pure float32 certificate is unusable.** It adds up to +3.1 mC at the alarm (its margin is −0.286 mC) and up to
  40 mC at a fold.
- **A float32 solve with a float64 certificate works.**
  - The LP data is quantised to float32 and solved at tol 1e-6.
  - One float64 basis back-solve, Bᵀπ = c_B, refines the duals.
  - The end-to-end online replay detects at 695 with a margin of −0.28548 mC, and no fold needed raising.
- **An int64 fixed-point certificate (Q30 × Q24)** shows no soundness violation over 1,842 LPs. Its accumulator peaks
  at 61 bits, and it adds at most 0.012 mC at a fold.

## Reading (INFERRED, to be tested)

- **The obstacle looked like the LP solver. With warm starts it mostly goes away.** A step is about one pivot on
  average, and a whole fold about 560 pivots.
- **F's SRAM of roughly 100–115 KiB in float32** fits Cortex-M4 and M7 parts with 192 KiB or more.
- **Not yet shown:**
  - a real float32 (or fixed-point) dual simplex on a device;
  - the worst case over all of DEV, not one run;
  - measured cycles;
  - the warm start of the fold's first direction.

  These are the 2b items, together with a WCET-certified solver (the DAQP or EIQP line).

## 2c. The template state on an 8-bit board (exploratory, DEV only; 2026-11-21)

**Status:** exploratory, not pre-registered. DEV seeds only; no validation seed was generated. The candidate is
freeze 1's cyl16p, in its **float32 C build** (`frozen/c/tables_cyl16p_float.h`), not the validated float64 form.

**Setup:**
- **Board:** an Arduino Uno (ATmega328P, 16 MHz, 2 KB SRAM, 32 KB flash), driven from Arch over USB serial.
- **Code** (`mcu/avr/`):
  - `avr_state.c` is `c/v3_state.c` with the tables read from flash and `nextafter` written on the bit patterns.
  - The tables are a copy of the frozen header with `PROGMEM` added. `make_progmem.py` checks that nothing else
    differs.
  - The command part S is binary64 (avr-gcc 16.2, `-mdouble=64`); a static assert refuses any other build.
- **Reference:** `host_trace.c` runs the unchanged `c/v3_state.c` on the PC with the same inputs. After every sample
  the board's state (k, tc, ts, flag, h) is compared with the PC's, byte for byte.
- **Results:** `results/v3/mcu/avr-uno-20261121/` (runs, the arithmetic test, build facts, hashes).

**OBSERVED, four DEV runs** (430030 jump_0.5 E1 rw, 430031 stuck E1 ramp, 430010 drift_0.0005 E0 ramp, 430030
healthy E0 ramp edge):

| | |
|---|---|
| first inconsistent sample, board = PC | on all four: 500, 462, 3575, none |
| time per sample | median 74.1–74.7 ms, max 75.3 ms (1 s sampling: about 13× margin) |
| SRAM | 602 of 2048 bytes at peak (271 static), by stack painting |
| flash | 28,064 of 32,768 bytes |
| state equal to the PC's, bit for bit | at the start, and on few samples after; most samples differ by 1–2 ulp in h |

**OBSERVED, the board's arithmetic** (`fptest`, 2000 operand pairs per operation, against IEEE 754
round-to-nearest-even on the PC):
- float ×, +, −: equal on all 6000.
- double → float conversion: 1002 of 2000 are one ulp toward zero. The conversion truncates.
- binary64 (libf7) ×: 128 of 2000 differ by ±1 ulp; + and −: 22 each. Faithful, not correctly rounded.

**INFERRED, to be checked before any claim:**
- The h differences come from the truncating conversion of the slab bounds lo and hi.
  - The code steps one float ulp outward after that conversion (`DOWN`, `UP`). That covers any conversion error
    below one ulp, so the board's lo and hi stay outer bounds; they are just tighter than the PC's.
  - The supports are monotone in h (the table weights are ≥ 0), and the float operations matched IEEE on every
    tested pair. So the board's h stays an outer bound under the float model the pads were computed for.
  - Not proved here: "matched on every tested pair" is a sample, not a proof about avr-libc's routines.
- The command part S is binary64 on both machines, and its recursion error is covered by no pad, on the PC either
  (section "Precision" of V3_NOTES.md says only that float32 is unbounded). On the board it is faithful, not
  correctly rounded. Its size over 3600 samples is not measured yet. (Closed in 2g, 2026-11-21: ε = 4.85e-13 °C,
  9.9e-13 on the Uno.)

**Not done:**
- the float64 tables, which are the validated form (about 36 KB: too big for the Uno, fits a Mega);
- more runs, and the full DEV comparison;
- a worst-case timing bound.

## 2d. The template state on an ESP32 (exploratory, DEV only; 2026-11-21)

**Status:** exploratory, not pre-registered. DEV seeds only. The same four DEV runs as 2c.

**Setup:**
- **Board:** ESP32-WROOM-32 (ESP32-D0WD-V3 rev 3.1, 240 MHz, 4 MB flash), Arduino-ESP32 core 4.0.0 via arduino-cli
  1.5.1, on Arch over USB serial (CP2102).
- **Code** (`mcu/esp32/`): the **unchanged** `c/v3_state.c` and `c/v3_state.h` and the frozen table header are copied
  into the sketch by `prepare.sh`, which checks their sha256 against the sources. No line of the state code is
  ported.
- **Flags:** `-ffp-contract=off -fno-fast-math`. `prepare.sh` disassembles the state object and refuses a build
  with fused multiply-adds. The check was tested: the same file built with GCC's default contraction has 2 of them.
- **Reference:** `host_trace` (the PC build of the same files), byte for byte after every sample.
- **Results:** `results/v3/mcu/esp32-20261121/`. The double build's `size.txt` was copied by hand from the compile
  output; `prepare.sh` saves it from the float build on.

**OBSERVED:**

| build | samples compared | equal to the PC, bit for bit | first inconsistent sample (= PC) | time per sample, median / max |
|---|---|---|---|---|
| cyl16p **float64** (the validated form) | 8,149 | **8,149** | 500, 462, 3575, none | 3.72–3.74 ms / 4.47 ms |
| cyl16p float32 | 8,149 | **8,149** | 500, 462, 3575, none | 0.49 ms / 1.13 ms |

- **Arithmetic** (`fptest`, 2000 operand pairs each, against IEEE 754 round-to-nearest-even): float ×, +, −,
  binary64 ×, +, −, and the binary64 → float conversion are all equal, 14,000 of 14,000.
- **Memory:** heap 385 KB, 337 KB free after the runs, at least 305 KB free at any time; 6.6 KB of the loop task's
  stack never used. The sketch is 327 KB of the 1.3 MB app partition (float64 build).

**INFERRED:**
- On this board the C code of the validated candidate computes exactly what the PC computes, on these 8,149 samples.
  So whatever holds for the PC build on these inputs holds for the board's output on them.
- The difference from the Uno (2c) is the arithmetic: here every tested operation is IEEE round-to-nearest; on the
  Uno the double-to-float conversion truncates and binary64 is faithful only.
- A pitfall of the default build: GCC contracts two multiply-adds of `v3_state.c` into fused ones on this core. The
  result would no longer be bit-equal to the PC, and the pads were computed for separate roundings.

**Not shown:** all of DEV; a worst-case timing bound (the maximum is over these runs only); F3 (it needs an LP
solver on the board); a real sensor.

## 2e. MCU-2E result: the ESP32 equals the PC bit for bit on all 1400 DEV rows (2026-11-21)

Plan `MCU-2E-PLAN.md`, committed before the run (`3f761a20`). Arch; the board flashed from `prepare.sh
cyl16p_double` at that commit (`BAUD=921600`); the six script files on Arch were checked against the commit
(sha256) before flashing. Run 03:49:54 to 06:44:23 (+0300). Results in `results/v3/mcu/esp32-2e-3f761a20/`.

**Verdict: PASS.** All 1400 rows complete with 3600 samples each, 5,040,000 samples. The init states are equal
byte for byte, and on every sample the flag and the 16-byte hash of the state dump are equal: no row has any
difference. 1078 rows flag, at the same sample on the board and the PC; 322 flag on neither. No infrastructure
restart. Rescored on the Mac from `rows.jsonl` (the row set against `dev_full.rows()`, the counts): the same.

**Before the run** (`controls.txt`, not counted):
- Rehearsal: the first two rows through the hash path, and one of them again through the full-dump path of 2d:
  no difference.
- Negative controls, changing only the PC side: P + 1e-6 at sample 1000 gives 2600 differing samples (all from
  1000 on); one flipped bit of the PC dump at sample 2000 gives exactly 1. One-ulp changes of y or P at sample 1000
  give none, because the state they produce is the same; they do not test the comparison.
- A first control was wrongly designed (the float32 PC build against the float64 board) and was discarded.

**Reported, not deciding:**
- Cycles per sample at 240 MHz, on the 322 rows that never flag: median of the row medians 871,410 (3.63 ms);
  largest row p99 922,834 (3.85 ms); maximum 1,094,108 (4.56 ms). After a flag the state returns at once
  (`v3_state.c` line 46), so the median of the flagged rows' medians is 1,844 cycles; `score.json`'s
  `cycles_median_of_row_medians` (1,846) mixes both kinds of row and is not the cost of a sample.
- Memory after the run: heap 373,852 bytes, 317,560 free, at least 293,784 free at any time; 6,656 bytes of the
  loop task's stack never used. The sketch is 331,777 of 1,310,720 bytes.
- Wall time 2 h 54 min, 16.0 to 16.1 s for a row that never flags.

**INFERRED:** on these 1400 DEV rows, whatever holds for the PC build of freeze 1's cyl16p (float64) holds for
the board's output, because the output is the same bit for bit. On other inputs this is an inference from the
arithmetic of 2d (every tested operation IEEE round-to-nearest), not a test.

**Not shown:** a real sensor or plant; F3 (no LP solver on the board); other boards, compilers or flags; a
worst-case timing bound (the maximum is over these runs).

## 2f. MCU-2F result: the Uno's decisions equal the PC's on 30 DEV rows (2026-11-21)

Plan `MCU-2F-PLAN.md`, committed before the run (`82af2a44`). Arch, clean clone at that commit, the Uno flashed
from it. Results in `results/v3/mcu/uno-2f-82af2a44/`.

**Verdict: PASS.** On all 30 rows the board's first flagged sample equals the PC float32 build's: 26 rows flag,
at the same sample; 4 flag on neither.

**Reported, not deciding:**
- 37,181 samples compared; the whole state is bit-equal on 1,654 of them.
- S (tc, ts) differs on 17,527 samples, on 19 of the 30 rows. The board's binary64 is faithful, not correctly
  rounded (2c).
- h components below the PC's: 292,082 component-samples; above: 311,434. The largest distances are 1,988,608 ulps
  below and 331,776 above.
- Cycles per sample: at most 1,209,720 (75.6 ms at 16 MHz).
- One infrastructure restart: a serial timeout on 430013 drift_0.002 E0 ramp, at its first attempt. The row was
  restarted from its first sample and completed.

**Diagnosis after the verdict** (not deciding; `diagnosis-430005-noise_x2.txt`): the row with the largest ulp
distance, replayed with full dumps.
- The 1,988,608 ulps are at a value near zero: h[13] at sample 460 is −2.64e-6 on the board and −2.19e-6 on the PC.
  That is 4.5e-7 °C, on the less conservative side.
- The largest absolute difference in h in that row is 7.2e-7 °C (about 3 ulps of −2.23).
- S differs by at most 1.1e-14 °C.
- Ulp counts mislead near zero. The absolute differences of the other 29 rows were not recorded.

**INFERRED:** the decisions agree although the states drift apart in the last bits, because the differences
(≤ 7.2e-7 °C where measured) are far below the margins at which the alarm test turns. Whether the board's bounds
stay outer bounds is still the inferred argument of 2c, not a proof; a difference of 4.5e-7 °C on the less
conservative side is smaller than the per-direction pads (≈ 5.5e-6 to 3.1e-5 °C) but is not covered by them by
construction.

## 2g. The C state against the exact recurrence: the S gap (2026-11-21)

**The gap** (2c above; V3_NOTES section 5): the C state computes S in binary64 and its slab from z = y − S with a
one-ulp outward rounding, so S's rounding error is covered by no pad. Its tables were also built against the float
matrix M, not the exact recurrence. F3 closed the same gap with DIAG-3 amendment 9 (the exact recurrence and the
data allowance η = 1e-9 °C); this C state (freeze 1's cyl16p, the code of 2c–2f) has neither.

**The check:** `diag/check_c_state.py`, committed with its criteria before its first run (`1c4cb409`). Exact
rationals throughout; the model is the exact recurrence MX (thermal.py's `step()` with its float parameters taken
exactly). Output `results/v3/c-state/check-1c4cb409.json`.

| | double header | float header |
|---|---|---|
| K1 header = codegen's output from `frozen/cyl16p.json` | yes | yes |
| K2 every table entry's pad covers the dot product's rounding and the residual against MX^T d (1318 entries) | yes; smallest slack 87 % of the pad | yes; 75 % |
| K3 every clamp ≥ the exact recurrence's reachable supremum | yes | yes |
| K4 every rate pad ≥ ρ_A \|d_3\| | yes | yes |
| K5 every start support ≥ the start segment's | **no**: directions 14, 15 | **no**: the same |
| K6 data bound ε < η | ε = 4.85e-13 °C | |

**Verdict of the check: OPEN,** because of K5. Directions 14 and 15 (= −d14) are error-plane directions whose stored
coordinates sum to ±5.55e-17 instead of 0. Codegen summed them in float (0), so their start supports are the
smallest subnormal, while the start segment {t (1, 1, 1) : |t| ≤ 2} needs 1.11e-16.

**Follow-up, written after K5 failed** (`diag/check_c_state_start.py`, committed before its run, `fd4f8591`;
`results/v3/c-state/check-start-fd4f8591.json`): add the shortfall to the start supports and check K2's inequality
again for every entry at k = 0. The 213 entries that use h[14] or h[15] gain at most 2.6e-16; every entry is still
covered, smallest slack 88 % (double) and 75 % (float) of the pad. **Holds.** So the first step absorbs the start
gap, and from k = 1 on K2–K4 carry the induction.

**K6, the data bound (MATH):**
- For commands in [0, 42] from the P0 steady state, the exact recurrence keeps 0 ≤ ts ≤ 42/H and 0 ≤ tc − ts ≤ 42/K.
  (With d = tc − ts: ts′ = (1 − H/CS) ts + (K/CS) d and d′ = (23/30) d + p/CC + (H/CS) ts. All coefficients are ≥ 0,
  the map is monotone, and the steady state at p = 42 is its fixed point.)
- One float step of S errs by at most R = (9.2e-15, 8.9e-15) (core, surface), from the standard model on each of
  the step's operations inside that box.
- The error then propagates through the exact recurrence's 2×2 part A, which is ≥ 0 with row sums 1 and 1 − H/CS.
  So |e_k| ≤ |e_0| + (I − A)⁻¹ R, with (I − A)⁻¹ = [[52.5, 15], [37.5, 15]] and e_0 = 1.4e-15 (the start's
  rounding). Surface: 4.82e-13 °C.
- With z's own rounding (3.0e-15; zs = z − 25 is exact by Sterbenz), ε = 4.85e-13 °C.
- Measured on DEV commands (31 sequences, 80-digit decimals): at most 3.5e-14.

**What is shown (MATH, with the check's exact results):** for every command sequence in [0, 42], the C state with
either frozen header, in IEEE 754 arithmetic (binary64 round-to-nearest for S and z, the header's precision for h),
never flags a record that the exact recurrence explains with |v| ≤ δ − ε, ε = 4.85e-13 °C, and (b), (c), (e). This
is Theorem 2 for the C state, with δ − ε in place of δ.
- **ESP32:** every tested operation was IEEE (2d), so this applies to the board's own arithmetic. Its output is
  also the PC's on 5,040,000 DEV samples (2e).
- **Uno:** its binary64 is faithful only, so every u doubles: ε = 9.9e-13 °C. Its truncating conversions of lo and hi
  are followed by one float ulp outward (`DOWN`, `UP`), so the slab stays outward. This replaces the inference
  of 2c, under two assumptions not proved here: that its float ×, +, − round to nearest (tested on 6,000 pairs), and
  that `avr_state.c` is `v3_state.c`'s logic (it was written so, not checked).

**Not shown, and what it does not cover:**
- Records with |v| exactly δ are outside the condition. The simulated edge-noise runs are such records, and their
  data carry the generator's own float error, up to 1.2e-13 °C (amendment 9). The C state flagged none of the 80
  on the ESP32 (2e), but no theorem says it cannot.
- Freeze 1's Python template computes its start supports the same way. It is not checked here.
- F3 is covered by amendment 9, not by this.

**A clean fix for a later version** (not made: it changes frozen tables and code):
- start supports from the exact coordinate sums (h[14] and h[15] become 1.2e-16);
- the slab with δ + η, as in F3, so that the condition becomes |v| ≤ δ.
