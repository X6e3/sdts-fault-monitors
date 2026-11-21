#!/bin/bash
# ISOLATION-PLAN.md: waits for the baselines' DEV run to finish (Can, 2026-11-21: "iso testini bitince başlat"),
# then I1 (identity), the 1400 DEV rows with simulated solver failures, and the summary.
until [ -e /home/x6e3/Research/sdts-runs/v3-bl-dev-58db0897.done ]; do sleep 120; done
cd /home/x6e3/Research/sdts-v3-iso-35f479c5/experiments/v3
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
O=/home/x6e3/Research/sdts-runs/v3-iso-35f479c5
nice -n 19 $P -B diag/iso_run.py identity $O > $O.identity.log 2>&1; echo "IDENTITY_EXIT=$?" >> $O.identity.log
nice -n 19 $P -B diag/iso_run.py run $O --workers 10 > $O.run.log 2>&1; echo "RUN_EXIT=$?" >> $O.run.log
$P -B diag/iso_run.py summary $O > $O.summary.log 2>&1; echo "SUMMARY_EXIT=$?" >> $O.summary.log
touch $O.done
