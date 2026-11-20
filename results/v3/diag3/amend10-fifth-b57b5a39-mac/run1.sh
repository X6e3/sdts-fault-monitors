#!/bin/bash
S=/Users/x6e3/Downloads/sdts-runs/v3-mac-src-b57b5a39
O=/Users/x6e3/Downloads/sdts-runs/v3-a10-mac-b57b5a39
P=/Users/x6e3/Downloads/sdts-v3/.venv/bin/python
cd $S/experiments/v3/diag
nice -n 19 $P -B amend10_u0c.py $O/U0c > $O/U0c.log 2>&1; echo "U0c exit $?" >> $O/U0c.log
nice -n 19 $P -B amend10_u0b.py $O/U0b > $O/U0b.log 2>&1; echo "U0b exit $?" >> $O/U0b.log
nice -n 19 $P -B amend10.py paths $O/R0 > $O/R0.log 2>&1; echo "R0 exit $?" >> $O/R0.log
nice -n 19 $P -B amend10_i1a.py $S $O/I2a > $O/I2a.log 2>&1; echo "I2a exit $?" >> $O/I2a.log
$P -B amend10_i1_compare.py /Users/x6e3/Downloads/sdts-runs/v3-a10-mac-000cd215/I1a/old $O/I2a > $O/I2a-compare.log 2>&1; echo "compare exit $?" >> $O/I2a-compare.log
touch $O/run1.done
