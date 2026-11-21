"""H-FB: the frozen F3 under injected LP failures, on fresh seeds (plan: experiments/v3/FB-PLAN.md).

The seeds 450000-450024 are generated in their own namespace, "v3fb" (never generated before; not DEV, not the
validation block). The laws and the per-seed design are freeze 3's (MANIFEST-V3: 11 cells x E0/E1 x rw/ramp with
uniform noise, plus healthy x E0/E1 x rw/ramp with edge noise: 48 runs a seed, 1200 in all).
The failures are injected by DIAG-3 amendment 10's harness (amend10.Harness), unchanged: the same settings, rates and
hash rule, keyed by this test's row keys. The candidate code is checked against MANIFEST-V3 before anything runs.

  python -B fb_run.py oracle OUT [--workers 13]              the oracle t* and v2 for every row (once)
  python -B fb_run.py run OUT --setting none|a..f [--variant F3|F3a] [--workers 13] [--limit N]
  python -B fb_run.py summary OUT/RUN_DIR                    the per-setting criteria
  python -B fb_run.py verdict OUT                            the decision of FB-PLAN.md section 4
  python -B fb_run.py identity OUT --setting S --n N         rehearsal: N DEV rows with amend10's keys, compared
                                                             with the R1/R2 records of amend10 (all but time)
"""
import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
ROOT = HERE.parents[2]
for sub in ("experiments/v3", "experiments/v3/diag", "experiments/oracle", "experiments/machine",
            "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import amend10 as A  # noqa: E402
import dev_scenarios as S  # noqa: E402
import run_validation as RV1  # noqa: E402
import template_state as V  # noqa: E402
import thermal_oracle as O  # noqa: E402
import thermal_v2_env  # noqa: E402

C, CD, G, T = A.C, A.CD, A.G, A.T
W, K = A.W, A.K
MANIFEST = V3 / "frozen" / "MANIFEST-V3.json"
FB = range(450000, 450025)
NAMESPACE = "v3fb"
TIME_FIELDS = ("seconds", "step_ms", "fold_step_ms")

# ---- the seed namespace: fresh seeds, without touching dev_scenarios.py ----------------------------------------
_prefix_orig = S._prefix


def _prefix(seed):
    if seed in FB:
        return NAMESPACE
    return _prefix_orig(seed)


S._prefix = _prefix
assert not set(FB) & set(S.DEV) and not set(FB) & set(S.VALIDATION)


def check_manifest():
    m = json.loads(MANIFEST.read_text())
    bad = [p for p, h in m["files"].items() if RV1.sha256(ROOT / p) != h]
    if bad:
        raise SystemExit(f"frozen manifest mismatch: {bad}")
    return m, RV1.sha256(MANIFEST)


PLAN = V3 / "FB-PLAN.md"


def check_approval():
    """fresh seeds are generated only under an approved plan and from a clean tree"""
    import re
    hit = re.search(r"^Status: APPROVED by Can Koç on (\d{4}-\d{2}-\d{2})$", PLAN.read_text(), re.M)
    if not hit:
        raise SystemExit("FB-PLAN.md is not approved: no v3fb seed may be generated")
    head, dirty = git_state()
    if dirty:
        raise SystemExit("the working tree has tracked changes: commit first")
    return hit.group(0)


def rows(m):
    return RV1.tasks(m, FB)


def key(t):
    seed, cell, arm, al, nl = t
    return f"fb-{seed}-{cell}-{arm}-{al}-{nl}"


def git_state():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    return head, bool(dirty)


def generate(t):
    seed, cell_name, arm, al, nl = t
    return S.run(seed, next(c for c in T.CELLS if c.name == cell_name), arm, al, nl)


# ---- stage 1: the oracle ----------------------------------------------------------------------------------------
def oracle_job(args):
    t, out = args
    r = generate(t)
    t0 = time.monotonic()
    t_star, status = O.first_inconsistent(r["z"], attempt_dir=Path(out) / "solver_attempts" / key(t))
    return {"key": key(t), "seed": t[0], "cell": t[1], "arm": t[2], "ambient": t[3], "noise": t[4], "t_f": r["t_f"],
            "oracle": {"t_star": t_star, "status": status, "seconds": round(time.monotonic() - t0, 2)},
            "v2": RV1.v2_first(r["y"], r["P"])}


def oracle(out, workers):
    approval = check_approval()
    m, msha = check_manifest()
    env = thermal_v2_env.check()
    head, dirty = git_state()
    out.mkdir(parents=True, exist_ok=False)
    todo = rows(m)
    meta = {"stage": "oracle", "approval": approval, "git_head": head, "git_dirty_tracked": dirty, "env": env, "manifest_sha256": msha,
            "namespace": NAMESPACE, "seeds": [FB[0], FB[-1]], "rows": len(todo), "host": platform.node(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out / "oracle-meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    with ProcessPoolExecutor(workers) as pool, (out / "oracle.jsonl").open("w") as f:
        for row in pool.map(oracle_job, [(t, str(out)) for t in todo], chunksize=1):
            f.write(json.dumps(row) + "\n")
            f.flush()
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    meta["oracle_sha256"] = RV1.sha256(out / "oracle.jsonl")
    (out / "oracle-meta.json").write_text(json.dumps(meta, indent=1) + "\n")


# ---- stage 2: F3 under a setting ---------------------------------------------------------------------------------
_TP = None


def _init(directions, sha):
    global _TP
    _TP = V.load_frozen(directions, sha)


def run_job(args):
    k, t, ts, setting, var, out = args
    path = Path(out) / f"{k}.json"
    if path.exists():
        return k, "done before"
    r = generate(t)
    h = A.Harness(setting, k).install()
    try:
        res = CD.online(var, G.zs_of(r), W, K, ts, tp=_TP)
    finally:
        h.uninstall()
    res = {"key": k, "kind": "fb", "setting": setting, **res, "harness": h.log, "folds": h.folds,
           "audit": getattr(h.w, "audit", None)}
    path.write_text(json.dumps(res, default=str) + "\n")
    return k, res["detect"], res["seconds"]


def load_oracle(out):
    return {r["key"]: r for r in map(json.loads, (out / "oracle.jsonl").read_text().splitlines()) if r}


def run(out, setting, var, workers, limit):
    approval = check_approval()
    m, msha = check_manifest()
    head, dirty = git_state()
    orc = load_oracle(out)
    d = out / f"{setting}-{var}"
    d.mkdir(parents=True, exist_ok=True)
    c = m["candidate"]
    todo = [(key(t), t, orc[key(t)]["oracle"]["t_star"], setting, var, str(d)) for t in rows(m)]
    todo.sort(key=lambda j: orc[j[0]]["oracle"]["t_star"] is not None)          # the long healthy rows first
    todo = todo[:limit] if limit else todo
    meta = {"stage": "run", "approval": approval, "setting": setting, "variant": var, "W": W, "K": K, "workers": workers,
            "git_head": head, "git_dirty_tracked": dirty, "manifest_sha256": msha, "namespace": NAMESPACE,
            "oracle_sha256": RV1.sha256(out / "oracle.jsonl"), "machine": platform.machine(),
            "platform": platform.platform(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (d / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    with ProcessPoolExecutor(workers, initializer=_init, initargs=(ROOT / c["directions_file"],
                                                                    c["directions_sha256"])) as pool:
        for f in as_completed([pool.submit(run_job, j) for j in todo]):
            print(f.result(), flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (d / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


# ---- stage 3: the criteria of one setting ------------------------------------------------------------------------
def summary(d):
    out = d.parent
    meta = json.loads((d / "meta.json").read_text())
    orc = load_oracle(out)
    xs = {p.stem: json.loads(p.read_text()) for p in d.glob("fb-*.json")}
    ref_dir = out / f"none-{meta['variant']}"
    ref = {p.stem: json.loads(p.read_text())["detect"] for p in ref_dir.glob("fb-*.json")} if ref_dir.exists() else {}
    sound, early, uncert, mism, differs, earlier, tot = [], [], [], [], [], [], {}
    for k, x in xs.items():
        r = orc[k]
        admissible = r["cell"] == "healthy" or (r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None)
        ts = r["oracle"]["t_star"] if r["oracle"]["status"] == "certified" else None
        det = x["detect"]
        if det is not None and admissible:
            sound.append([k, det])
        if det is not None and ts is not None and det < ts:
            early.append([k, det, ts])
        cert = x["alarm_certificate"] or {}
        marg = cert.get("certified_margin_mC")
        if det is not None and not (cert.get("certified") and isinstance(marg, (int, float)) and math.isfinite(marg)
                                    and marg < 0):
            uncert.append([k, det, cert])
        if A._counts_by_role(x["failsafe"]) != A._harness_by_role(x["harness"]):
            mism.append([k, A._counts_by_role(x["failsafe"]), x["harness"]])
        if k in ref and det != ref[k]:
            differs.append([k, det, ref[k]])
            if det is not None and (ref[k] is None or det < ref[k]):
                earlier.append([k, det, ref[k]])
        for name, v in x["failsafe"].items():
            if isinstance(v, dict):
                for kk, n in v.items():
                    tot[f"{name}|{kk}"] = tot.get(f"{name}|{kk}", 0) + n
            else:
                tot[name] = tot.get(name, 0) + v
    expected = set(orc)
    complete = set(xs) == expected
    events = [k for k, r in orc.items() if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    B = [k for k in events if orc[k]["v2"] is not None and k in xs]
    Lv2 = sum(orc[k]["v2"] - orc[k]["oracle"]["t_star"] for k in B)
    lag = {k: (xs[k]["detect"] if xs[k]["detect"] is not None else T.N) - orc[k]["oracle"]["t_star"]
           for k in events if k in xs}
    rep = {"meta": meta, "rows": len(xs), "expected": len(expected), "complete": complete,
           "missing_keys": sorted(expected - set(xs))[:20], "extra_keys": sorted(set(xs) - expected)[:20],
           "soundness_violations": sound, "early_alarms": early, "uncertified_alarms": uncert,
           "max_kept": max(x["max_kept"] for x in xs.values()) if xs else None,
           "counter_mismatches": mism[:20], "n_counter_mismatches": len(mism),
           "totals": dict(sorted(tot.items())),
           "slab_failures": {k: v for k, v in tot.items() if k.endswith("|slab")},
           "harness_totals": {k: sum(x["harness"].get(k, 0) for x in xs.values())
                              for k in sorted({k for x in xs.values() for k in x["harness"]})},
           "reported": {"events": len(events), "misses": sum(1 for k in events if k in xs and xs[k]["detect"] is None),
                        "detect_differs_from_none": len(differs), "earlier_than_none": earlier[:20],
                        "n_earlier_than_none": len(earlier),
                        "D_paired": (1 - sum(lag[k] for k in B) / Lv2) if Lv2 else None,
                        "after_reset_detections": sum(1 for k in events if k in xs and xs[k]["detect"] is not None
                                                      and xs[k]["failsafe"]["fold_full_resets"] > 0),
                        "box_alarms": tot.get("box_alarms", 0), "seconds": sum(x["seconds"] for x in xs.values())}}
    a = [x["audit"] for x in xs.values() if x.get("audit")]
    if a:
        rep["audit"] = {"n": sum(y["n"] for y in a), "violations": sum(y["violations"] for y in a),
                        "min_slack_C": min(y["min_slack_C"] for y in a),
                        "n_implied": sum(y["n_implied"] for y in a),
                        "min_slack_implied_C": min(y["min_slack_implied_C"] for y in a)}
    rep["C1_complete"] = complete
    rep["C2_C3_C4_sound"] = complete and not sound and not early and not uncert
    rep["C5_memory"] = complete and rep["max_kept"] is not None and rep["max_kept"] <= K + 1
    rep["C6_counters"] = complete and not mism
    rep["C7_no_slab"] = complete and not any(rep["slab_failures"].values())
    if "audit" in rep:
        rep["C9_audit"] = complete and rep["audit"]["n"] > 0 and rep["audit"]["violations"] == 0
    (d / "summary.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("counter_mismatches", "totals")}, indent=1,
                     default=str))
    return rep


# ---- the decision ------------------------------------------------------------------------------------------------
NEED = [f"{n}|{kind}" for n in ("fold_dir_fallbacks", "fold_apriori_fallbacks", "range_failures", "cert_fallbacks")
        for kind in ("2", "4")] + ["range_fallbacks|one", "range_fallbacks|both", "fold_full_resets", "fold_implied",
                                   "measurements_not_kept"]


def verdict(out):
    sms, rep = {}, {}
    for s in A.SETTINGS:
        p = out / f"{s}-F3" / "summary.json"
        sms[s] = json.loads(p.read_text()) if p.exists() else None
    audits = {s: json.loads((out / f"{s}-F3a" / "summary.json").read_text())
              for s in ("b", "e") if (out / f"{s}-F3a" / "summary.json").exists()}
    keys = ("C1_complete", "C2_C3_C4_sound", "C5_memory", "C6_counters", "C7_no_slab")
    rep["settings"] = {s: ({k: sm[k] for k in keys} if sm else None) for s, sm in sms.items()}
    tot = {}
    for s in "abcdef":
        if sms[s]:
            for k, v in sms[s]["totals"].items():
                tot[k] = tot.get(k, 0) + v
    rep["paths_totals"] = {k: tot.get(k, 0) for k in NEED}
    rep["C8_paths"] = all(tot.get(k, 0) > 0 for k in NEED)
    rep["audits"] = {s: {"C1_complete": a["C1_complete"], "C9_audit": a.get("C9_audit"), "audit": a.get("audit")}
                     for s, a in audits.items()}
    n_implied = sum((a.get("audit") or {}).get("n_implied", 0) for a in audits.values())
    rep["C9"] = len(audits) == 2 and all(a.get("C9_audit") for a in audits.values()) and n_implied > 0
    missing = [s for s, sm in sms.items() if not sm or not sm["C1_complete"]] + \
              [s for s in ("b", "e") if s not in audits or not audits[s]["C1_complete"]]
    failed = [s for s, sm in sms.items() if sm and sm["C1_complete"] and not all(sm[k] for k in keys[1:])]
    failed += [f"{s}-F3a" for s, a in audits.items() if a["C1_complete"] and not a.get("C9_audit")]
    if failed:
        rep["verdict"] = "FAIL"
    elif missing:
        rep["verdict"] = "INCOMPLETE"
    elif not rep["C8_paths"] or not rep["C9"]:
        rep["verdict"] = "INCONCLUSIVE"
    else:
        rep["verdict"] = "PASS"
    rep["failed"], rep["missing"] = failed, missing
    (out / "verdict.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))
    return rep


# ---- rehearsal: the same code path on DEV rows, against amend10's own records ------------------------------------
def identity(out, setting, n, workers):
    m, _ = check_manifest()
    c = m["candidate"]
    ref_dir = ROOT / "results" / "v3" / "diag3" / "amend10-r1r2-0ce80072-arch" / f"R-{setting}"
    dev = [json.loads(l) for l in A.D.ROWS.read_text().splitlines() if l.strip()]
    dev = [r for r in dev if (ref_dir / f"{A.D.key(r)}.json").exists()][:n]
    d = out / f"identity-{setting}"
    d.mkdir(parents=True, exist_ok=True)
    jobs = [(A.D.key(r), None, r["oracle"].get("t_star"), setting, "F3", str(d)) for r in dev]
    runs = {A.D.key(r): r for r in dev}

    def job_dev(j):
        k, _, ts, s, var, dd = j
        r = runs[k]
        t = (r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"])
        return (k, t, ts, s, var, dd)

    with ProcessPoolExecutor(workers, initializer=_init, initargs=(ROOT / c["directions_file"],
                                                                    c["directions_sha256"])) as pool:
        list(pool.map(run_job, [job_dev(j) for j in jobs]))
    bad = []
    for k in runs:
        mine = json.loads((d / f"{k}.json").read_text())
        theirs = json.loads((ref_dir / f"{k}.json").read_text())
        diff = sorted(f for f in set(mine) | set(theirs) if f not in TIME_FIELDS + ("kind", "key")
                      and mine.get(f) != theirs.get(f))
        if diff:
            bad.append([k, diff])
    # the oracle stage's job on the first two DEV rows, against the DEV rows file (no fresh seed is generated)
    orc = []
    for r in dev[:2]:
        t = (r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"])
        o = oracle_job((t, str(d)))
        orc.append([A.D.key(r), o["oracle"]["t_star"], o["oracle"]["status"], r["oracle"]["t_star"],
                    r["oracle"]["status"], o["v2"], r["v2"]])
    orc_bad = [x for x in orc if (x[1], x[2], x[5]) != (x[3], x[4], x[6])]
    rep = {"setting": setting, "rows": len(runs), "differ": bad, "oracle_checked": orc, "oracle_differ": orc_bad}
    (d / "identity.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep))
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("oracle", "run", "summary", "verdict", "identity"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--setting", choices=A.SETTINGS, default="none")
    ap.add_argument("--variant", choices=("F3", "F3a"), default="F3")
    ap.add_argument("--workers", type=int, default=13)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--n", type=int, default=6)
    a = ap.parse_args()
    if a.cmd == "oracle":
        oracle(a.out, a.workers)
    elif a.cmd == "run":
        run(a.out, a.setting, a.variant, a.workers, a.limit)
    elif a.cmd == "summary":
        summary(a.out)
    elif a.cmd == "verdict":
        verdict(a.out)
    else:
        identity(a.out, a.setting, a.n, a.workers)


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
