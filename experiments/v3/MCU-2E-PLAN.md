# MCU-2E: the validated template state on an ESP32, bit for bit, on the whole DEV set (plan, 2026-11-21)

Written and committed before the run. DEV seeds only; no validation seed is generated. This tests an
implementation, not the algorithm: the algorithm was validated in freeze 1 (`RECORD-2026-11-18-validation.md`).

## Question

Does the frozen C code of freeze 1's cyl16p, in its float64 form, compute on the ESP32 exactly what it computes on
the PC, on every sample of every DEV row?

**H-MCU2E.** On this ESP32-WROOM-32 (ESP32-D0WD-V3 rev 3.1), the unchanged `c/v3_state.c` with the frozen
`frozen/c/tables_cyl16p_double.h`, built by `mcu/esp32/prepare.sh` at this commit (`BAUD=921600`), gives after every
sample a state (k, tc, ts, flag, h) bit-equal to the PC build of the same files (`host_trace`), on all 1400 rows.

## Object

- **Board build:** `prepare.sh cyl16p_double` at this commit; Arduino-ESP32 core 4.0.0, arduino-cli 1.5.1;
  `-ffp-contract=off -fno-fast-math`; refused if the state object has a fused multiply-add. The copied state
  files and the table header are sha256-checked against the sources.
- **PC reference:** `host_trace` from the same script: `mcu/avr/host_trace.c` with the unchanged `c/v3_state.c`,
  GCC on Arch, `-O2 -std=c99 -ffp-contract=off -fno-fast-math`.
- **Inputs:** the generator's y and P (`dev_scenarios.run`), sent to the board as binary64 and to the PC as Python
  repr text (exact).

## Rows (1400)

- The DEV comparison rows of `run_dev.py`: seeds 430000–430029 × 11 cells × E0, E1 × rw, ramp, uniform noise
  (1320).
- The edge-noise rows of DIAG-3 amendment 7: healthy, seeds 430070–430089 × E0, E1 × rw, ramp, edge noise (80).
- Every row runs all 3600 samples, also after a flag.

## Comparison

- After every sample the board returns its flag, its cycle count, and the first 16 bytes of the SHA-256 of its
  357-byte state dump (k, tc, ts, flag, h). The PC computes the same from `host_trace`'s dump.
- The init state is compared in full, byte for byte.

## Decision (fixed)

- **PASS:** all 1400 rows complete with 3600 samples each, the init states equal, and on every sample the flag and
  the 16-byte hash equal.
- **FAIL:** any difference on any sample. A row with a difference is never rerun. After the verdict it may be
  replayed with full dumps (`stream.py`) to find the field; that is a diagnosis and does not change the verdict.
- **INCOMPLETE:** rows missing after the run.
- **Infrastructure:** a serial timeout or a board reset during a row is not a difference. The row is restarted from
  its first sample, at most three attempts, each logged in `infrastructure.log`. Only a complete attempt counts.

## Before the run

A rehearsal on the first two rows (`--limit 2`, a separate output directory), and one of them also through the
full-dump path (`stream.py`), to check the hash path against the byte comparison of 2d. The rehearsal does not
count, and its rows are run again in the main run.

## Reported, not deciding

Cycles per sample (median, p99, max per row), heap and stack after the run, wall time, infrastructure restarts.

## What a PASS shows, and what it does not

- **Shows:** on this board, this build computes the PC's state exactly on 5,040,000 DEV samples. So the freeze 1
  results of the PC build carry over to the board's output on such inputs.
- **Does not show:** behaviour on a real sensor or plant; F3 (no LP solver on the board); other boards, compilers
  or flags; a worst-case timing bound (the maximum is over these runs).
