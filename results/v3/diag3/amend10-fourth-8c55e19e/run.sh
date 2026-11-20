#!/bin/bash
cd /Users/x6e3/Downloads/sdts-runs/v3-mac-src-8c55e19e/experiments/v3/diag
nice -n 19 /Users/x6e3/Downloads/sdts-v3/.venv/bin/python -B amend10_u0b.py /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/U0b > /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/U0b.log 2>&1; echo "U0b exit $?" >> /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/U0b.log
nice -n 19 /Users/x6e3/Downloads/sdts-v3/.venv/bin/python -B amend10.py paths /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/R0 > /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/R0.log 2>&1; echo "R0 exit $?" >> /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/R0.log
nice -n 19 /Users/x6e3/Downloads/sdts-v3/.venv/bin/python -B amend10_i1a.py /Users/x6e3/Downloads/sdts-runs/v3-mac-src-8c55e19e /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/I2a > /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/I2a.log 2>&1; echo "I2a exit $?" >> /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/I2a.log
/Users/x6e3/Downloads/sdts-v3/.venv/bin/python -B amend10_i1_compare.py ~/Downloads/sdts-runs/v3-a10-mac-000cd215/I1a/old /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/I2a > /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/I2a-compare.log 2>&1
touch /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-8c55e19e/all.done
