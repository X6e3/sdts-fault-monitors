#!/bin/bash
cd /home/x6e3/Research/sdts-v3-a10-1ca4df40/experiments/v3/diag
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
O=/home/x6e3/Research/sdts-runs/v3-a10-1ca4df40
R=/home/x6e3/Research/sdts-runs/v3-a10-0ce80072
$P -B amend10_i2b.py run $O/I2b --workers 10 > $O/I2b-run.log 2>&1; echo EXIT=$? >> $O/I2b-run.log
$P -B amend10_i2b.py compare $R $O/I2b > $O/I2b-compare.log 2>&1; echo EXIT=$? >> $O/I2b-compare.log
$P -B amend10.py summary $O/I2b/R-none > $O/I2b-none-summary.log 2>&1; echo EXIT=$? >> $O/I2b-none-summary.log
touch $O/i2b.done
