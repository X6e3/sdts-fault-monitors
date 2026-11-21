#!/bin/bash
# H-FB Mac part (FB-PLAN.md section 6, step 4): wait for the Arch oracle, copy oracle.jsonl (sha256 checked), then
# F3a for settings b and e, and their summaries.
set -u
W=$HOME/Downloads/sdts-runs/v3-fb-mac-459e6813/experiments/v3
O=$HOME/Downloads/sdts-runs/v3-fb-459e6813-mac
A=/home/x6e3/Research/sdts-runs/v3-fb-459e6813
P=$HOME/Downloads/sdts-v3/.venv/bin/python
until ssh -o BatchMode=yes -o ConnectTimeout=15 x6e3@192.168.1.106 "test -e $A.oracle.done" 2>/dev/null; do sleep 120; done
mkdir -p $O
scp -q x6e3@192.168.1.106:$A/oracle.jsonl x6e3@192.168.1.106:$A/oracle-meta.json $O/
want=$(python3 -c "import json;print(json.load(open('$O/oracle-meta.json'))['oracle_sha256'])")
got=$(shasum -a 256 $O/oracle.jsonl | cut -d' ' -f1)
echo "oracle sha256 want $want got $got"
[ "$want" = "$got" ] || { echo "ORACLE SHA MISMATCH"; exit 1; }
cd $W && export OPENBLAS_NUM_THREADS=1
for s in b e; do
  caffeinate -i nice -n 10 $P -B diag/fb_run.py run $O --setting $s --variant F3a --workers 8 > $O.run-$s-F3a.log 2>&1; echo "RUN_EXIT=$?" >> $O.run-$s-F3a.log
  $P -B diag/fb_run.py summary $O/$s-F3a > $O.summary-$s-F3a.log 2>&1; echo "SUMMARY_EXIT=$?" >> $O.summary-$s-F3a.log
done
touch $O.mac.done
echo "MAC DONE"; tail -3 $O.summary-b-F3a.log $O.summary-e-F3a.log
