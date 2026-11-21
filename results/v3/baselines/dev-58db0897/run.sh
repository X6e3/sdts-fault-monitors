#!/bin/bash
# BASELINE-PLAN.md section 7, step 2: the DEV tuning grid, the LP-rescaling subset, then the tuning rule.
cd /home/x6e3/Research/sdts-v3-bl-58db0897/experiments/v3
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
O=/home/x6e3/Research/sdts-runs/v3-bl-dev-58db0897
nice -n 19 $P -B diag/baselines_run.py dev $O --workers 10 > $O.dev.log 2>&1; echo "DEV_EXIT=$?" >> $O.dev.log
nice -n 19 $P -B diag/baselines_run.py dev $O --workers 10 --only B1lp --subset 200 > $O.lp.log 2>&1; echo "LP_EXIT=$?" >> $O.lp.log
$P -B diag/baselines_run.py tune $O > $O.tune.log 2>&1; echo "TUNE_EXIT=$?" >> $O.tune.log
touch $O.done
