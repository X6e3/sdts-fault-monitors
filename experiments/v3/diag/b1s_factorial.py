"""Why is B1s later than B1? A 2 x 2 diagnostic on development rows (RECORD-2026-11-23-baselines2.md, review r7).

Review r7 traced, on 3 DEV rows, B1s's lateness to two of its changes, each of which alone turns on eliminations of
strip slack generators that B1 skips when rounding leaves their excess just above 0: EXACT_TOL = 1e-12 in
`_eliminate_one` (B1: exactly 0) and the outward pad of `_bounds`. This script measures that on the 100 DEV rows of
BASELINE2's stability check (the smallest sha256 keys), for (n_c, o) = (1, 2) and (4, 8), fifo, box+err:
  - B1, the first comparison's code;
  - B1s with EXACT_TOL in {1e-12, 0} x the `_bounds` pad {on, off}; (1e-12, on) is B1s, and is checked against
    `baselines_strong.ConZonoStrong` itself at shift 0 on every row (the copy below must change nothing else);
each with the data shifted by 0, +1e-15, -1e-15 and 2e-15 (BASELINE2's SHIFTS).
Reported per configuration and variant, descriptive only (no pass or fail, development seeds only): paired lag over
the rows' paired events (certified t*, IM detects) with a miss at 3,600, misses, alarms on admissible rows or before
t*, rows whose detection changes under the shifts, and at shift 0 the eliminations of generators with norm at most
CZ.TOL (slack) and above it (state).

  python -B experiments/v3/diag/b1s_factorial.py OUT [--workers 14] [--rows 100]     (from the repository root)
"""
import argparse, hashlib, json, sys, time, warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import baselines_run as R  # noqa: E402
import baselines_strong as BS  # noqa: E402
import baselines_cz as CZ  # noqa: E402
BL, S, T, G = R.BL, R.S, R.T, R.G
N = 3600
SHIFTS = [0.0, 1e-15, -1e-15, 2e-15]
CONFIGS = [(1, 2), (4, 8)]
VARIANTS = [(1e-12, True), (1e-12, False), (0.0, True), (0.0, False)]


class B1sVar(BS.ConZonoStrong):
    """ConZonoStrong with EXACT_TOL and the `_bounds` pad as parameters, and elimination counts; the two methods are
    copies of baselines_strong's with only those changes"""

    def __init__(self, n_c, order, exact_tol, pad):
        super().__init__(n_c, order, "fifo", "box+err", "interval")
        self.exact_tol, self.pad_on = exact_tol, pad
        self.elim_slack = self.elim_state = 0

    def _eliminate_one(self):
        A, b, Gm = self.A, self.b, self.G
        absA = np.abs(A)
        ok = absA > 1e-9
        zero = ~ok.any(axis=1)
        if zero.any():
            if np.any(np.abs(b[zero]) > absA[zero].sum(axis=1) + 1e-9):
                self.empty = True
            keep = ~zero
            self.A, self.b, self.age = A[keep], b[keep], self.age[keep]
            return
        with np.errstate(divide="ignore", invalid="ignore"):
            rad = (absA.sum(axis=1)[:, None] - absA) / absA
            over = np.maximum(0.0, np.abs(b[:, None] / A) + rad - 1.0)
        gn = np.linalg.norm(Gm, axis=0)[None, :] * np.ones_like(A)
        bad = (gn <= CZ.TOL) & (over > self.exact_tol)
        score = np.where(ok, over * gn, np.inf)
        score = np.where(bad, np.inf, score)
        if not np.isfinite(score).any():
            score = np.where(ok, over, np.inf)
        exact = ok & (over <= self.exact_tol)
        if exact.any():
            score = np.where(exact, gn, np.inf)
        elif self.policy == "fifo":
            oldest = self.age == self.age.min()
            score = np.where(oldest[:, None], score, np.inf)
            if not np.isfinite(score).any():
                score = np.where(oldest[:, None] & ok, over, np.inf)
        flat = np.argmin(BS._quantize(score))
        i, j = np.unravel_index(flat, A.shape)
        if gn[i, j] <= CZ.TOL:
            self.elim_slack += 1
        else:
            self.elim_state += 1
        aij = A[i, j]
        g = Gm[:, j] / aij
        self.c = self.c + g * b[i]
        Gn = Gm - np.outer(g, A[i])
        an = A[:, j] / aij
        An = A - np.outer(an, A[i])
        bn = b - an * b[i]
        keep_r = np.arange(A.shape[0]) != i
        keep_c = np.arange(A.shape[1]) != j
        self.G, self.A, self.b = Gn[:, keep_c], An[np.ix_(keep_r, keep_c)], bn[keep_r]
        self.age = self.age[keep_r]

    def _bounds(self, sweeps=3):
        A, b = self.A, self.b
        ng = self.G.shape[1]
        lo, hi = -np.ones(ng), np.ones(ng)
        on = 1.0 if self.pad_on else 0.0
        for _ in range(sweeps):
            for i in range(A.shape[0]):
                idx = np.nonzero(A[i])[0]
                r = A[i, idx]
                big = np.abs(r) > BS.TIGHT_TOL
                if not big.any():
                    continue
                tlo, thi = np.minimum(r * lo[idx], r * hi[idx]), np.maximum(r * lo[idx], r * hi[idx])
                slo, shi = tlo.sum(), thi.sum()
                pad = on * ((idx.size + 8) * BS.EPS * (abs(b[i]) + float(np.abs(r) @ np.maximum(np.abs(lo[idx]), np.abs(hi[idx]))))
                            + (idx.size + 4) * BS.TINY)
                if not (np.isfinite(b[i]) and np.isfinite(slo) and np.isfinite(shi) and np.isfinite(pad)):
                    continue
                rb, j = r[big], idx[big]
                rest_lo, rest_hi = slo - tlo[big] - pad, shi - thi[big] + pad
                a1, a2 = (b[i] - rest_hi) / rb, (b[i] - rest_lo) / rb
                lo[j] = np.maximum(lo[j], np.nextafter(np.minimum(a1, a2), -np.inf))
                hi[j] = np.minimum(hi[j], np.nextafter(np.maximum(a1, a2), np.inf))
        return lo, hi


def job(r):
    warnings.filterwarnings("ignore")
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    out = {"key": R.key(r)}
    for nc, o in CONFIGS:
        cfg = {"n_c": nc, "order": o, "policy": "fifo", "prior": "box+err"}
        tag = f"{nc},{o}"
        out[f"B1 {tag}"] = [BL.run_set_method(BL.METHODS["B1"](cfg), [z + e for z in zs])[0] for e in SHIFTS]
        out[f"B1s-ref {tag}"] = BL.run_set_method(BL.METHODS["B1s"](cfg), zs)[0]
        for tol, pad in VARIANTS:
            name = f"tol {tol:g} pad {'on' if pad else 'off'} {tag}"
            dets, counts = [], None
            for e in SHIFTS:
                m = B1sVar(nc, o, tol, pad)
                dets.append(BL.run_set_method(m, [z + e for z in zs])[0])
                if e == 0.0:
                    counts = [m.elim_slack, m.elim_state]
            out[name] = dets
            out[name + " elim"] = counts
    return out


def summary(rows, got):
    by = {R.key(r): r for r in rows}
    names = [k for k in got[0] if k != "key" and not k.endswith(" elim") and not k.startswith("B1s-ref")]
    res = {}
    for nm in names:
        lag = miss = early_adm = unstable = 0
        slack = state = 0
        for g in got:
            r, d = by[g["key"]], g[nm]
            d0 = d[0]
            adm = r["cell"] == "healthy" or (r["status"] == "certified" and r["t_star"] is None)
            ev = r["status"] == "certified" and r["t_star"] is not None
            if ev and r["v2"] is not None:
                lag += (N if d0 is None else d0) - r["t_star"]
            if ev and d0 is None:
                miss += 1
            if d0 is not None and (adm or (ev and d0 < r["t_star"])):
                early_adm += 1
            unstable += len(set(d)) > 1
            if nm + " elim" in g:
                slack += g[nm + " elim"][0]; state += g[nm + " elim"][1]
        res[nm] = {"paired_lag": lag, "misses": miss, "admissible_or_early_alarms": early_adm, "rows_unstable": unstable}
        if not nm.startswith("B1 "):
            res[nm] |= {"elim_slack": slack, "elim_state": state}
    lag_im = sum(r["v2"] - r["t_star"] for r in rows if r["status"] == "certified" and r["t_star"] is not None
                 and r["v2"] is not None)
    ref = {f"{nc},{o}": sum(g[f"B1s-ref {nc},{o}"] != g[f"tol 1e-12 pad on {nc},{o}"][0] for g in got) for nc, o in CONFIGS}
    events = sum(r["status"] == "certified" and r["t_star"] is not None for r in rows)
    paired = sum(r["status"] == "certified" and r["t_star"] is not None and r["v2"] is not None for r in rows)
    return {"rows": len(rows), "events": events, "paired": paired, "IM_paired_lag": lag_im,
            "copy_check_rows_differing_from_B1s": ref, "table": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--rows", type=int, default=100)
    a = ap.parse_args()
    rows = sorted(R.dev_rows(), key=lambda r: hashlib.sha256(R.key(r).encode()).hexdigest())[:a.rows]
    a.out.mkdir(parents=True, exist_ok=False)
    head, dirty = R.git_state()
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as pool:
        got = list(pool.map(job, rows))
    with (a.out / "rows.jsonl").open("x") as f:
        for g in got:
            f.write(json.dumps(g, sort_keys=True) + "\n")
    res = {"git_head": head, "git_dirty_tracked": dirty, "seconds": round(time.time() - t0, 1),
           "shifts": SHIFTS} | summary(rows, got)
    (a.out / "summary.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
