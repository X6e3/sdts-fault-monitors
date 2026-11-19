"""Score a run_validation_v2.py output with the rules frozen in FREEZE-V2.md (section 4). Nothing here is tunable.

Sets, lags, D_paired, D_censored, the bootstrap and the per-cell table are freeze 1's (score_validation.py, imported
unchanged). For the candidate F:
  soundness violations  F flags a run in A, or detects r in R before t*(r)
  uncertified alarms    an alarm of F whose separation is not certified by its dual bound
  misses                r in R with no F alarm; must not exceed v2's misses
  primary metric        D_paired = 1 - L_F / L_v2 over B = {r in R : v2 detects r}, an F miss in B counts as N - t*
Checks of the run (DIAG-3 amendment 9):
  identity   every expected key (seed, cell, arm, ambient, noise) occurs exactly once, with no extra keys; in validation
             mode the seeds are the manifest's block
  integrity  meta's mode, the manifest sha256, the rows sha256 (recomputed), the finished stamp, the environment against
             thermal_v2_env.LOCK field by field; in validation mode also the approval line and a clean tracked tree
Verdict, in this order:
  INCONCLUSIVE  an integrity check failed
  FAIL          a soundness violation or an uncertified alarm on a row with an expected key, even if rows are missing
  INCONCLUSIVE  missing, duplicate or extra rows, or |U| > 1 % of |F|
  FAIL          misses > v2 misses, or D_paired < target (D_paired undefined, i.e. L_v2 = 0, is a FAIL)
  PASS          otherwise
Reported, not deciding: runs where F is later than v2 (there is no dominance theorem for F), D_censored, exact
matches, lag quantiles, per cell and ambient, the seed-cluster bootstrap, evictions and kept measurements, and the
subgroups drift_0.0005/ramp and the rw cells.
usage: python -B score_validation_v2.py RUN_DIR [--manifest frozen/MANIFEST-V2.json] [--out scores.json]
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import score_validation as SV

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "env"))
import thermal_v2_env  # noqa: E402

KEY = lambda r: (r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"])


def expected_keys(manifest, lo, hi):
    out = []
    for seed in range(lo, hi + 1):
        for cell in manifest["cells"]:
            for arm in manifest["arms"]:
                out += [(seed, cell, arm, al, nl) for al, nl in manifest["laws_all_cells"]]
        for arm in manifest["arms"]:
            out += [(seed, "healthy", arm, al, nl) for al, nl in manifest["laws_healthy_extra"]]
    return set(out)


def identity(rows, manifest, lo, hi):
    keys, exp = [KEY(r) for r in rows], expected_keys(manifest, lo, hi)
    seen = Counter(keys)
    return {"expected": len(exp), "missing": len(exp - set(keys)), "duplicates": sum(n - 1 for n in seen.values() if n > 1),
            "extra": len(set(keys) - exp), "examples": {"missing": [list(k) for k in sorted(exp - set(keys))[:5]],
                                                        "extra": [list(k) for k in sorted(set(keys) - exp)[:5]]}}, exp


def integrity(meta, manifest, manifest_sha, rows_sha):
    bad, mode = [], meta.get("mode")
    if mode not in ("validation", "rehearsal"):
        bad.append(f"mode {mode!r}")
    if meta.get("manifest_sha256") != manifest_sha:
        bad.append("meta's manifest sha256 is not this manifest's")
    if not meta.get("finished"):
        bad.append("no finished stamp")
    if meta.get("rows_sha256") != rows_sha:
        bad.append("rows.jsonl does not match meta's rows sha256")
    env = meta.get("env") or {}
    bad += [f"env {k} {env.get(k)!r} != {v!r}" for k, v in thermal_v2_env.LOCK.items() if env.get(k) != v]
    if env.get("implementation") != "CPython":
        bad.append(f"env implementation {env.get('implementation')!r}")
    if mode == "validation":
        if list(meta.get("seeds") or []) != list(manifest["validation_block"]):
            bad.append("the seeds are not the manifest's validation block")
        if not meta.get("approval"):
            bad.append("no approval line recorded")
        if meta.get("git_dirty_tracked") is not False:
            bad.append("tracked changes in the tree")
    return bad


def score(rows, manifest, expected=None, problems=()):
    """expected: the set of expected keys (None: take the rows as they are); problems: integrity failures."""
    seen = Counter(KEY(r) for r in rows)
    complete = expected is None or (set(seen) == expected and all(n == 1 for n in seen.values()))
    if expected is not None:
        rows = [r for r in rows if KEY(r) in expected]  # an extra key is not scored; it makes the run incomplete
    F, U, R, A = SV._sets(rows)
    v2 = lambda r: r["v2"]
    fget = lambda r: r["F"]["detect"]
    out = {"runs": len(rows), "expected_runs": None if expected is None else len(expected), "complete": complete,
           "integrity_problems": list(problems),
           "fault_runs": len(F), "uncertified_oracle": len(U), "detection_events": len(R), "admissible_runs": len(A),
           "v2": {"soundness_violations": SV._soundness(rows, R, A, v2), **SV.describe(R, v2)}}
    sound = SV._soundness(rows, R, A, fget)
    uncert = [(r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"], r["F"]["detect"], r["F"]["alarm_certificate"])
              for r in rows if r["F"]["detect"] is not None and not (r["F"]["alarm_certificate"] or {}).get("certified")]
    later = [(r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"], r["v2"], fget(r)) for r in rows
             if r["v2"] is not None and (fget(r) is None or fget(r) > r["v2"])]
    later_by = [x[6] - x[5] for x in later if x[6] is not None]
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
    if problems:
        verdict = "INCONCLUSIVE"
    elif sound or uncert:
        verdict = "FAIL"                              # a hard finding on a valid row stands, even if rows are missing
    elif not complete or len(U) > 0.01 * len(F):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "FAIL" if reasons else "PASS"
    out["F"] = {
        "verdict": verdict, "fail_reasons": reasons,
        "target_paired_lag_reduction": target, "D_paired": d_p, "paired_set": nb, "L_paired": lc, "L_paired_v2": lv2,
        "D_censored": d_c, "L_censored": lcc, "L_censored_v2": lvc,
        "D_paired_bootstrap95_descriptive": SV.bootstrap(R, fget),
        "soundness_violations": sound, "uncertified_alarms": uncert, "later_than_v2_reported": later,
        "later_than_v2_largest_s": max(later_by) if later_by else None,
        "v2_detects_F_misses": sum(1 for x in later if x[6] is None),
        "unproved_primal_alarms": sum(r["F"].get("unproved_primal_alarms", 0) for r in rows), **desc,
        "evictions": sum(r["F"]["evictions"] for r in rows),
        "runs_with_evictions": sum(1 for r in rows if r["F"]["evictions"]),
        "max_kept": {"median": SV.q(kept, .5), "p95": SV.q(kept, .95), "max": kept[-1] if kept else None},
        "max_rows": max((r["F"]["max_rows"] for r in rows), default=None),
        "max_vars": max((r["F"]["max_vars"] for r in rows), default=None),
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
    manifest_sha = hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    meta = json.loads((a.run_dir / "meta.json").read_text())
    rows_path = a.run_dir / "rows.jsonl"
    rows = [json.loads(l) for l in rows_path.read_text().splitlines() if l.strip()]
    lo, hi = manifest["validation_block"] if meta.get("mode") == "validation" else meta["seeds"]
    ident, exp = identity(rows, manifest, lo, hi)
    problems = integrity(meta, manifest, manifest_sha, hashlib.sha256(rows_path.read_bytes()).hexdigest())
    s = score(rows, manifest, expected=exp, problems=problems)
    s["mode"], s["identity"] = meta.get("mode"), ident
    (a.out or a.run_dir / "scores.json").write_text(json.dumps(s, indent=1) + "\n")
    c = s["F"]
    print(f"F: {c['verdict']}  D_paired={c['D_paired']}  target={c['target_paired_lag_reduction']}  "
          f"misses={c['misses']} (v2 {s['v2']['misses']})  soundness={len(c['soundness_violations'])}  "
          f"uncertified={len(c['uncertified_alarms'])}  later_than_v2={len(c['later_than_v2_reported'])} "
          f"(largest {c['later_than_v2_largest_s']} s)  unproved={c['unproved_primal_alarms']}  "
          f"{c['fail_reasons']}")
    print(f"identity {ident}  integrity problems {problems}")
    print(f"runs {s['runs']}  fault {s['fault_runs']}  uncertified oracle {s['uncertified_oracle']}  "
          f"events {s['detection_events']}")


if __name__ == "__main__":
    main()
