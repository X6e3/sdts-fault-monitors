#!/bin/bash
# BASELINE-PLAN.md section 9 (approved by Can 2026-11-21): the block run on 440400-440599, then the score.
cd /home/x6e3/Research/sdts-v3-bl-9438dffa/experiments/v3
export OPENBLAS_NUM_THREADS=1
P=/home/x6e3/Research/sdts-v3-a10-0ce80072/.venv/bin/python
O=/home/x6e3/Research/sdts-runs/v3-bl-block-9438dffa
C=/home/x6e3/Research/sdts-v3-bl-9438dffa/results/v3/baselines/dev-58db0897/chosen.json
nice -n 19 $P -B diag/baselines_run.py block $O --chosen $C --workers 14 > $O.block.log 2>&1; echo "BLOCK_EXIT=$?" >> $O.block.log
$P -B diag/baselines_run.py score $O > $O.score.log 2>&1; echo "SCORE_EXIT=$?" >> $O.score.log
touch $O.done
