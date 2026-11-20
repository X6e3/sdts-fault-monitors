#!/bin/bash
S=/Users/x6e3/Downloads/sdts-runs/v3-mac-src-b57b5a39
O=/Users/x6e3/Downloads/sdts-runs/v3-a10-mac-b57b5a39
P=/Users/x6e3/Downloads/sdts-v3/.venv/bin/python
cd $S/experiments/v3/diag
nice -n 19 $P -B amend10_i3.py $O/I3 > $O/I3.log 2>&1; echo "I3 exit $?" >> $O/I3.log
touch $O/run2.done
