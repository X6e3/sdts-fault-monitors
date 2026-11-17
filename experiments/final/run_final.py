"""The single FINAL run of thermal protocol v2 with addendum A1 (A1.6), and its CAL rehearsal.

  --rehearsal   CAL seeds only (implementation check of this script; results are not FINAL)
  --final       FINAL seeds 420000-420029 per cell-arm and 420100-420299 healthy; refuses unless the
                environment matches the lock, the tracked tree is clean and the thresholds file is
                committed unchanged. Run once.

Per run: oracle full verdict and t*, oracle ablations without (b), (c), (d); machine full, without (b),
without (c); every baseline variant's outcome with its arm's TRAIN threshold; the true sensor error;
P4 prefixes for jumps 2 and 5; P7 prefixes for stuck; offset enclosure and the P6 rule for healthy runs.
P1 twin pairs on the first seed block. Scoring is separate (score_final.py).
usage: python -B run_final.py OUT --thresholds FILE (--rehearsal | --final) [--workers 8]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for sub in ("experiments/oracle", "experiments/machine", "experiments/baselines", "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import thermal_oracle as O  # noqa: E402
import thermal_baselines as B  # noqa: E402
import thermal_twins  # noqa: E402
import thermal_v2_env  # noqa: E402
from thermal_machine import ThermalMachine  # noqa: E402
from validate_cal import first_big_change, p6_rule  # noqa: E402

T = O.T
CELL = {c.name: c for c in T.CELLS}
SEEDS = {"final": {"cells": range(420000, 420030), "healthy": range(420100, 420300), "twins": range(420000, 420030)},
         "rehearsal": {"cells": range(410000, 410003), "healthy": range(410100, 410110), "twins": range(410000, 410002)}}
THRESHOLDS = None
LOG = None


def num(x):
    """JSON-safe bound: None stands for an infinite or missing value (no solver evidence)."""
    return x if x is not None and abs(x) != float("inf") else None


def init(thresholds, log):
    global THRESHOLDS, LOG
    THRESHOLDS, LOG = thresholds, Path(log)


def machine(y, P, **kw):
    m = ThermalMachine(**kw)
    first = None
    for k, (yk, pk) in enumerate(zip(y, P)):
        if m.observe(yk, pk) and first is None:
            first = k
    out = {"first_inconsistent": first, "R1": m.verdict(1), "R3": m.verdict(3)}
    if kw.get("box", True):
        out["offset_outer"] = m.offset_outer
    return out


def baselines(y, arm, t_f):
    return {v: B.outcome(v, y, THRESHOLDS[v][arm]["threshold"], t_f) for v in B.VARIANTS}


def run_job(args):
    seed, name, arm = args
    cell = CELL[name]
    r = T.run(seed, cell, arm)
    z, y, P, t_f = r["z"], r["y"], r["P"], r["t_f"]
    log = LOG / "solver_attempts" / name / f"{seed}-{arm}"
    t0 = time.monotonic()
    full = O.verdict(z, attempt_dir=log / "full")
    t_star, t_status = (None, "certified") if full[0] == "consistent" else O.first_inconsistent(z, attempt_dir=log / "latency")
    row = {"seed": seed, "cell": name, "arm": arm, "t_f": t_f,
           "oracle": {"full": {"verdict": full[0], "d_lo": num(full[1]), "d_up": num(full[2]),
                               "t_star": t_star, "t_star_status": t_status}},
           "machine": {"full": machine(y, P), "no_b": machine(y, P, rate=False), "no_c": machine(y, P, box=False)},
           "baselines": baselines(y, arm, None if cell.kind == "healthy" else t_f)}
    for key, call in (("no_b", lambda: O.verdict(z, rate=False, attempt_dir=log / "no_b")),
                      ("no_c", lambda: O.verdict(z, box=False, attempt_dir=log / "no_c")),
                      ("no_d", lambda: O.verdict_free_command(y, attempt_dir=log / "no_d"))):
        v = call()
        row["oracle"][key] = {"verdict": v[0], "d_lo": num(v[1]), "d_up": num(v[2])}
    err = [a - b - c for a, b, c in zip(y, r["Ts"], r["v"])]
    row["sensor_error"] = {"end": err[-1], "max_abs": max(abs(e) for e in err)}
    pad = 1e-9
    row["offset_box_bound"] = [max(z) - T.TA_HI - T.DELTA - pad, min(z) - T.TA_LO + T.DELTA + pad]
    if name in ("jump_2", "jump_5"):
        row["P4"] = {"before": O.verdict(z, t_f, attempt_dir=log / "P4")[0],
                     "at": O.verdict(z, t_f + 1, attempt_dir=log / "P4")[0]}
    if name == "stuck" and arm == "E1":
        k = first_big_change(P, t_f)
        row["P7"] = {"k_change": k}
        if k is not None:
            row["P7"].update({"at_tf": O.verdict(z, t_f + 1, attempt_dir=log / "P7")[0],
                              "before_change": O.verdict(z, k, attempt_dir=log / "P7")[0],
                              "by_k_plus_30": O.verdict(z, min(len(z), k + 31), attempt_dir=log / "P7")[0]})
    if cell.kind == "healthy":
        A = T.ambient_part(r["TA"])
        v, lo, up, inner, outer = O.verdict_and_offsets(z, attempt_dir=log / "P6")
        row["P6"] = {"interval": inner, "outer_interval": outer, "A_min": min(A), "A_max": max(A),
                     "rule": {str(R): p6_rule(min(A), max(A), R) for R in (1, 3)}}
    row["seconds"] = round(time.monotonic() - t0, 3)
    return row


def twin_job(args):
    seed, case, arm, draw, b, (y_a, P_a, y_b, P_b) = args
    log = LOG / "solver_attempts" / "P1" / f"{case}-{seed}-{arm}-{draw}"
    out = {"seed": seed, "case": case, "arm": arm, "draw": draw, "offset": b,
           "max_abs_y_diff": max(abs(p - q) for p, q in zip(y_a, y_b))}
    members = []
    for tag, y, P in (("a", y_a, P_a), ("b", y_b, P_b)):
        z = [p - s for p, s in zip(y, T.known_part(P))]
        v = O.verdict(z, attempt_dir=log / tag)
        members.append({"oracle": v[0], "d_lo": num(v[1]), "d_up": num(v[2]), "machine": machine(y, P),
                        "baselines": {f"{var}@{arm_t}": B.outcome(var, y, THRESHOLDS[var][arm_t]["threshold"])["alarm"]
                                      for var in B.VARIANTS for arm_t in T.ARMS}})
    out["members"] = members
    return out


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--thresholds", type=Path, required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--rehearsal", action="store_true")
    mode.add_argument("--final", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    kind = "final" if a.final else "rehearsal"
    env = thermal_v2_env.check()
    thresholds_path = a.thresholds.resolve()
    rel = thresholds_path.relative_to(ROOT)
    if a.final:
        if subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT).returncode:
            raise SystemExit("FINAL refused: tracked files differ from HEAD")
        if not git("ls-files", str(rel)):
            raise SystemExit("FINAL refused: the thresholds file is not committed")
    thresholds = json.loads(thresholds_path.read_text())["thresholds"]
    a.out.mkdir(parents=True, exist_ok=False)
    seeds = SEEDS[kind]
    tasks = ([(s, c.name, arm) for c in T.CELLS for arm in T.ARMS for s in seeds["cells"]]
             + [(s, "healthy", arm) for arm in T.ARMS for s in seeds["healthy"]])
    twins = list(thermal_twins.pairs(T, seeds["twins"]))
    meta = {"kind": kind, "git_head": git("rev-parse", "HEAD"), "env": env, "thresholds_file": str(rel),
            "thresholds_sha256": __import__("hashlib").sha256(thresholds_path.read_bytes()).hexdigest(),
            "dmreda_reference_sha256": B.verify_reference(),
            "seeds": {k: [v[0], v[-1]] for k, v in seeds.items()}, "runs": len(tasks), "twin_pairs": len(twins),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    t0 = time.monotonic()
    with ProcessPoolExecutor(a.workers, initializer=init, initargs=(thresholds, str(a.out))) as pool, \
            (a.out / "runs.jsonl").open("w") as runs, (a.out / "twins.jsonl").open("w") as tw:
        for row in pool.map(run_job, tasks, chunksize=1):
            runs.write(json.dumps(row, allow_nan=False) + "\n")
            runs.flush()
        for row in pool.map(twin_job, twins, chunksize=1):
            tw.write(json.dumps(row, allow_nan=False) + "\n")
            tw.flush()
    meta["seconds"] = round(time.monotonic() - t0, 1)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps({k: meta[k] for k in ("kind", "runs", "twin_pairs", "seconds")}))


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()
