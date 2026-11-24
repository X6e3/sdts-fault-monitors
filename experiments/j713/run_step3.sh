#!/bin/bash
# J713 thermal step test 3 (validation run of PLAN-step3.md; recorded only after the plan is approved and frozen).
# macOS, on AC power, read-only logging at 1 Hz; the load is plain busy loops:
# idle 600 s, 6 threads 900 s, 1 thread 900 s, idle 1500 s (3900 s in all).
# Guard: if the battery hotspot TB0T exceeds 40 C, the load stops (phase guard_stop) and the idle phase begins.
set -u
cd "$(dirname "$0")"
OUT=${1:?usage: run_step3.sh OUTDIR}
mkdir -p "$OUT"
phase() { echo "$1,$(date +%s.%N)" >> "$OUT/phases.csv"; }
tb0t() {
    awk -F, 'NR == 1 { for (i = 1; i <= NF; i++) if ($i == "smc:TB0T") c = i; next } { v = $c } END { print v + 0 }' "$OUT/log.csv"
}
load() {                      # $1 threads for $2 seconds, with the TB0T guard; returns 1 if the guard fired
    local pids=() end
    for _ in $(seq "$1"); do (e=$((SECONDS + $2)); while [ $SECONDS -lt $e ]; do :; done) & pids+=($!); done
    end=$((SECONDS + $2))
    while [ $SECONDS -lt $end ]; do
        sleep 10
        if awk -v t="$(tb0t)" 'BEGIN { exit !(t > 40.0) }'; then
            kill "${pids[@]}" 2>/dev/null; wait "${pids[@]}" 2>/dev/null; phase guard_stop; return 1
        fi
    done
    wait "${pids[@]}" 2>/dev/null; return 0
}
echo "phase,t_unix" > "$OUT/phases.csv"
{ pmset -g batt; sysctl -n hw.model; sw_vers; } > "$OUT/machine.txt" 2>&1
caffeinate -i ./thermlog log "$OUT/log.csv" 1000 3900 ALL &
LOGGER=$!
phase idle0_start; sleep 600
phase load6_start
if load 6 900; then
    phase load1_start
    load 1 900
fi
phase idle_cool_start
while kill -0 $LOGGER 2>/dev/null; do sleep 10; done
phase end
pmset -g batt >> "$OUT/machine.txt"
echo done
