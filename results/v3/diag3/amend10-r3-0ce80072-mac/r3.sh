#!/bin/bash
S=~/Downloads/sdts-runs/v3-mac-src-0ce80072/experiments/v3/diag
O=~/Downloads/sdts-runs/v3-a10-mac-0ce80072
P=~/Downloads/sdts-v3/.venv/bin/python
cd $S
export OPENBLAS_NUM_THREADS=1
for s in a b e; do
  $P -B amend10.py run $O/R3-$s --setting $s --variant F3a --workers 8 > $O/R3-$s.log 2>&1; echo EXIT=$? >> $O/R3-$s.log
  $P -B amend10.py summary $O/R3-$s > $O/R3-$s.summary.log 2>&1; echo EXIT=$? >> $O/R3-$s.summary.log
done
touch $O/R3.done
