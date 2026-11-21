# MCU-2F: the template state on an Arduino Uno, decision by decision (plan, 2026-11-21)

Written and committed before the run. DEV seeds only. Exploratory follow-up of MCU-NOTES 2c, where the Uno's
float32 state differed from the PC's in the last bits but flagged at the same samples on four runs.

## Question

On the Uno, is the float32 build's **decision** the PC's, although its arithmetic is not (the double-to-float
conversion truncates, binary64 is faithful only; MCU-NOTES 2c)?

**H-MCU2F.** On this Arduino Uno (ATmega328P), the float32 build of freeze 1's cyl16p (`mcu/avr/build.sh
atmega328p cyl16p_float` at this commit) flags at the same first sample as the PC's float32 build (`host_trace`:
the unchanged `c/v3_state.c` with `frozen/c/tables_cyl16p_float.h`) on each of 30 DEV rows, and where neither
flags, neither does.

The float64 form, which is the validated one, does not fit the Uno's 32 KB flash; it is MCU-2E's object, on the
ESP32.

## Rows

The 30 of MCU-2E's 1400 DEV rows whose key has the smallest sha256 (`uno_2f.py rows()`; a fixed choice). Each row runs
until both have flagged, plus 3 samples; a row that neither flags runs all 3600 samples.

## Decision (fixed)

- **PASS:** all 30 rows complete, and on every row the first flagged sample is the same on the board and the PC
  (or neither flags).
- **FAIL:** any row where they differ. Not rerun.
- **INCOMPLETE:** rows missing. A serial timeout or a board reset restarts the row (at most three attempts, logged).

## Reported, not deciding

- samples whose whole state is bit-equal;
- samples where S (tc, ts) differs;
- for h, how many components are below and above the PC's value, and the largest distance in ulps each way;
- cycles per sample.

Below the PC is the less conservative side. MCU-NOTES 2c gives an inferred argument why the board's bounds still
stay outer bounds; this test does not prove it.

## What a PASS shows, and what it does not

- **Shows:** on these 30 DEV rows, the 8-bit board's decisions equal the PC float32 build's, although the states
  differ in the last bits.
- **Does not show:** soundness of the board's float model (inferred only); anything about the float64 form on the
  Uno; rows beyond these 30.
