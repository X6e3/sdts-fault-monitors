"""Score a run_validation.py output with the rules frozen in FREEZE-V1.md (section 4). Nothing here is tunable.

Sets (N = record length, 3600 samples):
  F  fault runs: cell != healthy, noise uniform
  U  runs in F whose oracle t* is not certified          -> excluded from every comparison, counted
  R  runs in F with a certified oracle t* (inconsistent) -> the detection events
  A  admissible runs: every healthy run (both noise laws; ground truth) and every run in F that the oracle
     certifies consistent
Per method m, f_m(r) is its first inconsistent sample or None.
  soundness violations  m flags a run in A, or f_m(r) < t*(r) for r in R
  dominance violations  (candidates) v2 detects at k and the candidate is None or later than k, any run
  misses                r in R with f_m(r) = None
  paired lag            B = {r in R : f_v2(r) is not None}; L_m = sum over B of (f_m - t*), a candidate miss in B
                        (itself a dominance violation) counts as N - t*
  primary metric        D_paired = 1 - L_cand / L_v2
  secondary             D_censored over R with every miss counted as N - t*; exact matches; lag quantiles;
                        per cell and ambient law; a seed-cluster bootstrap interval (descriptive, fixed rng)
Verdict per candidate:
  INCONCLUSIVE  the run is incomplete, the environment check failed, or |U| > 1 % of |F|
  FAIL          soundness violations > 0, or dominance violations > 0, or misses > v2 misses,
                or D_paired < the candidate's frozen target
  PASS          otherwise
The C builds are scored for soundness and agreement with the Python reference; they do not enter the verdict.
usage: python -B score_validation.py RUN_DIR [--manifest frozen/MANIFEST.json] [--out scores.json]
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

N = 3600
HERE = Path(__file__).resolve().parent


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else None


def _sets(rows):
    F = [r for r in rows if r["cell"] != "healthy" and r["noise"] == "uniform"]
    U = [r for r in F if r["oracle"]["status"] != "certified"]
    R = [r for r in F if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    A = [r for r in rows if r["cell"] == "healthy"] + \
        [r for r in F if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None]
    return F, U, R, A


def _soundness(rows, R, A, get):
    out = []
    for r in A:
        if get(r) is not None:
            out.append(("flags an admissible run", r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"], get(r)))
    for r in R:
        f = get(r)
        if f is not None and f < r["oracle"]["t_star"]:
            out.append(("earlier than the oracle", r["seed"], r["cell"], r["arm"], r["ambient"], f, r["oracle"]["t_star"]))
    return out


def _lag(f, t):
    return (N - t) if f is None else (f - t)


def paired_delta(R, get):
    B = [r for r in R if r["v2"] is not None]
    lv2 = sum(r["v2"] - r["oracle"]["t_star"] for r in B)
    lc = sum(_lag(get(r), r["oracle"]["t_star"]) for r in B)
    return (1 - lc / lv2 if lv2 else None), lc, lv2, len(B)


def censored_delta(R, get):
    lv2 = sum(_lag(r["v2"], r["oracle"]["t_star"]) for r in R)
    lc = sum(_lag(get(r), r["oracle"]["t_star"]) for r in R)
    return (1 - lc / lv2 if lv2 else None), lc, lv2


def bootstrap(R, get, reps=2000, seed=20261118):
    """Seed-cluster bootstrap of D_paired (descriptive only; the verdict uses the point value)."""
    by = defaultdict(list)
    for r in R:
        by[r["seed"]].append(r)
    seeds = sorted(by)
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        pick = [rng.choice(seeds) for _ in seeds]
        d, *_ = paired_delta([r for s in pick for r in by[s]], get)
        if d is not None:
            vals.append(d)
    vals.sort()
    return [q(vals, 0.025), q(vals, 0.975)] if vals else None


def describe(R, get):
    lags = [get(r) - r["oracle"]["t_star"] for r in R if get(r) is not None]
    return {"detected": len(lags), "misses": sum(get(r) is None for r in R),
            "equal_to_oracle": sum(x == 0 for x in lags), "lag_median": q(lags, .5), "lag_p90": q(lags, .9),
            "lag_max": max(lags) if lags else None, "lag_sum_detected": sum(lags)}


def by_cell(R, getters):
    per = defaultdict(lambda: defaultdict(lambda: {"n": 0, "miss": 0, "lag_sum": 0}))
    for r in R:
        key = f"{r['cell']}/{r['ambient']}"
        for name, get in getters.items():
            f = get(r)
            d = per[key][name]
            d["n"] += 1
            if f is None:
                d["miss"] += 1
            else:
                d["lag_sum"] += f - r["oracle"]["t_star"]
    return {k: dict(v) for k, v in sorted(per.items())}


def score(rows, manifest, expected_runs=None, env_ok=True):
    F, U, R, A = _sets(rows)
    complete = expected_runs is None or len(rows) == expected_runs
    inconclusive = (not complete) or (not env_ok) or len(U) > 0.01 * len(F)
    v2get = lambda r: r["v2"]
    out = {"runs": len(rows), "expected_runs": expected_runs, "complete": complete, "env_ok": env_ok,
           "fault_runs": len(F), "uncertified": len(U), "detection_events": len(R), "admissible_runs": len(A),
           "v2": {"soundness_violations": _soundness(rows, R, A, v2get), **describe(R, v2get)}, "candidates": {}}
    getters = {"v2": v2get}
    for name, c in manifest["candidates"].items():
        get = (lambda nm: (lambda r: r["candidates"][nm]))(name)
        getters[name] = get
        sound = _soundness(rows, R, A, get)
        dom = [(r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"], r["v2"], get(r)) for r in rows
               if r["v2"] is not None and (get(r) is None or get(r) > r["v2"])]
        d_p, lc, lv2, nb = paired_delta(R, get)
        d_c, lcc, lvc = censored_delta(R, get)
        desc = describe(R, get)
        target = c["target_paired_lag_reduction"]
        reasons = []
        if sound:
            reasons.append(f"{len(sound)} soundness violations")
        if dom:
            reasons.append(f"{len(dom)} dominance violations")
        if desc["misses"] > out["v2"]["misses"]:
            reasons.append(f"misses {desc['misses']} > v2 {out['v2']['misses']}")
        if d_p is None or d_p < target:
            reasons.append(f"D_paired {d_p} < target {target}")
        verdict = "INCONCLUSIVE" if inconclusive else ("FAIL" if reasons else "PASS")
        out["candidates"][name] = {
            "verdict": verdict, "fail_reasons": reasons, "target_paired_lag_reduction": target,
            "D_paired": d_p, "paired_set": nb, "L_paired": lc, "L_paired_v2": lv2,
            "D_censored": d_c, "L_censored": lcc, "L_censored_v2": lvc,
            "D_paired_bootstrap95_descriptive": bootstrap(R, get),
            "soundness_violations": sound, "dominance_violations": dom, **desc}
    out["by_cell"] = by_cell(R, getters)
    c_out = {}
    tags = sorted({t for r in rows for t in r.get("c", {})})
    for tag in tags:
        get = (lambda tg: (lambda r: r["c"][tg]))(tag)
        py = next(nm for nm in manifest["candidates"] if tag.startswith(nm + "_"))
        rel = defaultdict(int)
        for r in rows:
            a, b = get(r), r["candidates"][py]
            rel["same" if a == b else ("C misses, Python detects" if a is None else
                                       "C detects, Python misses" if b is None else
                                       "C later" if a > b else "C earlier")] += 1
        c_out[tag] = {"soundness_violations": _soundness(rows, R, A, get), "vs_python": dict(rel),
                      "D_paired": paired_delta(R, get)[0], **describe(R, get)}
    out["c_builds"] = c_out
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--manifest", type=Path, default=HERE / "frozen" / "MANIFEST.json")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    manifest = json.loads(a.manifest.read_text())
    meta = json.loads((a.run_dir / "meta.json").read_text())
    rows = [json.loads(l) for l in (a.run_dir / "rows.jsonl").read_text().splitlines() if l.strip()]
    lo, hi = meta["seeds"]
    per_seed = len(manifest["cells"]) * 2 * len(manifest["laws_all_cells"]) + 2 * len(manifest["laws_healthy_extra"])
    s = score(rows, manifest, expected_runs=per_seed * (hi - lo + 1), env_ok=bool(meta.get("env")))
    s["mode"] = meta.get("mode")
    text = json.dumps(s, indent=1) + "\n"
    (a.out or a.run_dir / "scores.json").write_text(text)
    for name, c in s["candidates"].items():
        print(f"{name}: {c['verdict']}  D_paired={c['D_paired']}  target={c['target_paired_lag_reduction']}  "
              f"misses={c['misses']} (v2 {s['v2']['misses']})  soundness={len(c['soundness_violations'])}  "
              f"dominance={len(c['dominance_violations'])}  {c['fail_reasons']}")
    print(f"runs {s['runs']}  fault {s['fault_runs']}  uncertified {s['uncertified']}  events {s['detection_events']}")


if __name__ == "__main__":
    main()
