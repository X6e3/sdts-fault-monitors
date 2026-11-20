#!/bin/bash
cd /Users/x6e3/Downloads/sdts-runs/v3-mac-src-44ddd682/experiments/v3/diag
export OPENBLAS_NUM_THREADS=1
O=/Users/x6e3/Downloads/sdts-runs/v3-a10-mac-44ddd682
nice -n 19 /Users/x6e3/Downloads/sdts-v3/.venv/bin/python -B amend10_u5b.py $O/U5b --workers 4 > $O/U5b.log 2>&1; echo "U5b exit $?" >> $O/U5b.log
touch $O/u5b.done
