"""The certificate audit A1 on every DEV comparison row, at the frozen code (after the freeze-2 approval; DEV only).

A1 (DIAG-3 amendment 6) audited 5,676 bounds on the five diagnosis runs: every fold bound, every alarm bound and every
eighth as-range bound, each evaluated again in exact rational arithmetic (diag3_cw.exact_bound) and compared with
its float evaluation. This runs the same audited variant (Fa: F with the hardened certificate, no cap) on all 1320
DEV comparison rows through diag3_cw_dev.online(). On DEV, F with K_cap = 64 never evicts, so Fa and F take the same
steps there.

Criteria, fixed before the run:
  AF1  on every audited bound, the float bound is at least its exact rational evaluation (no violation);
  AF2  Fa detects at the same sample as F (K_cap = 64) at the frozen code (results/v3/diag3/cwdev-F-K64-42252a3) on
       every row, and every alarm is certified.
Nothing in the manifest is changed or rerun; the validation is not touched.
usage: python -B audit_dev.py run OUT [--workers 8]
       python -B audit_dev.py summary OUT
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diag3_cw as C  # noqa: E402
import diag3_cw_dev as CD  # noqa: E402

D, S, T, G = CD.D, CD.S, CD.T, CD.G
REF = HERE.parents[2] / "results" / "v3" / "diag3" / "cwdev-F-K64-42252a3"
_win = {}


def _make(var, tp, _orig=C.make):
    w = _orig(var, tp)
    _win["w"] = w
    return w


def job(args):
    r, out = args
    path = Path(out) / f"audit-{D.key(r)}.json"
    if path.exists():
        return D.key(r), "done before"
    C.make = _make
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    res = {"key": D.key(r), **CD.online("Fa", G.zs_of(run), C.W, None, r["oracle"].get("t_star"))}
    res["audit"] = _win["w"].audit
    path.write_text(json.dumps(res) + "\n")
    return D.key(r), res["detect"], res["audit"]["n"], res["audit"]["violations"], res["seconds"]


def summary(out):
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    got, missing = {}, []
    for r in rows:
        p = out / f"audit-{D.key(r)}.json"
        (got.__setitem__(D.key(r), json.loads(p.read_text())) if p.exists() else missing.append(D.key(r)))
    ref = {k: json.loads((REF / f"cwdev-{k}-F.json").read_text()) for k in got}
    a = [x["audit"] for x in got.values()]
    s = {"rows": len(rows), "done": len(got), "missing": len(missing),
         "audited_bounds": sum(x["n"] for x in a), "violations": sum(x["violations"] for x in a),
         "min_slack_C": min((x["min_slack_C"] for x in a), default=None),
         "max_coefficient_term_C": max((x["max_coefficient_term_C"] for x in a), default=None),
         "max_gap_to_value_C": max((x["max_gap_to_value_C"] for x in a), default=None),
         "detect_differs_from_F": [[k, x["detect"], ref[k]["detect"]] for k, x in got.items()
                                   if x["detect"] != ref[k]["detect"]],
         "uncertified_alarms": [k for k, x in got.items() if x["detect"] is not None
                                and not (x["alarm_certificate"] or {}).get("certified")],
         "alarms": sum(1 for x in got.values() if x["detect"] is not None)}
    s["AF1"] = s["violations"] == 0 and s["done"] > 0
    s["AF2"] = not s["detect_differs_from_F"] and not s["uncertified_alarms"]
    (out / "summary.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps(s, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.cmd == "summary":
        return summary(a.out)
    a.out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: r["oracle"].get("t_star") is not None)      # the long healthy rows first
    rows = rows[:a.limit] if a.limit else rows
    meta = {"git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
            "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "workers": a.workers}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    with ProcessPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(job, (r, str(a.out))) for r in rows]):
            print(f.result(), flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    main()
