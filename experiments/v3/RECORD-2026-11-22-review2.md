# Record: the second blind review and the changes it led to (2026-11-22)

**What was reviewed:** the preprint PDF (v0.2 text, 25 pages) and a clean clone of the repository at `984e8dea`, given
to an outside reviewer with no internet access, a fixed Python environment (CPython 3.12.13, numpy 2.5.5, scipy 1.18.1)
and the instruction to reproduce numbers with its own scripts. The reviewer wrote its report before reading the first
review's report, and sealed it by its sha256 (`03320308…12de`). The report and its working files are kept with the
project's notes, outside this repository. Its verdict: major revision. Part B of the task, checking the first review's
findings one by one against `984e8dea`, was done by a second outside reviewer on another machine (section at the end).

## Reproduced by the reviewer, with its own scripts from the stored rows

- Validation 3: 8,000 fault runs = 7,255 certified events + 742 certified consistent + 3 undetermined; WM's paired lag
  1,264 s, IM's 262,482 s; every one of the 7,258 alarms has a finite negative margin; no alarm on the 2,342
  admissible runs.
- Table 6 (baselines block): every number, and the three verdicts, both with its own bootstrap and with the plan's.
- The wider-box table: the split is exact on every one of the 1,081 frozen events; no t\* earlier at a wider box.
- Single rows run again from the repository's code: Figure 3's 430010 (695 / 3575 / 3575 / 695), 430027 drift 0.0005
  at [22, 28] and [23, 27], 430000 jump 0.2. The vertex check of Lemma A.5 at the three boxes (3,528 steps each, none
  above a clamp).

## Findings and what was done

1. **A healthy record on which the validated Python template flags (major).** The reviewer constructed it; we ran it
   again with our own script, `diag/s_gap_witness.py`, which writes the same 600-line record (sha256 of
   `results/v3/review2/witness-42W.txt`: `83011769…c86b`, equal to the reviewer's file).
   - Construction: ambient held at 27 °C, start at the steady state of P0 = 20 W, command 42 W; each measurement the
     largest binary64 number not above the exact surface temperature plus δ, with |v| ≤ δ asserted in rational
     arithmetic at every sample.
   - Result: freeze 1's Python template (cyl16p) flags at sample 309, where the noise is 4.6e-15 °C inside the bound
     and the template's binary64 command part S is 1.6e-14 °C below the exact one. The frozen C state and the revised
     C state (c1), built on the PC in float64 with `c/harness.c`, do not flag on this record (600 samples).
   - Cause: S is computed in binary64 and no pad covers its rounding. This was in our records
     (`MCU-NOTES.md` 2g: the C state is sound for |v| ≤ δ − ε, ε = 4.85e-13 °C; `diag/check_py_template.py`: the same
     S recursion, the same ε, for the Python template), but the paper stated the Python template's conditions with
     only the 2.1e-21 rate pads open. The validated scores do not change.
   - Done: the paper states the restriction (Section 4, the precision section, contribution 2, the limitations) and
     reports the record in "What went wrong". Not done: the fix in the Python template (the revised C state's slab
     δ + η and exact start sums), which changes frozen code and is for a later version.
2. **"Every difference is information the representation discarded" was too strong.** An implementation's
   conservative arithmetic (the allowance η, outward rounding of the box test, padded supports) can also delay an
   alarm; the reviewer gave a one-sample example. Its check of the 12 delayed events of validation 3 found the
   oracle's lower bound above δ by at least 1.06e-7 °C at each, so η and the model gap do not explain them. Done: the
   abstract and the introduction now say a delay is what a monitor loses against the full history, including what its
   arithmetic gives up.
3. **Table 6's largest LP for B1 was wrong.** The decision LP is solved after one new generator and up to seven prior
   strips, so it has up to n_c + 7 equality rows and 3o + n_c + 8 generators: 8 × 15 at M1 and 11 × 36 at M2, which
   development data reach (observed 5 × 12 and 8 × 33 on 440400 jump 0.5). Done: the table gives these bounds. Also:
   B1's interval rescaling treats coefficients below 1e-12 as zero, which can lose the outer property in a
   constructed case; the paper says so. No method alarmed early or on an admissible run on the block.
4. **Smaller points, done:** contribution 1 ("for every run it can certify"); "bit for bit" on the ESP32 stated as the
   alarm flag and a 16-byte state hash after every sample; B5 against WM: the same sample on 7,237 of the 7,255
   events, WM earlier on 18, in 7 of the 200 seeds, never later (checked from the stored rows), at 34.5 against
   20.4 ms per sample; the wider-box table's new event (430003 drift 0.001 E1 rw, IM 50 s after its t\*) as a column;
   WM's median step without a fold (14 ms) against 34.5 ms per sample with folds; the fold's error class (only a
   `RuntimeError` outside the solver call is recorded as an uncertified alarm; `diag/diag3_cw_dev.py`); Table 2's
   0.9045461 rounded to 0.905; Figure 1's fold LP has a node at t; Figure 2's axis counts reals; "in general no
   longer convex"; the draft's date.
5. **Not done here:** a second plant, a measured set-up, a worst-case time (the reviewer's main reasons for a major
   revision at Automatica or TCST; it named Control Engineering Practice or IFAC SAFEPROCESS as realistic now and
   eess.SY with math.OC for arXiv); archiving the certificates' LP data; the B1 rescaling fix.

## Part B: the first review's findings against `984e8dea`

A second outside reviewer, given the same package and both reports, judged the first review's 11 findings: 4 resolved,
7 partly resolved, none unresolved or wrong. It ran the healthy-record witness again on Arch (the same alarm at sample
309) and read the mechanism in the code: the frozen C state passes that record because its pad for the group of the
unit basis is the group's largest (7.6e-14 °C), not because the S gap is closed. Points it raised that were still open
in `984e8dea`, and what was done (checked from the stored rows where a number is involved):

- Corollary 1 said every sample of IM's delay is discarded information: now "in exact arithmetic".
- The same symbol z for y − S and for the shifted measurement: z is now defined as y − S − 25 once.
- The two arms are not independent for the additive faults: on validation 3, IM and WM flag at the same sample in all
  3,200 additive E0/E1 pairs. The protocol now says so and that every interval resamples whole seeds.
- The 742 certified-consistent fault runs: 400 are the stuck sensor under E0 (the simulator keeps adding fresh noise
  to the frozen reading; with a constant command it stays explainable), 342 are drifts of 0.0005 and 0.001 °C/s; every
  stuck run under E1 is an event. Now in the validation 3 results.
- Figure 2: TS's development and validation markers coincide (caption); Figure 4: drift rates in °C/s (caption).
- Still open: detection delay from the fault onset t_f; byte-level RAM and step-time distributions; the B1 rescaling
  fix; archiving the certificates' LP data; a second plant.
