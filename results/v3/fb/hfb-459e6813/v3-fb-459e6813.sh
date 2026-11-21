#!/bin/bash
# H-FB on Arch (FB-PLAN.md section 6): oracle, then none and a-f, then the summaries. Mac runs the F3a audits.
cd /home/x6e3/Research/sdts-v3-fb-459e6813/experiments/v3
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
O=/home/x6e3/Research/sdts-runs/v3-fb-459e6813
nice -n 19 $P -B diag/fb_run.py oracle $O --workers 13 > $O.oracle.log 2>&1; echo "ORACLE_EXIT=$?" >> $O.oracle.log
touch $O.oracle.done
for s in none a b c d e f; do
  nice -n 19 $P -B diag/fb_run.py run $O --setting $s --workers 13 > $O.run-$s.log 2>&1; echo "RUN_EXIT=$?" >> $O.run-$s.log
  $P -B diag/fb_run.py summary $O/$s-F3 > $O.summary-$s.log 2>&1; echo "SUMMARY_EXIT=$?" >> $O.summary-$s.log
done
touch $O.arch.done
