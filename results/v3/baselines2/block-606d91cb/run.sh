#!/bin/bash
# BASELINE2 v3.1 FROZEN (606d91cb, 2026-11-23): identity check and block on validation 3, then the score.
cd /home/x6e3/Research/sdts-v3-c8c4971c
[ "$(git rev-parse --short=8 HEAD)" = "606d91cb" ] || { echo "clone not at 606d91cb"; exit 1; }
OUT=/home/x6e3/Research/sdts-runs/baselines2-block-606d91cb
echo "block start $(date '+%F %T')"
nice -n 19 .venv/bin/python -B experiments/v3/diag/baselines2_run.py block $OUT --chosen results/v3/baselines2/dev-3b363394/chosen.json --workers 14
echo "block exit $? $(date '+%F %T')"
.venv/bin/python -B experiments/v3/diag/baselines2_run.py score $OUT
echo "score exit $? $(date '+%F %T')"
