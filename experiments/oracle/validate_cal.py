"""First independent validation of the generator and the LP oracle on CAL seeds
(experiments/specs/thermal_single_sensor_consistency.md, protocol v2, order of work step 1).

CAL seeds only. FINAL seeds (420000-) are never generated here.

  cells: certified full-run verdict for every cell x arm on CAL 410000-410049, and the first inconsistent
         sample on CAL 410000-410009
  V0   : every healthy CAL run (410000-410199, both arms) is consistent
  P2   : additive faults: z (= y - S) is the same under E0 and E1, and so is the oracle's verdict
  P4   : jumps of 2 and 5 C: t* == t_f, on all 200 CAL seeds
  P5   : constant offsets with the box (c) removed: consistent
  P6   : healthy runs: oracle offset interval inside [-R, R] follows the A_min/A_max rule (margin > delta)
  P7   : stuck: E0 consistent; E1 t* within 30 s after the first >= 5 W command change after t_f
         (an empirical criterion, reported as a rate, not an algebraic certainty)

Run: .venv/bin/python experiments/oracle/validate_cal.py OUTDIR
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "generators")]
import numpy  # noqa: E402
import scipy  # noqa: E402
import thermal as T  # noqa: E402
import thermal_oracle as O  # noqa: E402

CAL_ALL = list(range(410000, 410200))
CAL_MAP = CAL_ALL[:50]        # full-run verdicts for every cell
CAL_LAT = CAL_ALL[:10]        # first inconsistent sample (binary search) for every cell
CELL = {c.name: c for c in T.CELLS}


def job_verdict(args):
    seed, name, arm = args
    r = T.run(seed, CELL[name], arm)
    v, lo, up = O.verdict(r["z"])
    return {"seed": seed, "cell": name, "arm": arm, "verdict": v, "d_lo": lo, "d_up": up}


def job_latency(args):
    seed, name, arm = args
    r = T.run(seed, CELL[name], arm)
    t, status = O.first_inconsistent(r["z"])
    return {"seed": seed, "cell": name, "arm": arm, "t_f": r["t_f"], "t_star": t, "status": status}


def job_z_pair(args):
    seed, name = args
    z0 = T.run(seed, CELL[name], "E0")["z"]
    z1 = T.run(seed, CELL[name], "E1")["z"]
    return max(abs(a - b) for a, b in zip(z0, z1))


def job_healthy(args):
    seed, arm = args
    r = T.run(seed, CELL["healthy"], arm)
    A = T.ambient_part(r["TA"])
    v, lo, up = O.verdict(r["z"])
    iv = O.offset_interval(r["z"]) if v == "consistent" else None
    return {"seed": seed, "arm": arm, "verdict": v, "d_up": up, "interval": iv, "A_min": min(A), "A_max": max(A)}


def job_jump(args):
    seed, name, arm = args
    r = T.run(seed, CELL[name], arm)
    t_f = r["t_f"]
    before = O.verdict(r["z"], t_f)[0]        # samples 0..t_f-1
    at = O.verdict(r["z"], t_f + 1)[0]        # samples 0..t_f
    return {"seed": seed, "cell": name, "arm": arm, "before": before, "at": at,
            "ok": before == "consistent" and at == "inconsistent"}


def job_nobox(args):
    seed, name, arm = args
    r = T.run(seed, CELL[name], arm)
    return {"seed": seed, "cell": name, "arm": arm, "without_box": O.verdict(r["z"], box=False)[0],
            "with_box": O.verdict(r["z"])[0]}


def job_stuck(args):
    seed, arm = args
    r = T.run(seed, CELL["stuck"], arm)
    if arm == "E0":
        return {"seed": seed, "arm": arm, "full": O.verdict(r["z"])[0]}
    k = first_big_change(r["P"], r["t_f"])
    if k is None:
        return {"seed": seed, "arm": arm, "k_change": None}
    at_tf = O.verdict(r["z"], r["t_f"] + 1)[0]
    by_30 = O.verdict(r["z"], min(len(r["z"]), k + 31))[0]
    return {"seed": seed, "arm": arm, "k_change": k, "t_f": r["t_f"], "at_tf": at_tf, "by_k_plus_30": by_30}


def first_big_change(P, t_f):
    for k in range(t_f, len(P)):
        if k % T.E1_PERIOD == 0 and k > 0 and abs(P[k] - P[k - 1]) >= 5.0:
            return k
    return None


def p6_rule(A_min, A_max, R):
    """+1 rule says certifiable by margin > delta, -1 not certifiable by margin > delta, 0 boundary."""
    m1, m2 = (T.TA_LO + R) - A_min, A_max - (T.TA_HI - R)   # both >= 0 iff certifiable
    if m1 > T.DELTA and m2 > T.DELTA:
        return 1
    if m1 < -T.DELTA or m2 < -T.DELTA:
        return -1
    return 0


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main(out):
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    workers = max(1, (os.cpu_count() or 2) - 2)
    add = [c.name for c in T.CELLS if c.additive and c.kind != "healthy"]
    with ProcessPoolExecutor(workers) as ex:
        healthy = list(ex.map(job_healthy, [(s, a) for s in CAL_ALL for a in T.ARMS], chunksize=4))
        jumps = list(ex.map(job_jump, [(s, n, a) for s in CAL_ALL for n in ("jump_2", "jump_5") for a in T.ARMS],
                            chunksize=8))
        zdiff = max(ex.map(job_z_pair, [(s, n) for s in CAL_MAP for n in add], chunksize=8))
        nobox = list(ex.map(job_nobox, [(s, n, a) for s in CAL_MAP for n in ("offset_1", "offset_3")
                                        for a in T.ARMS], chunksize=4))
        stuck = list(ex.map(job_stuck, [(s, a) for s in CAL_MAP for a in T.ARMS], chunksize=2))
        verdicts = list(ex.map(job_verdict, [(s, c.name, a) for s in CAL_MAP for c in T.CELLS for a in T.ARMS],
                               chunksize=4))
        lat = list(ex.map(job_latency, [(s, c.name, a) for s in CAL_LAT for c in T.CELLS for a in T.ARMS],
                          chunksize=2))

    V = {(v["seed"], v["cell"], v["arm"]): v["verdict"] for v in verdicts}
    p2_diff = [(s, n, V[(s, n, "E0")], V[(s, n, "E1")]) for s in CAL_MAP for n in add
               if V[(s, n, "E0")] != V[(s, n, "E1")]]

    p6 = {}
    for R in (1.0, 3.0):
        scored = agree = boundary = 0
        for h in healthy:
            rule = p6_rule(h["A_min"], h["A_max"], R)
            if rule == 0:
                boundary += 1
                continue
            iv = h["interval"]
            oracle_cert = iv is not None and iv[0] >= -R and iv[1] <= R
            scored += 1
            agree += (oracle_cert == (rule == 1))
        p6[f"R={R:g}"] = {"scored": scored, "agree": agree, "boundary_not_scored": boundary,
                          "rule_certifiable": sum(1 for h in healthy if p6_rule(h["A_min"], h["A_max"], R) == 1)}

    e0 = [x for x in stuck if x["arm"] == "E0"]
    e1 = [x for x in stuck if x["arm"] == "E1" and x.get("k_change") is not None]
    p7 = {"E0_consistent": [sum(x["full"] == "consistent" for x in e0), len(e0)],
          "E1_inconsistent_by_change_plus_30s": [sum(x["by_k_plus_30"] == "inconsistent" for x in e1), len(e1)],
          "E1_already_inconsistent_at_t_f": sum(x["at_tf"] == "inconsistent" for x in e1),
          "E1_runs_without_a_5W_change": sum(1 for x in stuck if x["arm"] == "E1" and x.get("k_change") is None)}

    cells = {}
    for c in T.CELLS:
        for a in T.ARMS:
            vs = [v for v in verdicts if v["cell"] == c.name and v["arm"] == a]
            ls = [x for x in lat if x["cell"] == c.name and x["arm"] == a and x["t_star"] is not None]
            d = sorted(x["t_star"] - x["t_f"] for x in ls)
            cells[f"{c.name}/{a}"] = {
                "runs": len(vs),
                "inconsistent": sum(v["verdict"] == "inconsistent" for v in vs),
                "consistent": sum(v["verdict"] == "consistent" for v in vs),
                "undetermined": sum(v["verdict"] == "undetermined" for v in vs),
                "latency_runs": len(ls),
                "latency_after_onset_min_med_max": [d[0], d[len(d) // 2], d[-1]] if d else None,
                "latency_uncertified": sum(x["status"] != "certified" for x in lat
                                           if x["cell"] == c.name and x["arm"] == a)}

    out_doc = {
        "protocol": "experiments/specs/thermal_single_sensor_consistency.md v2",
        "seeds": {"verdicts": [CAL_MAP[0], CAL_MAP[-1]], "latency": [CAL_LAT[0], CAL_LAT[-1]],
                  "healthy_and_jumps": [CAL_ALL[0], CAL_ALL[-1]], "final": "not touched"},
        "env": {"python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__,
                "machine": platform.machine(), "workers": workers},
        "source": {
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                       cwd=HERE).stdout.strip(),
            "git_dirty_tracked": bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                                     capture_output=True, text=True, cwd=HERE).stdout.strip()),
            "thermal.py": sha(os.path.join(HERE, "..", "generators", "thermal.py")),
            "thermal_oracle.py": sha(os.path.join(HERE, "thermal_oracle.py")),
            "validate_cal.py": sha(os.path.abspath(__file__))},
        "V0_healthy": {v: sum(h["verdict"] == v for h in healthy) for v in ("consistent", "inconsistent",
                                                                             "undetermined")},
        "V0_healthy_max_d_up": max(h["d_up"] for h in healthy),
        "P2_max_abs_z_E0_minus_E1_additive": zdiff,
        "P2_full_run_verdict_pairs_differing": [len(p2_diff), len(CAL_MAP) * len(add), p2_diff[:10]],
        "P4_jump_tstar_equals_tf": [sum(j["ok"] for j in jumps), len(jumps),
                                    [j for j in jumps if not j["ok"]][:5]],
        "P5_offset_without_box": {v: sum(n["without_box"] == v for n in nobox)
                                  for v in ("consistent", "inconsistent", "undetermined")},
        "P5_info_offset_with_box": {n: {v: sum(1 for x in nobox if x["cell"] == n and x["with_box"] == v)
                                        for v in ("consistent", "inconsistent", "undetermined")}
                                    for n in ("offset_1", "offset_3")},
        "P6": p6,
        "P7_empirical": p7,
        "cells": cells,
        "seconds": round(time.time() - t0, 1),
    }
    json.dump(out_doc, open(os.path.join(out, "summary.json"), "w"), indent=1)
    with open(os.path.join(out, "verdicts.csv"), "w") as f:
        f.write("seed,cell,arm,verdict,d_lo,d_up\n")
        for v in verdicts:
            f.write(f'{v["seed"]},{v["cell"]},{v["arm"]},{v["verdict"]},{v["d_lo"]:.9f},{v["d_up"]:.9f}\n')
    with open(os.path.join(out, "latency.csv"), "w") as f:
        f.write("seed,cell,arm,t_f,t_star,status\n")
        for x in lat:
            f.write(f'{x["seed"]},{x["cell"]},{x["arm"]},{x["t_f"]},{"" if x["t_star"] is None else x["t_star"]},'
                    f'{x["status"]}\n')
    with open(os.path.join(out, "healthy.csv"), "w") as f:
        f.write("seed,arm,verdict,d_up,b_min,b_max,A_min,A_max\n")
        for h in healthy:
            iv = h["interval"] or (None, None)
            f.write(f'{h["seed"]},{h["arm"]},{h["verdict"]},{h["d_up"]:.9f},{iv[0]},{iv[1]},{h["A_min"]},'
                    f'{h["A_max"]}\n')
    print(json.dumps({k: v for k, v in out_doc.items() if k != "cells"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
