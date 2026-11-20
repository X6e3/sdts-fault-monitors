#!/bin/bash
cd /home/x6e3/Research/sdts-v3-a10-0ce80072/experiments/v3/diag
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
$P -B amend10.py paths /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R0 > /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R0.log 2>&1; echo EXIT=$? >> /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R0.log
$P -B amend10_r4.py /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R4 > /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R4.log 2>&1; echo EXIT=$? >> /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R4.log
for s in none a b c d e f; do
  $P -B amend10.py run /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R-$s --setting $s --workers 14 > /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R-$s.log 2>&1; echo EXIT=$? >> /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R-$s.log
  $P -B amend10.py summary /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R-$s > /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R-$s.summary.log 2>&1; echo EXIT=$? >> /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/R-$s.summary.log
done
touch /home/x6e3/Research/sdts-runs/v3-a10-0ce80072/all.done
