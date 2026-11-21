"""ISOLATION-PLAN.md: F3-iso on the DEV rows, with simulated solver failures, and its checks I1-I5.

  python -B iso_run.py identity OUT                    I1: F3-iso without injection against F3, 6 DEV rows
  python -B iso_run.py run OUT [--workers 6]           the 1400 DEV rows with the rates of section 2 (resumable)
  python -B iso_run.py summary OUT                     I2-I5 and the verdict
"""
import argparse
import hashlib
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
sys.path[:0] = [str(HERE)]
import diag3_cw as C  # noqa: E402
import diag3_cw_dev as CD  # noqa: E402
import f3_iso as ISO  # noqa: E402
import baselines_run as BR  # noqa: E402  (the 1400 DEV rows with their oracle)

S, T, G = C.S, C.T, C.G
RATES = {"fold": 0.002, "range": 0.001, "cert": 0.5, "implied": 0.2}
K = 64
TIMING = {"seconds", "step_ms", "fold_step_ms"}
_MAKE = C.make


def _iso_make(var, cy):
    w = _MAKE("F3", cy)
    ISO.install(w)
    return w


def one(r, rates, iso=True):
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    if iso:
        C.make = _iso_make
        ISO.inject(rates, BR.key(r))
        before = ISO._SOLVER.n_restarts if ISO._SOLVER is not None else 0
    try:
        res = CD.online("F3", G.zs_of(run), C.W, K, r["t_star"])
    finally:
        C.make = _MAKE
        if iso:
            ISO.uninstall()
    if iso:
        res["injected"] = dict(ISO._INJECT["log"])
        res["restarts"] = (ISO._SOLVER.n_restarts if ISO._SOLVER is not None else 0) - before
    return {"key": BR.key(r), **res}


def job(args):
    r, out = args
    path = Path(out) / f"iso-{BR.key(r)}.json"
    if path.exists():
        return BR.key(r), "done before"
    rec = one(r, RATES)
    path.write_text(json.dumps(rec, default=str) + "\n")
    return BR.key(r), rec["detect"], rec["injected"], rec["restarts"]


def git_state():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=HERE, capture_output=True,
                           text=True).stdout.strip()
    return head, bool(dirty)


def identity(out):
    out.mkdir(parents=True, exist_ok=True)
    rows = sorted(BR.dev_rows(), key=lambda r: hashlib.sha256(BR.key(r).encode()).hexdigest())[:6]
    res = []
    for r in rows:
        a = one(r, {}, iso=False)
        b = one(r, {}, iso=True)
        diff = [k for k in a if k not in TIMING and json.dumps(a[k], default=str) != json.dumps(b.get(k), default=str)]
        res.append({"key": BR.key(r), "differs": diff, "restarts": b["restarts"]})
        print(res[-1], flush=True)
    ok = all(not x["differs"] and x["restarts"] == 0 for x in res)
    (out / "identity.json").write_text(json.dumps({"rows": res, "I1": ok}, indent=1) + "\n")
    print("I1", ok)


def run(out, workers):
    out.mkdir(parents=True, exist_ok=True)
    head, dirty = git_state()
    if not (out / "meta.json").exists():
        (out / "meta.json").write_text(json.dumps({"git_head": head, "git_dirty_tracked": dirty, "rates": RATES,
            "K": K, "W": C.W, "machine": platform.machine(), "platform": platform.platform(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n")
    jobs = [(r, str(out)) for r in BR.dev_rows()]
    with ProcessPoolExecutor(workers) as pool:
        for f in as_completed([pool.submit(job, j) for j in jobs]):
            print(f.result(), flush=True)
    meta = json.loads((out / "meta.json").read_text())
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def summary(out):
    rows = {BR.key(r): r for r in BR.dev_rows()}
    xs = {p.stem[4:]: json.loads(p.read_text()) for p in out.glob("iso-*.json")}
    complete = set(xs) == set(rows)
    sound, early, uncert, mism, restarts_bad, kept, slab = [], [], [], [], [], 0, []
    inj_tot, nat = {}, 0
    for k, x in xs.items():
        r = rows[k]
        admissible = r["cell"] == "healthy" or (r["status"] == "certified" and r["t_star"] is None)
        det, ts = x["detect"], (r["t_star"] if r["status"] == "certified" else None)
        if det is not None and admissible:
            sound.append(k)
        if det is not None and ts is not None and det < ts:
            early.append(k)
        cert = x["alarm_certificate"] or {}
        m = cert.get("certified_margin_mC")
        if det is not None and not (cert.get("certified") and isinstance(m, (int, float)) and math.isfinite(m) and m < 0):
            uncert.append(k)
        fs = x["failsafe"]
        got = {role: fs[name].get("exception", 0) for role, name in
               (("range", "range_failures"), ("cert", "cert_fallbacks"), ("fold", "fold_dir_fallbacks"),
                ("implied", "fold_apriori_fallbacks"))}
        want = {role: x["injected"].get(role, 0) for role in got}
        if got != want:
            mism.append([k, got, want])
        n_inj = sum(want.values())
        for role, n in want.items():
            inj_tot[role] = inj_tot.get(role, 0) + n
        if x["restarts"] < 3 * n_inj:
            restarts_bad.append([k, x["restarts"], n_inj])
        nat += x["restarts"] - 3 * n_inj
        kept = max(kept, x["max_kept"])
        if any(v for kk, v in fs.items() if isinstance(v, dict) and v.get("slab")):
            slab.append(k)
    rep = {"rows": len(xs), "I2_complete": complete, "I3_sound": complete and not (sound or early or uncert),
           "soundness": sound, "early": early, "uncertified": uncert,
           "I4_counters": complete and not mism and not restarts_bad, "counter_mismatches": mism[:20],
           "restart_shortfalls": restarts_bad[:20], "injected_by_role": inj_tot, "natural_restarts": nat,
           "I5_memory_slab": complete and kept <= K + 1 and not slab, "max_kept": kept, "slab_rows": slab,
           "seconds": round(sum(x["seconds"] for x in xs.values()), 1)}
    idf = out / "identity.json"
    rep["I1_identity"] = json.loads(idf.read_text())["I1"] if idf.exists() else None
    failed = complete and not (rep["I3_sound"] and rep["I4_counters"] and rep["I5_memory_slab"])
    rep["verdict"] = ("FAIL" if failed or rep["I1_identity"] is False else
                      "INCOMPLETE" if not complete or rep["I1_identity"] is None else "PASS")
    (out / "summary.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("identity", "run", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    {"identity": lambda: identity(a.out), "run": lambda: run(a.out, a.workers),
     "summary": lambda: summary(a.out)}[a.cmd]()


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
