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
  correctly rounded. Its size over 3600 samples is not measured yet.

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
