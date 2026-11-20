"""DIAG-3 amendment 10, fifth addendum, I3 (DIAG-3-PLAN.md): on R0's and I2a's rows, the strict certified bound of the
fifth addendum equals the fourth addendum's bit for bit wherever the latter is finite.

Written and committed with the fifth addendum's code, before it ran. Nothing here is part of the candidate. Every call
of certified_max with strict=True is wrapped: the new function's value is returned unchanged, and the fourth
addendum's function (OLD_SOURCE below, verbatim from 1c0439cd, checked against git at run time) is evaluated on the
same last LP and compared. R0 (amend10.paths) and I2a's 16 jobs (amend10_i1a's selection, settings none and d) are
run under the wrapper; their records go to OUT and are not I2a's deciding records.
usage: python -B amend10_i3.py OUT
"""
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import amend10 as A  # noqa: E402  (sets the paths, as R0 does)

C = A.C

OLD_SOURCE = r'''
def certified_max(harden=False, strict=False):
    """a rigorous upper bound on max (-c) x of the last LP: weak duality with the solver's multipliers, every
    variable boxed, float rounding bounded explicitly. harden: also enclose the rounding of the LP coefficients
    themselves (each one correctly rounded from its exact value, so off by less than 2u |a|), so that the bound holds
    for the LP with the exact coefficients (exact powers of M), not only for its float64 copy. strict (F3, fourth
    addendum): NaN instead of a bound when a term is not finite or the sum overflows; finite terms give the same
    value as without it."""
    c, kw, res = Rec.last
    bnd = kw["bounds"]
    lb, ub = bnd[:, 0], bnd[:, 1]
    s, sa, k, parts = c.astype(float).copy(), np.abs(c).astype(float), 1, []
    if kw.get("A_ub") is not None:
        A, y = kw["A_ub"], np.maximum(0.0, -np.asarray(res.ineqlin.marginals))
        s += A.T @ y
        sa += abs(A).T @ y
        k += _colnnz(A)
        parts.append(y * kw["b_ub"])
    if kw.get("A_eq") is not None:
        A, nu = kw["A_eq"], -np.asarray(res.eqlin.marginals)
        s += A.T @ nu
        sa += abs(A).T @ np.abs(nu)
        k += _colnnz(A)
        parts.append(nu * kw["b_eq"])
    parts.append(-np.minimum(s * lb, s * ub))
    xm = np.maximum(np.abs(lb), np.abs(ub))
    parts.append(2 * _gam(k + 1) * sa * xm)
    if harden:
        parts.append(2 * U * (sa - np.abs(c)) * xm)
    p = np.concatenate(parts)
    if not strict:
        tot = math.fsum(p)
        return tot + 4 * (_gam(4) * math.fsum(np.abs(p)) + U * abs(tot))
    if not np.all(np.isfinite(p)):
        return math.nan
    try:
        tot = math.fsum(p)
        b = tot + 4 * (_gam(4) * math.fsum(np.abs(p)) + U * abs(tot))
    except OverflowError:
        return math.nan
    return b if math.isfinite(b) else math.nan
'''

_ns = dict(vars(C))
exec(OLD_SOURCE, _ns)                                              # noqa: S102  (the fourth addendum's function)
old_certified_max = _ns["certified_max"]


def old_source_matches_git():
    src = subprocess.run(["git", "show", "1c0439cd:experiments/v3/diag/diag3_cw.py"], cwd=HERE, capture_output=True,
                         text=True).stdout
    i, j = src.find("def certified_max("), src.find("def exact_bound(")
    return i >= 0 and j > i and src[i:j].rstrip("\n") + "\n" == OLD_SOURCE.lstrip("\n")


class Compare:
    def __init__(self):
        self.n_strict, self.n_old_finite, self.n_equal = 0, 0, 0
        self.n_old_nonfinite, self.n_new_nan_where_old_nonfinite = 0, 0
        self.diffs = []

    def __enter__(self):
        self.new = C.certified_max
        box = self

        def wrapped(harden=False, strict=False):
            v = box.new(harden, strict)
            if strict:
                box.n_strict += 1
                o = old_certified_max(harden, strict)
                if math.isfinite(o):
                    box.n_old_finite += 1
                    if math.isfinite(v) and v.hex() == o.hex():
                        box.n_equal += 1
                    elif len(box.diffs) < 50:
                        box.diffs.append({"harden": harden, "old": o.hex(), "new": v.hex() if math.isfinite(v)
                                          else repr(v)})
                else:
                    box.n_old_nonfinite += 1
                    box.n_new_nan_where_old_nonfinite += int(math.isnan(v))
            return v
        C.certified_max = wrapped
        return self

    def __exit__(self, *a):
        C.certified_max = self.new

    def report(self):
        return {"n_strict": self.n_strict, "n_old_finite": self.n_old_finite, "n_equal": self.n_equal,
                "n_differ": self.n_old_finite - self.n_equal, "n_old_nonfinite": self.n_old_nonfinite,
                "n_new_nan_where_old_nonfinite": self.n_new_nan_where_old_nonfinite, "diffs_first_50": self.diffs}


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    rep = {"old_source_matches_1c0439cd": old_source_matches_git()}
    with Compare() as cmp_r0:
        A.paths(out / "R0")
    rep["R0"] = cmp_r0.report()
    print("R0", json.dumps(rep["R0"])[:400], flush=True)
    rows = [json.loads(l) for l in A.D.ROWS.read_text().splitlines() if l.strip()]
    fault = sorted((r for r in rows if r["oracle"].get("t_star") is not None), key=lambda r: A.D.key(r))
    dev = [fault[i] for i in (0, 100, 200, 300)]
    edge = list(A.EDGE)[:4]
    rep["I2a_rows"] = {}
    for setting in ("none", "d"):
        o = out / "I2a" / setting
        o.mkdir(parents=True, exist_ok=True)
        for kind, spec in [("edge", e) for e in edge] + [("dev", r) for r in dev]:
            with Compare() as c:
                key = A.job((kind, spec, setting, "F3", str(o)))[0]
            rep["I2a_rows"][f"{setting}/{key}"] = c.report()
            print(setting, key, json.dumps(c.report())[:300], flush=True)
    allr = [rep["R0"]] + list(rep["I2a_rows"].values())
    rep["total"] = {k: sum(r[k] for r in allr) for k in ("n_strict", "n_old_finite", "n_equal", "n_differ",
                                                         "n_old_nonfinite", "n_new_nan_where_old_nonfinite")}
    rep["I3"] = rep["old_source_matches_1c0439cd"] and rep["total"]["n_differ"] == 0 and rep["total"]["n_old_finite"] > 0
    rep["git_head"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    rep["git_dirty_tracked"] = bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode)
    (out / "i3.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps({k: rep[k] for k in ("I3", "total", "old_source_matches_1c0439cd")}, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
