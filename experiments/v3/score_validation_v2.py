"""Score a run_validation_v2.py output with the rules frozen in FREEZE-V2.md (section 4). Nothing here is tunable.

Sets, lags, D_paired, D_censored, the bootstrap and the per-cell table are freeze 1's (score_validation.py, imported
unchanged). For the candidate F:
  soundness violations  F flags a run in A, or detects r in R before t*(r)
  uncertified alarms    an alarm of F whose separation is not certified by its dual bound
  misses                r in R with no F alarm; must not exceed v2's misses
  primary metric        D_paired = 1 - L_F / L_v2 over B = {r in R : v2 detects r}, an F miss in B counts as N - t*
Verdict:
  INCONCLUSIVE  the run is incomplete, the environment check failed, or |U| > 1 % of |F|
  FAIL          soundness violations > 0, or uncertified alarms > 0, or misses > v2 misses, or D_paired < target
  PASS          otherwise
Reported, not deciding: runs where F is later than v2 (there is no dominance theorem for F), D_censored, exact
matches, lag quantiles, per cell and ambient, the seed-cluster bootstrap, evictions and kept measurements, and the
subgroups drift_0.0005/ramp and the rw cells.
usage: python -B score_validation_v2.py RUN_DIR [--manifest frozen/MANIFEST-V2.json] [--out scores.json]
"""
import argparse
import json
from pathlib import Path

import score_validation as SV

HERE = Path(__file__).resolve().parent


def score(rows, manifest, expected_runs=None, env_ok=True):
    F, U, R, A = SV._sets(rows)
    complete = expected_runs is None or len(rows) == expected_runs
    inconclusive = (not complete) or (not env_ok) or len(U) > 0.01 * len(F)
    v2 = lambda r: r["v2"]
    fget = lambda r: r["F"]["detect"]
    out = {"runs": len(rows), "expected_runs": expected_runs, "complete": complete, "env_ok": env_ok,
           "fault_runs": len(F), "uncertified_oracle": len(U), "detection_events": len(R), "admissible_runs": len(A),
           "v2": {"soundness_violations": SV._soundness(rows, R, A, v2), **SV.describe(R, v2)}}
    sound = SV._soundness(rows, R, A, fget)
    uncert = [(r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"], r["F"]["detect"], r["F"]["alarm_certificate"])
              for r in rows if r["F"]["detect"] is not None and not (r["F"]["alarm_certificate"] or {}).get("certified")]
    later = [(r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"], r["v2"], fget(r)) for r in rows
             if r["v2"] is not None and (fget(r) is None or fget(r) > r["v2"])]
    d_p, lc, lv2, nb = SV.paired_delta(R, fget)
    d_c, lcc, lvc = SV.censored_delta(R, fget)
    desc = SV.describe(R, fget)
    target = manifest["candidate"]["target_paired_lag_reduction"]
    reasons = []
    if sound:
        reasons.append(f"{len(sound)} soundness violations")
    if uncert:
        reasons.append(f"{len(uncert)} uncertified alarms")
    if desc["misses"] > out["v2"]["misses"]:
        reasons.append(f"misses {desc['misses']} > v2 {out['v2']['misses']}")
    if d_p is None or d_p < target:
        reasons.append(f"D_paired {d_p} < target {target}")
    kept = sorted(r["F"]["max_kept"] for r in rows)
    sub = {}
    for label, keep in (("drift_0.0005/ramp", lambda r: r["cell"] == "drift_0.0005" and r["ambient"] == "ramp"),
                        ("rw", lambda r: r["ambient"] == "rw")):
        Rs = [r for r in R if keep(r)]
        sub[label] = {"events": len(Rs), "D_paired": SV.paired_delta(Rs, fget)[0], **SV.describe(Rs, fget)}
    out["F"] = {
        "verdict": "INCONCLUSIVE" if inconclusive else ("FAIL" if reasons else "PASS"), "fail_reasons": reasons,
        "target_paired_lag_reduction": target, "D_paired": d_p, "paired_set": nb, "L_paired": lc, "L_paired_v2": lv2,
        "D_censored": d_c, "L_censored": lcc, "L_censored_v2": lvc,
        "D_paired_bootstrap95_descriptive": SV.bootstrap(R, fget),
        "soundness_violations": sound, "uncertified_alarms": uncert, "later_than_v2_reported": later, **desc,
        "evictions": sum(r["F"]["evictions"] for r in rows),
        "runs_with_evictions": sum(1 for r in rows if r["F"]["evictions"]),
        "max_kept": {"median": SV.q(kept, .5), "p95": SV.q(kept, .95), "max": kept[-1] if kept else None},
        "max_rows": max(r["F"]["max_rows"] for r in rows), "max_vars": max(r["F"]["max_vars"] for r in rows),
        "folds_raised_to_dual_bound": sum(r["F"]["folds_raised_to_dual_bound"] for r in rows),
        "subgroups": sub}
    out["by_cell"] = SV.by_cell(R, {"v2": v2, "F": fget})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--manifest", type=Path, default=HERE / "frozen" / "MANIFEST-V2.json")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    manifest = json.loads(a.manifest.read_text())
    meta = json.loads((a.run_dir / "meta.json").read_text())
    rows = [json.loads(l) for l in (a.run_dir / "rows.jsonl").read_text().splitlines() if l.strip()]
    lo, hi = meta["seeds"]
    per_seed = len(manifest["cells"]) * 2 * len(manifest["laws_all_cells"]) + 2 * len(manifest["laws_healthy_extra"])
    s = score(rows, manifest, expected_runs=per_seed * (hi - lo + 1), env_ok=bool(meta.get("env")))
    s["mode"] = meta.get("mode")
    (a.out or a.run_dir / "scores.json").write_text(json.dumps(s, indent=1) + "\n")
    c = s["F"]
    print(f"F: {c['verdict']}  D_paired={c['D_paired']}  target={c['target_paired_lag_reduction']}  "
          f"misses={c['misses']} (v2 {s['v2']['misses']})  soundness={len(c['soundness_violations'])}  "
          f"uncertified={len(c['uncertified_alarms'])}  later_than_v2={len(c['later_than_v2_reported'])}  "
          f"{c['fail_reasons']}")
    print(f"runs {s['runs']}  fault {s['fault_runs']}  uncertified oracle {s['uncertified_oracle']}  "
          f"events {s['detection_events']}")


if __name__ == "__main__":
    main()
