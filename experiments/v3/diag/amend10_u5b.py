"""DIAG-3 amendment 10, U5b (DIAG-3-PLAN.md, proposed 2026-11-20 05:40, run on Can's OK): U5's fault part on rows the
oracle detects.

Unchanged from U5 in every other respect: F3a, W = 256, K = 64, a measurement 10 C above the box written into the
window at key 250 (amend10_u5.one, FORCE_FAULT), the same checks and tolerances. The rows are 430000 and 430001 x
(drift_0.002, E0, rw, uniform) and (stuck, E1, rw, uniform). Each runs forced and unforced. The healthy part of U5
passed and is not repeated. The code is the frozen candidate's (diag3_cw.py as at b57b5a39). Written and committed
before it ran. Nothing here is part of the candidate.
Pass if all hold, on every forced row:
  - an alarm, certified;
  - at every fold before the onset, the true state at the new tau lies in the base (+1e-9 degC), at least one fold;
  - at every alarm certificate up to the onset, the true a_s lies within both certified bounds (+1e-9 degC);
  - the forcing at 250 is followed by exactly one full reset, 42 slab fold failures and slab range failures;
  - the detection comes after that reset;
  - the exact audit finds no violation.
Reported, not deciding: each row's oracle t*, onset, forced and unforced detection, dropped measurements and the
samples from forcing to reset.
usage: python -B amend10_u5b.py OUT [--workers N]
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import amend10 as A  # noqa: E402
import amend10_u5 as U  # noqa: E402

D = A.D
ROWS = [(430000, "drift_0.002", "E0", "rw", "uniform"), (430001, "drift_0.002", "E0", "rw", "uniform"),
        (430000, "stuck", "E1", "rw", "uniform"), (430001, "stuck", "E1", "rw", "uniform")]


def oracle_tstar():
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    by = {(r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"]): r["oracle"].get("t_star") for r in rows}
    return {k: by[k] for k in ROWS}


def judge(rows, tstar):
    by = {(tuple(r["key"]), r["forced"]): r for r in rows}
    forced = [by[(k, True)] for k in ROWS]
    ok = {
        "rows_have_oracle_tstar": all(tstar[k] is not None for k in ROWS),
        "onsets_after_forcing": all(r["t_f"] is not None and r["t_f"] > max(U.FORCE_FAULT) for r in forced),
        "fault_alarms_certified": all(r["record"]["detect"] is not None
                                      and r["record"]["alarm_certificate"]["certified"] for r in forced),
        "fold_coverage": all(not r["check"]["fold_fail"] and r["check"]["fold_checks"] > 0 for r in forced),
        "cert_coverage": all(r["check"]["max_cert_excess_C"] is None or r["check"]["max_cert_excess_C"] <= U.TOL
                             for r in forced),
        "forcing_counters": all(r["check"]["forced_at"] == list(U.FORCE_FAULT)
                                and r["record"]["failsafe"]["fold_full_resets"] == 1
                                and len(r["check"]["resets_at"]) == 1
                                and r["record"]["failsafe"]["fold_dir_fallbacks"].get("slab", 0) == 42
                                and r["record"]["failsafe"]["range_failures"].get("slab", 0) > 0 for r in forced),
        "recovery": all(r["record"]["detect"] is not None and r["check"]["resets_at"]
                        and r["record"]["detect"] > r["check"]["resets_at"][-1] for r in forced),
        "audit": all(r["audit"]["violations"] == 0 and r["audit"]["n"] > 0 for r in forced),
    }
    res = {"/".join(map(str, k)): {
        "oracle_t_star": tstar[k], "onset": by[(k, True)]["t_f"],
        "detect_unforced": by[(k, False)]["record"]["detect"], "detect_forced": by[(k, True)]["record"]["detect"],
        "certified_forced": (by[(k, True)]["record"]["alarm_certificate"] or {}).get("certified"),
        "resets_at": by[(k, True)]["check"]["resets_at"],
        "samples_force_to_reset": [b - a for a, b in zip(by[(k, True)]["check"]["forced_at"],
                                                         by[(k, True)]["check"]["resets_at"])],
        "measurements_not_kept": by[(k, True)]["record"]["failsafe"]["measurements_not_kept"],
        "fold_checks": by[(k, True)]["check"]["fold_checks"],
        "max_fold_excess_C": by[(k, True)]["check"]["max_fold_excess_C"],
        "cert_checks": by[(k, True)]["check"]["cert_checks"],
        "max_cert_excess_C": by[(k, True)]["check"]["max_cert_excess_C"],
        "audit": by[(k, True)]["audit"]} for k in ROWS}
    return {k: bool(v) for k, v in ok.items()}, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    tstar = oracle_tstar()
    jobs = [(k, U.FORCE_FAULT) for k in ROWS] + [(k, ()) for k in ROWS]
    rows = []
    with ProcessPoolExecutor(a.workers) as ex, open(a.out / "rows.jsonl", "w") as f:
        for r in ex.map(U.one, jobs):
            rows.append(r)
            f.write(json.dumps(r, default=str) + "\n")
            f.flush()
            print(r["key"], r["forced"], r["record"]["detect"], r["check"]["max_fold_excess_C"], r["seconds"], flush=True)
    ok, res = judge(rows, tstar)
    git = ["git", "rev-parse", "HEAD"], ["git", "diff", "--quiet", "HEAD"]
    rep = {"ok": ok, "U5b": all(ok.values()), "details": res,
           "git_head": subprocess.run(git[0], cwd=HERE, capture_output=True, text=True).stdout.strip(),
           "git_dirty_tracked": bool(subprocess.run(git[1], cwd=HERE).returncode)}
    (a.out / "u5b.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
