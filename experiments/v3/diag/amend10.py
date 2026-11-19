"""DIAG-3 amendment 10 (DIAG-3-PLAN.md): F3, F with a sound path for solver failures. DEV only.

  R0  paths    constructed cases, one per failure branch (criterion U0)
  R1  run --setting none     F3 on the 1320 DEV rows and the 80 edge-noise runs (U1)
  R2  run --setting a..f     the same, with failures injected by the harness below (U2)
  R3  run --variant F3a      the exact rational audit, fallback bounds included (U3)
  summary OUT                the criteria of one run directory

The harness is not part of the candidate: it replaces diag3_cw.solve_f3 for the run, so that a chosen LP fails in
all three attempts (n_retry + 3, as a real failure), and logs every failed LP, injected or not, by role. The choice is
a deterministic hash of (row, t, role, direction or side, setting), fixed before any result:
  a  1 % of fold-direction LPs            b  10 % of fold-direction LPs
  c  1 % of as-range and 1 % of certificate LPs
  d  every direction of every fourth fold (folds 4, 8, ...: full resets)
  e  10 % of fold-direction LPs and every P_J fallback LP (the a priori path)
  f  every certificate LP of the upper side (box-sided certificates)
Half of the injected failures have status 2, half status 4 (another bit of the same hash).
usage: python -B amend10.py paths OUT
       python -B amend10.py run OUT --setting none|a|b|c|d|e|f [--variant F3|F3a] [--workers 14] [--limit N]
       python -B amend10.py summary OUT
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import diag3_cw as C  # noqa: E402
import diag3_cw_dev as CD  # noqa: E402
import diag3_dev as D  # noqa: E402

G, S, T, V = C.G, C.S, C.T, C.V
W, K = 256, 64
EDGE = [(s, arm, al) for s in range(430070, 430090) for arm in ("E0", "E1") for al in ("rw", "ramp")]
REF = HERE.parents[2] / "results" / "v3" / "diag3"
SETTINGS = ("none", "a", "b", "c", "d", "e", "f")


def _u(*parts):
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:13], 16) / 16 ** 13, int(h[13], 16) % 2


class Harness:
    def __init__(self, setting, key, rule=None):
        self.setting, self.key, self.rule = setting, key, rule
        self.w, self.folds, self.log = None, 0, {}

    def decide(self, w):
        kind, what = w.role if w.role else (None, None)
        t = w.now
        if self.rule is not None:                                  # R0: a constructed case
            return self.rule(t, kind, what, self)
        u, bit = _u(self.key, t, kind, what, self.setting)
        st = 2 if bit == 0 else 4
        s = self.setting
        if s in ("a", "b", "e") and kind == "fold" and u < (0.01 if s == "a" else 0.10):
            return st
        if s == "e" and kind == "implied":
            return st
        if s == "c" and kind in ("range", "cert") and u < 0.01:
            return st
        if s == "d" and kind == "fold" and self.folds % 4 == 0:
            return st
        if s == "f" and kind == "cert" and what == "up":
            return st
        return None

    def install(self):
        orig_solve, orig_make, orig_fold = C.solve_f3, C.make, C.Failsafe.fold
        h = self

        def solve_f3(win, cvec, **kw):
            st = h.decide(win) if h.setting != "none" or h.rule is not None else None
            if st is not None:
                win.n_retry += len(C.ATTEMPTS)
                win.n_lp += 1
                f = C.Failed(st, "injected")
                injected = True
            else:
                f = orig_solve(win, cvec, **kw)
                injected = False
            if isinstance(f, C.Failed):
                k = f"{win.role[0] if win.role else None}|{f.kind()}|{'injected' if injected else 'natural'}"
                h.log[k] = h.log.get(k, 0) + 1
            return f

        def make(var, cy):
            h.w = orig_make(var, cy)
            return h.w

        def fold(self_, t):
            h.folds += 1
            return orig_fold(self_, t)

        C.solve_f3, C.make, C.Failsafe.fold = solve_f3, make, fold
        self._orig = (orig_solve, orig_make, orig_fold)
        return self

    def uninstall(self):
        C.solve_f3, C.make, C.Failsafe.fold = self._orig


def _counts_by_role(fs):
    """the window's failure counters, by role and status kind (pre-solve empty slabs are not the harness's)"""
    out = {}
    for role, name in (("range", "range_failures"), ("cert", "cert_fallbacks"), ("fold", "fold_dir_fallbacks"),
                       ("implied", "fold_apriori_fallbacks")):
        for kind, n in fs[name].items():
            if kind != "slab" and n:
                out[f"{role}|{kind}"] = n
    return out


def _harness_by_role(log):
    out = {}
    for k, n in log.items():
        role, kind, _ = k.split("|")
        out[f"{role}|{kind}"] = out.get(f"{role}|{kind}", 0) + n
    return out


# ---- R1, R2, R3: the runs ----------------------------------------------------------------------------------------

def job(args):
    kind, spec, setting, var, out = args
    if kind == "dev":
        r = spec
        key = D.key(r)
        run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
        ts = r["oracle"].get("t_star")
    else:
        seed, arm, al = spec
        key = f"edge-{seed}-{arm}-{al}"
        run = S.run(seed, next(c for c in T.CELLS if c.name == "healthy"), arm, al, "edge")
        ts = None
    path = Path(out) / f"{key}.json"
    if path.exists():
        return key, "done before"
    h = Harness(setting, key).install()
    try:
        res = CD.online(var, G.zs_of(run), W, K, ts, tp=V.load_frozen(G.V3 / "frozen" / "cyl16p.json"))
    finally:
        h.uninstall()
    res = {"key": key, "kind": kind, "setting": setting, **res, "harness": h.log, "folds": h.folds,
           "audit": getattr(h.w, "audit", None)}
    path.write_text(json.dumps(res, default=str) + "\n")
    return key, res["detect"], res["seconds"]


def run(out, setting, var, workers, limit):
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: r["oracle"].get("t_star") is not None)          # the long healthy rows first
    jobs = [("edge", e, setting, var, str(out)) for e in EDGE] + [("dev", r, setting, var, str(out)) for r in rows]
    jobs = jobs[:limit] if limit else jobs
    meta = {"setting": setting, "variant": var, "W": W, "K": K, "workers": workers,
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
            "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode),
            "machine": platform.machine(), "platform": platform.platform(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    with ProcessPoolExecutor(workers) as pool:
        for f in as_completed([pool.submit(job, j) for j in jobs]):
            print(f.result(), flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


FALLBACK = ("fold_dir_fallbacks", "fold_apriori_fallbacks", "fold_full_resets", "range_fallbacks", "range_failures",
            "cert_fallbacks", "measurements_not_kept", "fold_implied")     # box_alarms is not a fallback (addendum 2)


def _margin_box_check(k, r, m_ref, cert3):
    """replay row k with F, record F's certified bounds at its alarm, and check that F3's margin is F's with the
    deciding side clipped to the box (DIAG-3 amendment 10, second addendum)"""
    calls, orig_ca, orig_lc = [], C.Stats.certify_alarm, C.Stats.lp_cert
    flag = {"on": False}

    def lc(self, *a):
        res = orig_lc(self, *a)
        if flag["on"]:
            calls.append(res)
        return res

    def ca(self, t, z):
        calls.clear()
        flag["on"] = True
        try:
            out = orig_ca(self, t, z)
        finally:
            flag["on"] = False
        calls.append(("z", z, out))
        return out

    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    C.Stats.certify_alarm, C.Stats.lp_cert = ca, lc
    try:
        recF = CD.online("F", G.zs_of(run), W, K, r["oracle"].get("t_star"), tp=V.load_frozen(G.V3 / "frozen" / "cyl16p.json"))
    finally:
        C.Stats.certify_alarm, C.Stats.lp_cert = orig_ca, orig_lc
    (_, cup), (_, cdn), (_, z, _) = calls[-3], calls[-2], calls[-1]
    zl, zu = np.nextafter(z - C.DELTA_F, -np.inf), np.nextafter(z + C.DELTA_F, np.inf)
    mF = 1e3 * min(zu + cdn, cup - zl)
    m3 = 1e3 * min(zu + min(cdn, -C.LO), min(cup, C.HI) - zl)
    ok = (mF == m_ref and m3 == cert3.get("certified_margin_mC") and (cup > C.HI or cdn > -C.LO) and m3 != mF)
    return {"ok": bool(ok), "F_detect": recF["detect"], "cup": cup, "cdn": cdn, "mF": mF, "m3": m3}


def summary(out):
    meta = json.loads((out / "meta.json").read_text())
    rows = {D.key(r): r for r in map(json.loads, D.ROWS.read_text().splitlines()) if r}
    xs = {p.stem: json.loads(p.read_text()) for p in out.glob("*.json") if p.name not in ("meta.json", "summary.json")}
    refF = {k: json.loads((REF / "cwdev-F-K64-42252a3" / f"cwdev-{k}-F.json").read_text())["detect"] for k in rows}
    refE = {f"edge-{s}-{a}-{al}": json.loads((REF / "edge-42252a3" / f"edge-{s}-{a}-{al}.json").read_text())["detect"]
            for s, a, al in EDGE}
    refM = {k: (json.loads((REF / "cwdev-F-K64-42252a3" / f"cwdev-{k}-F.json").read_text())["alarm_certificate"] or {})
            .get("certified_margin_mC") for k in rows}
    sound, uncert, early, mism, differs, margin_differs, margin_box = [], [], [], [], [], [], []
    tot = {}
    for k, x in xs.items():
        r = rows.get(k)
        admissible = (x["kind"] == "edge" or r["cell"] == "healthy"           # FREEZE-V2 §4: every healthy run
                      or (r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None))
        ts = r["oracle"]["t_star"] if r is not None and r["oracle"]["status"] == "certified" else None
        det = x["detect"]
        if det is not None and admissible:
            sound.append([k, det])
        if det is not None and ts is not None and det < ts:
            early.append([k, det, ts])
        if det is not None and not (x["alarm_certificate"] or {}).get("certified"):
            uncert.append([k, det, x["alarm_certificate"]])
        if _counts_by_role(x["failsafe"]) != _harness_by_role(x["harness"]):
            mism.append([k, _counts_by_role(x["failsafe"]), x["harness"]])
        ref = refE.get(k) if x["kind"] == "edge" else refF.get(k)
        if det != ref:
            differs.append([k, det, ref])
        elif det is not None and x["kind"] == "dev":
            mf = refM[k]
            if mf != (x["alarm_certificate"] or {}).get("certified_margin_mC"):
                (margin_box if (x["alarm_certificate"] or {}).get("box_sides") else margin_differs).append(
                    [k, mf, x["alarm_certificate"]])
        for name, v in x["failsafe"].items():
            if isinstance(v, dict):
                for kk, n in v.items():
                    tot[f"{name}|{kk}"] = tot.get(f"{name}|{kk}", 0) + n
            else:
                tot[name] = tot.get(name, 0) + v
    events = [k for k, r in rows.items() if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    lag = {k: (xs[k]["detect"] if xs[k]["detect"] is not None else T.N) - rows[k]["oracle"]["t_star"]
           for k in events if k in xs}
    lagF = {k: (refF[k] if refF[k] is not None else T.N) - rows[k]["oracle"]["t_star"] for k in events}
    v2 = {k: rows[k]["v2"] for k in events}
    B = [k for k in events if v2[k] is not None and k in xs]
    Lv2 = sum(v2[k] - rows[k]["oracle"]["t_star"] for k in B)
    rep = {"meta": meta, "rows": len(xs), "expected": len(rows) + len(EDGE),
           "soundness_violations": sound, "early_alarms": early, "uncertified_alarms": uncert,
           "max_kept": max(x["max_kept"] for x in xs.values()) if xs else None,
           "counter_mismatches": mism[:20], "n_counter_mismatches": len(mism),
           "detect_differs_from_F": differs[:50], "n_detect_differs_from_F": len(differs),
           "totals": dict(sorted(tot.items())),
           "harness_totals": {k: sum(x["harness"].get(k, 0) for x in xs.values())
                              for k in sorted({k for x in xs.values() for k in x["harness"]})},
           "misses": sum(1 for k in events if k in xs and xs[k]["detect"] is None),
           "misses_F": sum(1 for k in events if k in xs and refF[k] is None),
           "lag_sum": sum(lag.values()), "lag_sum_F": sum(lagF[k] for k in lag),
           "D_paired_dev": (1 - sum(lag[k] for k in B) / Lv2) if Lv2 else None,
           "D_paired_dev_F": (1 - sum(lagF[k] for k in B) / Lv2) if Lv2 else None,
           "after_reset_detections": sum(1 for k in events if k in xs and xs[k]["detect"] is not None
                                         and xs[k]["failsafe"]["fold_full_resets"] > 0),
           "seconds": sum(x["seconds"] for x in xs.values())}
    a = [x["audit"] for x in xs.values() if x.get("audit")]
    if a:
        rep["audit"] = {"n": sum(y["n"] for y in a), "violations": sum(y["violations"] for y in a),
                        "min_slack_C": min(y["min_slack_C"] for y in a),
                        "n_implied": sum(y["n_implied"] for y in a),
                        "min_slack_implied_C": min(y["min_slack_implied_C"] for y in a)}
    expected = set(rows) | {f"edge-{s}-{a}-{al}" for s, a, al in EDGE}
    complete = set(xs) == expected                                   # the key set, not only the count
    rep["complete"] = complete
    rep["missing_keys"], rep["extra_keys"] = sorted(expected - set(xs))[:20], sorted(set(xs) - expected)[:20]
    rep["slab_failures"] = {k: v for k, v in tot.items() if k.endswith("|slab")}
    rep["U2_soundness"] = complete and not sound and not early and not uncert
    rep["U2_memory"] = complete and rep["max_kept"] is not None and rep["max_kept"] <= K + 1
    rep["U2_injections_match"] = complete and not mism
    rep["U2_no_slab"] = complete and not any(rep["slab_failures"].values())
    rep["fallback_totals"] = {k: v for k, v in tot.items() if k.split("|")[0] in FALLBACK}
    if meta["setting"] == "none":
        verified, unexplained = [], list(margin_differs)
        for case in margin_box:                                       # the clipped side must decide the margin
            chk = _margin_box_check(case[0], rows[case[0]], case[1], case[2])
            (verified if chk["ok"] else unexplained).append([*case, chk])
        rep["margin_box_verified"] = verified
        rep["margin_differs_from_F"] = unexplained[:20]
        rep["n_margin_differs_from_F"] = len(unexplained)
        rep["U1"] = rep["U2_soundness"] and not differs and not unexplained and complete
        rep["U1_no_fallback"] = not any(rep["fallback_totals"].values())
    if meta["setting"] == "d":
        rep["U2_recovery"] = complete and rep["after_reset_detections"] > 0
    if "audit" in rep:
        rep["U3"] = complete and rep["audit"]["n"] > 0 and rep["audit"]["violations"] == 0
    (out / "summary.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("detect_differs_from_F", "counter_mismatches")},
                     indent=1, default=str))


def criteria(r2_dirs, r3_dirs):
    """U2 paths over settings (a)-(f) together, and U3's n_implied over the R3 settings together"""
    tot, rep = {}, {}
    for d in r2_dirs:
        sm = json.loads((d / "summary.json").read_text())
        for k, v in sm["totals"].items():
            tot[k] = tot.get(k, 0) + v
        rep[str(d)] = {k: sm.get(k) for k in ("complete", "U2_soundness", "U2_memory", "U2_injections_match", "U2_no_slab",
                                             "U2_recovery") if k in sm}
    need = [f"{n}|{kind}" for n in ("fold_dir_fallbacks", "fold_apriori_fallbacks", "range_failures", "cert_fallbacks")
            for kind in ("2", "4")] + ["range_fallbacks|one", "range_fallbacks|both", "fold_full_resets", "fold_implied",
                                       "measurements_not_kept"]
    rep["paths_totals"] = {k: tot.get(k, 0) for k in need}
    rep["box_alarms_total"] = tot.get("box_alarms", 0)
    rep["U2_paths"] = all(tot.get(k, 0) > 0 for k in need)
    if r3_dirs:
        a = [json.loads((d / "summary.json").read_text()) for d in r3_dirs]
        rep["U3_settings"] = {str(d): x.get("U3") for d, x in zip(r3_dirs, a)}
        rep["U3_n_implied_total"] = sum((x.get("audit") or {}).get("n_implied", 0) for x in a)
        rep["U3"] = all(x.get("U3") for x in a) and rep["U3_n_implied_total"] > 0
    print(json.dumps(rep, indent=1))
    return rep


# ---- R0: the paths -----------------------------------------------------------------------------------------------

def paths(out):
    out.mkdir(parents=True, exist_ok=True)
    tp = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    healthy = next(r for r in rows if r["cell"] == "healthy" and r["noise"] == "uniform")
    fault = next(r for r in rows if r["oracle"]["t_star"] is not None and r["cell"].startswith("jump"))

    def zs_of(r):
        run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
        return G.zs_of(run), r["oracle"].get("t_star")

    def go(zs, ts, rule, horizon):
        h = Harness("paths", "r0", rule).install()
        try:
            rec = CD.online("F3", zs, W, K, ts, horizon=horizon, tp=tp)
        finally:
            h.uninstall()
        return rec, h

    res, ok = {}, {}
    zh, _ = zs_of(healthy)
    zf, tsf = zs_of(fault)
    apriori = tp.clamp(np.full(len(tp.D), np.inf))

    ctl, hc = go(zh, None, lambda *a: None, 80)
    kept = [j for j in sorted(hc.w.zs) if j >= 50]
    tk = kept[0]
    rec, h = go(zh, None, lambda t, k, w, _: 4 if (t == tk and k == "range" and w == "up") else None, tk)
    ok["range_one_side"] = (rec["failsafe"]["range_fallbacks"]["one"] == 1 and tk not in h.w.zs
                            and rec["failsafe"]["measurements_not_kept"] == 1 and rec["detect"] is None)
    rec, h = go(zh, None, lambda t, k, w, _: 2 if (t == tk and k == "range") else None, tk)
    ok["range_both_sides"] = (rec["failsafe"]["range_fallbacks"]["both"] == 1 and tk not in h.w.zs and rec["detect"] is None
                              and rec["failsafe"]["measurements_not_kept"] == 1)

    zb = list(zh)
    zb[100] = 3.0                                                  # outside the as box [-2, 2]
    rec, h = go(zb, None, lambda t, k, w, _: 4 if (t == 100 and k in ("range", "cert")) else None, 100)
    ok["box_alarm"] = (rec["detect"] == 100 and rec["alarm_certificate"]["certified"]
                       and rec["failsafe"]["box_alarms"] == 1 and sorted(rec["alarm_certificate"]["box_sides"]) == ["down", "up"])
    res["box_alarm"] = rec["alarm_certificate"]

    base, _ = go(zf, tsf, lambda *a: None, None)
    ta = base["detect"]
    rec1, _ = go(zf, tsf, lambda t, k, w, _: 4 if (t == ta and k == "cert" and w == "up") else None, None)
    rec2, _ = go(zf, tsf, lambda t, k, w, _: 2 if (t == ta and k == "cert") else None, None)
    ok["cert_one_side"] = (rec1["failsafe"]["cert_fallbacks"].get("4") == 1 and rec1["detect"] is not None
                           and rec1["alarm_certificate"]["certified"] and rec1["detect"] >= ta)
    ok["cert_both_sides"] = ((rec2["detect"] is None or rec2["detect"] == ta or rec2["unproved_primal_alarms"] >= 1)
                             and rec2["failsafe"]["cert_fallbacks"].get("2") == 2
                             and (rec2["detect"] is None or (rec2["alarm_certificate"]["certified"] and rec2["detect"] >= ta)))
    res["cert"] = {"base_detect": ta, "one_side": [rec1["detect"], rec1["alarm_certificate"]],
                   "both_sides": [rec2["detect"], rec2["alarm_certificate"], rec2["unproved_primal_alarms"]]}

    rec, h = go(zh, None, lambda t, k, w, _: 4 if (t == 273 and k == "fold" and w == 40) else None, 273)
    ok["fold_implied"] = (rec["failsafe"]["fold_implied"] == 1 and h.w.tau == 16 and h.w.base[40] < apriori[40]
                          and h.w.base is not None)
    res["fold_implied_base40"] = [float(h.w.base[40]), float(apriori[40])]
    rec, h = go(zh, None, lambda t, k, w, _: 4 if (t == 273 and k in ("fold", "implied") and w == 40) else None, 273)
    ok["fold_apriori"] = (rec["failsafe"]["fold_apriori_fallbacks"].get("4") == 1 and rec["failsafe"]["fold_implied"] == 0
                          and h.w.base[40] == apriori[40])
    rec, h = go(zh, None, lambda t, k, w, _: 2 if (t == 289 and k == "fold") else None, 289)
    ok["full_reset"] = (rec["failsafe"]["fold_full_resets"] == 1 and h.w.tau == 32 and h.w.zs == {} and h.w.last_active == {}
                        and h.w.base is not None and np.array_equal(h.w.base, apriori))
    rec, h = go(zh, None, lambda t, k, w, _: 2 if (t == 289 and k == "fold") else None, 600)
    ok["full_reset_continues"] = (rec["failsafe"]["fold_full_resets"] == 1 and rec["detect"] is None
                                  and sum(rec["failsafe"]["range_failures"].values()) == 0 and len(h.w.zs) > 0)

    z0 = list(zh)
    z0[0] = 3.0                                                    # z_0 outside the box
    rec, h = go(z0, None, lambda *a: None, 50)
    ok["z0_outside_box"] = (rec["detect"] == 0 and rec["alarm_certificate"]["certified"]
                            and rec["failsafe"]["box_alarms"] == 1 and h.w.zs == {})

    w = C.make("F3", tp)                                           # an as-range value past HI by a solver tolerance
    w.zs[0] = zh[0]
    w.lp = lambda t_end, upto, st, vec: (C.HI + 1e-8) if vec[1] > 0 else (-C.LO + 1e-8)
    w.lp_cert = lambda *a: (w.lp(*a), w.lp(*a) + 1e-9)
    lo, up = w.as_range(5)
    zx = C.HI + w.delta + 5e-9                                     # its slab lies just above the box
    cx = w.certify_alarm(5, zx)
    ok["range_overshoot"] = (lo == C.LO and up == C.HI and up < zx - w.delta and cx["certified"]
                             and "up" in cx["box_sides"] and w.fs["box_alarms"] == 1)
    res["range_overshoot"] = cx

    zo = list(zh)                                                  # the overshoot through online(): a z_t just above
    zo[tk] = C.HI + C.DELTA_F + 5e-9                               # the box, range and certificate LPs past HI by 1e-8
    o_lp, o_lc = C.Failsafe.lp, C.Failsafe.lp_cert

    def lp_o(self, t_end, upto, st, vec):
        if self.now == tk and vec[1] > 0 and st == t_end:
            return C.HI + 1e-8
        return o_lp(self, t_end, upto, st, vec)

    def lc_o(self, *a):
        if self.now == tk and self.role == ("cert", "up"):
            return C.HI + 1e-8, C.HI + 2e-8
        return o_lc(self, *a)

    C.Failsafe.lp, C.Failsafe.lp_cert = lp_o, lc_o
    try:
        rec, h = go(zo, None, lambda *a: None, tk + 5)
    finally:
        C.Failsafe.lp, C.Failsafe.lp_cert = o_lp, o_lc
    ok["overshoot_online"] = (rec["detect"] == tk and rec["alarm_certificate"]["certified"]
                              and "up" in rec["alarm_certificate"]["box_sides"] and rec["failsafe"]["box_alarms"] == 1
                              and tk not in h.w.zs)
    res["overshoot_online"] = rec["alarm_certificate"]

    w = C.make("F3", tp)
    w.zs[0], w.zs[5] = zh[0], 10.0                                 # a slab outside the box: empty before any solve
    v = w.lp(6, 5, 6, (0, 1.0, 0))
    ok["slab_empty"] = isinstance(v, C.Failed) and v.kind() == "slab"

    ok = {k: bool(v) for k, v in ok.items()}
    rep = {"ok": ok, "U0": all(ok.values()), "details": res, "healthy_row": D.key(healthy), "fault_row": D.key(fault),
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()}
    (out / "paths.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps(rep, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("paths", "run", "summary", "criteria"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--setting", choices=SETTINGS, default="none")
    ap.add_argument("--variant", choices=("F3", "F3a"), default="F3")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--r3", type=Path, nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "paths":
        return paths(a.out)
    if a.cmd == "summary":
        return summary(a.out)
    if a.cmd == "criteria":                                        # OUT: a run base with R-a..R-f; --r3: R3 dirs
        return criteria([a.out / f"R-{s}" for s in "abcdef"], a.r3)
    run(a.out, a.setting, a.variant, a.workers, a.limit)


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
