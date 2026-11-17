"""First independent validation of the generator and the LP oracle on CAL seeds
(experiments/specs/thermal_single_sensor_consistency.md, protocol v2, order of work step 1).

CAL seeds only. FINAL seeds (420000-) are never generated here.

  map  : t* (first inconsistent sample, oracle) for every cell x arm on CAL 410000-410049
  V0   : every healthy CAL run (410000-410199, both arms) is consistent
  P2   : additive faults: z (= y - S) and the oracle's t* are the same under E0 and E1
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
CAL_MAP = CAL_ALL[:50]
CELL = {c.name: c for c in T.CELLS}


def job_map(args):
    seed, name, arm = args
    r = T.run(seed, CELL[name], arm)
    t, d, border = O.first_inconsistent(r["z"])
    return {"seed": seed, "cell": name, "arm": arm, "t_f": r["t_f"], "t_star": t, "d_star": d,
            "borderline": border}


def job_z_pair(args):
    seed, name = args
    z0 = T.run(seed, CELL[name], "E0")["z"]
    z1 = T.run(seed, CELL[name], "E1")["z"]
    return max(abs(a - b) for a, b in zip(z0, z1))


def job_healthy(args):
    seed, arm = args
    r = T.run(seed, CELL["healthy"], arm)
    A = T.ambient_part(r["TA"])
    iv = O.offset_interval(r["z"])
    d = O.margin(r["z"])
    return {"seed": seed, "arm": arm, "consistent": d <= T.DELTA, "d_star": d, "interval": iv,
            "A_min": min(A), "A_max": max(A)}


def job_jump(args):
    seed, name, arm = args
    r = T.run(seed, CELL[name], arm)
    t_f = r["t_f"]
    before = O.consistent(r["z"], t_f)        # samples 0..t_f-1
    at = O.consistent(r["z"], t_f + 1)        # samples 0..t_f
    return {"seed": seed, "cell": name, "arm": arm, "ok": before and not at}


def job_nobox(args):
    seed, name, arm = args
    r = T.run(seed, CELL[name], arm)
    return {"seed": seed, "cell": name, "arm": arm, "consistent_without_box": O.consistent(r["z"], box=False),
            "consistent_with_box": O.consistent(r["z"])}


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
    res = {}
    with ProcessPoolExecutor(workers) as ex:
        tasks = [(s, c.name, a) for s in CAL_MAP for c in T.CELLS for a in T.ARMS]
        res["map"] = list(ex.map(job_map, tasks, chunksize=4))
        res["healthy"] = list(ex.map(job_healthy, [(s, a) for s in CAL_ALL for a in T.ARMS], chunksize=4))
        res["jumps"] = list(ex.map(job_jump, [(s, n, a) for s in CAL_ALL for n in ("jump_2", "jump_5")
                                              for a in T.ARMS], chunksize=8))
        res["nobox"] = list(ex.map(job_nobox, [(s, n, a) for s in CAL_MAP for n in ("offset_1", "offset_3")
                                               for a in T.ARMS], chunksize=4))
        add = [c.name for c in T.CELLS if c.additive and c.kind != "healthy"]
        res["zdiff"] = max(ex.map(job_z_pair, [(s, n) for s in CAL_MAP for n in add], chunksize=8))

    # P2 from the map: t* equal across arms for additive cells
    tstar = {(m["seed"], m["cell"], m["arm"]): m["t_star"] for m in res["map"]}
    add = [c.name for c in T.CELLS if c.additive and c.kind != "healthy"]
    p2_pairs = [(s, n) for s in CAL_MAP for n in add]
    p2_diff = [(s, n, tstar[(s, n, "E0")], tstar[(s, n, "E1")]) for s, n in p2_pairs
               if tstar[(s, n, "E0")] != tstar[(s, n, "E1")]]

    # P6
    p6 = {}
    for R in (1.0, 3.0):
        scored = agree = boundary = 0
        for h in res["healthy"]:
            rule = p6_rule(h["A_min"], h["A_max"], R)
            if rule == 0:
                boundary += 1
                continue
            iv = h["interval"]
            oracle_cert = iv is not None and iv[0] >= -R and iv[1] <= R
            scored += 1
            agree += (oracle_cert == (rule == 1))
        cert = sum(1 for h in res["healthy"] if p6_rule(h["A_min"], h["A_max"], R) == 1)
        p6[f"R={R:g}"] = {"scored": scored, "agree": agree, "boundary_not_scored": boundary,
                          "rule_certifiable": cert}

    # P7 (empirical)
    p7 = {"E0_consistent": 0, "E0_runs": 0, "E1_within_30s": 0, "E1_runs": 0, "E1_no_big_change": 0}
    for s in CAL_MAP:
        p7["E0_runs"] += 1
        p7["E0_consistent"] += tstar[(s, "stuck", "E0")] is None
        r = T.run(s, CELL["stuck"], "E1")
        k = first_big_change(r["P"], r["t_f"])
        if k is None:
            p7["E1_no_big_change"] += 1
            continue
        p7["E1_runs"] += 1
        t = tstar[(s, "stuck", "E1")]
        p7["E1_within_30s"] += t is not None and t <= k + 30

    # map summary per cell x arm
    summary = {}
    for c in T.CELLS:
        for a in T.ARMS:
            rows = [m for m in res["map"] if m["cell"] == c.name and m["arm"] == a]
            det = [m for m in rows if m["t_star"] is not None]
            early = [m for m in det if m["t_star"] < T.T_WARM]
            lat = sorted(m["t_star"] - m["t_f"] for m in det if c.kind not in ("offset",))
            summary[f"{c.name}/{a}"] = {
                "runs": len(rows), "inconsistent": len(det), "inconsistent_before_300": len(early),
                "latency_after_onset_median": lat[len(lat) // 2] if lat else None,
                "latency_min": lat[0] if lat else None, "latency_max": lat[-1] if lat else None}

    out_doc = {
        "protocol": "experiments/specs/thermal_single_sensor_consistency.md v2",
        "seeds": {"map": [CAL_MAP[0], CAL_MAP[-1]], "all_cal": [CAL_ALL[0], CAL_ALL[-1]], "final": "not touched"},
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
        "V0_healthy_consistent": [sum(h["consistent"] for h in res["healthy"]), len(res["healthy"])],
        "V0_healthy_max_d_star": max(h["d_star"] for h in res["healthy"]),
        "map_borderline_verdicts": [sum(m["borderline"] for m in res["map"]), len(res["map"])],
        "P2_max_abs_z_E0_minus_E1": res["zdiff"],
        "P2_tstar_pairs_differing": [len(p2_diff), len(p2_pairs), p2_diff[:10]],
        "P4_jump_tstar_equals_tf": [sum(j["ok"] for j in res["jumps"]), len(res["jumps"])],
        "P5_offset_consistent_without_box": [sum(n["consistent_without_box"] for n in res["nobox"]),
                                             len(res["nobox"])],
        "P5_info_offset_consistent_with_box": {
            n: [sum(x["consistent_with_box"] for x in res["nobox"] if x["cell"] == n),
                sum(1 for x in res["nobox"] if x["cell"] == n)] for n in ("offset_1", "offset_3")},
        "P6": p6,
        "P7_empirical": p7,
        "map_summary": summary,
        "seconds": round(time.time() - t0, 1),
    }
    json.dump(out_doc, open(os.path.join(out, "summary.json"), "w"), indent=1)
    with open(os.path.join(out, "map.csv"), "w") as f:
        f.write("seed,cell,arm,t_f,t_star,d_star,borderline\n")
        for m in res["map"]:
            t = "" if m["t_star"] is None else m["t_star"]
            f.write(f'{m["seed"]},{m["cell"]},{m["arm"]},{m["t_f"]},{t},{m["d_star"]:.9f},{int(m["borderline"])}\n')
    with open(os.path.join(out, "healthy.csv"), "w") as f:
        f.write("seed,arm,consistent,b_min,b_max,A_min,A_max\n")
        for h in res["healthy"]:
            iv = h["interval"] or (None, None)
            f.write(f'{h["seed"]},{h["arm"]},{int(h["consistent"])},{iv[0]},{iv[1]},{h["A_min"]},{h["A_max"]}\n')
    print(json.dumps({k: v for k, v in out_doc.items() if k != "map_summary"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
