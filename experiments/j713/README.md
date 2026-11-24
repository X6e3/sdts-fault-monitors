# J713 thermal step tests: plan, time stamps, record and scripts

The data are in `data/j713/` (README there: columns and units). These files are copies of the author's working folder,
unchanged, so paths inside them (`step3/log.csv`, `~/Research/...`) refer to that folder.

| file | what |
|---|---|
| `PLAN-step3.md`, `PLAN-step3-ADDENDUM-{1,2,3}.md` | the plan and its addenda, each written before its use |
| `PLAN-step3-manifest.txt`, `RESULT-step3-manifest.txt`, `*.ots` | sha256 manifests and their OpenTimestamps proofs (Bitcoin) |
| `RECORD-2026-11-23-step3.md`, `RECORD-2026-11-23-step3-NOTE-ots.md`, `NOTE-2026-11-24-wording.md` | the result, what the time stamps date, and a wording note |
| `step3-eval.json`, `dev-rehearsal-step1-step2.json` | outputs of the frozen evaluation and of the rehearsal on development data |
| `thermlog.c`, `run_step3.sh` | the read-only 1 Hz logger (macOS) and the run script |
| `analyze.py`, `eval_step3.py` | the model and fit, and the frozen evaluation; they read the full logs, which are not released |
| `reproduce_step3.py` | the same model, fit and refit on the released columns; checks what the data determine (TA, residuals, the fit's invariants) against `step3-eval.json` |
| `PILOT-2026-11-24-monitors.md`, `pilot_monitors.py`, `pilot_jump_margin.py` | a pilot of the oracle and monitors on the development runs (step 1 and 2), kept for a later study; outputs in `results/j713/pilot-dev-2026-11-24/` |

The manifests hash the full logs; the released files are column extracts of them, so their own hashes differ.
`reproduce_step3.py` is the check that the released columns carry the result.
