# Reproducing the v3 validations

Each validation of the paper is fixed by a freeze document, a manifest and an approval commit. The runner checks every
file of the manifest by sha256 and refuses any other code, later commits of this repository included
(`RECORD-2026-11-22-postfreeze-fixes.md` changes `diag/diag3_cw.py` after the freeze). The scorer of validations 2 and
3 checks the manifest's sha256 and the rows' sha256 that the run recorded in `meta.json`. So every step below starts from
the approval commit, not from the tip of the branch. The results directories were committed after the approval, so
take them from this branch.

## Environment

```
uv venv --python 3.12.13 .venv
uv pip install --python .venv/bin/python -r env/requirements-thermal-v2.txt
```

The lock is CPython 3.12.13, numpy 2.5.5, scipy 1.18.1 and HiGHS 1.12.0 (the one bundled with that scipy).
`env/thermal_v2_env.py` checks it, and the runners refuse to start without it.

## The three validations

| | seeds | approval commit | freeze document | runner | scorer | results (on this branch) |
|---|---|---|---|---|---|---|
| 1 | 440000–440199 | `8e589911` | `FREEZE-V1.md` | `run_validation.py` | `score_validation.py` | `results/v3/freeze1/validation-440000-440199/` |
| 2 | 440200–440399 | `35b344df` | `FREEZE-V2.md` | `run_validation_v2.py` | `score_validation_v2.py` | `results/v3/freeze2/validation-440200-440399-35b344df/` |
| 3 | 440400–440599 | `948b46b0` | `FREEZE-V3.md` | `run_validation_v3.py` | `score_validation_v3.py` | `results/v3/freeze3/validation-440400-440599-948b46b0/` |

| | manifest sha256 | `rows.jsonl` sha256 | `scores.json` sha256 |
|---|---|---|---|
| 1 | `e8dd60f134252c1855aca040a46836281db57c1ee19da9713f4c7a25d6e18a96` | `0d5c5013d5084f168381eea4769b84804ebce04d85dd62a236e72f42f6cbe1e3` | `ec9c2c6e2db5e0c82b9bb833f90025083b0a8a2a9de44cbdd2cc4e0684efcba9` |
| 2 | `cc7adffa240b6ab4eab9b45652f4437ce582f784123b1b1cac8341f4db303385` | `4ad0b493c11079c6bfc61714a2da89fde7abfad2409602d0502ad620398738de` | `d35e2b09a852254f52e67b294b70772157a697876e7f1e5d1819ca05b28be6f1` |
| 3 | `0a40cbdf863da6eb046a1c76726d53bf2e967bfa3e0056b1ac15b87cbc7b85c7` | `d9b90cef1c9b932468888fa375ff11c8373520ce0d972337b5631cbee3f6988f` | `ea0b4b8b618af45a53dcf74eb3d675e31945c87642bd263ab23b80a0eced1f67` |

The dated records (`RECORD-2026-11-18-validation.md`, `RECORD-2026-11-19-validation.md`,
`RECORD-2026-11-21-validation.md`) give the same hashes, the run times and the verdicts.

## 1. Score the recorded rows again (minutes)

For validation 3, from the root of a clone of this repository (`REPO`):

```
git archive 948b46b0 experiments env | tar -x -C /tmp/v3-948b46b0
cd /tmp/v3-948b46b0/experiments/v3
REPO/.venv/bin/python -B score_validation_v3.py \
    REPO/results/v3/freeze3/validation-440400-440599-948b46b0 --out /tmp/scores-v3.json
shasum -a 256 /tmp/scores-v3.json
```

The hash must equal the table's. For validations 1 and 2, use their commit, scorer and results directory from the
table. Checked on 2026-11-22: all three `scores.json` files came out byte for byte equal to the recorded ones.

## 2. Generate a block again (hours)

```
git clone REPO v3-948b46b0 && cd v3-948b46b0 && git checkout 948b46b0
# environment as above, inside this clone
cd experiments/v3
../../.venv/bin/python -B run_validation_v3.py OUT --workers 14
../../.venv/bin/python -B score_validation_v3.py OUT
```

The runner refuses unless the tracked tree is clean, the environment lock holds, every file of the manifest matches,
the freeze document carries its approval line and `OUT` does not exist. The data are deterministic functions of the
seeds. The recorded runs took 13,114 s (validation 1), 41,603 s (2) and 39,742 s (3) with 14 workers.

`rows.jsonl` holds wall-clock times (the oracle's and WM's `seconds`, and WM's `step_ms` and `fold_step_ms`), so a new
run will not reproduce its hash; compare every other field, and `scores.json`, which uses none of them. A second full
generation of a block has not been run yet.

`--rehearsal --seeds 430096 430097` runs the same pipeline on two development seeds in a few minutes, without the
approval.

## The independent scorer (validations 2 and 3)

`independent/independent_score.py` was written from section 4 of `FREEZE-V2.md` alone and imports only the Python
standard library. It scores the recorded rows again, checks `meta.json` and the manifest's files at the approval
commit (and, with `--worktree`, in a checkout of it), and compares every number with the run's `scores.json`:

```
python3 -I experiments/v3/independent/independent_score.py --freeze 3 --repo REPO \
    --run REPO/results/v3/freeze3/validation-440400-440599-948b46b0 --out /tmp/independent-v3.json
```

The file is the two scripts that scored the validations (`RECORD-2026-11-19-validation.md`,
`RECORD-2026-11-21-validation.md`), cleaned on 2026-11-22: the paths became arguments and the two variants one file
(`--freeze 2` or `3`); the scoring is unchanged. Checked on 2026-11-22: for both validations its output equals the
recorded output in every field but the task name (288 fields for validation 2, whose recorded output has sha256
`2811e6326c2746b40a7ff4127fd618b670b4deae3f1c17af13df6eb053acd631`, and 247 for validation 3, `02b5e909…`).

## The vertex check of Appendix A.5 (seconds)

```
REPO/.venv/bin/python -B experiments/v3/diag/widebox_vertices.py /tmp/vertices.json
```

In rational arithmetic, it checks that the clamp set of the frozen tables is invariant under one step of the exact
recurrence: 28 vertices of C and 14 more from the two cuts, both ends of w, every direction. Checked on 2026-11-22: no
step above a clamp, and both ends of the start segment lie in C. It does the same for the wider boxes of
`WIDEBOX-PLAN.md`.

## Not in this repository

- The oracle's per-attempt solver logs of each block (`solver_attempts/`, 9 to 30 MB per block); the records give the
  sha256 of each archive.

## Development results

The development results of the paper (Table 2, the figures, the ambient study, the injection and isolation tests,
the microcontroller runs) are in their own records under `experiments/v3/`, each with its commit, command and
output hashes. `paper/figures/make_data.py` regenerates the data of the paper's figures from them.
