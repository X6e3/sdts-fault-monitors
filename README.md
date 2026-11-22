# SDTS: bounded-memory sound fault monitors, measured against the exact oracle

**SDTS (Software-Defined Temporal Sensing) is the current research in this repository.** It is unrelated to the USGS
Spatial Data Transfer Standard, which has the same acronym. DMREDA and MGDE are the author's earlier research lines on
temporal state in embedded fault handling; both are closed. Until 22 November 2026 this repository was named
`dmreda-sdts-research`. It was reset to SDTS on 16 August 2026. DMREDA's material from before the reset is kept byte for byte in
`archive/pre-reset-2026-08-16/`, negative results included. MGDE is not in this repository.

Code, frozen plans, dated records and results for the preprint

> Can Koç, *How much of the record does a sound fault monitor need? Bounded-memory set-membership detection of sensor
> faults, measured against the exact oracle*, preprint, 2026. The preprint link will be added here.

A set-membership fault detector raises an alarm when no admissible explanation of the sensor record exists. The exact
detector keeps a set whose description grows with the record; a monitor on a microcontroller keeps a bounded outer
approximation of it and can only alarm later. This project measures that loss. A certified linear program over the
full history gives the exact detection time of every run it can certify, and bounded monitors are scored against it
under the same assumptions, on a two-node thermal plant with one temperature sensor, a known heat input and an unknown
ambient temperature.

## Where things are

| Path | Contents |
|---|---|
| `paper/preprint/` | the paper (`main.tex`, `refs.bib`, figures) and `make_arxiv.sh`, which builds the arXiv upload |
| `experiments/v3/` | the monitors, the three freeze documents, the run and scoring scripts, the dated records (`RECORD-*.md`) and `REPRODUCE.md` |
| `experiments/v3/diag/` | diagnostic studies and checks that the records cite |
| `results/v3/` | the stored rows, manifests and summaries of each run |
| `experiments/generators/`, `machine/`, `oracle/`, `baselines/`, `specs/`, `final/`, `records/` | the simulator, the oracle and SDTS's first thermal study (v2), which v3 builds on |
| `tests/`, `env/` | tests; the environment lock and its check |
| `archive/pre-reset-2026-08-16/` | DMREDA, the closed earlier line, as it stood at the reset, negative results included |
| `docs/` | the research charter and validation rules written when the project was reset on 16 August 2026 |

## Reproducing

Each validation is fixed by a freeze document, a manifest and an approval commit. The runners check every file of the
manifest by sha256 and refuse to start outside the locked environment (CPython 3.12.13, numpy 2.5.5, scipy 1.18.1).
`experiments/v3/REPRODUCE.md` gives the commands that score the stored rows again, regenerate a block, run the
wider-box study and rebuild the healthy-record witness of the second review.

## Failures and known limits

The paper reports what went wrong (its Section "What went wrong") and lists the open problems. Two that a reader of the
code meets first:

- The first validation of the window monitor failed on one unsolved LP. The failure, its diagnosis and the fallback
  that replaced it are in the paper (Section "Validation 2") and in `experiments/v3/`.
- The frozen Python template is sound only for noise at least 4.85e-13 °C inside the bound. A constructed healthy
  record makes it flag (`experiments/v3/RECORD-2026-11-22-review2.md`, `experiments/v3/diag/s_gap_witness.py`). The
  fix is not in the frozen code.

Reproductions that disagree with a reported number are welcome; please write (address below).

## License

- Source code (`.py`, `.c`, `.h`, `.ino`, `.sh` and the other program files): Apache License 2.0, see `LICENSE` and
  `NOTICE`.
- The paper, figures, plans, records, notes and result data: Creative Commons Attribution 4.0 International
  (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/.
- `archive/pre-reset-2026-08-16/` follows the same split.

## Citing

See `CITATION.cff` (GitHub shows it as "Cite this repository").

## Contact

Can Koç, cankoc.dev@proton.me: questions, reproductions, industrial use and collaboration.

`HANDOFF.md`, a working handoff of 17 November 2026 cited by
`experiments/records/thermal_v2_cal_review/RECORD-2026-11-17.md`, is no longer at the tip; it is in the history at
commit `7cad493e`.
