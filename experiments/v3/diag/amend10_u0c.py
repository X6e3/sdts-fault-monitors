"""DIAG-3 amendment 10, fifth addendum, U0c (DIAG-3-PLAN.md): review M2's witnesses as path tests.

Written and committed with the fifth addendum's code, before it ran. Nothing here is part of the candidate.
  1. shape errors raise ValueError with no solver call (M2: a (2, 2) objective, b_ub without A_ub; and the other new
     checks: A_ub without b_ub, a right-hand side of rank 2, lb > ub);
  2. a status-0 answer with multiplier arrays of the wrong length is a failed attempt of kind "nonfinite": directly in
     solve_f3, and in a fold through online() (U0b's harness, the fold at t = 289, direction 40), with no IndexError;
  3. M2's underflow LP (one variable in [-1/4, 1/4], objective -2^-1074, no rows): the strict bound is at least the
     exact maximum 2^-1076 (Fraction);
  4. under np.errstate(all="raise") the overflow case of U0b test 4 still returns NaN.
The fourth addendum's certified_max (from amend10_i3, verbatim from 1c0439cd) is evaluated beside the new one on 3 and
4, for the record only.
usage: python -B amend10_u0c.py OUT
"""
import json
import math
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import scipy.sparse as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import amend10 as A  # noqa: E402  (sets the paths, as R0 does)
import amend10_i3 as I3  # noqa: E402
import amend10_u0b as B  # noqa: E402

C, CD, D, G, S, T, V = A.C, A.CD, A.D, A.G, A.S, A.T, A.V
W, K = A.W, A.K


class Calls:
    """count the calls that reach the solver"""

    def __enter__(self):
        self.n, self.orig = 0, C.rec_linprog

        def rec(c, **kw):
            self.n += 1
            return self.orig(c, **kw)
        C.rec_linprog = rec
        return self

    def __exit__(self, *a):
        C.rec_linprog = self.orig


def win():
    return SimpleNamespace(n_retry=0, lp_seconds=0.0, n_lp=0)


def small_lp():
    """max x0 + x1 over the a priori box with x0 + x1 + x2 <= 5"""
    return dict(cvec=np.array([-1.0, -1.0, 0.0]), A_ub=sp.csr_matrix(np.array([[1.0, 1.0, 1.0]])),
                b_ub=np.array([5.0]), bounds=np.array([[C.LO, C.HI]] * 3, dtype=float))


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    ok, res = {}, {}
    box3 = np.array([[C.LO, C.HI]] * 3, dtype=float)

    # 1. shape errors: ValueError, no solver call, nothing counted
    cases = {
        "objective_2x2": (np.zeros((2, 2)), dict(bounds=np.array([[0.0, 1.0], [0.0, 1.0]]))),
        "b_ub_without_A_ub": (np.array([-1.0, 0.0, 0.0]), dict(b_ub=np.array([1.0]), bounds=box3)),
        "A_ub_without_b_ub": (np.array([-1.0, 0.0, 0.0]), dict(A_ub=sp.csr_matrix(np.ones((1, 3))), bounds=box3)),
        "b_ub_rank_2": (np.array([-1.0, 0.0, 0.0]), dict(A_ub=sp.csr_matrix(np.ones((1, 3))), b_ub=np.array([[1.0]]),
                                                         bounds=box3)),
        "lb_above_ub": (np.array([-1.0, 0.0, 0.0]), dict(bounds=np.array([[0.0, 1.0], [2.0, 1.0], [0.0, 1.0]]))),
    }
    r1 = {}
    for name, (c, kw) in cases.items():
        w = win()
        with Calls() as k:
            try:
                v = C.solve_f3(w, c, **kw)
                r1[name] = {"raised": None, "returned": repr(v), "solver_calls": k.n, "n_lp": w.n_lp}
            except ValueError as e:
                r1[name] = {"raised": f"ValueError: {e}", "solver_calls": k.n, "n_lp": w.n_lp}
            except Exception as e:  # noqa: BLE001  (recorded: any other type fails the test)
                r1[name] = {"raised": f"{type(e).__name__}: {e}", "solver_calls": k.n, "n_lp": w.n_lp}
    ok["1_shape_errors_raise"] = all(x["raised"] is not None and x["raised"].startswith("ValueError")
                                     and x["solver_calls"] == 0 and x["n_lp"] == 0 for x in r1.values())
    res["1"] = r1

    # 2. multiplier arrays of the wrong length: a failed attempt, kind "nonfinite"
    lp = small_lp()
    w = win()
    ctl = C.solve_f3(w, lp["cvec"], A_ub=lp["A_ub"], b_ub=lp["b_ub"], bounds=lp["bounds"])
    r2 = {"control": {"value": ctl, "n_retry": w.n_retry}}
    for field, f in (("lower", lambda m: m[:0]), ("upper", lambda m: m[:2]), ("ineqlin", lambda m: m[:0])):
        orig = C.rec_linprog

        def rec(c, _f=f, _field=field, **kw):
            r = orig(c, **kw)
            getattr(r, _field)["marginals"] = _f(np.array(getattr(r, _field).marginals, dtype=float))
            C.Rec.last = (C.Rec.last[0], C.Rec.last[1], r)
            return r
        C.rec_linprog = rec
        w = win()
        try:
            v = C.solve_f3(w, lp["cvec"], A_ub=lp["A_ub"], b_ub=lp["b_ub"], bounds=lp["bounds"])
            r2[field] = {"returned": repr(v), "kind": v.kind() if isinstance(v, C.Failed) else None,
                         "n_retry": w.n_retry, "n_lp": w.n_lp}
        except Exception as e:  # noqa: BLE001
            r2[field] = {"raised": f"{type(e).__name__}: {e}"}
        finally:
            C.rec_linprog = orig
    direct = all(r2[f].get("kind") == "nonfinite" and r2[f]["n_retry"] == 3 and r2[f]["n_lp"] == 1
                 for f in ("lower", "upper", "ineqlin"))

    tp = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    healthy = next(r for r in rows if r["cell"] == "healthy" and r["noise"] == "uniform")
    run = S.run(healthy["seed"], next(c for c in T.CELLS if c.name == healthy["cell"]), healthy["arm"],
                healthy["ambient"], healthy["noise"])
    zh = G.zs_of(run)
    try:
        with B.Patch(B.at(289, ("fold", 40)), B.with_marginals("lower", lambda m: m[:0])) as p:
            rec = CD.online("F3", zh, W, K, None, horizon=289, tp=tp)
        fold = {"hits": p.hits, "fold_dir_fallbacks": rec["failsafe"]["fold_dir_fallbacks"],
                "fold_implied": rec["failsafe"]["fold_implied"], "detect": rec["detect"]}
        fold_ok = (p.hits == 3 and fold["fold_dir_fallbacks"] == {"nonfinite": 1} and rec["detect"] is None)
    except Exception as e:  # noqa: BLE001
        fold, fold_ok = {"raised": f"{type(e).__name__}: {e}"}, False
    r2["fold_289_dir40_lower_empty"] = fold
    ok["2_malformed_multipliers_fail_as_nonfinite"] = direct and fold_ok and isinstance(ctl, float)
    res["2"] = r2

    # 3. M2's underflow LP
    tiny = math.ldexp(1.0, -1074)
    exact = Fraction(1, 2 ** 1076)
    w = win()
    v = C.solve_f3(w, np.array([-tiny]), bounds=np.array([[-0.25, 0.25]]))
    r3 = {"solve": repr(v), "status": int(C.Rec.last[2].status)}
    if isinstance(v, C.Failed):
        ok["3_underflow_bound_sound"] = False
        r3["note"] = "the LP did not solve; the test is not exercised"
    else:
        b_new = {h: C.certified_max(h, strict=True) for h in (False, True)}
        b_old = {h: I3.old_certified_max(h, strict=True) for h in (False, True)}
        r3.update({"exact_max": "2^-1076", "new_strict": {str(h): b.hex() for h, b in b_new.items()},
                   "old_strict": {str(h): b.hex() for h, b in b_old.items()},
                   "new_minus_exact_units_2^-1076": {str(h): str(Fraction(b) / exact - 1) for h, b in b_new.items()}})
        ok["3_underflow_bound_sound"] = all(math.isfinite(b) and Fraction(b) >= exact for b in b_new.values())
    res["3"] = r3

    # 4. the overflow case under np.errstate(all="raise")
    w = win()
    v = C.solve_f3(w, lp["cvec"], A_ub=lp["A_ub"], b_ub=lp["b_ub"], bounds=lp["bounds"])
    c0, kw0, r0 = C.Rec.last
    r0["ineqlin"]["marginals"] = np.full_like(np.asarray(r0.ineqlin.marginals, dtype=float), -1.5e308)
    C.Rec.last = (c0, kw0, r0)
    r4 = {"solve": repr(v)}
    with np.errstate(all="raise"):
        try:
            b = C.certified_max(True, strict=True)
            r4["new"] = repr(b)
            new_ok = math.isnan(b)
        except Exception as e:  # noqa: BLE001
            r4["new"], new_ok = f"raised {type(e).__name__}: {e}", False
        r4["errstate_after_call"] = np.geterr()                  # the caller's state is restored
        try:
            r4["old"] = repr(I3.old_certified_max(True, strict=True))
        except Exception as e:  # noqa: BLE001
            r4["old"] = f"raised {type(e).__name__}: {e}"
    ok["4_overflow_nan_under_errstate_raise"] = (new_ok and
                                                 all(x == "raise" for x in r4["errstate_after_call"].values()))
    res["4"] = r4

    ok = {k: bool(x) for k, x in ok.items()}
    rep = {"ok": ok, "U0c": all(ok.values()), "details": res, "healthy_row": D.key(healthy),
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
           "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode)}
    (out / "u0c.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
