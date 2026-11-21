# Record: F3 with its LPs in a child process, under simulated solver failures (F3-iso, 2026-11-21)

Plan `ISOLATION-PLAN.md` (status DRAFT when run; its checks and verdict rule fixed before any run), with its variant
and runner committed before the run (`2aa927e5`, `35f479c5`). DEV seeds only. An engineering test: F3's decisions are
not changed and freeze 3's verdict is not revisited.

**Verdict: PASS** (I1–I5 hold).

## Provenance

- **Run:** on Arch, from a clean clone at `35f479c5` (`~/Research/sdts-v3-iso-35f479c5`), the venv of `0ce80072`
  (CPython 3.12.13, numpy 2.5.5, scipy 1.18.1), `nice 19`. The script waited for the baselines' DEV run to end, so
  that the two did not share the machine. I1 then ran on 6 rows; the 1400 rows ran with 10 workers from 20:24:30
  to 22:10:53 (+0300); the summary followed. Every step exited 0.
- **Outputs:** `results/v3/iso/iso-35f479c5-arch/`: 1400 per-row files, `identity.json`, `meta.json`,
  `summary.json`, the run script and the logs. The Mac copy equals Arch's (sha256 of the sorted per-file hashes,
  `083368d7…a0bd`).
- **Report:** `report.json`, from `diag/iso_report.py` (`55a3546d`). Written after the run and committed before it was
  run, for the items of the plan's section 5 that the summary does not compute. It reads this run's files and R1's
  records (DIAG-3 amendment 10, setting none, `results/v3/diag3/amend10-r1r2-0ce80072-arch/R-none`).

## The checks (section 4)

| check | result |
|---|---|
| I1 identity: without injection, F3-iso equals F3 in every field but time (6 rows) | holds: no field differs, no restart |
| I2 complete: 1400 records, no run ended by a process failure | holds |
| I3 sound: no alarm on an admissible row, none before t\*, every alarm certified | holds: 0, 0, 0 |
| I4 counters: "exception" counters equal the injection log on every row; 3 restarts per injected LP | holds: no mismatch, no shortfall |
| I5 memory and slab: at most 65 kept, no empty-slab failure | holds: 65, none |

Injected LP failures, each in all three attempts (half by `os._exit`, half by `SIGSEGV`): fold directions 8,026,
as-range 3,655, certificate 2,050, implied bound 1,589; 15,320 in all, on 1,365 of the 1400 rows. The child process
was restarted 45,960 times, three per injected LP; no restart came from a natural failure.

## Reported, not deciding (section 5)

- **Detections against R1** (F3 with no failure), row by row: 900 equal, 497 later (median 5, at most 2,844 samples),
  3 missed (430006 drift_0.0005 rw in both arms, R1 at 3574; 430021 drift_0.0005 E0 ramp, R1 at 1026), none earlier,
  no new alarm. 1,079 alarms in all, every one certified. On 13 rows the detection is the same but the certified
  margin differs.
- **D_paired** against v2 (1,073 paired events): 0.422, against R1's 0.99921. Paired lag 19,016 s against R1's 26 s
  (v2: 32,925 s).
- **Where the delay comes from (INFERRED):** the certificate rate was set at 50 % so that the rare certificate LPs
  would be reached. An alarm whose certificate fails all its attempts is not raised (F3 raises certified alarms only),
  and 3,654 measurements were not kept after a failed as-range LP. Both paths are documented in F3's fallbacks; the
  per-path split of the delays was not computed.
- **Cost of isolation:** the per-row seconds sum to 63,608 s, against R1's 67,392 s. The two ran with 10 and 14
  workers, and the injected failures change the work done, so this shows no large overhead and no more than that.
- No full reset occurred.

## What this shows, and what it does not

- **Shows:** with its LPs in a child process, F3 survives that process ending (by exit or by SIGSEGV) 15,320 times
  on 1400 DEV runs. The failed attempts reach F3's documented fallbacks, which keep it sound and correctly counted.
  As in the earlier injection tests, failures made detections later or missed them and never earlier or wrong.
- **Does not show:** how often a real solver ends its process; anything on validation seeds; anything about the
  microcontrollers (F3 is not on the boards). The injection rates are chosen to reach every path, not to model a
  real solver.
