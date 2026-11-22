#!/bin/bash
# WIDEBOX-PLAN.md (approved by Can 2026-11-22: Arch, 14 workers, after the baselines block): check, run, summary.
cd /home/x6e3/Research/sdts-v3-wb-a196fd68
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
O=/home/x6e3/Research/sdts-runs/v3-wb-a196fd68
nice -n 19 $P -B experiments/v3/diag/widebox.py check $O --workers 14 > $O.check.log 2>&1; echo "CHECK_EXIT=$?" >> $O.check.log
if grep -q "^CHECK_EXIT=0$" $O.check.log; then
    nice -n 19 $P -B experiments/v3/diag/widebox.py run $O --workers 14 > $O.run.log 2>&1; echo "RUN_EXIT=$?" >> $O.run.log
    $P -B experiments/v3/diag/widebox.py summary $O > $O.summary.log 2>&1; echo "SUMMARY_EXIT=$?" >> $O.summary.log
fi
touch $O.done
