"""WIDEBOX-PLAN.md: the oracle, IM (v2), TS (cyl16p) and WM (F3) under a wider assumed ambient box, on the DEV rows.

  python -B widebox.py check OUT [--workers 14]        the checks of the plan; writes OUT/check.json
  python -B widebox.py run OUT [--workers 14]          the run, after a passing check (boxes 21-29, then 22-28)
  python -B widebox.py summary OUT                     the measures of the plan; writes OUT/summary.json

The data are generated with the frozen box [23, 27]; only the box the oracle and the monitors assume changes. Four
modules bind the shifted box at import (template_state, diag1, diag3, diag3_cw); the generator, the oracle and v2 read
thermal.TA_LO and TA_HI when called. `box()` sets all of them, and `_guard()` stops the run if any other module of the
repository holds a box of its own.
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / "experiments/oracle"), str(ROOT / "env")]
import ambient_study as A  # noqa: E402
import thermal_oracle as O  # noqa: E402
import thermal_v2_env  # noqa: E402
import widebox_vertices as WV  # noqa: E402

C, CD, G, S, T, V = A.C, A.CD, A.G, A.S, A.T, A.V
W3 = C.W3
O.HERE = HERE / "widebox_oracle_worker.py"       # the oracle's solver child, at the parent's box (see that file)
FROZEN = (23.0, 27.0)
BOXES = {"23-27": FROZEN, "22-28": (22.0, 28.0), "21-29": (21.0, 29.0)}
RUN_ORDER = ("21-29", "22-28")
DEV_ROWS = ROOT / "results/v3/dev-45cff1d/rows.jsonl"
F3_REF = ROOT / "results/v3/diag3/amend10-r1r2-0ce80072-arch/R-none"
AMB_B = ROOT / "results/v3/ambient/amb-443d8b30-mac"
N_CHECK = 48
SLOW = ("drift_0.0005", "drift_0.001", "drift_0.002")


# ---- the box -------------------------------------------------------------------------------------------------------

def _guard(b):
    want = {"TA_LO": b[0], "TA_HI": b[1], "LO": b[0] - V.SHIFT, "HI": b[1] - V.SHIFT}
    for name, m in list(sys.modules.items()):
        f = getattr(m, "__file__", None)
        if not f or not Path(f).resolve().is_relative_to(ROOT / "experiments"):
            continue
        for a, v in want.items():
            x = getattr(m, a, None)
            if isinstance(x, (int, float)) and x != v:
                raise RuntimeError(f"{name}.{a} = {x}: a box this script does not set")


def set_box(b):
    T.TA_LO, T.TA_HI = b
    os.environ["WIDEBOX_TA"] = f"{b[0]!r},{b[1]!r}"          # read by the oracle's solver child
    for m in (V, G, W3, C):
        m.LO, m.HI = b[0] - V.SHIFT, b[1] - V.SHIFT
    _guard(b)


@contextmanager
def box(b):
    set_box(b)
    try:
        yield
    finally:
        set_box(FROZEN)


set_box(FROZEN)


def template(name):
    """cyl16p for the box: the frozen tables at 23-27, else ambient_study's clamps and start supports for the box"""
    return A.cyl16p() if name == "23-27" else A.cyl16p(BOXES[name])


# ---- rows ----------------------------------------------------------------------------------------------------------

def key(r):
    return f"{r['seed']}-{r['cell']}-{r['arm']}-{r['ambient']}-{r['noise']}"


def dev_rows():
    """the 1320 DEV comparison rows with their frozen-box oracle, and the 80 healthy edge-noise rows (430070-430089)"""
    rows = [json.loads(line) for line in DEV_ROWS.read_text().splitlines() if line.strip()]
    rows = [{k: r[k] for k in ("seed", "cell", "arm", "ambient", "noise")}
            | {"t_star": r["oracle"]["t_star"], "status": r["oracle"]["status"], "v2": r["v2"]} for r in rows]
    rows += [{"seed": s, "cell": "healthy", "arm": a, "ambient": al, "noise": "edge", "t_star": None,
              "status": None, "v2": None} for s in range(430070, 430090) for a in T.ARMS for al in ("rw", "ramp")]
    assert len(rows) == 1400 and len({key(r) for r in rows}) == 1400 and all(r["seed"] in S.DEV for r in rows)
    return rows


def check_rows(rows, n=N_CHECK):
    return sorted(rows, key=lambda r: hashlib.sha256(key(r).encode()).hexdigest())[:n]


def z_sha(run):
    return hashlib.sha256(json.dumps(run["z"]).encode()).hexdigest()


def generate(r):
    with box(FROZEN):
        return S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])


# ---- jobs ----------------------------------------------------------------------------------------------------------

def job(args):
    """one row at one assumed box: the oracle, v2, cyl16p and F3"""
    r, name, out = args
    k = key(r)
    path = Path(out) / name / f"{k}.json"
    if path.exists():
        return k, name, "done before"
    b = BOXES[name]
    run = generate(r)
    with box(b):
        t0 = time.monotonic()
        t_star, status = O.first_inconsistent(run["z"], attempt_dir=Path(out) / "solver_attempts" / name / k)
        oracle_s = round(time.monotonic() - t0, 2)
        n_att = attempts_at(Path(out) / "solver_attempts" / name / k, b)
        v2 = A.first_v2(run["y"], run["P"], b)
        ts = A.first_template(template(name), run["y"], run["P"], b)
        f3 = CD.online("F3", G.zs_of(run), C.W, 64, t_star, tp=template(name))
    rec = {"key": k, "box": name, **{x: r[x] for x in ("seed", "cell", "arm", "ambient", "noise")},
           "z_sha256": z_sha(run), "oracle": {"t_star": t_star, "status": status, "seconds": oracle_s, "attempts": n_att},
           "v2": v2, "cyl16p": ts, "F3": f3}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec) + "\n")
    tmp.rename(path)
    return k, name, t_star, v2, ts, f3["detect"]


def attempts_at(d, b):
    """the number of the oracle's solver attempts in d; stops if one of them was solved at another box"""
    n = 0
    for a in d.rglob("attempt.json"):
        got = json.loads((a.parent / "box.json").read_text()) if (a.parent / "box.json").exists() else None
        if got != list(b):
            raise RuntimeError(f"{a.parent}: solver attempt at box {got}, not {list(b)}")
        n += 1
    return n


def job_imts(r):
    """v2 and cyl16p at the three boxes, for the comparison with the ambient study's part (b)"""
    run = generate(r)
    rec = {"key": key(r)}
    for name, b in BOXES.items():
        with box(b):
            rec[f"v2@{name}"] = A.first_v2(run["y"], run["P"], b)
            rec[f"cyl16p@{name}"] = A.first_template(template(name), run["y"], run["P"], b)
    return rec


def pool_map(fn, jobs, workers):
    out = []
    with ProcessPoolExecutor(workers) as pool:
        for f in as_completed([pool.submit(fn, j) for j in jobs]):
            out.append(f.result())
            print(json.dumps(out[-1]) if isinstance(out[-1], dict) else out[-1], flush=True)
    return out


# ---- provenance ----------------------------------------------------------------------------------------------------

def provenance(workers):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    return {"git_head": head, "git_dirty_tracked": bool(dirty.strip()), "platform": platform.platform(),
            "env": thermal_v2_env.check(), "workers": workers, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


# ---- check ---------------------------------------------------------------------------------------------------------

def check(out, workers, n, imts):
    out.mkdir(parents=True, exist_ok=True)
    rep = {"meta": provenance(workers), "n_rows": n, "imts_rows": imts, "differences": []}
    diff = rep["differences"]

    # 1. the vertex check of Appendix A.5 at every box
    rep["vertices"] = {name: WV.check(A.cyl16p() if name == "23-27" else A.cyl16p(b), b) for name, b in BOXES.items()}
    fz = rep["vertices"]["23-27"]
    if (fz["vertices_C"], fz["vertices_cuts"]) != (28, 14):
        diff.append(["vertices at 23-27", [fz["vertices_C"], fz["vertices_cuts"]], [28, 14]])
    for name, v in rep["vertices"].items():
        if v["steps_above_a_clamp"] or not v["start_segment_ends_in_C"]:
            diff.append([f"vertex check at {name}", v["steps_above_a_clamp"], v["start_segment_ends_in_C"]])

    rows = dev_rows()
    # 2. IM and TS at the three boxes against the ambient study's part (b)
    uni = [r for r in rows if r["noise"] == "uniform"][:imts]
    for rec in pool_map(job_imts, uni, workers):
        ref = json.loads((AMB_B / f"b-{rec['key']}.json").read_text())
        for f in rec:
            if f != "key" and rec[f] != ref[f]:
                diff.append([rec["key"], f, rec[f], ref[f]])

    # 3. the full job at the frozen box on the rows with the smallest sha256 keys
    sub = check_rows(rows, n)
    ck = out / "check-23-27"
    pool_map(job, [(r, "23-27", str(ck)) for r in sub], workers)
    eps = 0.0
    for r in sub:
        k = key(r)
        got = json.loads((ck / "23-27" / f"{k}.json").read_text())
        if got["z_sha256"] != z_sha(S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"],
                                          r["ambient"], r["noise"])):
            diff.append([k, "z_sha256"])
        if r["noise"] == "uniform":
            for f, want in (("t_star", r["t_star"]), ("status", r["status"])):
                if got["oracle"][f] != want:
                    diff.append([k, f"oracle {f}", got["oracle"][f], want])
            if got["v2"] != r["v2"]:
                diff.append([k, "v2", got["v2"], r["v2"]])
            amb = json.loads((AMB_B / f"b-{k}.json").read_text())
            if got["cyl16p"] != amb["cyl16p@23-27"]:
                diff.append([k, "cyl16p", got["cyl16p"], amb["cyl16p@23-27"]])
        ref_name = f"edge-{r['seed']}-{r['arm']}-{r['ambient']}.json" if r["noise"] == "edge" else f"{k}.json"
        ref = json.loads((F3_REF / ref_name).read_text())
        a, b = got["F3"], ref
        if a["detect"] != b["detect"]:
            diff.append([k, "F3 detect", a["detect"], b["detect"]])
        ca, cb = a["alarm_certificate"] or {}, b["alarm_certificate"] or {}
        if ca.get("certified") != cb.get("certified"):
            diff.append([k, "F3 certified", ca.get("certified"), cb.get("certified")])
        if ca.get("certified_margin_mC") is not None and cb.get("certified_margin_mC") is not None:
            e = abs(ca["certified_margin_mC"] - cb["certified_margin_mC"])
            eps = max(eps, e)
            if e > C.MARGIN_TOL_E:
                diff.append([k, "F3 certified margin (mC)", ca["certified_margin_mC"], cb["certified_margin_mC"]])
    rep["F3_largest_certified_margin_difference_mC"] = eps
    rep["pass"] = not diff and n == N_CHECK and imts == 1320 and not rep["meta"]["git_dirty_tracked"]
    rep["meta"]["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "check.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if k != "meta"}, indent=1))
    return rep["pass"]


# ---- run -----------------------------------------------------------------------------------------------------------

def run(out, workers, boxes, n_rows, test):
    chk = json.loads((out / "check.json").read_text()) if (out / "check.json").exists() else {}
    meta = provenance(workers)
    if not test:
        if not chk.get("pass"):
            raise SystemExit("no passing check.json in OUT: run `check` first")
        if chk["meta"]["git_head"] != meta["git_head"] or meta["git_dirty_tracked"]:
            raise SystemExit("the check was made at another commit, or the tracked tree is dirty")
    rows = dev_rows()
    if n_rows:
        rows = check_rows(rows, n_rows)
    meta |= {"stage": "test" if test else "run", "boxes": list(boxes), "rows": len(rows)}
    if not (out / "meta.json").exists():
        (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    edge_first = sorted(rows, key=lambda r: (r["noise"] != "edge", key(r)))    # the longest WM runs first
    jobs = [(r, name, str(out)) for name in boxes for r in edge_first]
    pool_map(job, jobs, workers)
    m = json.loads((out / "meta.json").read_text())
    m["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(m, indent=1) + "\n")


# ---- summary -------------------------------------------------------------------------------------------------------

def _leaves(d, pre=""):
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            yield from _leaves(v, f"{pre}{k}.")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            yield f"{pre}{k}", v


def summary(out):
    N = T.N
    rows = {key(r): r for r in dev_rows()}
    ev0 = [k for k, r in rows.items() if r["status"] == "certified" and r["t_star"] is not None]
    rep = {"rows": len(rows), "frozen_events": len(ev0), "boxes": {}}
    for name in RUN_ORDER:
        d = out / name
        if not d.is_dir():
            continue
        got = {j["key"]: j for j in (json.loads(p.read_text()) for p in d.glob("*.json"))}
        b = {"rows": len(got), "complete": set(got) == set(rows)}
        keys = [k for k in rows if k in got]
        st = {k: got[k]["oracle"]["status"] for k in keys}
        ts = {k: got[k]["oracle"]["t_star"] for k in keys}
        uni = [k for k in keys if rows[k]["noise"] == "uniform"]
        ev = [k for k in uni if st[k] == "certified" and ts[k] is not None]
        both = [k for k in ev0 if k in got and st[k] == "certified" and ts[k] is not None]
        b["oracle"] = {
            "events": len(ev),
            "frozen_events_no_longer_detected": [k for k in ev0 if k in got and ts[k] is None],
            "assumption_delay_s": sum(ts[k] - rows[k]["t_star"] for k in both),
            "events_certified_at_both": len(both),
            "earlier_than_frozen": [k for k in both if ts[k] < rows[k]["t_star"]],
            "new_events": [k for k in ev if k not in ev0],
            "undetermined_uniform": sum(st[k] == "undetermined" for k in uni),
            "undetermined_edge": sum(st[k] == "undetermined" for k in keys if rows[k]["noise"] == "edge"),
            "seconds": sum(got[k]["oracle"]["seconds"] for k in keys)}
        adm = [k for k in keys if rows[k]["cell"] == "healthy" or (st[k] == "certified" and ts[k] is None)]

        def det(k, m):
            x = got[k][m]["detect"] if m == "F3" else got[k][m]
            return N if x is None else x

        paired = [k for k in ev if got[k]["v2"] is not None]
        lag_v2 = sum(det(k, "v2") - ts[k] for k in paired)
        b["paired"], b["v2_paired_lag"], b["monitors"] = len(paired), lag_v2, {}
        for m in ("v2", "cyl16p", "F3"):
            lag = sum(det(k, m) - ts[k] for k in paired)
            raw = {k: (got[k][m]["detect"] if m == "F3" else got[k][m]) for k in keys}
            b["monitors"][m] = {
                "paired_lag": lag, "D_paired": (1 - lag / lag_v2) if lag_v2 else None,
                "lag_all_events": sum(det(k, m) - ts[k] for k in ev),
                "misses": sum(raw[k] is None for k in ev), "at_t_star": sum(raw[k] == ts[k] for k in ev),
                "admissible_alarms": [k for k in adm if raw[k] is not None],
                "early": [k for k in ev if raw[k] is not None and raw[k] < ts[k]],
                "against_frozen_t_star": {
                    "lag_all_events": sum(det(k, m) - rows[k]["t_star"] for k in ev0 if k in got),
                    "lag_drift": sum(det(k, m) - rows[k]["t_star"] for k in ev0 if k in got
                                     and rows[k]["cell"].startswith("drift")),
                    "misses": sum(raw[k] is None for k in ev0 if k in got)},
                "slow_drift_cells": {c: {"events": sum(rows[k]["cell"] == c for k in ev),
                                         "lag": sum(det(k, m) - ts[k] for k in ev if rows[k]["cell"] == c),
                                         "misses": sum(raw[k] is None for k in ev if rows[k]["cell"] == c)}
                                     for c in SLOW}}
        b["oracle"]["slow_drift_delay_s"] = {c: sum(ts[k] - rows[k]["t_star"] for k in both if rows[k]["cell"] == c)
                                             for c in SLOW}
        f = [got[k]["F3"] for k in keys]
        alarms = [x for x in f if x["detect"] is not None]
        fs = {}
        for x in f:
            for leaf, v in _leaves(x.get("failsafe")):
                fs[leaf] = fs.get(leaf, 0) + v
        b["F3_cost"] = {
            "median_of_median_step_ms": float(np.median([x["step_ms"]["median"] for x in f])),
            "median_of_longest_fold_ms": float(np.median([x["fold_step_ms"]["max"] for x in f])),
            "longest_fold_ms": max(x["fold_step_ms"]["max"] for x in f),
            "runs_with_a_fold_over_1s": sum(x["fold_step_ms"]["max"] > 1000 for x in f),
            "max_kept": max(x["max_kept"] for x in f), "max_vars": max(x["max_vars"] for x in f),
            "max_rows": max(x["max_rows"] for x in f), "n_lp": sum(x["n_lp"] for x in f),
            "n_retry": sum(x["n_retry"] for x in f), "evictions": sum(x["evictions"] for x in f),
            "failsafe_totals": fs, "alarms": len(alarms),
            "certified_alarms": sum(bool((x["alarm_certificate"] or {}).get("certified")) for x in alarms),
            "seconds": sum(x["seconds"] for x in f)}
        rep["boxes"][name] = b
    (out / "summary.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("check", "run", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--n", type=int, default=N_CHECK, help="check: rows of the frozen-box job (the plan: 48)")
    ap.add_argument("--imts", type=int, default=1320, help="check: rows of the IM/TS comparison (the plan: 1320)")
    ap.add_argument("--boxes", nargs="+", default=list(RUN_ORDER), choices=RUN_ORDER)
    ap.add_argument("--rows", type=int, help="run: only the N rows with the smallest sha256 keys (a test)")
    ap.add_argument("--test", action="store_true", help="run without a passing check (a test; not the plan's run)")
    a = ap.parse_args()
    if a.cmd == "check":
        sys.exit(0 if check(a.out, a.workers, a.n, a.imts) else 1)
    if a.cmd == "run":
        a.out.mkdir(parents=True, exist_ok=True)
        run(a.out, a.workers, a.boxes, a.rows, a.test)
    else:
        summary(a.out)


if __name__ == "__main__":
    main()
