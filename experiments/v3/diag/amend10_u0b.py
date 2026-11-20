"""DIAG-3 amendment 10, fourth addendum, U0b (DIAG-3-PLAN.md): the solver-boundary path tests.

Each test patches diag3_cw.rec_linprog (or one method) for one chosen LP of R0's healthy or fault DEV row, runs F3
online, and checks the outcome written in the plan before the run. Nothing here is part of the candidate.
usage: python -B amend10_u0b.py OUT
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import amend10 as A  # noqa: E402  (sets the paths, as R0 does)

C, CD, D, G, S, T, V = A.C, A.CD, A.D, A.G, A.S, A.T, A.V
W, K = A.W, A.K


class Patch:
    """replace rec_linprog for the LPs that `pick(now, role, attempt)` selects with `act(attempt, call)`"""

    def __init__(self, pick, act):
        self.pick, self.act, self.seen, self.hits = pick, act, {}, 0

    def __enter__(self):
        self.orig, self.orig_make = C.rec_linprog, C.make
        box = self

        def rec(c, **kw):
            w = box.w
            k = (w.now, w.role)
            n = box.seen.get(k, 0)
            box.seen[k] = n + 1
            if box.pick(w.now, w.role, n):
                box.hits += 1
                return box.act(n, lambda: box.orig(c, **kw))
            return box.orig(c, **kw)

        def make(var, cy):
            box.w = box.orig_make(var, cy)
            return box.w

        C.rec_linprog, C.make = rec, make
        return self

    def __exit__(self, *a):
        C.rec_linprog, C.make = self.orig, self.orig_make


def at(t, role, attempts=(0, 1, 2)):
    return lambda now, r, n: now == t and r == role and n in attempts


def raise_(e):
    def act(n, call):
        raise e
    return act


def with_marginals(field, f):
    """call the solver, then replace res.<field>.marginals by f(marginals) (a copy; the solver's own is untouched)"""
    def act(n, call):
        res = call()
        m = np.array(getattr(res, field).marginals, dtype=float)
        getattr(res, field)["marginals"] = f(m)
        C.Rec.last = (C.Rec.last[0], C.Rec.last[1], res)
        return res
    return act


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    tp = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    healthy = next(r for r in rows if r["cell"] == "healthy" and r["noise"] == "uniform")
    fault = next(r for r in rows if r["oracle"]["t_star"] is not None and r["cell"].startswith("jump"))

    def zs_of(r):
        run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
        return G.zs_of(run), r["oracle"].get("t_star")

    def go(zs, ts, horizon, pick=lambda *a: False, act=None):
        with Patch(pick, act) as p:
            rec = CD.online("F3", zs, W, K, ts, horizon=horizon, tp=tp)
        return rec, p

    zh, _ = zs_of(healthy)
    zf, tsf = zs_of(fault)
    ok, res = {}, {}
    fs0 = lambda rec: {k: v for k, v in rec["failsafe"].items() if v not in (0, {}, {"one": 0, "both": 0})}

    # 1. an exception on the first attempt only: solved by the second
    ctl, _ = go(zh, None, 273)
    rec, p = go(zh, None, 273, at(273, ("fold", 40), (0,)), raise_(RuntimeError("simulated solver error")))
    ok["1_exception_first_attempt"] = (p.hits == 1 and rec["n_retry"] == ctl["n_retry"] + 1 and fs0(rec) == {}
                                       and rec["detect"] is None and rec["n_lp"] == ctl["n_lp"])
    res["1"] = {"n_retry": [ctl["n_retry"], rec["n_retry"]], "failsafe": fs0(rec)}

    # 2. an exception on all three attempts: the P_J bound
    rec, p = go(zh, None, 273, at(273, ("fold", 40)), raise_(RuntimeError("simulated solver error")))
    ok["2_exception_all_attempts"] = (p.hits == 3 and rec["failsafe"]["fold_dir_fallbacks"] == {"exception": 1}
                                      and rec["failsafe"]["fold_implied"] == 1 and rec["detect"] is None
                                      and p.w.tau == 16)
    res["2"] = fs0(rec)

    # 3. status 0 with a NaN inequality multiplier (t = 289: the first fold with base rows)
    def nan0(m):
        m[0] = np.nan
        return m
    rec, p = go(zh, None, 289, at(289, ("fold", 40)), with_marginals("ineqlin", nan0))
    ok["3_nonfinite_multiplier"] = (p.hits == 3 and rec["failsafe"]["fold_dir_fallbacks"] == {"nonfinite": 1}
                                    and rec["detect"] is None)
    res["3"] = fs0(rec)

    # 4. finite multipliers whose certified bound overflows
    rec, p = go(zh, None, 289, at(289, ("fold", 40)), with_marginals("ineqlin", lambda m: np.full_like(m, -1.5e308)))
    ok["4_certificate_overflow"] = (p.hits == 1 and rec["failsafe"]["fold_dir_fallbacks"] == {"nonfinite": 1}
                                    and rec["detect"] is None)
    res["4"] = {"hits": p.hits, "failsafe": fs0(rec)}

    # 5. a non-finite certificate on the "up" side of the alarm certificate, at the fault row's detection
    base, _ = go(zf, tsf, None)
    ta = base["detect"]
    log, orig_ca = {}, C.Failsafe.certify_alarm

    def ca(self, t, z):
        c = orig_ca(self, t, z)
        log[t] = c
        return c
    C.Failsafe.certify_alarm = ca
    try:
        rec, p = go(zf, tsf, None, at(ta, ("cert", "up")), with_marginals("ineqlin", lambda m: np.full_like(m, -1.5e308)))
    finally:
        C.Failsafe.certify_alarm = orig_ca
    ok["5_certificate_side_nonfinite"] = (rec["failsafe"]["cert_fallbacks"].get("nonfinite") == 1 and ta in log
                                          and "up" in log[ta]["box_sides"]
                                          and (rec["detect"] is None or rec["alarm_certificate"]["certified"]))
    res["5"] = {"base_detect": ta, "detect": rec["detect"], "cert_at_ta": log.get(ta), "failsafe": fs0(rec)}

    # 6. an exception on all attempts of one as-range side: that z_t is not kept
    _, pc = go(zh, None, 80)
    tk = [j for j in sorted(pc.w.zs) if j >= 50][0]
    rec, p = go(zh, None, tk, at(tk, ("range", "up")), raise_(RuntimeError("simulated solver error")))
    ok["6_range_exception"] = (p.hits == 3 and rec["failsafe"]["range_failures"] == {"exception": 1}
                               and tk not in p.w.zs and rec["failsafe"]["measurements_not_kept"] == 1
                               and rec["detect"] is None)
    res["6"] = {"t": tk, "failsafe": fs0(rec)}

    # 7. a NaN in our own LP's input: raised, not a Failed
    w = C.make("F3", tp)
    try:
        v = C.solve_f3(w, np.array([np.nan, 0.0, 0.0]), bounds=np.array([[C.LO, C.HI]] * 3))
        ok["7_nonfinite_input_raises"], res["7"] = False, repr(v)
    except ValueError as e:
        ok["7_nonfinite_input_raises"], res["7"] = True, str(e)

    # 8. a TypeError in our own code during a fold: it propagates
    orig_cub = C.Failsafe._cub

    def bad_cub(self, v):
        if self.role and self.role[0] == "fold":
            raise TypeError("simulated error in our own code")
        return orig_cub(self, v)
    C.Failsafe._cub = bad_cub
    try:
        go(zh, None, 273)
        ok["8_own_error_propagates"], res["8"] = False, "no exception"
    except TypeError as e:
        ok["8_own_error_propagates"], res["8"] = True, str(e)
    finally:
        C.Failsafe._cub = orig_cub

    # 9. a MemoryError inside the solver call: it propagates
    try:
        go(zh, None, 273, at(273, ("fold", 40), (0,)), raise_(MemoryError("simulated")))
        ok["9_memory_error_propagates"], res["9"] = False, "no exception"
    except MemoryError as e:
        ok["9_memory_error_propagates"], res["9"] = True, str(e)

    # 10. the reason codes
    ok["10_kinds"] = (C.Failed("exception").kind() == "exception" and C.Failed("nonfinite").kind() == "nonfinite"
                      and C.Failed(2).kind() == "2" and C.Failed(3).kind() == "other")

    ok = {k: bool(v) for k, v in ok.items()}
    rep = {"ok": ok, "U0b": all(ok.values()), "details": res, "healthy_row": D.key(healthy), "fault_row": D.key(fault),
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
           "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode)}
    (out / "u0b.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
