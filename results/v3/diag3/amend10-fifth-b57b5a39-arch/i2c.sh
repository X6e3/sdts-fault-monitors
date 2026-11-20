#!/bin/bash
cd /home/x6e3/Research/sdts-v3-a10-b57b5a39/experiments/v3/diag
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
O=/home/x6e3/Research/sdts-runs/v3-a10-b57b5a39
$P -B amend10_r4.py $O/I2c > $O/I2c.log 2>&1; echo EXIT=$? >> $O/I2c.log
touch $O/i2c.done
