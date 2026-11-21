# C1: the clean fix of the C template state (plan, 2026-11-21)

Written and committed before any result of it. DEV seeds only. This is a new version of the C state, not a change
to a frozen one: freeze 1's files (`c/v3_state.c`, `c/v3_state.h`, `codegen_c.py`, `frozen/c/*.h`, pinned in
`frozen/MANIFEST.json`) are not touched, and no validation seed is generated.

## Why

MCU-NOTES 2g: the frozen C state is sound against the exact recurrence only for |v| ≤ δ − ε (ε = 4.85e-13 °C,
the float error of S and of z), and its start supports in directions 14 and 15 are 1.11e-16 short. The follow-up
check showed that the first step absorbs the second. Both are closed here by construction, in the way F3 closed the
first (DIAG-3 amendment 9).

## The change (version c1)

1. **`c1/v3_state.c`** is `c/v3_state.c` with one change: the slab uses δ + η, η = 1e-9 °C (F3's value), in both
   bounds. Every other line is the same. `c1/v3_state.h` is `c/v3_state.h` unchanged.
2. **`c1/tables_cyl16p1_{double,float}.h`**, from `codegen_c1.py`: freeze 1's tables (`frozen/cyl16p.json`, through
   the unchanged `codegen_c.py`), with each start support raised to at least the exact start-segment support:
   H0_i = max(frozen H0_i, 2 |Σ_c d_ic| rounded up), then clamped as before. Only H0 can change; every other
   line of the header must be the frozen header's.
3. **`mcu/esp32/prepare.sh`** takes the source and table directories from the environment (`SRC`, `TABLES`). The
   defaults are the frozen ones, so its earlier builds are unchanged.

With ε < η, the c1 slab contains the exact slab for |v| ≤ δ, so the condition of MCU-NOTES 2g becomes |v| ≤ δ.

## Checks and decision (fixed)

- **Y1 tables:** each c1 header differs from the frozen header only in its first comment line and in V3_H0, and
  in V3_H0 only where the frozen value is below the exact start support.
- **Y2 code:** `c1/v3_state.c` differs from `c/v3_state.c` only in the lines of the change above.
- **Y3 soundness checks** (`diag/check_c1.py`, the functions of `check_c_state.py` on the c1 headers): K1–K5 hold
  for both headers, K5 without the follow-up, and K6's ε < η.
- **Y4 DEV, PC** (Arch, GCC, the flags of MCU-2E): on all 1400 DEV rows of MCU-2E, c1 (float64) and the frozen C
  state (float64) are run side by side.
  - c1 is never earlier than the frozen state. Every c1 support is ≥ the frozen one by induction: c1's start and
    slab are supersets, the supports are monotone in h, and rounding is monotone. An earlier c1 flag would be a bug.
  - The first flagged sample is the same on every row.
  - No edge-noise row flags.
- **Y5 ESP32** (MCU-2E's protocol, `dev_full.py`, 921600 baud): the c1 float64 build is bit-equal to its own PC
  build (`host_trace` with the c1 sources) on all 1400 rows × 3600 samples. A rehearsal on the first two rows comes
  first and does not count.

**Verdict:**
- **ACCEPT** c1 as the C state of later MCU work if Y1–Y5 hold.
- **REJECT** if Y1, Y2, Y3 or Y5 fails, or if c1 is earlier on any row (Y4).
- **INCOMPLETE** if rows are missing.
- A Y4 row where c1 is later is reported with its margins. It does not reject c1, since a wider slab can make a
  detection later; it is a cost, recorded as such.

Infrastructure (a serial timeout, a board reset) restarts a row, at most three attempts, as in MCU-2E.

## What an ACCEPT shows, and what it does not

- **Shows:** a C state whose soundness against the exact recurrence holds by construction for |v| ≤ δ, with the
  same decisions as freeze 1's C state on DEV and the PC's output on the ESP32.
- **Does not show:** anything about validation seeds (c1 is not validated; freeze 1's validation was of the Python
  template); the Uno (its port, `avr_state.c`, is not changed here); a real sensor.

## Addendum: the Uno (added 2026-11-21, before any Uno result of c1)

The ESP32 runs `c1/v3_state.c` itself; the Uno runs a port, `mcu/avr/avr_state.c` (tables read from flash, bit-level
nextafter), in float32 (the float64 tables do not fit). The c1 port is `mcu/avr/avr_state_c1.c`. `mcu/avr/build.sh`
takes `SRC`, `TABLES` and `AVR_STATE` from the environment (defaults unchanged).

- **U1 code:** `avr_state_c1.c` differs from `avr_state.c` only in the ETA define and the two slab lines, as in Y2.
- **U2 tables:** the Uno's flash header is `make_progmem.py`'s copy of `c1/tables_cyl16p1_float.h`; its own check
  (nothing differs but PROGMEM) passes, and its first line names that file's sha256.
- **U3 Uno decisions** (`uno_2f.py`, MCU-2F's 30 rows and protocol): on every row, the Uno c1 float32 build's first
  flagged sample equals the PC c1 float32 build's (`host_trace` with `c1/v3_state.c` and the c1 float header).
- **Reported, not deciding:** the same first flags as MCU-2F's frozen builds or not; bit-equal samples; h below and
  above the PC in ulps; a negative control (the Uno c1 build against the frozen PC float32 build on one row).

**Verdict for the Uno:** ACCEPT if U1–U3 hold; REJECT if U1 or U2 fails or a first flag differs; INCOMPLETE if rows
are missing. Its soundness then rests on Y3 for the float header, K6 with a faithful binary64 (ε = 9.9e-13 °C < η),
and MCU-NOTES 2g's two assumptions for the Uno: its float ×, +, − round to nearest (tested, not proved), and the
port is `v3_state.c`'s logic (written so, not checked).
